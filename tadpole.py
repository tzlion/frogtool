#GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import (QIcon)
#OS imports - these should probably be moved somewhere else
import os
import sys
import string
#Feature imports
import frogtool
import tadpole_functions


def RunFrogTool():
    drive = window.combobox_drive.currentText()
    console = window.combobox_console.currentText()
    
    print(f"Running frogtool with drive ({drive}) and console ({console})")
    try:
        if(console =="ALL"):
            for console in frogtool.systems.keys():
                result = frogtool.process_sys(drive,console, False)
                QMessageBox.about(window,"Result",result)

        else:
            result = frogtool.process_sys(drive,console, False)
            QMessageBox.about(window,"Result",result)
    except frogtool.StopExecution:
        pass
        
def reloadDriveList():
    available_drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
    window.combobox_drive.clear()
    for drive in available_drives:
        window.combobox_drive.addItem(QIcon(),drive,drive)

def loadROMsToTable():
    drive = window.combobox_drive.currentText()
    system = window.combobox_console.currentText()
    if drive == "???" or system == "???":
        return
    roms_path = f"{drive}/{system}"
    try:
        files = frogtool.getROMList(roms_path)
        window.tbl_gamelist.setRowCount(len(files))
        for i, (name) in enumerate(files):
            window.tbl_gamelist.setItem(i,0,QTableWidgetItem(f"{name}"))
    except frogtool.StopExecution:
        #Empty the table
        window.tbl_gamelist.setRowCount(0)
        
    window.tbl_gamelist.show()

#SubClass QMainWindow to create a Tadpole general interface
class MainWindow (QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tadpole - SF2000 Tool")
        widget = QWidget()
        self.setCentralWidget(widget)
        
        #Load the Menus
        self.create_actions()
        self.loadMenus()
        
        layout = QGridLayout(widget)
        rowCounter = 0
        colCounter = 0
        #Drive Select Widgets
        self.lbl_drive = QLabel(text="Drive:")     
        self.combobox_drive = QComboBox()
        self.combobox_drive.currentIndexChanged.connect(loadROMsToTable)
        self.btn_refreshDrives = QPushButton()
        self.btn_refreshDrives.setIcon(self.style().standardIcon(getattr(QStyle, "SP_BrowserReload")))
        self.btn_refreshDrives.clicked.connect(reloadDriveList)
        layout.addWidget(self.lbl_drive, rowCounter, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_drive, rowCounter, colCounter)
        colCounter += 1
        layout.addWidget(self.btn_refreshDrives,rowCounter,colCounter)
        colCounter += 1
         
        #Console Select Widgets
        self.lbl_console = QLabel(text="Console:")
        self.combobox_console = QComboBox()
        self.combobox_console.currentIndexChanged.connect(loadROMsToTable)
        layout.addWidget(self.lbl_console, rowCounter, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_console, rowCounter, colCounter)
        colCounter += 1        
        
        #Update Button Widget
        self.btn_update = QPushButton("Update!")
        layout.addWidget(self.btn_update, rowCounter, colCounter)
        self.btn_update.clicked.connect(RunFrogTool)
        colCounter += 1  
        
        self.lbl_fillerR1 = QLabel()
        layout.addWidget(self.lbl_fillerR1, rowCounter, colCounter)
        layout.setColumnStretch(colCounter,1)
        colCounter += 1  
        
        #New Row
        rowCounter += 1
        colCounter = 0       
             
        #Game Table Widget
        self.tbl_gamelist = QTableWidget()
        self.tbl_gamelist.setColumnCount(4)
        self.tbl_gamelist.setHorizontalHeaderLabels(["Name","Size","Thumbnail","Actions"])
        layout.addWidget(self.tbl_gamelist,rowCounter, 0, 1, -1)
    
 
    def loadMenus(self):
        self.menu_file = self.menuBar().addMenu("&File")
        self.menu_file.addAction(self.about_action)
        self.menu_file.addAction(self.exit_action)
        
        self.menu_os = self.menuBar().addMenu("&OS")
        self.menu_os.addAction(self.GBABIOSFix_action)
    

    def create_actions(self):
        self.about_action = QAction("&About", self, triggered=self.about)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q",triggered=self.close)
        self.GBABIOSFix_action = QAction("&GBA BIOS Fix", self, triggered=self.GBABIOSFix)


    def about(self):
        QMessageBox.about(self, "About Tadpole","Tadpole was created by EricGoldstein based on the original work from tzlion on frogtool")

    def GBABIOSFix(self):
        drive = window.combobox_drive.currentText()
        try:
            tadpole_functions.GBABIOSFix(drive)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(self, "GBA BIOS Fix","An error occurred. Please ensure that you have the right drive selected and <i>gba_bios.bin</i> exists in the <i>bios</i> folder")
            return
        QMessageBox.about(self, "GBA BIOS Fix","BIOS successfully copied")
        
    
    def UnderDevelopmentPopup(self):
        QMessageBox.about(self, "Developement","This feature is still under development")

#Initialise the Application
app = QApplication(sys.argv)

# Build the Window
window = MainWindow()

#Update list of drives
available_drives_placeholder = "???"
window.combobox_drive.addItem(QIcon(),available_drives_placeholder,available_drives_placeholder)
reloadDriveList()


#Update list of consoles
available_consoles_placeholder = "???"
window.combobox_console.addItem(QIcon(),available_consoles_placeholder,available_consoles_placeholder)
window.combobox_console.clear()
for console in frogtool.systems.keys():
    window.combobox_console.addItem(QIcon(),console,console)
    
#Add ALL to the list to add this fucntionality from frogtool
window.combobox_console.addItem(QIcon(),"ALL","ALL")



window.show()
app.exec()