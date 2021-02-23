import os, logging
from datetime import datetime

#Logging.basicConfig must be done before importing juliabase modules because their settings can't be overwritten
log_path = os.path.join(str(""), str("jopes.log"))
logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")

#Juliabase imports
from jb_remote_iek5 import *
from jb_remote import *
#The vamas file
from vamasSimple import VAMAS_File

#Login to JuliaBase with user, pwd from .bash_profile vars
login(os.environ["CRAWLERS_LOGIN"], os.environ["CRAWLERS_PASSWORD"])

def safe_cast_to_number(value, integer = False):
    cast = int if integer else float
    try:
        return cast(value)
    except ValueError as e:
        splits = value.split(" ")
        try:
            return cast(splits[0])
        except ValueError as ee:
            if value not in ["not findable"]:
                logging.warning("\"" + value + "\" may be wrong")
            return 0 if integer else 0.0

class JOPES_Investigation:

    def import_investigation(self, vms:VAMAS_File):
        """import data for Chantal JOPES Investigation from VAMAS_File into dict

        ### Arguments:
            vms {VAMAS_File} -- VAMAS File dataclass

        ### Returns:
            {int} -- Investigation id
        """

        self.sample = None #Chantal sample object

        try:
            self.sample = Sample(vms.sampleName)
        except JuliaBaseError:
            logging.error("Sample %s was not found in the database", vms.sampleName)
            return 0

        if vms.operatorName not in primary_keys["users"]:
            logging.warning("Operator %s not found in the database", vms.operatorName)
            self.chantalUser = "chantal" # default operator to chantal
        else:
            self.chantalUser = vms.operatorName

        self.data = {
            "operator": primary_keys["users"][self.chantalUser],
            "timestamp": vms.date, #format_timestamp(datetime.strptime(raw_data["Timestamp"], "%Y %m %d %H %M %S")),
            "timestamp_inaccuracy": 2,
            "sample": self.sample.id,
            "finished": True,
            "remove_from_my_samples": False,
            "jopes_type": vms.technique,
            "spec_state": "not found",
            "experiment_version": "not found",
            "result_file_path": vms.fileName,
            "file_creator": vms.commentCreatedWith,
            "load_status": "not found",
            "p_ig": safe_cast_to_number(vms.commentpIG),
            "p_his": safe_cast_to_number(vms.commentpHIS),
            "bias": safe_cast_to_number(vms.sampleBias),
        }

        if vms.technique != "UPS":
            self.data["i_fil"] = safe_cast_to_number(vms.xrayFilCurr)
            self.data["xray_power"] = safe_cast_to_number(vms.xrayPower)
            self.data["xray_voltage"] = safe_cast_to_number(vms.xrayVoltage)
            self.data["excitation_source_label"] = vms.analysisSourceLabel
        else:
            #UPS
            self.data["u_hv"] = safe_cast_to_number(vms.commentVHIS)
            self.data["u_start"] = safe_cast_to_number(vms.commentVHISstart)
            self.data["dis_power"] = safe_cast_to_number(vms.commentWHIS)

        try:
            #Talk to chantal...
            self.inv_id = connection.open("jopesinvestigation/add/", self.data)
            logging.info("Added the investigation to Chantal, id: %i", self.inv_id)
            return self.inv_id
        except Exception as e:
            logging.error("Could not write the investigation to Chantal: " + str(e))
        return 0            


class JOPES_Measurement:

    def import_measurement(self, vms:VAMAS_File, inv_id:int, meas_number = 1):
        """Import JOPES measurement into Chantal and append to JOPES Investigation with given id

        ### Arguments:
            vms {VAMAS_File} -- the VAMAS file dataclass 
            inv_id {int} -- Investigation ID

        ### Keyword Arguments:
            meas_number {int} -- Measurement number (default: {1})

        ### Returns:
            {int} -- Measurement ID
        """


        self.data = {
            "investigation": inv_id,
            "timestamp": vms.date,
            "dimensions": 2,
            "number": meas_number,
            "aperture": safe_cast_to_number(vms.analyserAperture, True),
            "transition": vms.blockName,
            "magnification": safe_cast_to_number(vms.analyzerMagnification, True),
            "exit_slit": safe_cast_to_number(vms.analyserExitSlit, True),
            "src_analyser_angle": safe_cast_to_number(vms.commentSourceAnalyzerAngle),
            "cae_crr_val": safe_cast_to_number(vms.analyzerPEorRR),
            "points": vms.numYAxisValues/vms.numYAxisVars,
            "excitation_energy": safe_cast_to_number(vms.analysisSourceEnergy),
            "sample_position_x": safe_cast_to_number(vms.sampleStageX),
            "sample_position_y": safe_cast_to_number(vms.sampleStageY),
            "sample_position_z": safe_cast_to_number(vms.sampleStageZ),
            "sample_normal_phi": safe_cast_to_number(vms.sampleStagePhi),
            "sample_normal_theta": safe_cast_to_number(vms.sampleStageTheta),
            "run_cycle": safe_cast_to_number(1, True),      #TODO

            "comments": vms.comment,
            "file_path": vms.fileName,

            "start_energy": vms.xAxisStart,
            "step_energy": vms.xAxisIncrement,
            "end_energy": vms.xAxisEnd,
            "dwell_time": vms.dwellTime,
            "meas_time": int(vms.dwellTime*abs(vms.xAxisStart - vms.xAxisEnd)/vms.xAxisIncrement + .5),         
        }

        data_default = {
            "bricklet_number": 0,
            "scan_cycle": 0,
            "rating": 0,
            "normal_checksum": 0,
            "dispersion_checksum": 0,
            "usage_checksum": 0,
            "normal_string": "",
            "dispersion_string": "",
            "usage_string": "",
            "deflector_height": 0,
            "deflector_width": 0,
            "e_beam_x": 0,
            "e_beam_y": 0,
            "lines": 0,
            "mcp_v1": 0,
            "mcp_v2": 0,
            "cae_crr_mode": 0,
        }

        self.data.update(data_default)


        try:
            self.meas_id = connection.open("jopesregion/add/", self.data)

            logging.info("Added measurement %d to Chantal, id: %d", meas_number, self.meas_id)
            return self.meas_id
        except Exception as e:
            logging.error("Could not write measurement %d to Chantal: %s", meas_number, str(e))
            return 0