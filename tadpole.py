#GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
#OS imports - these should probably be moved somewhere else
import os
import sys
import string
#Feature imports
import frogtool
import tadpole_functions

import time

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
    loadROMsToTable()
    
def reloadDriveList():
    currentDrive =  window.combobox_drive.currentText()
    available_drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
    window.combobox_drive.clear()
    for drive in available_drives:
        window.combobox_drive.addItem(QIcon(),drive,drive)
    window.combobox_drive.setCurrentText(currentDrive)

def loadROMsToTable():   
    drive = window.combobox_drive.currentText()
    system = window.combobox_console.currentText()
    if drive == "???" or system == "???":
        return
    roms_path = f"{drive}/{system}"
    try:
        files = frogtool.getROMList(roms_path)
        window.tbl_gamelist.setRowCount(len(files))
        for i,f in enumerate(files):
            filesize = os.path.getsize(f"{roms_path}/{f}")
            humanReadableFileSize = "ERROR"
            if filesize > 1024*1024: #More than 1 Megabyte
                humanReadableFileSize = f"{round(filesize/(1024*1024),2)} MB"
            elif filesize > 1024: #More than 1 Kilobyte
                humanReadableFileSize = f"{round(filesize/1024,2)} KB"
            else: #Less than 1 Kilobyte
                humanReadableFileSize = f"filesize Bytes"
            window.tbl_gamelist.setItem(i,0,QTableWidgetItem(f"{f}")) #Filename
            window.tbl_gamelist.setItem(i,1,QTableWidgetItem(f"{humanReadableFileSize}")) #Filesize
            window.tbl_gamelist.setItem(i,2,QTableWidgetItem(f"view")) #View Thumbnail Button
            window.tbl_gamelist.setItem(i,3,QTableWidgetItem(f"change")) #Change Thumbnail Button
            
        #Adjust column widths
        window.tbl_gamelist
    except frogtool.StopExecution:
        #Empty the table
        window.tbl_gamelist.setRowCount(0)
        
    window.tbl_gamelist.show()


def catchTableCellClicked(clickedRow, clickedColumn):
    print(f"clicked view thumbnail for {clickedRow},{clickedColumn}")
    if clickedColumn == 2:
        drive = window.combobox_drive.currentText()
        system = window.combobox_console.currentText()
        gamename = window.tbl_gamelist.item(clickedRow, 0).text()
        viewThumbnail(f"{drive}/{system}/{gamename}")
    elif clickedColumn == 3:
        drive = window.combobox_drive.currentText()
        system = window.combobox_console.currentText()
        gamename = window.tbl_gamelist.item(clickedRow, 0).text()
        newCoverFileName = QFileDialog.getOpenFileName(window, 'Open file','c:\\',"Image files (*.jpg *.png *.webp);;All Files (*.*)")[0]
        print(f"user tried to load image: {newCoverFileName}")
        if(newCoverFileName == None or newCoverFileName == ""):
            print("user cancelled image select")
            return
        
        try:
            tadpole_functions.changeZXXThumbnail(f"{drive}/{system}/{gamename}", newCoverFileName)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(window, "Change ROM Cover","An error occurred.")
            return
        QMessageBox.about(window, "Change ROM Cover","ROM cover successfully changed")
        

def viewThumbnail(rom_path):
    window.window_thumbnail = thumbnailWindow()  
    window.window_thumbnail.loadThumbnail(rom_path)
    window.window_thumbnail.show()
    
