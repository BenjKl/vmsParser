import sys, os, configparser

from PyQt5.QtWidgets import QApplication, QMainWindow,QFileDialog,QDialog
from PyQt5.QtWidgets import QDataWidgetMapper
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSettings, QModelIndex, QAbstractTableModel, QTransposeProxyModel, QSortFilterProxyModel

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from dataclasses import dataclass, fields, field, asdict, replace
from vamasSimple import VAMAS_File
from jopes import JOPES_Investigation, JOPES_Measurement

#VIEW <-> CONTROLLER <-> MODEL <-> DATA pattern with PyQt5
#  ^                      ^
#  |------DataMapper------|


class ParameterModel(QAbstractTableModel):
    """2-Dim MODEL using a list of dataclasses to save the data

    """

    def __init__(self, data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dataList = data
        
        self.selectedColumns = [False] * len(data)
        self.selectedRows = [False] * len(fields(self.dataList[0]))
        print("Init {0} cols and {1} rows".format(len(self.selectedColumns), len(self.selectedRows)))


    def appendData(self, data):
        """Append new column data to the model
        """
        self.beginInsertColumns(QModelIndex(), self.columnCount()-1, self.columnCount()- 1)
        self.dataList.insert(self.columnCount(),  data) 
        #Insert new item in selectedColumns list
        self.selectedColumns.insert(self.columnCount()-1, False)
        self.endInsertColumns()
        return True        

    # Implemented
    def removeColumns(self, pos, cols=1, parent=QModelIndex()):
        """Delete columns from the model
        """
        self.beginRemoveColumns(QModelIndex(), pos, pos+cols-1)
        for col in range(cols):
            #delete the object at the given index in the dataList and selectedColumnsList
            del self.dataList[pos+col-1]
            del self.selectedColumns[pos+col-1]
        if len(self.dataList) == 0:
            self.dataList.append(VAMAS_File())
            self.selectedColumns.append(False)
        self.endRemoveColumns()
        return True

    # Implemented
    def flags(self, index):
        """ Returns the property flags for each item, if it appears as text or checkbox
            First row and column will contain checkboxes

        ### Arguments:
            index {QModelIndex} -- Row and column index of the item

        ### Returns:
            {QItemFlag} -- Flags of the item
        """
        if index.row() == 0 and index.column() == 0:
            return Qt.NoItemFlags
        defaultFlags = super().flags(index) #Get default flag for item
        if index.row() == 0 or index.column() == 0:
            #print ("Returning checkable for ", index.row(),  index.column())
            #Return enable checkbox for 1st row and column
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
        else:
            return defaultFlags

    # Implemented
    def data(self, index, role): 
        """This is called by the view to provide data to display in the table cell or as tooltip

        ### Arguments:
            index {QModelIndex} -- Row and column index of the item
            role {int} -- Role of the requested data (Text for cell or tooltip, checked state for checkbox)

        ### Returns:
            {object} -- The data
        """
        
        if not index.isValid():
            return None
        #print("Data request for row {0} and col {1}".format(index.row(), index.column()))
        if role == Qt.CheckStateRole and index.row() == 0:
            #print ("checkbox data ", index.row(),  index.column(), "role: ", role)
            if self.selectedColumns[index.column()-1]:
                return Qt.Checked
            else:
                return Qt.Unchecked
        if role == Qt.CheckStateRole and index.column() == 0:
            #print ("checkbox data ", index.row(),  index.column(), "role: ", role)
            if self.selectedRows[index.row()-1]:
                return Qt.Checked
            else:
                return Qt.Unchecked                
        elif (role == Qt.DisplayRole  or role == Qt.ToolTipRole) and index.row() > 0 and index.column() > 0:
                # use only the row to get the data from our todo list
                #print ("data ", index.row(),  index.column(), "role: ", role)
                #print ("data ", index.row(),  index.column(), getattr(self.dataList[index.column()], fields(self.dataList[index.column()])[index.row()].name))
                return str(getattr(self.dataList[index.column()-1], fields(self.dataList[index.column()-1])[index.row()-1].name))

    # Implemented
    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        """This is called by the view to provide text for the row and column headers

        ### Arguments:
            section {int} -- Row or column index depending on orientation
            orientation {Qt.Orientation} -- Qt.Horizontal or Qt.Vertical
            role {int} -- Role of the requested data (Text for cell or tooltip)

        ### Returns:
            {str} -- Text to display
        """
        if role == Qt.DisplayRole or role == Qt.ToolTipRole:
            if orientation == Qt.Vertical and section>0:
                #Use the dataclass field=variable name for the header
                return fields(self.dataList[0])[section-1].name

    # Implemented
    def setData(self, index, value, role=Qt.EditRole):
        #print("setData request for row {0} and col {1}".format(index.row(), index.column()))
        if not index.isValid():
            return False

        if role == Qt.CheckStateRole:
            if index.row() == 0:
                if value == Qt.Checked:
                    self.selectedColumns[index.column()-1] = True
                else:
                    self.selectedColumns[index.column()-1] = False
            elif index.column() == 0:
                if value == Qt.Checked:
                    self.selectedRows[index.row()-1] = True
                else:
                    self.selectedRows[index.row()-1] = False     
            self.dataChanged.emit(index, index)                               
        else:
            newValue = value
            oldValue = getattr(self.dataList[index.column()-1], fields(self.dataList[index.column()-1])[index.row()-1].name) 
            if newValue != oldValue:
                #print ("setData ", index.row(),  index.column(), newValue)

                setattr(self.dataList[index.column()-1], fields(self.dataList[index.column()-1])[index.row()-1].name, newValue)
                self.dataChanged.emit(index, index)
        return True

    # Implemented
    def rowCount(self, parent=QModelIndex()):
        """Return number of rows of model = number of fields in dataclass + checkbox row

        ### Keyword Arguments:
            parent {QModelIndex} -- only used for trees (default: {QModelIndex()})

        ### Returns:
            {int} -- total number of rows
        """
        return len(fields(self.dataList[0]))+1 #+1

    # Implemented
    def columnCount(self, parent=QModelIndex()):
        """Return number of model columns = number of dataclass objectes + checkbox row

        ### Keyword Arguments:
            parent {QModelIndex} -- only used for trees (default: {QModelIndex()})

        ### Returns:
            {int} -- total number of columns
        """
        return len(self.dataList)+1

    def loadData(self, newData):
        #Replace the datalist with newData
        self.layoutAboutToBeChanged.emit()
        self.dataList = newData
        self.selectedColumns = [False] * len(newData)
        #self.selectedRows = [False] * len(fields(newData[0]))     
        #print("LoadData Reinit {0} cols and {1} rows".format(len(self.selectedColumns), len(self.selectedRows)))   
        self.layoutChanged.emit()

    def loadFromConfigFile(self, fileName):
        #Load new data from config file
        #Create new empty data list (List of dataclass objects)
        data = list()
        with open(fileName, 'r') as f:
            config = configparser.ConfigParser()
            #Make it case-sensitive
            config.optionxform = str            
            config.read_file(f)
            #Iterate through config sections
            for section in config.sections():
                #Check if section name starts with "Parameters1"
                if section.startswith('VAMAS_File'):
                    #Create new dataclass object unpacking the dict made out of the config
                    dat = VAMAS_File(**dict(config[section]))
                    #Append to data list
                    data.append(dat)

        self.loadData(data)


            

    def saveModelToConfigFile(self, fileName):
        """Saves the model as .ini type file using ConfigParser

        ### Arguments:
            fileName {str} -- full filepath
        """
        #Create Configparser obect
        config = configparser.ConfigParser()
        #Make it case-sensitive
        config.optionxform = str
        #Iterate through dict of dicts
        for key, value in self.dataAsDict().items():
            #Write all key-value pairs of one column as config 
            config[key] = value #Value is a dict
        #Write the configparser to the selected file
        with open(fileName, 'w') as f:
            config.write(f)

    def getFieldIndex(self, name):
        """Return the index of named dataclass field in the model

        ### Arguments:
            name {str} -- field name

        ### Returns:
            {int} -- model index (row) for parameter
        """
        #return the index of name in list of parameters
        return list(f.name for f in fields(self.dataList[0])).index(name)    

    def dataAsDict(self):
        """Create a dict of dicts from the datalist using the classname of the dataclass + index as key values

        ### Returns:
            {dict} -- Dict of dicts of the model data
        """
        return {str(d.__class__.__name__) + "_" + str(i+1) : asdict(d) for i, d in enumerate(self.dataList)}

    def getObject(self, index):
        """Return the indexed dataclass

        ### Arguments:
            index {int} -- Column index for the model

        ### Returns:
            {type of dataclass} -- returns the dataclass object
        """
        return self.dataList[index-1]

    def getData(self):
        """Return the whole list of dataclass objects

        ### Returns:
            {list} -- List of dataclas objects
        """
        return self.dataList

class MplCanvas(FigureCanvasQTAgg):
    """Matplotlib plot in a a qt canvas

    ### Arguments:
        FigureCanvasQTAgg {[class]} -- Prototype
    """
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        #Create the figure with constrained_layout to automatically resize correctly respecting space for labels
        self.fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)



