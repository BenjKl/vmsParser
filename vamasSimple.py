
from dataclasses import dataclass, fields, field, asdict, replace
from datetime import datetime
import re


#DataClass to store the experiment data contained in a VAMAS file
@dataclass
class VAMAS_File:
    """ DataClass to store the experiment data contained in a VAMAS file
        Format describeb in 
        Dench, W. A., L. B. Hazell, M. P. Seah, und the VAMAS Community. 
        „VAMAS Surface Chemical Analysis Standard Data Transfer Format with Skeleton Decoding Programs“. 
        Surface and Interface Analysis 13, Nr. 2–3 (November 1988): 63–122. 
        https://doi.org/10.1002/sia.740130202
    """
    fileName:str= ""

    #vms Identifier strings
    formatName:str = "VAMAS Surface Chemical Analysis Standard Data Transfer Format 1988"
    institutionName:str = "Not Specified"
    instrumentModelName:str = "Not Specified"
    operatorName:str = "Not Specified"
    experimentName:str = "Not Specified"
    numCommentLines:str = 0 #number of lines in comment
    comment:str = "Not Specified"

    #Optional parameters parsed from comment:
    commentCreatedWith:str=""
    commentAcquisition:str=""
    commentSourceAnalyzerAngle:float=0
    commentpIG:float=0 #Chamber pressure
    commentpPir:float=0 #Chamber rough pressure (Pirani)
    
    commentpHIS:float=0 #HIS UPS source pressure
    commentVHIS:float=0 #HIS UPS source voltage
    commentVHISstart:float=0 #HIS UPS source start voltage
    commentWHIS:float=0 #HIS UPS source power

    commentSampleBias:float=0 #Sample Bias

    commentUPSFilterNr:int=0 #UPS filter No.
    commentUPSFilterAngle:float=0 #UPS filter wheel angle



    expMode:str = "NORM"
    # Experiment mode: 'MAP' | 'MAPDP' | 'MAPSV' | 'MAPSVDP' | 'NORM' | 'SDP' | 'SDPSV' | 'SEM'
    # Always 'NORM' for Omicron
    # Either independent data or data which refers to a specified set of single values of
    # one or more experimental variables; the data may be spectral or non-spectral.

    scanMode:str = "REGULAR"
    # ScanMode: 'REGULAR' | 'IRREGULAR' | 'MAPPING'
    # Always 'REGULAR' for Omicron

    # Always 0 for Omicron
    numSpectralRegions: int = 0

    # only present if experiement_mode is 'MAP', or 'MAPDP'
    numAnalysisPositions: int = 0
    numDiscreteXCoordFullMap: int = 0
    numDiscreteYCoordFullMap: int = 0

    numExpVariables: int = 0 #number of experimental variables

    # specified by the value of numExpVariables
    expVariableLabels : list = field(default_factory=list)
    expVariableUnits : list = field(default_factory=list)
    
    #number of entries in parameter inclusion or exclusion list
    lenParamExclusionInclusionList: int = 0 

    #parameter_inclusion_or_exclusion_prefix_numbers
    paramExclusionInclusionPrefix : list = field(default_factory=list) 

    #number of manually entered items in block
    numManuallyBlockItems: int = 0

    #prefix number of manually entered item
    numManuallyBlockItemsPrefix : list = field(default_factory=list)

    # Always 0 for Omicron
    #number of future upgrade experiment entries
    numFutureExpEntries: int = 0
    #number of future upgrade block entries
    numFutureBlockEntries: int = 0

    #future upgrade experiment entry
    futureExpEntriesList : list = field(default_factory=list)

    #Number of data blocks
    #To keep the dataclass 1-dim only first block is read, so this is always 1
    numBlocks: int = 1


    #Block 1 data
    blockName:str = "Not Specified" #Block identifier
    sampleName:str = "Not Specified" #Sample identifier
    #B.K. added: part of sample name after . is MATRIX V4.4.9 stage position name
    posName:str = ""
    #Block datetime
    date:datetime = datetime.now()
    timeZone:int = 0 #number of hours in advance of Greenwich Mean Time
    numBlockCommentLines:int = 0 #number of lines in block commen
    blockComment:str = "Not Specified"

    #metadata from MATRIX block comment
    xrayVoltage:float = 0
    xrayPower:float = 0
    xrayEmCurr:float = 0
    xrayFilCurr:float = 0
    xrayLeakCurr:float = 0
    
    analyserAperture:int = 0
    analyserSettingStr:str = "" #Easy to read identifier for Aperture/Magnification settings like "2low"

    analyserExitSlit:str = ""

    sampleStageX:float=0
    sampleStageY:float=0
    sampleStageZ:float=0
    sampleStageTheta:float=0
    sampleStagePhi:float=0
    
    #Analysis technique
    # 'AES diff | 'AES dir' | 'EDX' | 'ELS' | 'FABMS' | 'FABMSenergy spec' | 'ISS' | 'SIMS'
    # 'SIMS energy spec' | 'SNMS' | 'SNMS energy spec' | 'UPS' | 'XPS' | 'XRF' 
    #Always XPS for Omicron MATRIX V4.4.9 is saved. :-(
    technique:str = "XPS"

    # Not used by Omicron
    xCoord:float = 0
    yCoord:float = 0

    #values of experimental variables
    expVariablesList : list = field(default_factory=list)

    #Like AlKalpha
    AnalysisSourceLabel:str = "Not Specified"

    #Not used
    sputteringIonAtomicNum:int = 0 #sputtering ion or atom atomic number
    numAtomsSputteringIon:int = 0 #number of atoms in sputtering ion or atom particl
    sputteringIonCharge:int = -1 #sputtering ion or atom charge sign and number

    analysisSourceEnergy:float = 0 #analysis source characteristic energy in eV

    analyisSourceStrength:float = 0 #analysis source strength in W or beam current in nA

    analysisSourceBeamWidthX:float = 0 #in µm
    analysisSourceBeamWidthY:float = 0

    # Not used
    fieldOfViewX:float = 0 # FOV in µm
    fieldOfViewY:float = 0

    firstLineScanStartXCoord:float = 0
    firstLineScanStartYCoord:float = 0
    firstLineScanFinishXCoord:float = 0
    firstLineScanFinishYCoord:float = 0
    lastLineScanFinishXCoord:float = 0
    lastLineScanFinishYCoord:float = 0

    # analysis source polar angle of incidence
    analysisSourceAngleOfIncidence:float = 0

    # degrees clockwise from the y-direction towards the operator, defined by the sample stage
    analysisSourceAzimuth:float = 0

    #Analyzer Mode:'FAT', 'FRR', 'constant delta m', 'constant m/delta m'
    #Always 'FAT' for Omicron
    analyserMode:str = "FAT"
    
    # analyser pass energy or retard ratio or mass resolution
    analyzerPEorRR:float = 0 # in eV

    # Only used for 'AES diff'.
    diffWidth:float = 0

    #magnification of analyser transfer lens
    analyzerMagnification:int = 1

    # analyser work function or acceptance energy of atom or ion
    analyzerWorkFunction:float = 0 # in eV

    # targetBias
    # Read from comment
    sampleBias:float = 0 # in V

    analysisWidthX:float = 0 # in µm
    analysisWidthY:float = 0

    # analyser axis take off polar angle
    analysisTakeOffAngle:float = 0

    # analyser axis take off azimuth
    analysisTakeoffAzimuth:float = 0

    # elemental symbol or molecular formula
    speciesLabel:str = "Not Specified"

    # eg: '1s' for XPS, 'KLL' for AES, 
    #transition or charge state label
    transitionLabel:str = "Not Specified"

    #  -1 for AES and XPS, 
    detectedParticleCharge:str = -1

    # Only used for 'REGULAR'. Abscissa = xaxis parameter
    xAxisLabel:str = "Not Specified"  # text line
    xAxisUnit:str = "Not Specified"  # units
    xAxisStart:float = 0      # real number
    xAxisIncrement:float = 0  # real number
    #B.K. added
    xAxisEnd:float = 0


    # number of corresponding = y axis variables
    numYAxisVars:int = 1

    # corresponding variable label
    yAxisVarsLabelList : list = field(default_factory=list)
    #corresponding variable units
    yAxisVarsUnitList : list = field(default_factory=list)

    #Always 'pulse counting'
    signalMode:str = "Not Specified"

    #signal collection time
    dwellTime:float = 0 # Dwell time in s

    #number of scans to compile this block
    #=Number of averaged sweeps
    numSweeps:int = 1

    signalTimeCorr:float = 0

    # Used for sputtering / depth profiling:

    sputteringSourceEnergy:float = 0 #in eV
    sputteringSourceBeamCurrent:float = 0 # in nA
    sputteringSourceWidthX:float = 0 # in µnm
    sputteringSourceWidthY:float = 0
    sputteringSourceAngleOfIncidence:float = 0 # in Deg
    sputteringSourceAzimuth:float = 0
    sputteringMode:str = "Not Specified"   #'continuous' or 'cyclic'
  

    # sample nomial polar angle of tilt
    sampleNormalTiltAngle:float = 0

    # sample normal tilt azimut
    sampleNormalTiltAzimuth:float = 0

    sampleRotationAngle:float = 0

    #number of additional numerical parameters
    numAddNumParams:int = 0

    addParamsLabelList : list = field(default_factory=list)  
    addParamUnitList : list = field(default_factory=list)  
    addParamValueList : list = field(default_factory=list) 

    #Depedending on numFutureBlockEntries
    futureBlockEntriesList : list = field(default_factory=list)

    #Product of numYAxisVars and len of yAxis values list
    numYAxisValues:int = 1 #number of ordinate values

    minYAxisValuesList : list = field(default_factory=list)
    maxYAxisValuesList : list = field(default_factory=list)

    # Replace by numpy dings
    yAxisValuesList : list = field(default_factory=list)
    #B.K. added:
    xAxisValuesList : list = field(default_factory=list)
    
    #End of file
    expTerm:str = 'end of experiment'




    def readVamasFile(self):
        """Read the content of the VAMAS file into the dataclass according to the paper
        """
        self.file = open(self.fileName, encoding='cp1252') #Western Windows encoding
        self.file.seek(0)
        lines = iter(self.file.readlines())

        self.formatName = next(lines).strip()
        self.institution_identifier = next(lines).strip()
        self.instrumentModelName = next(lines).strip()
        self.operator_identifier = next(lines).strip()
        self.experiment_identifier = next(lines).strip()
        self.numCommentLines = int(next(lines).strip())

        #Parse the comment
        for i in range(self.numCommentLines):
            if i == 0:
                self.comment = ""
            self.comment = self.comment + next(lines)

        #B.K. Parse Additional Info from comment:
        self.commentCreatedWith, self.comment = parseString(self.comment, "Created with")
        self.commentAcquisition, self.comment = parseString(self.comment, "Date of Acquisition")
        self.commentSourceAnalyzerAngle, unit, self.comment = parseParameter(self.comment, "SourceAnalyserAngle")
        self.commentpIG, unit, self.comment = parseParameter(self.comment, "pIG")
        self.commentpPir, unit, self.comment = parseParameter(self.comment, "pPIR")
        self.commentpHIS, unit, self.comment = parseParameter(self.comment, "pHIS")
        self.commentVHIS, unit, self.comment = parseParameter(self.comment, "VHIS")
        self.commentWHIS, unit, self.comment = parseParameter(self.comment, "WHIS")
        self.commentVHISstart, unit, self.comment = parseParameter(self.comment, "VHIS")
        self.commentUPSFilterNr, unit, self.comment = parseParameter(self.comment, "Filter")
        self.commentUPSFilterAngle, unit, self.comment = parseParameter(self.comment, "FilterDeg")
        self.commentSampleBias, unit, self.comment = parseParameter(self.comment, "Bias")
        #Save to vamas field for sample bias
        self.sampleName = self.commentSampleBias

        #Remove comment header
        self.comment = self.comment.replace("CREATION COMMENT START", "")
        self.comment = self.comment.replace("CREATION COMMENT END", "")
        self.comment = self.comment.strip()


        self.expMode = next(lines).strip()
        self.scanMode = next(lines).strip()

        normalModes = ['MAP', 'MAPDP', 'NORM', 'SDP']
        if self.expMode in normalModes:
            self.numSpectralRegions = int(next(lines).strip())

        mappingModes = ['MAP', 'MAPDP']
        if self.expMode in mappingModes:
            self.numAnalysisPositions = int(next(lines).strip())
            self.numDiscreteXCoordFullMap = int(next(lines).strip())
            self.numDiscreteYCoordFullMap = int(next(lines).strip())

        self.numExpVariables = int(next(lines).strip())

        for i in range(self.numExpVariables):
            self.expVariableLabels.append(next(lines).strip())
            self.expVariableUnits.append(next(lines).strip())

        self.lenParamExclusionInclusionList = int(next(lines).strip())

        for i in range(abs(self.lenParamExclusionInclusionList)):
            self.paramExclusionInclusionPrefix.append(int(next(lines).strip()))

        self.numManuallyBlockItems = int(next(lines).strip())

        for i in range(self.numManuallyBlockItems):
            self.numManuallyBlockItemsPrefix.append(int(next(lines).strip()))

        self.numFutureExpEntries = int(next(lines).strip())

        self.numFutureBlockEntries = int(next(lines).strip())

        for i in range(self.numFutureBlockEntries):
            self.futureExpEntriesList.append(next(lines).strip())

        self.numBlocks = int(next(lines).strip())

        #Read only first block:

        
        self.blockName = next(lines).strip()
        self.sampleName = next(lines).strip()
        #B.K. split sample identifier into sample name and positon name at 1st dot
        if '.' in self.sampleName:
            self.sampleName, self.posName = self.sampleName.split(".", 1)
        #Parse dateTime:
        year = int(next(lines).strip())
        month = int(next(lines).strip())
        day = int(next(lines).strip())
        hours = int(next(lines).strip())
        if hours == 24:
            hours = 0 #24:00 = 00:00
        minutes = int(next(lines).strip())
        seconds = int(next(lines).strip())

        self.timeZone = int(next(lines).strip())
        #Todo: Correct for Timezone and DST
        try:
            self.date = datetime(year,month,day,hours,minutes,seconds)
        except:
            print("failed creating datetime object: {0}y, {1}m, {2}d, {3}h, {4}m, {5}s".format(year,month,day,hours,minutes,seconds))
            self.date = datetime.fromtimestamp(0) #Zero timestamp


        # 8
        self.numBlockCommentLines = int(next(lines).strip())
    
        for i in range(self.numBlockCommentLines):
            if i == 0:
                self.blockComment = ""
            self.blockComment = self.blockComment + next(lines)

        #B.K. parse optional parameters from block comment
        self.analyserAperture, unit, self.block_comment = parseParameter(self.blockComment, "Aperture")    
        #X-Ray source parameters
        self.xrayVoltage, unit, self.block_comment = parseParameter(self.blockComment, "X-Ray Source Voltage")
        self.xrayPower, unit, self.block_comment = parseParameter(self.blockComment, "X-Ray Source Power")    
        self.xrayEmCurr, unit, self.block_comment = parseParameter(self.blockComment, "X-Ray Source Emission Current")    
        self.xrayFilCurr, unit, self.block_comment = parseParameter(self.blockComment, "X-Ray Source Filament Current")    
        self.xrayLeakCurr, unit, self.block_comment = parseParameter(self.blockComment, "X-Ray Source Leak Current")    
        #Sample stage parameters
        self.sampleStageX, unit, self.block_comment = parseParameter(self.blockComment, "Sample Position X")
        self.sampleStageY, unit, self.block_comment = parseParameter(self.blockComment, "Sample Position Y")
        self.sampleStageZ, unit, self.block_comment = parseParameter(self.blockComment, "Sample Position Z")
        self.sampleStageTheta, unit, self.block_comment = parseParameter(self.blockComment, "Sample Position Theta")
        self.sampleStagePhi, unit, self.block_comment = parseParameter(self.blockComment, "Sample Position Phi")
        self.analyserExitSlit, self.block_comment = parseString(self.blockComment, "Exit Slit")

        self.blockComment = self.blockComment.strip()

        self.technique = next(lines).strip()

        if self.expMode in mappingModes:
            self.xCoord = int(next(lines).strip())
            self.yCoord = int(next(lines).strip())

        for i in range(self.numExpVariables):
            self.expVariablesList.append(float(next(lines).strip()))

        self.AnalysisSourceLabel = next(lines).strip()

        sputteringModes = ['MAPDP', 'MAPSVDP', 'SDP', 'SDPSV']
        sputteringTechs = ['FABMS', 'FABMS energy spec', 'ISS', 'SIMS', 'SIMS energy spec', 'SNMS', 'SNMS energy spec']
        if self.expMode in sputteringModes or self.technique in sputteringTechs:
            self.sputteringIonAtomicNum = next(lines).strip()
            self.numAtomsSputteringIon = int(next(lines).strip())
            self.sputteringIonCharge = int(next(lines).strip())

        self.analysisSourceEnergy = float(next(lines).strip())
        #B.K: Guess UPS technique from source energy
        if self.analysisSourceEnergy < 100:
            self.technique = 'UPS'

        self.analyisSourceStrength = float(next(lines).strip())
        #B.K. added: Use HIS13 power if UPS:
        if self.technique == 'UPS':
            self.analyisSourceStrength = self.commentWHIS

        # 16
        self.analysisSourceBeamWidthX = float(next(lines).strip())
        self.analysisSourceBeamWidthY = float(next(lines).strip())

        # 17
        mode = ['MAP', 'MAPDP', 'MAPSV', 'MAPSVDP', 'SEM']
        if self.expMode in mode:
            self.fieldOfViewX = float(next(lines).strip())
            self.fieldOfViewY = float(next(lines).strip())

        # 18
        mode = ['MAPSV', 'MAPSVDP', 'SEM']
        if self.expMode in mode:
            self.firstLineScanStartXCoord = int(next(lines).strip())
            self.firstLineScanStartYCoord = int(next(lines).strip())
            self.firstLineScanFinishXCoord = int(next(lines).strip())
            self.firstLineScanFinishYCoord = int(next(lines).strip())
            self.lastLineScanFinishXCoord = int(next(lines).strip())
            self.lastLineScanFinishYCoord = int(next(lines).strip())

        # 19
        self.analysisSourceAngleOfIncidence = float(next(lines).strip())

        # 20
        self.analysisSourceAzimuth = float(next(lines).strip())

        # 21
        self.analyserMode = next(lines).strip()

        # 22
        self.analyzerPEorRR = float(next(lines).strip())

        # 23
        if (self.technique == 'AES DIFF'):
            self.diffWidth = float(next(lines).strip())

        # 24
        self.analyzerMagnification = float(next(lines).strip())
        #B.K. Build analyzer setting string from Aperture and magnification
        self.analyserSettingStr = str(self.analyserAperture)
        mag = self.analyzerMagnification
        self.analyserSettingStr += "low" if mag == 1 else ("med" if mag == 2 else ("high" if mag == 5 else "n.d."))

        # 25
        self.analyzerWorkFunction = float(next(lines).strip())

        # 26
        self.targetBias = float(next(lines).strip())

        # 27
        self.analysisWidthX = float(next(lines).strip())
        self.analysisWidthY = float(next(lines).strip())

        # 28
        self.analysisTakeOffAngle = float(next(lines).strip())
        self.analysisTakeoffAzimuth = float(next(lines).strip())

        # 29
        self.speciesLabel = next(lines).strip()

        # 30
        self.transitionLabel = next(lines).strip()
        self.detectedParticleCharge = int(next(lines).strip())

        # 31: Parse x axis info
        if (self.scanMode == 'REGULAR'):
            self.xAxisLabel = next(lines).strip()
            self.xAxisUnit = next(lines).strip()
            self.xAxisStart = float(next(lines).strip())
            self.xAxisIncrement = float(next(lines).strip())
    

        # 32: Parse y axis info
        self.numYAxisVars = int(next(lines).strip())
        for i in range(self.numYAxisVars):
            self.yAxisVarsLabelList.append(next(lines).strip())
            self.yAxisVarsUnitList.append(next(lines).strip())


        # 33
        self.signalMode = next(lines).strip()

        # 34
        self.dwellTime = float(next(lines).strip())

        # 35
        self.numSweeps = int(next(lines).strip())

        # 36
        self.signalTimeCorr = float(next(lines).strip())

        # 37
        sputteringCoTechs = ['AES diff', 'AES dir', 'EDX', 'ELS', 'UPS', 'XPS', 'XRF']
        if self.technique in sputteringCoTechs and self.expMode in sputteringTechs:
            self.sputteringSourceEnergy = float(next(lines).strip())
            self.sputtering_source_beam_current = float(next(lines).strip())
            self.sputteringSourceWidthX = float(next(lines).strip())
            self.sputteringSourceWidthY = float(next(lines).strip())
            self.sputteringSourceAngleOfIncidence = float(next(lines).strip())
            self.sputteringSourceAzimuth = float(next(lines).strip())
            self.sputteringMode = next(lines).strip()

        # 38
        self.sampleNormalTiltAngle = float(next(lines).strip())
        self.sampleNormalTiltAzimuth = float(next(lines).strip())

        # 39
        self.sampleRotationAngle = float(next(lines).strip())

        # 40 Additional Parameters
        self.numAddNumParams = int(next(lines).strip())
        for i in range(self.numAddNumParams):
            self.addParamsLabelList.append(next(lines).strip())
            self.addParamUnitList.append(next(lines).strip())
            self.addParamValueList.append(float(next(lines).strip()))

        # 40 Future Block Entries
        for i in range(self.numFutureBlockEntries):
            self.futureBlockEntriesList.append(next(lines).strip())

        self.numYAxisValues = int(next(lines).strip())

        #B.K. Added test for number of vars > 0
        if self.numYAxisVars > 0:
            #Calculate x axis end:
            self.xAxisEnd = self.xAxisStart + self.xAxisIncrement*int(self.numYAxisValues/self.numYAxisVars)

            variables = []
            for i in range(self.numYAxisVars):
                self.minYAxisValuesList.append(float(next(lines).strip()))
                self.maxYAxisValuesList.append(float(next(lines).strip()))
                variables.append([])

            for i in range(int(self.numYAxisValues/self.numYAxisVars)):
                for j in range(self.numYAxisVars):
                    variables[j].append(float(next(lines).strip()))

            self.yAxisValuesList = variables

            #Create x-values
            self.xAxisValuesList = []
            for i in range(int(self.numYAxisValues/self.numYAxisVars)):
                self.xAxisValuesList.append(self.xAxisStart +  i*self.xAxisIncrement)