def BGM_change(source=""):
    #Check the selected drive looks like a Frog card
    drive = window.combobox_drive.currentText()
    
    if not tadpole_functions.checkDriveLooksFroggy(drive):
        QMessageBox.about(window, "Something doesn't Look Right","The selected drive doesn't contain critical SF2000 files. The action you selected has been aborted for your safety.")
        return
    
    msgBox = QMessageBox()
    msgBox.setWindowTitle("Downloading Background Music")
    msgBox.setText("Now downloading Background music. Depending on your internet connection speed this may take some time, please wait patiently.")
    msgBox.show()
    if tadpole_functions.changeBackgroundMusic(drive,source):
        msgBox.close()
        QMessageBox.about(window,"Success","Background music changed successfully")
    else:
        msgBox.close()
        QMessageBox.about(window,"Failure","Something went wrong while trying to change the background music")


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
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.tbl_gamelist.cellClicked.connect(catchTableCellClicked)
        layout.addWidget(self.tbl_gamelist,rowCounter, 0, 1, -1)
    
    def create_actions(self):
        #File Menu
        self.about_action = QAction("&About", self, triggered=self.about)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q",triggered=self.close)
        #OS Menu
        self.action_changeBootLogo  = QAction("Change &Boot Logo", self, triggered=self.changeBootLogo)
        self.GBABIOSFix_action = QAction("&GBA BIOS Fix", self, triggered=self.GBABIOSFix)
        self.action_changeShortcuts = QAction("Change Game Shortcuts", self, triggered=self.changeGameShortcuts)
        self.action_removeShortcutLabels = QAction("Remove Shortcut Labels", self, triggered=self.removeShortcutLabels)
        #Background Music Menu
        self.action_DisableBackgroundMusic = QAction("&Disable", self, triggered=self.BGM_DisableBackgroundMusic)
        self.action_bgm_donkeyKong = QAction("Donkey Kong", self, triggered=self.BGM_DonkeyKong)
        self.action_bgm_pokemon = QAction("Pokemon", self, triggered=self.BGM_Pokemon)
        self.action_bgm_supermariooverworld = QAction("Super Mario Overworld", self, triggered=self.BGM_SuperMarioOverworld)
        #Console Logos
        self.action_consolelogos_Default = QAction("Restore Default", self, triggered=self.ConsoleLogos_RestoreDefault)
        self.action_consolelogos_Western = QAction("Western Logos", self, triggered=self.ConsoleLogos_WesternLogos)
        
        
    def loadMenus(self):
        self.menu_file = self.menuBar().addMenu("&File")
        self.menu_file.addAction(self.about_action)
        self.menu_file.addAction(self.exit_action)
        
        self.menu_os = self.menuBar().addMenu("&OS")
        self.menu_os.addAction(self.action_changeBootLogo)
        self.menu_os.addAction(self.GBABIOSFix_action)
        self.menu_os.addAction(self.action_changeShortcuts)
        self.menu_os.addAction(self.action_removeShortcutLabels)
        
        self.menu_bgm = self.menuBar().addMenu("&Background Music")
        self.menu_bgm.addAction(self.action_DisableBackgroundMusic)
        self.menu_bgm.addAction(self.action_bgm_donkeyKong) 
        self.menu_bgm.addAction(self.action_bgm_pokemon) 
        self.menu_bgm.addAction(self.action_bgm_supermariooverworld) 

        self.menu_consoleLogos = self.menuBar().addMenu("Console Logos")
        self.menu_consoleLogos.addAction(self.action_consolelogos_Default)
        self.menu_consoleLogos.addAction(self.action_consolelogos_Western)

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
        
    def changeBootLogo(self):
        drive = window.combobox_drive.currentText()
        newLogoFileName = QFileDialog.getOpenFileName(self, 'Open file','c:\\',"Image files (*.jpg *.png *.webp);;All Files (*.*)")[0]
        
        print(f"user tried to load image: {newLogoFileName}")
        if(newLogoFileName == None or newLogoFileName == ""):
            print("user cancelled image select")
            return
        
        try:
            tadpole_functions.changeBootLogo(f"{drive}/bios/bisrv.asd", newLogoFileName)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(self, "Change Boot Logo","An error occurred. Please ensure that you have the right drive selected and <i>bisrv.asd</i> exists in the <i>bios</i> folder")
            return
        QMessageBox.about(self, "Change Boot Logo","Boot logo successfully changed")
      
    def changeGameShortcuts(self):
        drive = window.combobox_drive.currentText()
        #Check the selected drive looks like a Frog card
        
        #Open a new modal to change the shortcuts for a specific gamename
        window.window_shortcuts = changeGameShortcutsWindow()
        window.window_shortcuts.setDrive(drive)
        window.window_shortcuts.show()
    
    def removeShortcutLabels(self):
        self.UnderDevelopmentPopup()
        
    def ConsoleLogos_RestoreDefault(self):
        self.ConsoleLogos_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/ConsoleLogos/default/sfcdr.cpl")
    
    def ConsoleLogos_WesternLogos(self):
        self.ConsoleLogos_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/ConsoleLogos/western_console_logos/sfcdr.cpl")
    
    
    def BGM_DisableBackgroundMusic(self):
        BGM_change()
    
    def BGM_Pokemon(self):
        BGM_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/BackgroundMusic/Pokemon-Theme.bgm")
        
    def BGM_DonkeyKong(self):
        BGM_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/BackgroundMusic/Donkey_Kong_Country-Aquatic_Ambience.bgm")
    
    def BGM_SuperMarioOverworld(self):
        BGM_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/BackgroundMusic/Super_Mario-Overworld_Theme.bgm")
    
    def UnderDevelopmentPopup(self):
        QMessageBox.about(self, "Developement","This feature is still under development")
        
    def ConsoleLogos_change(self, url):
        drive = window.combobox_drive.currentText()
        
        if not tadpole_functions.checkDriveLooksFroggy(drive):
            QMessageBox.about(window, "Something doesn't Look Right","The selected drive doesn't contain critical SF2000 files. The action you selected has been aborted for your safety.")
            return
    
        msgBox = QMessageBox()
        msgBox.setWindowTitle("Downloading Console Logos")
        msgBox.setText("Now downloading Console Logos. Depending on your internet connection speed this may take some time, please wait patiently.")
        msgBox.show()
        if tadpole_functions.changeConsoleLogos(drive, url):
            msgBox.close()
            QMessageBox.about(self, "Success","Console logos successfully changed")
        else:
            msgBox.close()
            QMessageBox.about(self, "Failure","ERROR: Something went wrong while trying to change the console logos")
              
        