class MainWindow(QMainWindow):
    """Controller class for VmsParser

    ### Args:
        QMainWindow ([class]): Create the controller class
    """

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        #Load VIEW from resource file
        uic.loadUi(self.resourcePath('gui.ui'), self)


        #Create first data for the model
        self.data = [VAMAS_File()]
        #Create the MODEL
        self.model = ParameterModel(self.data)

        #Selected first model column
        self.selectedModelColumn = 1
     

        #Create the maptlotlib FigureCanvas object, 
        #which defines a single set of axes as self.axes.
        self.spectralPlot = MplCanvas(self, width=8, height=4, dpi=100)
        #self.spectralPlot.axes.plot([0,1,2,3,4], [10,1,20,3,40])
        toolbar = NavigationToolbar(self.spectralPlot, self)
        self.plotToolBar.addWidget(toolbar)
        self.plotWidget.addWidget(self.spectralPlot)        

        #Popup menu event
        self.dataSelector.currentIndexChanged.connect(lambda index: (self.selectModelColumn(index+1)))
        self.dataSelector.setCurrentIndex(0)    

        #Display model as table
        self.vmsTable.setModel(self.model)
        self.vmsTable.verticalHeader().setMaximumWidth(160)
        self.vmsTable.setColumnWidth(0, 30)
        #Hide the first row with model-column selector checkbox
        self.vmsTable.hideRow(0)
        self.model.dataChanged.connect(lambda index: (self.modelEditedEvent(index)))
        
        #Proxy model with swapped rows/columns for paramTabel
        self.proxy = QTransposeProxyModel()
        self.proxy.setSourceModel(self.model)

        #Sorting model
        self.proxy2 = QSortFilterProxyModel()
        self.proxy2.setSourceModel(self.proxy)

        #Display sorted proxy model for param table
        self.paramTable.setModel(self.proxy2)
        #Show only selected columns
        self.initSelectedFields()  
        #Movable columns
        self.paramTable.horizontalHeader().setSectionsMovable(True)
        self.paramTable.setColumnWidth(0, 30)
        #Double click event selects row from model and updates view
        self.paramTable.doubleClicked.connect(lambda index: (self.selectModelColumn(self.proxy2.mapToSource(index).row())))
        #Hide first row with model-row selector checkboxes
        self.paramTable.hideRow(0)

        #Menu Bar events
        self.actionSave.triggered.connect(self.saveModel)
        self.actionLoad.triggered.connect(self.loadModel)  
        self.actionAppend_Files.triggered.connect(self.appendData)                
        self.actionQuit.triggered.connect(self.close)
        self.actionRemove_Selected.triggered.connect(self.removeData)
        self.actionExport_to_Chantal.triggered.connect(self.exportToChantal)

        #Button events
        self.buttonPrevArea.clicked.connect(self.goToPreviousColumn)
        
        self.buttonNextArea.clicked.connect(self.goToNextColumn)

        self.colNumber.setText("0/0")

        self.show()

    def modelEditedEvent(self, index):
        """Event triggered when model data changed by clicking a checkbox

        ### Arguments:
            index {QModelIndex} -- row/colum of changed data
        """
        print("Model edited event row {0}, column {1} changed".format(index.row(), index.column()))
        #First column changes selected fields which are displayed in paramTable
        if index.column() == 0:
            if self.model.selectedRows[index.row()-1] == True:
                self.paramTable.showColumn(index.row())
            else:
                self.paramTable.hideColumn(index.row())

        #First row changes data columns to be plotted
        if index.row() == 0:
            self.updatePlot()


    def initSelectedFields(self):
        """Init selected dataclass fields = columns in param Table with default values
        """
        #Show only selected columns
        visibleColumns = ["sampleName", "blockName", "posName", "date", "technique", "analyserSettingStr", "analyzerPEorRR", "dwellTime"]
        for r in range(self.proxy.columnCount()):
            if not self.proxy.headerData(r, Qt.Horizontal) in visibleColumns:
                self.paramTable.hideColumn(r)
            else:
                self.model.selectedRows[r-1] = True
        self.paramTable.showColumn(0)  
    
    def goToNextColumn(self):
        """Select next column from model
        """
        if self.selectedModelColumn < self.model.columnCount()-1:
            self.selectedModelColumn+=1
            self.updateSelectedData()
    
    def goToPreviousColumn(self):
        """Select previous column from model
        """
        if self.selectedModelColumn > 1:
            self.selectedModelColumn-=1
            self.updateSelectedData()            
    
    def selectModelColumn(self, index):
        """Select indexed data column from the model, update the datamapper and view

        ### Arguments:
            index {int} -- Model column index
        """
        # self.dataMapper.submit()
        #self.dataMapper.setCurrentIndex(index)
        print("Selecting model column " + str(index))
        self.selectedModelColumn = index
        self.updateSelectedData()


    def updateSelectedData(self):
        """update dataSelector PopupMenu, Table and plot after a different data column selected from the model
        """
        #Update colNumber label
        self.colNumber.setText(str(self.selectedModelColumn) + "/" + str(self.model.columnCount()-1))
        #Select corresponding line in popupmenu without triggering event
        self.dataSelector.blockSignals(True)
        self.dataSelector.setCurrentIndex(self.selectedModelColumn-1)
        self.dataSelector.blockSignals(False)
        #Show only only the selected column (=dataclass) from the model in the vmsTable
        for column in range(self.model.columnCount()):
            if column == self.selectedModelColumn or column == 0:
                self.vmsTable.showColumn(column)
            else:
                self.vmsTable.hideColumn(column)
        
        #print ("Combobox currentIndex", self.dataSelector.currentIndex(), " from ", self.dataSelector.count())
        #Select line in inverse paramTable
        index = self.proxy.index(self.selectedModelColumn, 0) #Get column = row index from Transpose Proxy model
        print("Param table selecting row {0}".format(self.proxy2.mapFromSource(index).row()))
        #Deselect all
        self.paramTable.clearSelection()
        self.paramTable.selectRow(self.proxy2.mapFromSource(index).row()) #Convert to row index in sorted Proxy model

        #Plot data
        #Get current data class object
        self.updatePlot()

    def updatePlot(self):
        """update the plot with the selected data
        """
        #Get current data class object
        data = self.model.getObject(self.selectedModelColumn)
        #print("plotting column " + str(self.selectedModelColumn))
        if len(data.yAxisValuesList) > 0:
            self.spectralPlot.axes.cla()
            self.spectralPlot.axes.plot(data.xAxisValuesList, data.yAxisValuesList[0])
            #Create axis labels from data
            self.spectralPlot.axes.set_xlabel("{0} [{1}]".format(data.xAxisLabel, data.xAxisUnit))
            self.spectralPlot.axes.set_ylabel("{0} [{1}]".format(data.yAxisVarsLabelList[0], data.yAxisVarsUnitList[0]))


        #Plot also selected data columns
        for colIndex, checked in enumerate(self.model.selectedColumns):
            if checked and colIndex+1 != self.selectedModelColumn: #Starts from 0
                #print("plotting also column " + str(colIndex+1))
                #Get current data class object
                data = self.model.getObject(colIndex+1) #Starts from 0
                self.spectralPlot.axes.plot(data.xAxisValuesList, data.yAxisValuesList[0])

        #redraw
        self.spectralPlot.draw()            
            
            


    def resourcePath(self, relPath):
        """To access resources when bundled as an executable using PyInstaller relative paths are redirected to temporary _MEIPASS folder
            Ref.: https://blog.aaronhktan.com/posts/2018/05/14/pyqt5-pyinstaller-executable
        ### Args:
            relPath {str}: Relative path to resource file

        ### Returns:
            {str}: Converted path
        """
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relPath)
        return os.path.join(os.path.abspath('.'), relPath)


    def saveModel(self):
        """Present file dialog to save model data to config (.ini) file
        """
        #Present file dialog using last saved folder
        lastFolder = self.getLastSaveFolder()
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Save settings")
        dialog.setNameFilter("Ini files (*.ini)")
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setDirectory(lastFolder)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        if dialog.exec_() == QDialog.Accepted:
            fileName = dialog.selectedFiles()[0]
            self.saveLastFolder(fileName)
            #Save the model to config file
            self.model.saveModelToConfigFile(fileName)
            print ("Saved to " + fileName)
    
    def exportToChantal(self):
        """Export selected columns to CHANTAL
        """
        for colIndex, checked in enumerate(self.model.selectedColumns):
            if checked:
                #Get current data class object
                data = self.model.getObject(colIndex+1)
                print("Exporting column {0} from file {1}".format(colIndex+1, data.fileName))
                joInv = JOPES_Investigation()
                invID = joInv.import_investigation(data)
                print(joInv.data)
                joMeas = JOPES_Measurement()
                print(joMeas.import_measurement(data,invID))
                print(joMeas.data)


    def getLastSaveFolder(self):
        """ Try to get a selected folder from QSettings file
            (Mac: ~\library\preferences\)
            Defaults to userfolder ~
        ### Returns:
            {str}: folder path
        """
        try:
            settings = QSettings('vmsParser', 'vmsParser')
            print(settings.fileName())
            lastFolder = settings.value('saveFolder', type=str)
            
        except:
            lastFolder = os.path.expanduser('~')

        return lastFolder


    def saveLastFolder(self, foldername):
        """ Saves the last visited folder as QSettings
            (Mac: ~\library\preferences\)
        ### Args:
            foldername {str}: foldername
        """
        settings = QSettings('vmsParser', 'vmsParser')
        settings.setValue('saveFolder', os.path.dirname(foldername))

    def loadModel(self):
        """Present file dialog to load model data from .vms files
        """
        print("model column count before load " + str(self.model.columnCount()))
        #Present file dialog using last saved folder
        fileNames = self.vmsFileSelectorDialog()
        if fileNames: #Continue if files selected
            #Clear popup menu before loading new data
            self.dataSelector.clear()
            dataList = self.loadfilesIntoList(fileNames)
            #Supply the new datalist to the model to replace its data
            self.model.loadData(dataList)
            #Select first model column
            self.selectedModelColumn = 1
            #Update the column number
            self.colNumber.setText("1/" + str(self.model.columnCount()-1))
            #Refill popup menu with filenames
            for data in self.model.getData():
                self.dataSelector.addItem(os.path.basename(data.fileName))
            self.vmsTable.resizeRowsToContents() #Resize rows in table view to make space for multiline comments
    
    def appendData(self):
        """Present file dialog to append files
        """
        if self.dataSelector.currentText() == "":
            self.loadModel()
        else:
            #Present file dialog using last saved folder
            print("model column count before append " + str(self.model.columnCount()))
            print("Selected model column " + str(self.selectedModelColumn))
            fileNames = self.vmsFileSelectorDialog()
            if fileNames: #Continue if files selected
                #Deselect all
                self.paramTable.clearSelection()
                dataList = self.loadfilesIntoList(fileNames)
                #Get the number of columns before insert
                oldColumnNum = self.model.columnCount()
                for data in dataList:
                    self.dataSelector.addItem(os.path.basename(data.fileName))
                    self.model.appendData(data)
                self.selectModelColumn(oldColumnNum)
                self.vmsTable.resizeRowsToContents() #Resize rows in table view to make space for multiline comments

    def removeData(self):
        print("Selected Rows: ")
        selections = self.paramTable.selectionModel()
        rows = [selection.row() for selection in selections.selectedRows()]
        rows.sort(reverse=True)
        print(rows)
        #Remove all selected lines from selection
        for row in rows:
            print(row)
            self.model.removeColumns(row)
            self.dataSelector.blockSignals(True)
            self.dataSelector.removeItem(row-1)
            self.dataSelector.blockSignals(False)            

        self.selectModelColumn(1)


    def loadfilesIntoList(self, fileNames):
        """Load a list of vamas files into list of dataclasses to use as new model data

        ### Arguments:
            fileNames {list} -- List of filenames
        """
        data = list()   
        for filename in fileNames:
            vms = VAMAS_File(fileName=filename)
            vms.readVamasFile()
            data.append(vms)
        return data
    
    def vmsFileSelectorDialog(self):
        """ Present file dialog to select one or more vamas files
            Starting with last used folder from App preferences

        ### Returns:
            {list} -- list of selected filePaths
        """
        lastFolder = self.getLastSaveFolder()
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Open vms files")
        dialog.setNameFilter("vms files (*.vms)")
        dialog.setFileMode(QFileDialog.ExistingFiles) #Select multiple existing files
        dialog.setDirectory(lastFolder)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec_() == QDialog.Accepted:
            fileNames = dialog.selectedFiles()
            #Save selected foldername for next time
            self.saveLastFolder(fileNames[0])
            return fileNames
        else:
            return None


app = QApplication(sys.argv)
app.setWindowIcon(QIcon(MainWindow.resourcePath(None, 'icon_XPS.ico')))
window = MainWindow()
app.exec_()
