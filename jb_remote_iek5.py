#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

"""Library for communicating with Chantal through HTTP.  Typical usage is::

    from jb_remote_iek5 import *
    login("r.miller", "mysecurepassword")
    new_samples(10, "PECVD lab")
    logout()

This module writes a log file.  On Windows, it is in the current directory.  On
Unix-like systems, it is in /tmp.
"""

from __future__ import absolute_import, unicode_literals
from jb_remote import six
from jb_remote.six.moves import urllib, configparser

import re, logging, datetime, os
from jb_remote import *

credentials = configparser.SafeConfigParser()
read_files = credentials.read(["/var/www/chantal.auth", os.path.expanduser("~/chantal.auth")])
if read_files:
    CREDENTIALS = dict(credentials.items("DEFAULT"))
else:
    CREDENTIALS = {}
    logging.warning("file with authentication data not found; maybe no emails can be sent")

settings.ROOT_URL = "https://chantal.fz-juelich.de/"
settings.TESTSERVER_ROOT_URL = "http://bob.ipv.kfa-juelich.de/"
settings.SMTP_SERVER = "mail.fz-juelich.de"
settings.SMTP_LOGIN = CREDENTIALS.get("b.klingebiel")
settings.SMTP_PASSWORD = CREDENTIALS.get("fzj_password")
settings.EMAIL_TO = "chantal-admins@googlegroups.com"
settings.EMAIL_FROM = "chantal@fz-juelich.de"

__all__ = ["login", "logout", "new_samples", "Sample", "User", "as_json",
           "SixChamberDeposition", "SixChamberLayer", "SixChamberChannel",
           "LargeAreaDeposition", "LargeAreaLayer", "rename_after_deposition", "PDSMeasurement", "get_or_create_sample",
           "OldClusterToolDeposition", "OldClusterToolHotWireLayer", "OldClusterToolPECVDLayer", "raman_by_filepath",
           "RamanMeasurement", "JuliaBaseError", "DSRMeasurement", "DSRSpectralData", "DSRIVData",
           "Result", "LargeSputterDeposition", "LargeSputterLayer", "SputterCharacterization", "PHotWireDeposition",
           "PHotWireLayer", "NewClusterToolDeposition", "NewClusterToolHotWireLayer", "NewClusterToolPECVDLayer",
           "NewClusterToolSputterLayer", "NewClusterToolSputterSlot", "LumaMeasurement", "setup_logging",
           "MBEProcess", "MokeMeasurement"]


def new_samples(number_of_samples, current_location, substrate="asahi-u", timestamp=None, timestamp_inaccuracy=None,
                purpose=None, tags=None, topic=None, substrate_comments=None):
    """Creates new samples in the database.  All parameters except the number
    of samples and the current location are optional.

    :Parameters:
      - `number_of_samples`: the number of samples to be created.  It must not
        be greater than 100.
      - `current_location`: the current location of the samples
      - `substrate`: the substrate of the samples.  You find possible values in
        `models_physical_processes`.
      - `timestamp`: the timestamp of the substrate process; defaults to the
        current time
      - `timestamp_inaccuracy`: the timestamp inaccuracy of the substrate
        process.  See ``samples.models_common`` for details.
      - `purpose`: the purpose of the samples
      - `tags`: the tags of the samples
      - `topic`: the name of the topic of the samples
      - `substrate_comments`: Further comments on the substrate process

    :type number_of_samples: int
    :type current_location: unicode
    :type substrate: unicode
    :type timestamp: unicode
    :type timestamp_inaccuracy: unicode
    :type purpose: unicode
    :type tags: unicode
    :type topic: unicode
    :type substrate_comments: unicode

    :Return:
      the IDs of the generated samples

    :rtype: list of int
    """
    samples = connection.open("samples/add/",
                              {"number_of_samples": number_of_samples,
                               "current_location": current_location,
                               "timestamp": format_timestamp(timestamp),
                               "timestamp_inaccuracy": timestamp_inaccuracy or 0,
                               "substrate": substrate,
                               "substrate_comments": substrate_comments,
                               "purpose": purpose,
                               "tags": tags,
                               "topic": primary_keys["topics"].get(topic),
                               "currently_responsible_person":
                                   primary_keys["users"][connection.username]})
    logging.info("Successfully created {number} samples with the ids {ids}.".format(
            number=len(samples), ids=comma_separated_ids(samples)))
    return samples