def parseParameter(comment, keyword):
    """
    parse <keyword>: <value> or <keyword>=<value> from a block comment
    If successful return rest of the comment without the match
    <value> is any number format with DECIMAL POINT (e.g., 23, 6e23. -0.1E-23, etc.)

    Arguments:
        comment {str} -- the comment string
        keyword {str} -- the keyword (case-insensitive) to find in comment

    Returns:
        [str, str, str] -- result, unit_string residual comment
    """

    #Escape spaces in keyword!
    keyword = keyword.replace(" ", r"\ ")

    regex = re.compile(r"""
        (?:                     #Start of non-capturing group
        (?:\s|\A)               #non-capturing group: Whitespace or <Start of string> before keyword!
        {}                      #Keyword inserted by .format()
        (?::|\ ?=)?             #Non-capturing optional group with either ":" or space + "="
        \ ?)                    #Optional space, end of group
        (                       #Start of capturing group which will contain the parsed number
        -?\ ?                   #Optional minus + optional space
        [0-9]+\.?[0-9]*         #One or more numbers + optional decimal point + numbers
        (?:                     #Start of optional non-capturing group with scientific exponent
        [Ee]\ ?[-+]?\ ?[0-9]+   #Exponent E followed by optional space, plus/minus and min one number
        )?                      #End of optional exponent group
        )                       #End of capturing group
        \ ?                     #Optional Space
        (                       #Start of optional capturing group for unit
        [A-Z°]+                  #One or more chars
        )?                      #End of optional capturing group
                        
    """.format(keyword), re.VERBOSE|re.IGNORECASE)
    #Scan forward through the comment for the first match
    result = regex.search(comment) 
    if result:
        #Return tuple with capturing-group and comment with removed match
        return result.group(1), result.group(2), comment.replace(result.group(0), "")
    else:
        return "", "", comment