# Subclass Qidget to create a thumbnail viewing window        
class thumbnailWindow(QWidget):
    """
        This window should be called without a parent widget so that it is created in its own window.
    """
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.thumbnail = QLabel()
        layout.addWidget(self.thumbnail)
        self.setLayout(layout)
    
    def loadThumbnail(self, filepath):
        self.setWindowTitle(f"Thumbnail - {filepath}")
        #self.thumbnail.setPixmap(QPixmap.fromImage(tadpole_functions.getThumbnailFromZXX(filepath)))

# Subclass Qidget to create a change shortcut window        
class changeGameShortcutsWindow(QWidget):
    """
        This window should be called without a parent widget so that it is created in its own window.
    """
    drive = ""
   
    def __init__(self):
        super().__init__()
        colCounter = 0
        layout = QGridLayout()
        #Console select
        self.lbl_console = QLabel(text="Console:")
        self.combobox_console = QComboBox()
        
        layout.addWidget(self.lbl_console, 0, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_console, 0, colCounter)
        colCounter += 1 
        
        #Position select
        self.lbl_shortcut = QLabel(text="Shortcut:")
        self.combobox_shortcut = QComboBox()
        layout.addWidget(self.lbl_shortcut, 0, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_shortcut, 0, colCounter)
        colCounter += 1
        
        #Game Select
        self.lbl_game = QLabel(text="Game:")
        self.combobox_games = QComboBox()
        layout.addWidget(self.lbl_game, 0, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_games, 0, colCounter)
        layout.setColumnStretch(colCounter,1)
        colCounter += 1 
        
        #Update Button Widget
        self.btn_update = QPushButton("Update!")
        layout.addWidget(self.btn_update, 0, colCounter)
        self.btn_update.clicked.connect(self.changeShortcut) 
        colCounter += 1
        
        self.setLayout(layout)
        self.setWindowTitle(f"Change System Shortcuts") 
        for console in frogtool.systems.keys():
            self.combobox_console.addItem(QIcon(),console,console)
        
        for i in range(1,5):
            self.combobox_shortcut.addItem(QIcon(),f"{i}",i)
        self.combobox_console.currentIndexChanged.connect(self.loadROMsToGameShortcutList) 
          
    
    def setDrive(self,drive):
        self.drive = drive
        self.setWindowTitle(f"Change System Shortcuts - {drive}") 
    
    def loadROMsToGameShortcutList(self,index):
        print("reloading shortcut game table")
        #TODO
        if self.drive == "":
            print("ERROR: tried to load games for shortcuts on a blank drive")
            return
        system = self.combobox_console.currentText()
        if system == "" or system == "???":
            print("ERROR: tried to load games for shortcuts on an incorrect system")
            return
        roms_path = f"{self.drive}/{system}"
        try:
            files = frogtool.getROMList(roms_path)
            self.combobox_games.clear()
            for file in files:
                self.combobox_games.addItem(QIcon(),file,file)
            #window.window_shortcuts.combobox_games.adjustSize()
        except frogtool.StopExecution:
            #Empty the table
            window.tbl_gamelist.setRowCount(0)
            
    def changeShortcut(self):
        console = self.combobox_console.currentText()
        position = int(self.combobox_shortcut.currentText()) - 1 
        game = self.combobox_games.currentText()
        if console == "" or position == "" or game == "":
            print("ERROR: There was an error due to one of the shortcut parameters being blank!")
            QMessageBox.about(self, "ERROR","One of the shortcut parameters was blank. That's not allowed for your safety.")
            return
        tadpole_functions.changeGameShortcut(f"{self.drive}",console,position,game)
        print(f"changed {console} shortcut {position} to {game} successfully")
        QMessageBox.about(window,"Success",f"changed {console} shortcut {position} to {game} successfully")
        

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
#Add ALL to the list to add this fucntionality from frogtool
window.combobox_console.addItem(QIcon(),"ALL","ALL")
for console in frogtool.systems.keys():
    window.combobox_console.addItem(QIcon(),console,console)
    




window.show()
app.exec()