class Result(object):

    def __init__(self, id_=None, with_image=True):
        """Class constructor.

        :Parameters:
          - `id_`: if given, the instance represents an existing result process
            of the database.  Note that this triggers an exception if the
            result ID is not found in the database.
          - `with_image`: whether the image data should be loaded, too

        :type id_: int or unicode
        :type with_image: bool
        """
        if id_:
            self.id = id_
            data = connection.open("results/{0}".format(id_))
            self.sample_ids = data["samples"]
            self.sample_series = data["sample_series"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.title = data["title"]
            self.image_type = data["image_type"]
            if self.image_type != "none" and with_image:
                self.image_data = connection.open("results/images/{0}".format(id_), response_is_json=False)
            self.external_operator = data["external_operator"]
            self.quantities_and_values = json.loads(data["quantities_and_values"])
            self.existing = True
        else:
            self.id = None
            self.sample_ids = []
            self.sample_series = []
            self.external_operator = self.operator = self.timestamp = self.comments = self.title = self.image_type = None
            self.timestamp_inaccuracy = 0
            self.quantities_and_values = []
            self.existing = False
        self.image_filename = None
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the result to the database.

        :Return:
          the result process ID if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        number_of_quantities = len(self.quantities_and_values)
        number_of_values = number_of_quantities and len(self.quantities_and_values[0][1])
        data = {"finished": self.finished,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "title": self.title,
                "samples": self.sample_ids,
                "sample_series": self.sample_series,
                "number_of_quantities": number_of_quantities,
                "number_of_values": number_of_values,
                "previous-number_of_quantities": number_of_quantities,
                "previous-number_of_values": number_of_values,
                "remove_from_my_samples": False,
                "external_operator": self.external_operator and \
                    primary_keys["external_operators"][self.external_operator],
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for i, quantity_and_values in enumerate(self.quantities_and_values):
            quantity, values = quantity_and_values
            data["{0}-quantity".format(i)] = quantity
            for j, value in enumerate(values):
                data["{0}_{1}-value".format(i, j)] = value
        if self.image_filename:
            data["image_file"] = open(self.image_filename)
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("results/{0}/edit/".format(self.id), data)
            else:
                result = connection.open("results/add/", data)
                logging.info("Successfully added result {0}.".format(self.id))
        return result


class SixChamberDeposition(object):
    """Class that represents 6-chamber depositions.

    :ivar sample_ids: the IDs of the samples which took part in the deposition

    :ivar operator: the operator of the deposition.  You can set this parameter
      to someone other than you if you are an administrator.

    :ivar timestamp: the timestamp of the deposition.  It defaults to the
      current time.

    :ivar timestamp_inaccuracy: the timestamp inaccuracy of the substrate
      process.  See ``samples.models_common`` for details.

    :ivar comments: comments on the deposition as a whole (there are also layer
      comments, but they are with layers)

    :ivar number: the deposition number

    :ivar carrier: the carrier used in the deposition

    :ivar finished: whether the deposition is finished

    :ivar edit_description: description of the changes if you change an
      existing finished deposition which is finished

    :ivar edit_important: whether the change was important.  It defaults to
      ``True``.

    :ivar layers: the layers of the deposition

    :type sample_ids: list of int
    :type operator: unicode
    :type timestamp: unicode
    :type timestamp_inaccuracy: unicode
    :type comments: unicode
    :type number: unicode
    :type carrier: unicode
    :type finished: bool
    :type edit_description: unicode
    :type edit_important: bool
    :type layers: list of `SixChamberLayer`
    """

    def __init__(self, number=None):
        """Class constructor.

        :Parameters:
          - `number`: if given, the instance represents an existing deposition
            of the database.  Note that this triggers an exception if the
            deposition number is not found in the database.

        :type number: unicode
        """
        if number:
            data = connection.open("6-chamber_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.carrier = data["carrier"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                SixChamberLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.number = self.carrier = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the depositon to the database.

        :Return:
          the deposition number if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/B")
        data = {"number": self.number,
                "carrier": self.carrier,
                "finished": self.finished,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("6-chamber_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("6-chamber_depositions/add/", data)
                logging.info("Successfully added 6-chamber deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/SixChamberDeposition"))


class SixChamberLayer(object):
    """Class representing a single 6-chamber layer.  In contrast to other
    deposition systems, this one has gas channel objects as children of layers.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.pressure = data["pressure"]
            self.time = data["time"]
            self.substrate_electrode_distance = data["substrate_electrode_distance"]
            self.comments = data["comments"]
            self.transfer_in_chamber = data["transfer_in_chamber"]
            self.pre_heat = data["pre_heat"]
            self.gas_pre_heat_gas = data["gas_pre_heat_gas"]
            self.gas_pre_heat_pressure = data["gas_pre_heat_pressure"]
            self.gas_pre_heat_time = data["gas_pre_heat_time"]
            self.heating_temperature = data["heating_temperature"]
            self.transfer_out_of_chamber = data["transfer_out_of_chamber"]
            self.plasma_start_power = data["plasma_start_power"]
            self.plasma_start_with_carrier = data["plasma_start_with_carrier"]
            self.deposition_frequency = data["deposition_frequency"]
            self.deposition_power = data["deposition_power"]
            self.base_pressure = data["base_pressure"]
            self.channels = []
            channels = [value for key, value in data.items() if key.startswith("channel ")]
            for channel_data in channels:
                SixChamberChannel(self, channel_data)
        else:
            self.chamber = self.pressure = self.time = \
                self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
                self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
                self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
                self.deposition_frequency = self.deposition_power = self.base_pressure = None
            self.channels = []

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "chamber": self.chamber,
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_electrode_distance": self.substrate_electrode_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "plasma_start_power": self.plasma_start_power,
                prefix + "plasma_start_with_carrier": self.plasma_start_with_carrier,
                prefix + "deposition_frequency": self.deposition_frequency,
                prefix + "deposition_power": self.deposition_power,
                prefix + "base_pressure": self.base_pressure}
        for channel_index, channel in enumerate(self.channels):
            data.update(channel.get_data(layer_index, channel_index))
        return data


class SixChamberChannel(object):
    """Class representing a 6-Chamber channel.
    """

    def __init__(self, layer, data=None):
        self.layer = layer
        layer.channels.append(self)
        if data:
            self.number = data["number"]
            self.gas = data["gas"]
            self.flow_rate = data["flow_rate"]
        else:
            self.number = self.gas = self.flow_rate = None

    def get_data(self, layer_index, channel_index):
        prefix = "{0}_{1}-".format(layer_index, channel_index)
        return {prefix + "number": self.number, prefix + "gas": self.gas, prefix + "flow_rate": self.flow_rate}


class LargeAreaDeposition(object):
    """Class representing Large-Area depositions.  See `SixChamberDeposition`,
    which is very similar.
    """
    deposition_prefix = "{0}L-".format(datetime.date.today().strftime("%y"))
    deposition_number_pattern = re.compile(r"\d\dL-(?P<number>\d+)$")

    def __init__(self, number=None):
        if number:
            data = connection.open("large-area_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.carrier = data["carrier"]
            self.load_chamber = data["load_chamber"]
            self.sample_holder = data["sample_holder"]
            self.substrate_size = data["substrate_size"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                LargeAreaLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.number = self.operator = self.timestamp = self.comments = None
            self.carrier = self.load_chamber = self.substrate_size = self.sample_holder = None
            self.timestamp_inaccuracy = 0
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        # Returns the deposition number if succeeded
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            # ``number_base`` is the number of the first layer
            next_number = connection.open("next_deposition_number/L")
            number_base = int(self.deposition_number_pattern.match(next_number).group("number"))
            self.number = self.deposition_prefix + "{0:03}".format(number_base + len(self.layers) - 1)
        else:
            number_base = int(self.deposition_number_pattern.match(self.number).group("number")) - len(self.layers) + 1
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "carrier": self.carrier,
                "load_chamber": self.load_chamber,
                "sample_holder": self.sample_holder,
                "substrate_size": self.substrate_size,
                "remove_from_my_samples": False}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index + number_base, layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("large-area_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("large-area_depositions/add/", data)
                logging.info("Successfully added Large-Area deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        return set(connection.open("available_items/LargeAreaDeposition"))


class LargeAreaLayer(object):
    """Class representing Large-Area layer.  See `SixChamberLayer`, which is
    very similar except that this one doesn't have channels but stores the
    gases in attributes.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.date = data["date"]
            self.layer_type = data["layer_type"]
            self.station = data["station"]
            self.sih4 = data["sih4"]
            self.sih4_end = data["sih4_end"]
            self.h2 = data["h2"]
            self.h2_end = data["h2_end"]
            self.tmb = data["tmb"]
            self.ch4 = data["ch4"]
            self.co2 = data["co2"]
            self.ph3 = data["ph3"]
            self.power = data["power"]
            self.pressure = data["pressure"]
            self.temperature = data["temperature"]
            self.hf_frequency = data["hf_frequency"]
            self.time = data["time"]
            self.dc_bias = data["dc_bias"]
            self.electrode = data["electrode"]
            self.electrodes_distance = data["electrodes_distance"]
        else:
            self.date = self.layer_type = self.station = self.sih4 = self.sih4_end = self.h2 = self.h2_end = self.tmb = \
                self.ch4 = self.co2 = self.ph3 = self.power = self.pressure = self.temperature = self.hf_frequency = \
                self.time = self.dc_bias = self.electrode = self.electrodes_distance = None

    def get_data(self, layer_number, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_number,
                prefix + "date": self.date,
                prefix + "layer_type": self.layer_type,
                prefix + "station": self.station,
                prefix + "sih4": self.sih4,
                prefix + "sih4_end": self.sih4_end,
                prefix + "h2": self.h2,
                prefix + "h2_end": self.h2_end,
                prefix + "tmb": self.tmb,
                prefix + "ch4": self.ch4,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "power": self.power,
                prefix + "pressure": self.pressure,
                prefix + "temperature": self.temperature,
                prefix + "hf_frequency": self.hf_frequency,
                prefix + "time": self.time,
                prefix + "dc_bias": self.dc_bias,
                prefix + "electrode": self.electrode,
                prefix + "electrodes_distance": self.electrodes_distance}
        return data


class LargeSputterDeposition(object):
    """Class representing large sputter (LISSY) depositions.  See
    `LargeAreaDeposition`, which is very similar.
    """
    deposition_prefix = "{0}V-".format(datetime.date.today().strftime("%y"))
    deposition_number_pattern = re.compile(r"\d\dV-(?P<number>\d+)$")

    def __init__(self, number=None):
        if number:
            data = connection.open("large_sputter_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.loadlock = data["loadlock"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                LargeSputterLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.number = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.loadlock = None
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        # Returns the deposition number if succeeded
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            # ``number_base`` is the number of the first layer
            self.number = connection.open("next_deposition_number/V")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "loadlock": self.loadlock,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("large_sputter_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("large_sputter_depositions/add/", data)
                logging.info("Successfully added Large Sputter deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        return set(connection.open("available_items/LargeSputterDeposition"))


class LargeSputterLayer(object):
    """Class representing Large Sputter layer.  See `LargeAreaLayer`, which is
    very similar.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.layer_description = data["layer_description"]
            self.target = data["target"]
            self.mode = data["mode"]
            self.rpm = data["rpm"]
            self.temperature_ll = data["temperature_ll"]
            self.temperature_pc_1 = data["temperature_pc_1"]
            self.temperature_pc_2 = data["temperature_pc_2"]
            self.temperature_pc_3 = data["temperature_pc_3"]
            self.temperature_smc_1 = data["temperature_smc_1"]
            self.temperature_smc_2 = data["temperature_smc_2"]
            self.temperature_smc_3 = data["temperature_smc_3"]
            self.pre_heat = data["pre_heat"]
            self.operating_pressure = data["operating_pressure"]
            self.base_pressure = data["base_pressure"]
            self.throttle = data["throttle"]
            self.gen_power = data["gen_power"]
            self.ref_power = data["ref_power"]
            self.voltage_1 = data["voltage_1"]
            self.voltage_2 = data["voltage_2"]
            self.current_1 = data["current_1"]
            self.current_2 = data["current_2"]
            self.cl = data["cl"]
            self.ct = data["ct"]
            self.feed_rate = data["feed_rate"]
            self.steps = data["steps"]
            self.static_time = data["static_time"]
            self.ar_1 = data["ar_1"]
            self.ar_2 = data["ar_2"]
            self.o2_1 = data["o2_1"]
            self.o2_2 = data["o2_2"]
            self.ar_o2 = data["ar_o2"]
            self.n2 = data["n2"]
            self.pem_1 = data["pem_1"]
            self.pem_2 = data["pem_2"]
            self.u_cal_1 = data["u_cal_1"]
            self.u_cal_2 = data["u_cal_2"]
            self.calibration_1 = data["calibration_1"]
            self.calibration_2 = data["calibration_2"]
            self.frequency = data["frequency"]
            self.duty_cycle = data["duty_cycle"]
            self.accumulated_power = data["accumulated_power"]
        else:
            self.layer_description = self.target = self.mode = self.rpm = \
                self.temperature_ll = self.temperature_pc_1 = self.temperature_pc_2 = self.temperature_pc_3 = \
                self.temperature_smc_1 = self.temperature_smc_2 = self.temperature_smc_3 = self.pre_heat = \
                self.operating_pressure = self.base_pressure = self.throttle = self.gen_power = self.ref_power = \
                self.voltage_1 = self.voltage_2 = self.current_1 = self.current_2 = self.cl = self.ct = self.feed_rate = \
                self.steps = self.static_time = self.ar_1 = self.ar_2 = self.o2_1 = self.o2_2 = self.ar_o2 = \
                self.n2 = self.pem_1 = self.pem_2 = self.u_cal_1 = self.u_cal_2 = self.calibration_1 = self.calibration_2 = \
                self.frequency = self.duty_cycle = self.accumulated_power = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "layer_description": self.layer_description,
                prefix + "target": self.target,
                prefix + "mode": self.mode,
                prefix + "rpm": self.rpm,
                prefix + "temperature_ll": self.temperature_ll,
                prefix + "temperature_pc_1": self.temperature_pc_1,
                prefix + "temperature_pc_2": self.temperature_pc_2,
                prefix + "temperature_pc_3": self.temperature_pc_3,
                prefix + "temperature_smc_1": self.temperature_smc_1,
                prefix + "temperature_smc_2": self.temperature_smc_2,
                prefix + "temperature_smc_3": self.temperature_smc_3,
                prefix + "pre_heat": self.pre_heat,
                prefix + "operating_pressure": self.operating_pressure,
                prefix + "base_pressure": self.base_pressure,
                prefix + "throttle": self.throttle,
                prefix + "gen_power": self.gen_power,
                prefix + "ref_power": self.ref_power,
                prefix + "voltage_1": self.voltage_1,
                prefix + "voltage_2": self.voltage_2,
                prefix + "current_1": self.current_1,
                prefix + "current_2": self.current_2,
                prefix + "cl": self.cl,
                prefix + "ct": self.ct,
                prefix + "feed_rate": self.feed_rate,
                prefix + "steps": self.steps,
                prefix + "static_time": self.static_time,
                prefix + "ar_1": self.ar_1,
                prefix + "ar_2": self.ar_2,
                prefix + "o2_1": self.o2_1,
                prefix + "o2_2": self.o2_2,
                prefix + "ar_o2": self.ar_o2,
                prefix + "n2": self.n2,
                prefix + "pem_1": self.pem_1,
                prefix + "pem_2": self.pem_2,
                prefix + "u_cal_1": self.u_cal_1,
                prefix + "u_cal_2": self.u_cal_2,
                prefix + "calibration_1": self.calibration_1,
                prefix + "calibration_2": self.calibration_2,
                prefix + "frequency": self.frequency,
                prefix + "duty_cycle": self.duty_cycle,
                prefix + "accumulated_power": self.accumulated_power}
        return data


class PHotWireDeposition(object):
    """Class that represents p-hot-wire depositions.
    """

    def __init__(self, number=None):
        """Class constructor.

        :Parameters:
          - `number`: if given, the instance represents an existing deposition
            of the database.  Note that this triggers an exception if the
            deposition number is not found in the database.

        :type number: unicode
        """
        if number:
            data = connection.open("p_hot_wire_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                PHotWireLayer(self, layer_data)
            self.existing = True
        else:
            self.number = None
            self.sample_ids = []
            self.carrier = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the depositon to the database.

        :Return:
          the deposition number if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/O")
        data = {"number": self.number,
                "finished": self.finished,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("p_hot_wire_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("p_hot_wire_depositions/add/", data)
                logging.info("Successfully added p-hot-wire deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/PHotWireDeposition"))


class PHotWireLayer(object):
    """Class representing a single p-hot-wire layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.pressure = data["pressure"]
            self.time = data["time"]
            self.substrate_wire_distance = data["substrate_wire_distance"]
            self.comments = data["comments"]
            self.transfer_in_chamber = data["transfer_in_chamber"]
            self.pre_heat = data["pre_heat"]
            self.gas_pre_heat_gas = data["gas_pre_heat_gas"]
            self.gas_pre_heat_pressure = data["gas_pre_heat_pressure"]
            self.gas_pre_heat_time = data["gas_pre_heat_time"]
            self.heating_temperature = data["heating_temperature"]
            self.transfer_out_of_chamber = data["transfer_out_of_chamber"]
            self.filament_temperature = data["filament_temperature"]
            self.current = data["current"]
            self.voltage = data["voltage"]
            self.wire_power = data["wire_power"]
            self.wire_material = data["wire_material"]
            self.base_pressure = data["base_pressure"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
            self.mms = data["mms"]
            self.tmb = data["tmb"]
            self.ch4 = data["ch4"]
            self.ph3_sih4 = data["ph3_sih4"]
            self.ar = data["ar"]
            self.tmal = data["tmal"]
        else:
            self.pressure = self.time = \
                self.substrate_wire_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
                self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
                self.transfer_out_of_chamber = self.wire_material = self.voltage = \
                self.filament_temperature = self.current = self.base_pressure = None
            self.h2 = self.sih4 = self.tmb = self.ch4 = self.ph3_sih4 = self.ar = self.tmal = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_wire_distance": self.substrate_wire_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "wire_material": self.wire_material,
                prefix + "voltage": self.voltage,
                prefix + "filament_temperature": self.filament_temperature,
                prefix + "current": self.current,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4,
                prefix + "tmb": self.tmb,
                prefix + "ch4": self.ch4,
                prefix + "ph3_sih4": self.ph3_sih4,
                prefix + "ar": self.ar,
                prefix + "tmal": self.tmal}
        return data


class OldClusterToolDeposition(object):
    """Class representing Cluster Tool I depositions.  See
    `SixChamberDeposition`, which is very similar.
    """

    def __init__(self, number=None):
        if number:
            data = connection.open("old_cluster_tool_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.carrier = data["carrier"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                if layer_data["layer type"] == "PECVD":
                    OldClusterToolPECVDLayer(self, layer_data)
                elif layer_data["layer type"] == "hot-wire":
                    OldClusterToolHotWireLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.number = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.carrier = None
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/C")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("old_cluster_tool_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("old_cluster_tool_depositions/add/", data)
                logging.info("Successfully added cluster tool I deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/OldClusterToolDeposition"))


class OldClusterToolHotWireLayer(object):
    """Class representing Cluster Tool I hot-wire layer.  See
    `SixChamberLayer`, which is very similar except that this one doesn't have
    channels but stores the gases in attributes.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.pressure = data["pressure"]
            self.time = data["time"]
            self.substrate_wire_distance = data["substrate_wire_distance"]
            self.comments = data["comments"]
            self.transfer_in_chamber = data["transfer_in_chamber"]
            self.pre_heat = data["pre_heat"]
            self.gas_pre_heat_gas = data["gas_pre_heat_gas"]
            self.gas_pre_heat_pressure = data["gas_pre_heat_pressure"]
            self.gas_pre_heat_time = data["gas_pre_heat_time"]
            self.heating_temperature = data["heating_temperature"]
            self.transfer_out_of_chamber = data["transfer_out_of_chamber"]
            self.filament_temperature = data["filament_temperature"]
            self.current = data["current"]
            self.voltage = data["voltage"]
            self.wire_power = data["wire_power"]
            self.wire_material = data["wire_material"]
            self.base_pressure = data["base_pressure"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
            self.mms = data["mms"]
            self.tmb = data["tmb"]
            self.co2 = data["co2"]
            self.ph3 = data["ph3"]
            self.ch4 = data["ch4"]
            self.ar = data["ar"]
        else:
            self.pressure = self.time = \
                self.substrate_wire_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
                self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
                self.transfer_out_of_chamber = self.wire_material = self.voltage = \
                self.filament_temperature = self.current = self.base_pressure = None
            self.h2 = self.sih4 = self.mms = self.tmb = self.co2 = self.ph3 = self.ch4 = self.ar = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "hot-wire",
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_wire_distance": self.substrate_wire_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "wire_material": self.wire_material,
                prefix + "voltage": self.voltage,
                prefix + "filament_temperature": self.filament_temperature,
                prefix + "current": self.current,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4,
                prefix + "mms": self.mms,
                prefix + "tmb": self.tmb,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "ch4": self.ch4,
                prefix + "ar": self.ar}
        return data


class OldClusterToolPECVDLayer(object):
    """Class representing Cluster Tool I PECVD layer.  See `SixChamberLayer`,
    which is very similar except that this one doesn't have channels but stores
    the gases in attributes.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.pressure = data["pressure"]
            self.time = data["time"]
            self.substrate_electrode_distance = data["substrate_electrode_distance"]
            self.comments = data["comments"]
            self.transfer_in_chamber = data["transfer_in_chamber"]
            self.pre_heat = data["pre_heat"]
            self.gas_pre_heat_gas = data["gas_pre_heat_gas"]
            self.gas_pre_heat_pressure = data["gas_pre_heat_pressure"]
            self.gas_pre_heat_time = data["gas_pre_heat_time"]
            self.heating_temperature = data["heating_temperature"]
            self.transfer_out_of_chamber = data["transfer_out_of_chamber"]
            self.plasma_start_power = data["plasma_start_power"]
            self.plasma_start_with_shutter = data["plasma_start_with_shutter"]
            self.deposition_frequency = data["deposition_frequency"]
            self.deposition_power = data["deposition_power"]
            self.base_pressure = data["base_pressure"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
            self.mms = data["mms"]
            self.tmb = data["tmb"]
            self.co2 = data["co2"]
            self.ph3 = data["ph3"]
            self.ch4 = data["ch4"]
            self.ar = data["ar"]
        else:
            self.chamber = self.pressure = self.time = \
                self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
                self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
                self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
                self.deposition_frequency = self.deposition_power = self.base_pressure = None
            self.h2 = self.sih4 = self.mms = self.tmb = self.co2 = self.ph3 = self.ch4 = self.ar = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "PECVD",
                prefix + "chamber": self.chamber,
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_electrode_distance": self.substrate_electrode_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "plasma_start_power": self.plasma_start_power,
                prefix + "plasma_start_with_carrier": self.plasma_start_with_carrier,
                prefix + "deposition_frequency": self.deposition_frequency,
                prefix + "deposition_power": self.deposition_power,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4,
                prefix + "mms": self.mms,
                prefix + "tmb": self.tmb,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "ch4": self.ch4,
                prefix + "ar": self.ar}
        return data


class NewClusterToolDeposition(object):
    """Class representing Cluster Tool II depositions.  See
    `SixChamberDeposition`, which is very similar.
    """

    def __init__(self, number=None):
        if number:
            data = connection.open("new_cluster_tool_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.carrier = data["carrier"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                if layer_data["layer type"] == "PECVD":
                    NewClusterToolPECVDLayer(self, layer_data)
                elif layer_data["layer type"] == "hot-wire":
                    NewClusterToolHotWireLayer(self, layer_data)
                elif layer_data["layer type"] == "sputter":
                    NewClusterToolSputterLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.number = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.carrier = None
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/P")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("new_cluster_tool_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("new_cluster_tool_depositions/add/", data)
                logging.info("Successfully added cluster tool II deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/NewClusterToolDeposition"))


class NewClusterToolPECVDLayer(object):
    """Class representing Cluster Tool II PECVD layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.pressure = data["pressure"]
            self.time = data["time"]
            self.substrate_electrode_distance = data["substrate_electrode_distance"]
            self.comments = data["comments"]
            self.transfer_in_chamber = data["transfer_in_chamber"]
            self.pre_heat = data["pre_heat"]
            self.gas_pre_heat_gas = data["gas_pre_heat_gas"]
            self.gas_pre_heat_pressure = data["gas_pre_heat_pressure"]
            self.gas_pre_heat_time = data["gas_pre_heat_time"]
            self.heating_temperature = data["heating_temperature"]
            self.transfer_out_of_chamber = data["transfer_out_of_chamber"]
            self.plasma_start_power = data["plasma_start_power"]
            self.plasma_start_with_shutter = data["plasma_start_with_shutter"]
            self.deposition_frequency = data["deposition_frequency"]
            self.deposition_power = data["deposition_power"]
            self.base_pressure = data["base_pressure"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
            self.tmb = data["tmb"]
            self.co2 = data["co2"]
            self.ph3 = data["ph3"]
            self.ch4 = data["ch4"]
            self.ar = data["ar"]
            self.geh4 = data["geh4"]
            self.b2h6 = data["b2h6"]
            self.sih4_29 = data["sih4_29"]
        else:
            self.chamber = self.pressure = self.time = \
                self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
                self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
                self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
                self.deposition_frequency = self.deposition_power = self.base_pressure = None
            self.h2 = self.sih4 = self.tmb = self.co2 = self.ph3 = self.ch4 = self.ar = self.geh4 = self.b2h6 = \
                self.sih4_29 = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "PECVD",
                prefix + "chamber": self.chamber,
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_electrode_distance": self.substrate_electrode_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "plasma_start_power": self.plasma_start_power,
                prefix + "plasma_start_with_carrier": self.plasma_start_with_carrier,
                prefix + "deposition_frequency": self.deposition_frequency,
                prefix + "deposition_power": self.deposition_power,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4,
                prefix + "tmb": self.tmb,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "ch4": self.ch4,
                prefix + "ar": self.ar,
                prefix + "geh4": self.geh4,
                prefix + "b2h6": self.b2h6,
                prefix + "sih4_29": self.sih4_29}
        return data


class NewClusterToolHotWireLayer(object):
    """Class representing Cluster Tool II hot-wire layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.pressure = data["pressure"]
            self.time = data["time"]
            self.substrate_wire_distance = data["substrate_wire_distance"]
            self.comments = data["comments"]
            self.transfer_in_chamber = data["transfer_in_chamber"]
            self.pre_heat = data["pre_heat"]
            self.gas_pre_heat_gas = data["gas_pre_heat_gas"]
            self.gas_pre_heat_pressure = data["gas_pre_heat_pressure"]
            self.gas_pre_heat_time = data["gas_pre_heat_time"]
            self.heating_temperature = data["heating_temperature"]
            self.transfer_out_of_chamber = data["transfer_out_of_chamber"]
            self.filament_temperature = data["filament_temperature"]
            self.current = data["current"]
            self.voltage = data["voltage"]
            self.wire_power = data["wire_power"]
            self.wire_material = data["wire_material"]
            self.base_pressure = data["base_pressure"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
            self.tmb = data["tmb"]
            self.co2 = data["co2"]
            self.ph3 = data["ph3"]
            self.ch4 = data["ch4"]
            self.ar = data["ar"]
            self.geh4 = data["geh4"]
            self.b2h6 = data["b2h6"]
            self.sih4_29 = data["sih4_29"]
        else:
            self.pressure = self.time = \
                self.substrate_wire_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
                self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
                self.transfer_out_of_chamber = self.wire_material = self.voltage = \
                self.filament_temperature = self.current = self.base_pressure = None
            self.h2 = self.sih4 = self.tmb = self.co2 = self.ph3 = self.ch4 = self.ar = self.geh4 = self.b2h6 = \
                self.sih4_29 = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "hot-wire",
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_wire_distance": self.substrate_wire_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "wire_material": self.wire_material,
                prefix + "voltage": self.voltage,
                prefix + "filament_temperature": self.filament_temperature,
                prefix + "current": self.current,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4,
                prefix + "tmb": self.tmb,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "ch4": self.ch4,
                prefix + "ar": self.ar,
                prefix + "geh4": self.geh4,
                prefix + "b2h6": self.b2h6,
                prefix + "sih4_29": self.sih4_29}
        return data


class NewClusterToolSputterLayer(object):
    """Class representing Cluster Tool II sputter layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.comments = data["comments"]
            self.base_pressure = data["base_pressure"]
            self.working_pressure = data["working_pressure"]
            self.valve = data["valve"]
            self.set_temperature = data["set_temperature"]
            self.thermocouple = data["thermocouple"]
            self.ts = data["ts"]
            self.pyrometer = data["pyrometer"]
            self.ar = data["ar"]
            self.o2 = data["o2"]
            self.ar_o2 = data["ar_o2"]
            self.pre_heat = data["pre_heat"]
            self.pre_sputter_time = data["pre_sputter_time"]
            self.large_shutter = data["large_shutter"]
            self.small_shutter = data["small_shutter"]
            self.substrate_holder = data["substrate_holder"]
            self.rotational_speed = data["rotational_speed"]
            self.loading_chamber = data["loading_chamber"]
            self.slots = dict((number, NewClusterToolSputterSlot(data["slot {0}".format(number)])) for number in [1, 2, 3])
        else:
            self.comments = self.base_pressure = self.working_pressure = self.valve = self.set_temperature = \
                self.thermocouple = self.ts = self.pyrometer = self.ar = self.o2 = self.ar_o2 = self.pre_heat = \
                self.pre_sputter_time = self.large_shutter = self.small_shutter = self.substrate_holder = \
                self.rotational_speed = self.loading_chamber = None
            self.slots = dict((number, NewClusterToolSputterSlot()) for number in [1, 2, 3])

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "sputter",
                prefix + "comments": self.comments,
                prefix + "base_pressure": self.base_pressure,
                prefix + "working_pressure": self.working_pressure,
                prefix + "valve": self.valve,
                prefix + "set_temperature": self.set_temperature,
                prefix + "thermocouple": self.thermocouple,
                prefix + "ts": self.ts,
                prefix + "pyrometer": self.pyrometer,
                prefix + "ar": self.ar,
                prefix + "o2": self.o2,
                prefix + "ar_o2": self.ar_o2,
                prefix + "pre_heat": self.pre_heat,
                prefix + "pre_sputter_time": self.pre_sputter_time,
                prefix + "large_shutter": self.large_shutter,
                prefix + "small_shutter": self.small_shutter,
                prefix + "substrate_holder": self.substrate_holder,
                prefix + "rotational_speed": self.rotational_speed,
                prefix + "loading_chamber": self.loading_chamber}
        for slot_number in [1, 2, 3]:
            data.update(self.slots[slot_number].get_data(layer_index, slot_number - 1))
        return data


class NewClusterToolSputterSlot(object):
    """Class representing one sputter slot in a sputter layer of the Cluster
    Tool II.  Every sputter layer there has exactly three of these slots, but
    the ``mode`` may be ``None`` which means that this slot was not used.
    """

    def __init__(self, data=None):
        if data:
            self.mode = data["mode"]
            self.target = data["target"]
            self.time = data["time"]
            self.power = data["power"]
            self.power_end = data["power_end"]
            self.cl = data["cl"]
            self.ct = data["ct"]
            self.voltage = data["voltage"]
            self.voltage_end = data["voltage_end"]
            self.refl_power = data["refl_power"]
            self.current = data["current"]
            self.current_end = data["current_end"]
            self.u_bias = data["u_bias"]
            self.u_bias_end = data["u_bias_end"]
        else:
            self.mode = self.target = self.time = self.power = self.power_end = self.cl = self.ct = \
                self.voltage = self.voltage_end = self.refl_power = self.current = self.current_end = \
                self.u_bias = self.u_bias_end = None

    def get_data(self, layer_index, slot_index):
        prefix = "{0}-{1}-".format(layer_index, slot_index)
        data = {prefix + "mode": self.mode,
                prefix + "target": self.target,
                prefix + "time": self.time,
                prefix + "power": self.power,
                prefix + "power_end": self.power_end,
                prefix + "cl": self.cl,
                prefix + "ct": self.ct,
                prefix + "voltage": self.voltage,
                prefix + "voltage_end": self.voltage_end,
                prefix + "refl_power": self.refl_power,
                prefix + "current": self.current,
                prefix + "current_end": self.current_end,
                prefix + "u_bias": self.u_bias,
                prefix + "u_bias_end": self.u_bias_end}
        return data


def rename_after_deposition(deposition_number, new_names):
    """Rename samples after a deposition.  In the IEK-PV, it is custom to give
    samples the name of the deposition after the deposition.  This is realised
    here.

    :Parameters:
      `deposition_number`: the number of the deposition
      `new_names`: the new names of the samples.  The keys of this dictionary
        are the sample IDs.  The values are the new names.  Note that they must
        start with the deposition number.

    :type deposition_number: unicode
    :type new_samples: dict mapping int to unicode
    """
    data = {}
    for i, id_ in enumerate(new_names):
        data["{0}-sample".format(i)] = id_
        data["{0}-number_of_pieces".format(i)] = 1
        data["0-new_name"] = data["{0}_0-new_name".format(i)] = new_names[id_]
    connection.open("depositions/split_and_rename_samples/" + deposition_number, data)


class PDSMeasurement(object):
    """Class representing PDS measurements.
    """

    def __init__(self, number=None):
        """Class constructor.  See `SixChamberDeposition.__init__` for further
        details.  Only the attributes are different.
        """
        if number:
            data = connection.open("pds_measurements/{0}".format(number))
            self.sample_id = data["samples"][0]
            self.number = data["number"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.apparatus = data["apparatus"]
            self.raw_datafile = data["raw_datafile"]
            self.evaluated_datafile = data["evaluated_datafile"]
            self.phase_corrected_evaluated_datafile = data["phase_corrected_evaluated_datafile"]
            self.existing = True
        else:
            self.sample_id = self.number = self.operator = self.timestamp = self.comments = self.apparatus = None
            self.timestamp_inaccuracy = 0
            self.raw_datafile = self.evaluated_datafile = self.phase_corrected_evaluated_datafile = None
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"number": self.number,
                "apparatus": self.apparatus,
                "sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "raw_datafile": self.raw_datafile,
                "evaluated_datafile": self.evaluated_datafile,
                "phase_corrected_evaluated_datafile": self.phase_corrected_evaluated_datafile,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important
                }
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("pds_measurements/{0}/edit/".format(self.number), data)
            else:
                return connection.open("pds_measurements/add/", data)

    @classmethod
    def get_already_available_pds_numbers(cls):
        """Returns the already available PDS numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available PDS numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/PDSMeasurement"))


class SputterCharacterization(object):
    """Class representing post-sputter characterisations.
    """

    def __init__(self, id_=None):
        self.id = id_
        if self.id:
            data = connection.open("sputter_characterizations/{0}".format(id_))
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.thickness = data["thickness"]
            self.r_square = data["r_square"]
            self.rho = data["rho"]
            self.deposition_rate = data["deposition_rate"]
            self.large_sputter_deposition = data["large_sputter_deposition"]
            self.new_cluster_tool_deposition = data["new_cluster_tool_deposition"]
            self.existing = True
        else:
            self.sample_id = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.thickness = self.r_square = self.rho = self.deposition_rate = self.large_sputter_deposition = \
                self.new_cluster_tool_deposition = None
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "comments": self.comments,
                "thickness": self.thickness,
                "r_square": self.r_square,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important
                }
        if self.large_sputter_deposition:
            deposition_key = "large_sputter_deposition"
        elif self.new_cluster_tool_deposition:
            deposition_key = "new_cluster_tool_deposition"
        else:
            deposition_key = None
        if deposition_key:
            deposition_number = self.large_sputter_deposition or self.new_cluster_tool_deposition
            primary_keys = connection.open("primary_keys?depositions={0}".format(urllib.parse.quote_plus(deposition_number)))
            deposition_id = primary_keys["depositions"][deposition_number]
            data[deposition_key] = deposition_id
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("sputter_characterizations/{0}/edit/".format(self.id), data)
            else:
                return connection.open("sputter_characterizations/add/", data)


class LumaMeasurement(object):
    """Class representing Luma measurements.
    """

    def __init__(self, id_=None):
        self.id = id_
        if self.id:
            data = connection.open("luma_measurements/{0}".format(id_))
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.filepath = data["filepath"]
            self.laser_type = data["laser_type"]
            self.laser_intensity = data["laser_intensity"]
            self.cell_position = data["cell_position"]
            self.cell_area = data["cell_area"]
            self.existing = True
        else:
            self.sample_id = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.filepath = self.laser_type = self.laser_intensity = self.cell_position = self.cell_area = None
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "comments": self.comments,
                "filepath": self.filepath,
                "laser_type": self.laser_type,
                "laser_intensity": self.laser_intensity,
                "cell_position": self.cell_position,
                "cell_area": self.cell_area,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important
                }
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("luma_measurements/{0}/edit/".format(self.id), data)
            else:
                return connection.open("luma_measurements/add/", data)


class ConductivityMeasurementSet(object):

    def __init__(self, id_=None):
        if id_:
            data = connection.open("processes/{0}".format(id_))
            self.id = data["id"]
            self.apparatus = data["apparatus"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.measurements = []
            measurements = [(int(key[25:]), value) for key, value in data.items()
                            if key.startswith("conductivity measurement ")]
            for __, measurement_data in sorted(measurements):
                self.measurements.append(ConductivityMeasurement(measurement_data))
            self.existing = True
        else:
            self.sample_id = self.operator = self.timestamp = self.comments = self.id = self.apparatus = None
            self.timestamp_inaccuracy = 0
            self.measurements = []
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def append_single_measurement(self, single_measurement):
        if single_measurement in self.measurements:
            single_measurement.number = self.measurements[self.measurements.index(single_measurement)].number
            del self.measurements[self.measurements.index(single_measurement)]
        self.measurements.append(single_measurement)

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"apparatus": self.apparatus,
                 "sample": self.sample_id,
                 "operator": primary_keys["users"][self.operator],
                 "comments": self.comments,
                 "remove_from_my_samples": False,
                 "edit_description-description": self.edit_description,
                 "edit_description-important": self.edit_important}
        for index, measurement in enumerate(self.measurements):
            data.update(measurement.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                result = connection.open("conductivity_measurements/{0}/edit/".format(self.id), data)
            else:
                result = connection.open("conductivity_measurements/add/", data)
        return result

    @classmethod
    def by_timestamp(cls, apparatus, sample_id, timestamp):
        return cls(connection.open("conductivity_measurements/{0}/{1}?timestamp={2}".format(
                    apparatus, sample_id, urllib.parse.quote_plus(format_timestamp(timestamp)))))


class ConductivityMeasurement(object):
    """Class representing conductivity measurements in the database.
    """
    def __init__(self, data=None):
        if data:
            self.number = data["number"]
            self.filepath = data["filepath"]
            self.kind = data["kind"]
            self.tempering_time = data["tempering_time"]
            self.tempering_temperature = data["tempering_temperature"]
            self.in_vacuum = data["in_vacuum"]
            self.light = data["light"]
            self.sigma = data["sigma"]
            self.voltage = data["voltage"]
            self.assumed_thickness = data["assumed_thickness"]
            self.temperature = data["temperature"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
        else:
            self.number = self.filepath = self.kind = self.tempering_time = self.tempering_temperature = \
                self.in_vacuum = self.light = self.sigma = self.voltage = self.assumed_thickness = self.temperature = \
                self.timestamp = self.timestamp_inaccuracy = self.comments = None

    def get_data(self, index):
        prefix = six.text_type(index) + "-"
        data = {prefix + "number": self.number,
                prefix + "tempering_temperature": self.tempering_temperature,
                prefix + "in_vacuum": self.in_vacuum,
                prefix + "tempering_time": self.tempering_time,
                prefix + "filepath": self.filepath,
                prefix + "light": self.light,
                prefix + "timestamp": format_timestamp(self.timestamp),
                prefix + "timestamp_inaccuracy": self.timestamp_inaccuracy,
                prefix + "comments": self.comments}
        return data

    def __eq__(self, other):
        return self.filepath == other.filepath


class Substrate(object):
    """Class representing substrates in the database.
    """

    def __init__(self, initial_data=None):
        """Class constructor.  Note that in contrast to the processes, you
        currently can't retrieve an existing substrate from the database
        (except by retrieving its respective sample).
        """
        if initial_data:
            self.id, self.timestamp, self.timestamp_inaccuracy, self.operator, self.external_operator, self.material, \
                self.comments, self.sample_ids = \
                initial_data["id"], parse_timestamp(initial_data["timestamp"]), \
                initial_data["timestamp_inaccuracy"], initial_data["operator"], initial_data["external_operator"], \
                initial_data["material"], initial_data["comments"], initial_data["samples"]
        else:
            self.id = self.timestamp = self.timestamp_inaccuracy = self.operator = self.external_operator = self.material = \
                self.comments = None
            self.sample_ids = []

    def submit(self):
        data = {"timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "material": self.material,
                "comments": self.comments,
                "operator": primary_keys["users"][self.operator],
                "external_operator": self.external_operator and \
                    primary_keys["external_operators"][self.external_operator],
                "sample_list": self.sample_ids}
        if self.id:
            data["edit_description-description"] = "automatic change by a non-interactive program"
            connection.open("substrates/{0}/edit/".format(self.id), data)
        else:
            return connection.open("substrates/add/", data)


class Sample(object):
    """Class representing samples.
    """

    def __init__(self, name=None, id_=None):
        """Class constructor.

        :Parameters:
          - `name`: the name of an existing sample; it is ignored if `id_` is
            given
          - `id_`: the ID of an existing sample

        :type name: unicode
        :type id_: int
        """
        if name or id_:
            data = connection.open("samples/by_id/{0}".format(id_)) if id_ else \
                connection.open("samples/{0}".format(urllib.parse.quote(name)))
            self.id = data["id"]
            self.name = data["name"]
            self.current_location = data["current_location"]
            self.currently_responsible_person = data["currently_responsible_person"]
            self.purpose = data["purpose"]
            self.tags = data["tags"]
            self.topic = data["topic"]
            self.processes = dict((key, value) for key, value in data.items() if key.startswith("process "))
        else:
            self.id = self.name = self.current_location = self.currently_responsible_person = self.purpose = self.tags = \
                self.topic = self.timestamp = None
        self.legacy = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        data = {"name": self.name, "current_location": self.current_location,
                "currently_responsible_person": primary_keys["users"][self.currently_responsible_person],
                "purpose": self.purpose, "tags": self.tags,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        if self.topic:
            data["topic"] = primary_keys["topics"][self.topic]
        if self.id:
            connection.open("samples/by_id/{0}/edit/".format(self.id), data)
        else:
            if not self.timestamp:
                self.timestamp = datetime.datetime(1990, 1, 1)
            return connection.open("add_sample?" + urllib.parse.urlencode(
                    {"legacy": self.legacy, "timestamp": format_timestamp(self.timestamp)}), data)

    def add_to_my_samples(self):
        connection.open("change_my_samples", {"add": self.id})

    def remove_from_my_samples(self):
        connection.open("change_my_samples", {"remove": self.id})


main_sample_name_pattern = re.compile(r"(?P<year>\d\d)(?P<letter>[A-Za-z])-?"
                                      r"(?P<number>\d{1,4})(?P<suffix>[-A-Za-z_/#()][-A-Za-z_/0-9#()]*)?$")
maurice_sample_name_pattern = re.compile(r"(?P<year>\d\d)[Mm]-?"
                                         r"(?P<number>\d{1,4})(?P<suffix>[-A-Za-z_/][-A-Za-z_/0-9#()]*)?$")
acme_sample_pattern = re.compile(
    r"(ACME-)?(?P<initials>JH|SW|JG|JL|SL|TS|PW|mm|ST|MI|SK|MW|OW|DM|KB|AC|UD)(?P<number>\d{4})-(?P<index>\d+)"
    r"(?P<suffix>.*?)(?P<step>(_|/)\d+)?$", re.IGNORECASE)
tsol_sample_pattern = re.compile(r"TS(?P<name>\d{3}-\d{6}[A-Za-z0-9]*)$", re.IGNORECASE)
allowed_character_pattern = re.compile("[-A-Za-z_/0-9#()]")

def normalize_sample_name(sample_name):
    """Normalises a sample name.  Unfortunately, co-workers tend to write
    sample names in many variations.  For example, instead of 10B-010, they
    write 10b-010 or 10b010 or 10B-10.  In this routine, I normalise to known
    sample patterns.  Additionally, if a known pattern is found, this routine
    makes suggestions for the currently reponsible person, the topic, and some
    other things.

    This routine is used in crawlers and legacy importers.

    :Parameter:
      - `sample_name`: the raw name of the sample

    :type sample_name: unicode

    :Return:
      The normalised sample data.  The keys of this dictionary are ``"name"``
      (this is the normalised name), ``"currently_responsible_person"``,
      ``"current_location"``, ``"substrate_operator"``,
      ``"substrate_external_operator"``, ``"topic"``, and ``"legacy"``.  The
      latter is a boolean denoting whether the database must prepend a legacy
      prefix à la “10-LGCY--” when creating the sample.

    :rtype: dict mapping str to unicode
    """
    result = {"currently_responsible_person": "nobody", "substrate_operator": "nobody", "substrate_external_operator": None,
              "legacy": True, "current_location": "unknown", "topic": "Legacy", "alias": None}

    sample_name = " ".join(sample_name.split())
    translations = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
                    " ": "_", "°": "o"}
    for from_, to in translations.items():
        sample_name = sample_name.replace(from_, to)
    allowed_sample_name_characters = []
    for character in sample_name:
        if allowed_character_pattern.match(character):
            allowed_sample_name_characters.append(character)
    result["name"] = "".join(allowed_sample_name_characters)[:30]

    current_year = datetime.datetime.now().year % 100
    match = main_sample_name_pattern.match(sample_name)
    if match and int(match.group("year")) <= current_year:
        parts = match.groupdict("")
        parts["number"] = "{0:03}".format(int(parts["number"]))
        parts["letter"] = parts["letter"].upper()
        if parts["letter"] == "D":
            result["current_location"] = "02.4u/82b, Schrank hinter Flasher"
            result["topic"] = "LADA intern"
            parts["number"] = "{0:04}".format(int(parts["number"]))
        result["name"] = "{year}{letter}-{number}{suffix}".format(**parts)
        result["legacy"] = False
        return result
    match = maurice_sample_name_pattern.match(sample_name)
    if match and int(match.group("year")) <= current_year:
        parts = match.groupdict("")
        parts["number"] = "{0:03}".format(int(parts["number"]))
        result["name"] = "{year}M-{number}{suffix}".format(**parts)
        result["currently_responsible_person"] = result["substrate_operator"] = "m.nuys"
        result["current_location"] = "Maurice' Büro"
        result["legacy"] = False
        return result
    match = acme_sample_pattern.match(sample_name)
    if match:
        parts = match.groupdict("")
        parts["initials"] = parts["initials"].upper()
        if parts["initials"] == "MM":
            parts["initials"] = "mm"
        result["name"] = "ACME-{initials}{number}-{index}{suffix}".format(**parts)
        samples_with_significant_step = set(
            ["ACME-MW2067-10", "ACME-MW2067-18", "ACME-TS2111-3", "ACME-TS2158-8", "ACME-TS2186-11", "ACME-TS2187-14",
             "ACME-TS2187-2", "ACME-DM2284-2", "ACME-DM2284-3"] +
            ["ACME-JH2089-{0}".format(index) for index in range(1, 13)])
        if result["name"] in samples_with_significant_step and parts["step"]:
            result["name"] += "_" + parts["step"][1:]
        result["currently_responsible_person"] = "t.bronger"
        result["substrate_operator"] = "t.bronger"
        result["substrate_external_operator"] = "Evonik"
        result["current_location"] = "Torstens Büro"
        result["topic"] = "Evonik 1"
        result["legacy"] = False
        return result
    match = tsol_sample_pattern.match(sample_name)
    if match:
        parts = match.groupdict("")
        result["name"] = "HELI-TS{0}".format(parts["name"])
        result["currently_responsible_person"] = "k.bittkau"
        result["substrate_operator"] = "k.bittkau"
        result["substrate_external_operator"] = "T-Solar"
        result["topic"] = "Helathis"
        result["legacy"] = False
        return result
    return result


class SubstrateFound(Exception):
    """Exception raised for simpler control flow in
    `normalize_substrate_name`.  It is only used there.
    """
    def __init__(self, key_name, substrate_comments):
        self.key_name, self.substrate_comments = key_name, substrate_comments

unknown_substrate_comment = "unknown substrate material"

def normalize_substrate_name(substrate_name, is_general_comment=False, add_zno_warning=False):
    """Normalises a substrate name to data directly usable for the sample
    database.

    :Parameters:
      - `substrate_name`: a string which contains information about the substrate
      - `is_general_comment`: whether `substrate_name` is a general comment
        containing the substrate name somewhere, or only the substrate name
        (albeit in raw form)
      - `add_zno_warning`: whether a warning should be issued if the sample
        probably had a ZnO process (because such processes are not yet in the
        database)

    :type substrate_name: unicode
    :type is_general_comment: bool
    :type add_zno_warning: bool

    :Return:
      the substrate name as needed by Chantal, comments of the substrate
      process

    :rtype: unicode, unicode
    """
    substrate_name = " ".join(substrate_name.split())
    normalized_substrate_name = substrate_name.lower().replace("-", " ").replace("(", ""). \
        replace(")", "")
    normalized_substrate_name = " ".join(normalized_substrate_name.split())
    def test_name(pattern, key_name, comment=""):
        if re.match("^({0})$".format(pattern), normalized_substrate_name, re.UNICODE):
            raise SubstrateFound(key_name, comment)
        elif re.search(pattern, normalized_substrate_name, re.UNICODE):
            raise SubstrateFound(key_name, substrate_name if not is_general_comment else comment)
    try:
        if not normalized_substrate_name:
            raise SubstrateFound("custom", unknown_substrate_comment)
        test_name("asahi ?vu|asahi ?uv", "asahi-vu")
        test_name("asahi|ashi", "asahi-u")
        test_name("corning|coaring", "corning")
        test_name("eagle ?(2000|xg)", "corning", "Eagle 2000")
        test_name("quartz|quarz", "quartz")
        test_name("ilmasil", "quartz", "Ilmasil")
        test_name("qsil", "quartz", "Qsil")
        test_name("sapphire|saphir|korund|corundum", "sapphire")
        test_name("glas", "glass")
        test_name(r"\balu", "aluminium foil")
        test_name(r"\bsi\b.*wafer|wafer.*\bsi\b|silicon.*wafer|wafer.*silicon|c ?si", "si-wafer")
        raise SubstrateFound("custom", substrate_name if not is_general_comment else unknown_substrate_comment)
    except SubstrateFound as found_substrate:
        key_name, substrate_comments = found_substrate.key_name, found_substrate.substrate_comments
        if add_zno_warning and "zno" in normalized_substrate_name:
            if substrate_comments:
                substrate_comments += "\n\n"
            substrate_comments += "ZnO may have been applied to the substrate without an explicitly shown sputter process."
        return key_name, substrate_comments


def get_or_create_sample(sample_name, substrate_name, timestamp, timestamp_inaccuracy="3", comments=None,
                         add_zno_warning=False, create=True):
    """Looks up a sample name in the database, and creates a new one if it
    doesn't exist yet.  You can only use this function if you are an
    administrator.  This function is used in crawlers and legacy importers.
    The sample is added to “My Samples”.

    :Parameters:
      - `sample_name`: the name of the sample
      - `substrate_name`: the concise descriptive name of the substrate.  This
        routine tries heavily to normalise it.
      - `timestamp`: the timestamp of the sample/substrate
      - `timestamp_inaccuracy`: the timestamp inaccuracy of the
        sample/substrate
      - `comments`: Comment which may contain information about the substrate.
        They are ignored if `substrate_name` is given.  In a way, this
        parameter is a poor man's `substrate_name`.
      - `add_zno_warning`: whether a warnign should be issued if the sample
        probably had a ZnO process (because such processes are not yet in the
        database)
      - `create`: if ``True``, create the sample if it doesn't exist yet; if
        ``False``, return ``None`` if the sample coudn't be found

    :type sample_name: unicode
    :type substrate_name: unicode or ``NoneType``
    :type timestamp_inaccuracy: unicode
    :type comments: unicode
    :type add_zno_warning: bool

    :Return:
      the ID of the sample, either the existing or the newly created; or
      ``None`` if ``create=False`` and the sample could not be found

    :rtype: int or ``NoneType``
    """
    name_info = normalize_sample_name(sample_name)
    substrate_material, substrate_comments = normalize_substrate_name(substrate_name or comments or "",
                                                                      is_general_comment=not substrate_name,
                                                                      add_zno_warning=add_zno_warning)
    if name_info["name"] != "unknown_name":
        sample_id = connection.open("primary_keys?samples=" + urllib.parse.quote_plus(name_info["name"]))["samples"].\
            get(name_info["name"])
        if not sample_id and name_info["legacy"]:
            sample_name = "{year}-LGCY--{name}".format(year=timestamp.strftime("%y"), name=name_info["name"])[:30]
            sample_id = connection.open("primary_keys?samples=" + urllib.parse.quote_plus(sample_name))["samples"].\
                get(sample_name)
        if name_info["legacy"]:
            if sample_id is not None:
                best_match = {}
                sample_ids = sample_id if isinstance(sample_id, list) else [sample_id]
                for sample_id in sample_ids:
                    substrate_data = connection.open("substrates_by_sample/{0}".format(sample_id))
                    if substrate_data:
                        current_substrate = Substrate(substrate_data)
                        timedelta = abs(current_substrate.timestamp - timestamp)
                        if timedelta < datetime.timedelta(weeks=104) and \
                                ("timedelta" not in best_match or timedelta < best_match["timedelta"]):
                            best_match["timedelta"] = timedelta
                            best_match["id"] = sample_id
                            best_match["substrate"] = current_substrate
                sample_id = best_match.get("id")
                substrate = best_match.get("substrate")
        else:
            if isinstance(sample_id, list):
                sample_id = None
            elif sample_id is not None:
                substrate = Substrate(connection.open("substrates_by_sample/{0}".format(sample_id)))
                assert substrate.timestamp, Exception("sample ID {0} had no substrate".format(sample_id))
    else:
        sample_id = None
    if sample_id is None:
        if create:
            new_sample = Sample()
            new_sample.name = name_info["name"]
            new_sample.current_location = name_info["current_location"]
            new_sample.currently_responsible_person = name_info["currently_responsible_person"]
            new_sample.topic = name_info["topic"]
            new_sample.legacy = name_info["legacy"]
            new_sample.timestamp = timestamp
            sample_id = new_sample.submit()
            assert sample_id, Exception("Could not create sample {0}".format(name_info["name"]))
            substrate = Substrate()
            substrate.timestamp = timestamp - datetime.timedelta(seconds=2)
            substrate.timestamp_inaccuracy = timestamp_inaccuracy
            substrate.material = substrate_material
            substrate.comments = substrate_comments
            substrate.operator = name_info["substrate_operator"]
            substrate.sample_ids = [sample_id]
            if name_info["substrate_external_operator"]:
                substrate.external_operator = name_info["substrate_external_operator"]
            substrate_id = substrate.submit()
            assert substrate_id, Exception("Could not create substrate for {0}".format(name_info["name"]))
    else:
        connection.open("change_my_samples", {"add": sample_id})
        substrate_changed = False
        if substrate.timestamp > timestamp:
            substrate.timestamp = timestamp - datetime.timedelta(seconds=2)
            substrate.timestamp_inaccuracy = timestamp_inaccuracy
            substrate_changed = True
        if substrate.material == "custom" and substrate.comments == unknown_substrate_comment:
            substrate.material = substrate_material
            substrate.comments = substrate_comments
            substrate_changed = True
        else:
            if substrate.material != substrate_material:
                additional_substrate_comments = substrate_comments if substrate_material == "custom" else substrate_material
            elif substrate_material == "custom":
                additional_substrate_comments = substrate_comments
            else:
                additional_substrate_comments = None
            if additional_substrate_comments:
                if substrate.comments:
                    substrate.comments += "\n\n"
                substrate_comments += "Alternative information: " + additional_substrate_comments
                substrate_changed = True
        if substrate_changed:
            substrate.submit()
    return sample_id


def raman_by_filepath(filepath):
    """Returns a Raman measurement that corresponds to a filepath.  Since
    filepaths are unique and easy to handle, it makes sense to use them as an
    alternative primary key (in contrast to apparatus and number).

    :Parameters:
      - `filepath`: the filepath below “T:/Daten/“

    :type filepath: str

    :Return:
      the Raman measurement instance that corresponds to the filepath

    :rtype: RamanMeasurement
    """
    apparatus, number = connection.open("raman_measurements/by_filepath/{0}".format(urllib.parse.quote(filepath)))
    return RamanMeasurement(apparatus, number)


class RamanMeasurement(object):
    """Class representing Raman measurements.
    """

    def __init__(self, apparatus, number=None):
        self.apparatus = apparatus
        if number:
            data = connection.open("raman_measurements/{0}/{1}".format(self.apparatus, number))
            self.sample_id = data["samples"][0]
            self.number = data["number"]
            self.kind = data["kind"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.datafile = data["datafile"]
            self.evaluated_datafile = data["evaluated_datafile"]
            self.central_wavelength = data["central_wavelength"]
            self.excitation_wavelength = data["excitation_wavelength"]
            self.slit = data["slit"]
            self.accumulation = data["accumulation"]
            self.time = data["time"]
            self.laser_power = data["laser_power"]
            self.filters = data["filters"]
            self.icrs = data["icrs"]
            self.grating = data["grating"]
            self.objective = data["objective"]
            self.position_a_si = data["position_a_si"]
            self.position_muc_si = data["position_muc_si"]
            self.width_a_si = data["width_a_si"]
            self.width_muc_si = data["width_muc_si"]
            self.setup = data["setup"]
            self.detector = data["detector"]
            self.through_substrate = data["through_substrate"]
            self.dektak_measurement = data["dektak_measurement"]
            self.sampling_distance_x = data["sampling_distance_x"]
            self.sampling_distance_y = data["sampling_distance_y"]
            self.number_points_x = data["number_points_x"]
            self.number_points_y = data["number_points_y"]
            self.sampling_period = data["sampling_period"]
            self.existing = True
        else:
            self.sample_id = self.number = self.operator = self.timestamp = self.comments = self.dektak_measurement = None
            self.kind = "single"
            self.timestamp_inaccuracy = 0
            self.slit = self.central_wavelength = self.accumulation = self.time = self.laser_power = self.filters = \
                self.excitation_wavelength = self.icrs = self.datafile = self.evaluated_datafile = self.grating = \
                self.objective = None
            self.position_a_si = self.position_muc_si = self.width_a_si = self.width_muc_si = self.through_substrate = \
                self.setup = self.detector = None
            self.sampling_distance_x = self.sampling_distance_y = self.number_points_x = self.number_points_y = \
                self.sampling_period = None
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"number": self.number,
                "sample": self.sample_id,
                "kind": self.kind,
                "dektak_measurement": self.dektak_measurement,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "datafile": self.datafile,
                "evaluated_datafile": self.evaluated_datafile,
                "slit": self.slit,
                "central_wavelength": self.central_wavelength,
                "accumulation": self.accumulation,
                "time": self.time,
                "laser_power": self.laser_power,
                "filters": self.filters,
                "excitation_wavelength": self.excitation_wavelength,
                "icrs": self.icrs,
                "grating": self.grating,
                "objective": self.objective,
                "position_a_si": self.position_a_si,
                "position_muc_si": self.position_muc_si,
                "width_a_si": self.width_a_si,
                "width_muc_si": self.width_muc_si,
                "through_substrate": self.through_substrate,
                "setup": self.setup,
                "detector": self.detector,
                "comments": self.comments,
                "sampling distance x": self.sampling_distance_x,
                "sampling distance y": self.sampling_distance_y,
                "number of points x": self.number_points_x,
                "number of points y": self.number_points_y,
                "sampling period": self.sampling_period,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("raman_measurements/{0}/{1}/edit/".format(self.apparatus, self.number), data)
            else:
                return connection.open("raman_measurements/{0}/add/".format(self.apparatus), data)


class SolarsimulatorPhotoMeasurement(object):

    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("solarsimulator_measurements/photo/{0}".format(process_id))
            self.process_id = process_id
            self.irradiance = data["irradiance"]
            self.temperature = data["temperature"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.cells = {}
            for key, value in data.items():
                if key.startswith("cell position "):
                    cell = PhotoCellMeasurement(value)
                    self.cells[cell.position] = cell
            self.existing = True
        else:
            self.process_id = self.irradiance = self.temperature = self.sample_id = self.operator = self.timestamp = \
                self.timestamp_inaccuracy = self.comments = None
            self.cells = {}
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "irradiance": self.irradiance,
                "temperature": self.temperature,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, cell in enumerate(self.cells.values()):
            data.update(cell.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                query_string = "?only_single_cell_added=true" if only_single_cell_added else ""
                connection.open("solarsimulator_measurements/photo/{0}/edit/".format(self.process_id) + query_string, data)
            else:
                return connection.open("solarsimulator_measurements/photo/add/", data)

class SolarsimulatorDarkMeasurement(object):

    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("solarsimulator_measurements/dark/{0}".format(process_id))
            self.process_id = process_id
            self.irradiance = data["irradiance"]
            self.temperature = data["temperature"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.cells = {}
            for key, value in data.items():
                if key.startswith("cell position "):
                    cell = DarkCellMeasurement(value)
                    self.cells[cell.position] = cell
            self.existing = True
        else:
            self.process_id = self.irradiance = self.temperature = self.sample_id = self.operator = self.timestamp = \
                self.timestamp_inaccuracy = self.comments = None
            self.cells = {}
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "irradiance": self.irradiance,
                "temperature": self.temperature,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, cell in enumerate(self.cells.values()):
            data.update(cell.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                query_string = "?only_single_cell_added=true" if only_single_cell_added else ""
                connection.open("solarsimulator_measurements/dark/{0}/edit/".format(self.process_id) + query_string, data)
            else:
                return connection.open("solarsimulator_measurements/dark/add/", data)


class PhotoCellMeasurement(object):

    def __init__(self, data={}):
        if data:
            self.position = data["position"]
            self.cell_index = data["cell_index"]
            self.area = data["area"]
            self.eta = data["eta"]
            self.p_max = data["p_max"]
            self.ff = data["ff"]
            self.voc = data["voc"]
            self.isc = data["isc"]
            self.rs = data["rs"]
            self.rsh = data["rsh"]
            self.corr_fact = data["corr_fact"]
            self.data_file = data["data_file"]
        else:
            self.position = self.cell_index = self.area = self.eta = self.p_max = self.ff = self.voc = self.isc = \
                self.rs = self.rsh = self.corr_fact = self.data_file = None

    def get_data(self, index):
        prefix = six.text_type(index) + "-"
        return {prefix + "position": self.position,
                prefix + "cell_index": self.cell_index,
                prefix + "area": self.area,
                prefix + "eta": self.eta,
                prefix + "p_max": self.p_max,
                prefix + "ff": self.ff,
                prefix + "voc": self.voc,
                prefix + "isc": self.isc,
                prefix + "rs": self.rs,
                prefix + "rsh": self.rsh,
                prefix + "corr_fact": self.corr_fact,
                prefix + "data_file": self.data_file}

    def __eq__(self, other):
        return self.cell_index == other.cell_index and self.data_file == other.data_file


class DarkCellMeasurement(object):

    def __init__(self, data={}):
        if data:
            self.position = data["position"]
            self.cell_index = data["cell_index"]
            self.n_diode = data["n_diode"]
            self.i_0 = data["i_0"]
            self.data_file = data["data_file"]
        else:
            self.position = self.cell_index = self.n_diode = self.i_0 = self.data_file = None

    def get_data(self, index):
        prefix = six.text_type(index) + "-"
        return {prefix + "position": self.position,
                prefix + "cell_index": self.cell_index,
                prefix + "n_diode": self.n_diode,
                prefix + "i_0": self.i_0,
                prefix + "data_file": self.data_file}

    def __eq__(self, other):
        return self.cell_index == other.cell_index and self.data_file == other.data_file


class Structuring(object):
    def __init__(self):
        self.sample_id = None
        self.process_id = None
        self.operator = None
        self.timestamp = None
        self.timestamp_inaccuracy = None
        self.comments = None
        self.layout = None
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "process_id": self.process_id,
                "layout": self.layout,
                "comments": self.comments,
                "remove_from_my_samples": True,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.process_id:
                connection.open("structuring_process/{0}/edit/".format(self.process_id), data)
            else:
                return connection.open("structuring_process/add/", data)


class FiveChamberDeposition(object):
    """Class that represents 5-chamber depositions.
    """

    def __init__(self, number=None):
        """Class constructor.

        :Parameters:
          - `number`: if given, the instance represents an existing deposition
            of the database.  Note that this triggers an exception if the
            deposition number is not found in the database.

        :type number: unicode
        """
        if number:
            data = connection.open("5-chamber_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                FiveChamberLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.operator = self.timestamp = None
            self.comments = ""
            self.timestamp_inaccuracy = 0
            self.layers = []
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the depositon to the database.

        :Return:
          the deposition number if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/S")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": True,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("5-chamber_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("5-chamber_depositions/add/", data)
                logging.info("Successfully added 5-chamber deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/FiveChamberDeposition"))


class FiveChamberLayer(object):
    """Class representing a single 5-chamber layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.pressure = data["pressure"]
            self.base_pressure = data["base_pressure"]
            self.time = data["time"]
            self.electrode_distance = data["electrode_distance"]
            self.temperature_1 = data["temperature_1"]
            self.temperature_2 = data["temperature_2"]
            self.hf_frequency = data["hf_frequency"]
            self.power = data["power"]
            self.layer_type = data["layer_type"]
            self.sih4 = data["sih4"]
            self.h2 = data["h2"]
            self.tmb = data["tmb"]
            self.ch4 = data["ch4"]
            self.co2 = data["co2"]
            self.ph3 = data["ph3"]
            self.date = data["date"]
            self.dc_bias = data["dc_bias"]
            self.impurity = data["impurity"]
            self.in_situ_measurement = data["in_situ_measurement"]
            self.data_file = data["data_file"]
        else:
            self.chamber = self.pressure = self.time = self.electrode_distance = \
                self.temperature_1 = self.temperature_2 = self.hf_frequency = self.power = \
                self.layer_type = self.sih4 = self.h2 = self.tmb = self.ch4 = self.co2 = \
                self.ph3 = self.silane_concentration = self.date = self.dc_bias = \
                self.impurity = self.in_situ_measurement = self.data_file = self.base_pressure = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "chamber": self.chamber,
                prefix + "pressure": self.pressure,
                prefix + "base_pressure": self.base_pressure,
                prefix + "time": self.time,
                prefix + "electrodes_distance": self.electrode_distance,
                prefix + "temperature_1": self.temperature_1,
                prefix + "temperature_2": self.temperature_2,
                prefix + "date": self.date,
                prefix + "layer_type": self.layer_type,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2,
                prefix + "tmb": self.tmb,
                prefix + "ch4": self.ch4,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "power": self.power,
                prefix + "hf_frequency": self.hf_frequency,
                prefix + "dc_bias": self.dc_bias,
                prefix + "impurity": self.impurity,
                prefix + "in_situ_measurement": self.in_situ_measurement,
                prefix + "data_file": self.data_file}
        return data


class LADADeposition(object):

    def __init__(self, number=None):
        """Class constructor.

        :Parameters:
          - `number`: if given, the instance represents an existing deposition
            of the database.  Note that this triggers an exception if the
            deposition number is not found in the database.

        :type number: unicode
        """
        if number:
            data = connection.open("lada_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.customer = data["customer"]
            self.timestamp = data["timestamp"]
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.substrate_size = data["substrate_size"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                LADALayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.operator = self.timestamp = self.substrate_size = self.customer = None
            self.comments = ""
            self.timestamp_inaccuracy = 0
            self.layers = []
            self.existing = False
            self.number = None
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the depositon to the database.

        :Return:
          the deposition number if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        if not self.customer:
            self.customer = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/S")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "customer": primary_keys["users"][self.customer],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "substrate_size": self.substrate_size,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("lada_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("lada_depositions/add/", data)
                logging.info("Successfully added lada deposition {0}.".format(self.number))
        return result


class LADALayer(object):

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.layer_number = data["number"]
            self.date = data["date"]
            self.carrier = data["carrier"]
            self.layer_type = data["layer_type"]
            self.chamber = data["chamber"]
            self.sih4_1 = data["sih4_1"]
            self.sih4_1_end = data["sih4_1_end"]
            self.sih4_2 = data["sih4_2"]
            self.sih4_2_end = data["sih4_2_end"]
            self.h2_1 = data["h2_1"]
            self.h2_1_end = data["h2_1_end"]
            self.h2_2 = data["h2_2"]
            self.h2_2_end = data["h2_2_end"]
            self.ph3_1 = data["ph3_1"]
            self.ph3_1_end = data["ph3_1_end"]
            self.ph3_2 = data["ph3_2"]
            self.ph3_2_end = data["ph3_2_end"]
            self.sih4_mfc_number_1 = data["sih4_mfc_number_1"]
            self.sih4_mfc_number_2 = data["sih4_mfc_number_2"]
            self.h2_mfc_number_1 = data["h2_mfc_number_1"]
            self.h2_mfc_number_2 = data["h2_mfc_number_2"]
            self.tmb_1 = data["tmb_1"]
            self.tmb_2 = data["tmb_2"]
            self.ch4 = data["ch4"]
            self.co2 = data["co2"]
            self.power_1 = data["power_1"]
            self.power_2 = data["power_2"]
            self.power_reflected = data["power_reflected"]
            self.pressure = data["pressure"]
            self.base_pressure = data["base_pressure"]
            self.hf_frequency = data["hf_frequency"]
            self.time_1 = data["time_1"]
            self.time_2 = data["time_2"]
            self.electrodes_distance = data["electrodes_distance"]
            self.temperature_substrate = data["temperature_substrate"]
            self.temperature_heater = data["temperature_heater"]
            self.temperature_heater_depo = data["temperature_heater_depo"]
            self.cl_1 = data["cl_1"]
            self.cl_2 = data["cl_2"]
            self.ct_1 = data["ct_1"]
            self.ct_2 = data["ct_2"]
            self.u_dc_1 = data["u_dc_1"]
            self.u_dc_2 = data["u_dc_2"]
            self.additional_gas = data["additional_gas"]
            self.additional_gas_flow = data["additional_gas_flow"]
            self.comments = data["comments"]
            self.plasma_stop = data["plasma_stop"]
            self.v_lq = data["v_lq"]
            self.pendulum_lq = data["pendulum_lq"]
        else:
            self.layer_number = self.date = self.carrier = self.layer_type = self.chamber = \
                self.sih4_1 = self.sih4_1_end = self.sih4_2 = self.sih4_2_end = \
                self.h2_1 = self.h2_1_end = self.h2_2 = self.h2_2_end = self.ph3_1 = \
                self.ph3_1_end = self.ph3_2 = self.ph3_2_end = self.tmb_1 = self.tmb_2 = \
                self.sih4_mfc_number_1 = self.sih4_mfc_number_2 = self.h2_mfc_number_1 = \
                self.h2_mfc_number_2 = self.ch4 = self.co2 = self.power_1 = self.power_2 = \
                self.power_reflected = self.pressure = self.base_pressure = \
                self.hf_frequency = self.time_1 = self.time_2 = self.electrodes_distance = \
                self.temperature_substrate = self.temperature_heater = \
                self.temperature_heater_depo = self.cl_1 = self.cl_2 = self.ct_1 = \
                self.ct_2 = self.u_dc_1 = self.u_dc_2 = self.additional_gas = self.additional_gas_flow = \
                self.plasma_stop = self.v_lq = self.pendulum_lq = None
            self.comments = ""

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": self.layer_number,
                prefix + "date": self.date,
                prefix + "carrier": self.carrier,
                prefix + "layer_type": self.layer_type,
                prefix + "chamber": self.chamber,
                prefix + "sih4_1": self.sih4_1,
                prefix + "sih4_1_end": self.sih4_1_end,
                prefix + "sih4_2": self.sih4_2,
                prefix + "sih4_2_end": self.sih4_2_end,
                prefix + "h2_1": self.h2_1,
                prefix + "h2_1_end": self.h2_1_end,
                prefix + "h2_2": self.h2_2,
                prefix + "h2_2_end": self.h2_2_end,
                prefix + "ph3_1": self.ph3_1,
                prefix + "ph3_1_end": self.ph3_1_end,
                prefix + "ph3_2": self.ph3_2,
                prefix + "ph3_2_end": self.ph3_2_end,
                prefix + "tmb_1": self.tmb_1,
                prefix + "tmb_2": self.tmb_2,
                prefix + "sih4_mfc_number_1": self.sih4_mfc_number_1,
                prefix + "sih4_mfc_number_2": self.sih4_mfc_number_2,
                prefix + "h2_mfc_number_1": self.h2_mfc_number_1,
                prefix + "h2_mfc_number_2": self.h2_mfc_number_2,
                prefix + "ch4": self.ch4,
                prefix + "co2": self.co2,
                prefix + "power_1": self.power_1,
                prefix + "power_2": self.power_2,
                prefix + "power_reflected": self.power_reflected,
                prefix + "pressure": self.pressure,
                prefix + "base_pressure": self.base_pressure,
                prefix + "hf_frequency": self.hf_frequency,
                prefix + "time_1": self.time_1,
                prefix + "time_2": self.time_2,
                prefix + "electrodes_distance": self.electrodes_distance,
                prefix + "temperature_substrate": self.temperature_substrate,
                prefix + "temperature_heater": self.temperature_heater,
                prefix + "temperature_heater_depo": self.temperature_heater_depo,
                prefix + "cl_1": self.cl_1,
                prefix + "cl_2": self.cl_2,
                prefix + "ct_1": self.ct_1,
                prefix + "ct_2": self.ct_2,
                prefix + "u_dc_1": self.u_dc_1,
                prefix + "u_dc_2": self.u_dc_2,
                prefix + "additional_gas": self.additional_gas,
                prefix + "additional_gas_flow": self.additional_gas_flow,
                prefix + "comments": self.comments,
                prefix + "plasma_stop": self.plasma_stop,
                prefix + "v_lq": self.v_lq,
                prefix + "pendulum_lq": self.pendulum_lq}
        return data


class DSRMeasurement(object):

    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("dsr_measurements/{0}".format(process_id))
            self.process_id = process_id
            self.cell_position = data["cell_position"]
            self.irradiance = data["irradiance"]
            self.lens = data["lens"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.bias = data["bias"]
            self.parameter_file = data["parameter_file"]
            self.spectral_data = set()
            self.iv_data = set()
            for key, value in data.items():
                if key.startswith("spectral data"):
                    self.spectral_data.add(DSRSpectralData(value))
                elif key.startswith("iv data"):
                    self.iv_data.add(DSRIVData(value))
            self.existing = True
        else:
            self.process_id = self.irradiance = self.lens = self.sample_id = self.operator = self.timestamp = \
                self.timestamp_inaccuracy = self.comments = self.bias = self.parameter_file = self.cell_position = None
            self.spectral_data = set()
            self.iv_data = set()
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy or 1,
                "operator": primary_keys["users"][self.operator],
                "cell_position": self.cell_position,
                "irradiance": self.irradiance,
                "lens": self.lens,
                "bias": self.bias,
                "parameter_file": self.parameter_file,
                "comments": self.comments,
                "remove_from_my_samples": True,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, spectral_data in enumerate(self.spectral_data):
            data.update(spectral_data.get_data(index))
        for index, iv_data in enumerate(self.iv_data):
            data.update(iv_data.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                query_string = "?only_single_cell_added=true" if only_single_cell_added else ""
                connection.open("dsr_measurements/{0}/edit/".format(self.process_id) + query_string, data)
            else:
                return connection.open("dsr_measurements/add/", data)


class DSRSpectralData(object):
    def __init__(self, data={}):
        if data:
            self.spectral_data_file = data["spectral_data_file"]
        else:
            self.spectral_data_file = None

    def get_data(self, prefix):
        prefix = six.text_type(prefix) + "-"
        return {prefix + "spectral_data_file": self.spectral_data_file}

    def __eq__(self, other):
        return self.spectral_data_file == other.spectral_data_file

    def __hash__(self):
        return hash(self.spectral_data_file)


class DSRIVData(object):
    def __init__(self, data={}):
        if data:
            self.iv_data_file = data["iv_data_file"]
        else:
            self.iv_data_file = None

    def get_data(self, prefix):
        prefix = six.text_type(prefix) + "-"
        return {prefix + "iv_data_file": self.iv_data_file}

    def __eq__(self, other):
        return self.iv_data_file == other.iv_data_file

    def __hash__(self):
        return hash(self.iv_data_file)


class SmallSputterDeposition(object):
    def __init__(self, number=None):
        if number:
            data = connection.open("small_sputter_depositions/{0}".format(number))
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = data["timestamp"]
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.customer = data["customer"]
            self.target = data["target"]
            self.cathode = data["cathode"]
            self.holder = data["holder"]
            self.carrier = data["carrier"]
            self.base_pressure = data["base_pressure"]
            self.type = data["type"]
            self.bias = data["bias"]
            self.ar = data["ar"]
            self.o2_1percent = data["o2_1percent"]
            self.o2 = data["o2"]
            self.gas_label = data["gas_label"]
            self.gas_flow = data["gas_flow"]
            self.total_pressure = data["total_pressure"]
            self.throttle_setting = data["throttle_setting"]
            self.temperature = data["temperature"]
            self.time_pre_heat = data["time_pre_heat"]
            self.power = data["power"]
            self.ref_power = data["ref_power"]
            self.time = data["time"]
            self.pre_time = data["pre_time"]
            self.existing = True
        else:
            self.operator = self.timestamp = self.customer = self.target = \
                self.cathode = self.holder = self.carrier = self.base_pressure = \
                self.type = self.bias = self.ar = self.o2_1percent = self.o2 = \
                self.gas_label = self.gas_flow = self.total_pressure = \
                self.throttle_setting = self.temperature = self.time_pre_heat = \
                self.power = self.ref_power = self.time = self.pre_time = None
            self.timestamp_inaccuracy = 0
            self.sample_ids = []
            self.comments = ""
            self.existing = False
        self.number = number
        self.finished = True
        self.edit_description = None
        self.edit_important = True


    def submit(self):
        """Submit the depositon to the database.

        :Return:
          the deposition number if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        if not self.customer:
            self.customer = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/K")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "customer": primary_keys["users"][self.customer],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important,
                "target":self.target,
                "cathode":self.cathode,
                "holder":self.holder,
                "carrier":self.carrier,
                "base_pressure":self.base_pressure,
                "type":self.type,
                "bias":self.bias,
                "ar":self.ar,
                "o2_1percent":self.o2_1percent,
                "o2":self.o2,
                "gas_label":self.gas_label,
                "gas_flow":self.gas_flow,
                "total_pressure":self.total_pressure,
                "throttle_setting":self.throttle_setting ,
                "temperature":self.temperature,
                "time_pre_heat":self.time_pre_heat,
                "power":self.power,
                "ref_power":self.ref_power,
                "time":self.time,
                "pre_time":self.pre_time}

        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("small_sputter_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("small_sputter_depositions/add/", data)
                logging.info("Successfully added small sputter deposition {0}.".format(self.number))
        return result


class TRMeasurement(object):
    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("tr_measurements/{0}".format(process_id))
            self.process_id = process_id
            self.type = data["measurement type"]
            self.lighting_direction = data["lighting_direction"]
            self.lens = data["lens"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.cells = {}
            for key, value in data.items():
                if key.startswith("cell position "):
                    cell = TRCellMeasurement(value)
                    self.cells[cell.cell_position] = cell
            self.existing = True
        else:
            self.type = self.lighting_direction = self.lens = self.sample_id = self.operator = \
                self.timestamp = self.timestamp_inaccuracy = self.comments = None
            self.cells = {}
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "type": self.type,
                "lighting_direction": self.lighting_direction,
                "lens": self.lens,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, cell in enumerate(self.cells.values()):
            data.update(cell.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("tr_measurements/{0}/edit/".format(self.process_id), data)
            else:
                return connection.open("tr_measurements/add/", data)


class TRCellMeasurement(object):
    def __init__(self, data={}):
        if data:
            self.cell_position = data["cell_position"]
            self.data_file = data["data_file"]
        else:
            self.cell_position = self.data_file = None

    def get_data(self, prefix):
        prefix = six.text_type(prefix) + "-"
        return {prefix + "cell_position": self.cell_position,
                prefix + "data_file": self.data_file}

    def __eq__(self, other):
        return self.data_file == other.data_file


class TRLayerMeasurement(object):
    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("tr_layer_measurements/{0}".format(process_id))
            self.process_id = process_id
            self.type = data["type"]
            self.lighting_direction = data["lighting_direction"]
            self.lens = data["lens"]
            self.data_file = data["data_file"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.existing = True
        else:
            self.type = self.lighting_direction = self.lens = self.sample_id = self.operator = \
                self.timestamp = self.timestamp_inaccuracy = self.comments = self.data_file = None
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "type": self.type,
                "lighting_direction": self.lighting_direction,
                "lens": self.lens,
                "data_file": self.data_file,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("tr_layer_measurements/{0}/edit/".format(self.process_id), data)
            else:
                return connection.open("tr_layer_measurements/add/", data)


class ChemicalSubstances(object):
    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("processes/{0}".format(process_id))
            self.process_id = process_id
            self.manufacturer = data["manufacturer"]
            self.date = data["date"]
            self.type = data["type"]
            self.quantity = data["quantity"]
            self.unit = data["unit"]
            self.material_state = data["material_state"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.existing = True
        else:
            self.manufacturer = self.date = self.type = self.quantity = \
                self.material_state = self.sample_id = self.unit = self.operator = self.timestamp = \
                self.timestamp_inaccuracy = self.comments = self.data_file = None
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self):
        data = {"manufacturer": self.manufacturer,
                "type": self.type,
                "quantity": self.quantity,
                "unit": self.unit,
                "material_state": self.material_state,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample": self.sample_id,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("chemical_substances/{0}/edit/".format(self.process_id), data)
            else:
                result = connection.open("chemical_substances/add/", data)
        return result



class MokeMeasurement(object):
    """Class representing moke measurements.
    """

    def __init__(self, id_=None):
        """Class constructor.  See `SixChamberDeposition.__init__` for further
        details.  Only the attributes are different.
        """
        if id_:
            self.id = id_
            data = connection.open("moke_measurements/{0}".format(id_))
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.datafile = data["datafile"]
            self.loops = data["loops"]
            self.time_per_point = data["time_per_point"]
            self.temperature = data["temperature/K"]
            self.orientation = data["orientation"]
            self.time_per_measurement = data["time_per_measurement"]
            self.free_value = data["free_value"]
            self.existing = True
        else:
            self.sample_id = self.operator = self.timestamp = self.comments = self.datafile = \
                self.loops = self.time_per_point = self.orientation = self.time_per_measurement = \
                self.free_value = self.id = None
            self.timestamp_inaccuracy = 0
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "datafile": self.datafile,
                "loops": self.loops,
                "time_per_point": self.time_per_point,
                "temperature": self.temperature,
                "orientation": self.orientation,
                "time_per_measurement": self.time_per_measurement,
                "free_value": self.free_value,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("moke_measurements/{0}/edit/".format(self.id), data)
            else:
                return connection.open("moke_measurements/add/", data)


class MBEProcess(object):
    def __init__(self, id_=None):
        if id_:
            self.id = id_
            data = connection.open("mbe/{0}".format(id_))
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.notebook_page = data["lab_notebook_page"]
            self.layer = data["layer"]
            self.existing = True
        else:
            self.sample_id = self.operator = self.timestamp = self.id = \
                self.comments = self.notebookpage = self.layer = None
            self.timestamp_inaccuracy = 0
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "layer": self.layer,
                "notebook_page": self.notebook_page,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("mbe/{0}/edit/".format(self.id), data)
            else:
                return connection.open("mbe/add/", data)