def parseString(comment, keyword):
    """
    parse <keyword>: <value> or <keyword>=<value> from a block comment
    If successful return rest of the comment without the match
    <value> is any string terminated by NEWLINE

    Arguments:
        comment {str} -- the comment string
        keyword {str} -- the keyword (case-insensitive) to find in comment

    Returns:
        [str, str] -- result, residual comment
    """

    #Escape spaces in keyword!
    keyword = keyword.replace(" ", r"\ ")

    regex = re.compile(r"""
        (?:                     #Start of non-capturing group
        (?:\s|\A)               #non-capturing group: Whitespace or <Start of string> before keyword!
        {}                      #Keyword inserted by .format()
        (?::|\ ?=)?             #Non-capturing optional group with either ":" or space + "="
        \ ?)                    #Optional space, end of group
        (                       #Start of capturing group which will contain the parsed string
        .*                      #Any String except newline
        )                       #End of capturing group
        $                       #End of line                     
                        
    """.format(keyword), re.VERBOSE|re.IGNORECASE|re.MULTILINE)
    #Scan forward through the comment for the first match
    result = regex.search(comment) 
    if result:
        #Return tuple with capturing-group and comment with removed match
        return result.group(1), comment.replace(result.group(0), "")
    else:
        return "", comment        


if __name__ == "__main__":
    vms = VAMAS_File(fileName="test.vms")
    vms.readVamasFile()
    print(vms.fileName)
    print(vms.comment)
    print(vms.date)
    print(vms.blockComment)
    print(vms.xrayVoltage)
    print(vms.analyserAperture)
    print(vms.analyserSettingStr)
    
