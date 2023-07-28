# GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import Qt, QTimer, QUrl

# OS imports - these should probably be moved somewhere else
import os
import sys
import string
import threading
# Feature imports
import frogtool
import tadpole_functions
import requests
import wave
from io import BytesIO
import psutil
import json
import time

basedir = os.path.dirname(__file__)

static_NoDrives = "N/A"
static_AllSystems = "ALL"


def RunFrogTool():
    drive = window.combobox_drive.currentText()
    console = window.combobox_console.currentText()
    
    print(f"Running frogtool with drive ({drive}) and console ({console})")
    try:
        if(console == static_AllSystems):
            for console in frogtool.systems.keys():
                result = frogtool.process_sys(drive, console, False)
                QMessageBox.about(window, "Result", result)

        else:
            result = frogtool.process_sys(drive, console, False)
            QMessageBox.about(window, "Result", result)
    except frogtool.StopExecution:
        pass
    #loadROMsToTable()
    
def reloadDriveList():
    current_drive = window.combobox_drive.currentText()
    window.combobox_drive.clear()

    for drive in psutil.disk_partitions():
        if os.path.exists(os.path.join(drive.mountpoint, "bios", "bisrv.asd")):
            window.combobox_drive.addItem(QIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)),
                                          drive.mountpoint,
                                          drive.mountpoint)

    if len(window.combobox_drive) > 0:
        toggle_features(True)
        window.status_bar.showMessage("SF2000 Drive(s) Detected.", 20000)

    else:
        # disable functions
        window.combobox_drive.addItem(QIcon(), static_NoDrives, static_NoDrives)
        window.status_bar.showMessage("No SF2000 Drive Detected. Click refresh button to try again.", 20000)
        toggle_features(False)

    window.combobox_drive.setCurrentText(current_drive)


def toggle_features(enable: bool):
    """Toggles program features on or off"""
    features = [window.btn_update,
                window.combobox_console,
                window.combobox_drive,
                window.menu_os,
                window.menu_bgm,
                window.menu_consoleLogos,
                window.tbl_gamelist]

    for feature in features:
        feature.setEnabled(enable)

def loadROMsToTable():
    print("loading roms to table")
    drive = window.combobox_drive.currentText()
    system = window.combobox_console.currentText()
    if drive == static_NoDrives or system == "???" or system == static_AllSystems:
        return
    roms_path = os.path.join(drive, system)
    try:
        files = frogtool.getROMList(roms_path)
        window.tbl_gamelist.setRowCount(len(files))
        print(f"found {len(files)} ROMs")
        for i,f in enumerate(files):
            humanReadableFileSize = "ERROR"
            filesize = os.path.getsize(os.path.join(roms_path, f))           
            if filesize > 1024*1024:  # More than 1 Megabyte
                humanReadableFileSize = f"{round(filesize/(1024*1024),2)} MB"
            elif filesize > 1024:  # More than 1 Kilobyte
                humanReadableFileSize = f"{round(filesize/1024,2)} KB"
            else:  # Less than 1 Kilobyte
                humanReadableFileSize = f"filesize Bytes"
            window.tbl_gamelist.setItem(i, 0, QTableWidgetItem(f"{f}"))  # Filename
            window.tbl_gamelist.setItem(i, 1, QTableWidgetItem(f"{humanReadableFileSize}")) #Filesize
            window.tbl_gamelist.setItem(i, 2, QTableWidgetItem(f"view"))  # View Thumbnail Button
            window.tbl_gamelist.setItem(i, 3, QTableWidgetItem(f"change"))  # Change Thumbnail Button           
        print("finished loading roms to table")    
        # Adjust column widths
        #window.tbl_gamelist
    except frogtool.StopExecution:
        # Empty the table
        window.tbl_gamelist.setRowCount(0)
        print("frogtool stop execution on table load caught")
        
    window.tbl_gamelist.show()


def catchTableCellClicked(clickedRow, clickedColumn):
    print(f"clicked view thumbnail for {clickedRow},{clickedColumn}")
    if clickedColumn == 2:
        drive = window.combobox_drive.currentText()
        system = window.combobox_console.currentText()
        gamename = window.tbl_gamelist.item(clickedRow, 0).text()
        viewThumbnail(os.path.join(drive, system, gamename))
    elif clickedColumn == 3:
        drive = window.combobox_drive.currentText()
        system = window.combobox_console.currentText()
        gamename = window.tbl_gamelist.item(clickedRow, 0).text()
        newCoverFileName = QFileDialog.getOpenFileName(window,
                                                       'Open file',
                                                       'c:\\',
                                                       "Image files (*.jpg *.png *.webp);;All Files (*.*)")[0]
        print(f"user tried to load image: {newCoverFileName}")
        if newCoverFileName is None or newCoverFileName == "":
            print("user cancelled image select")
            return
        
        try:
            tadpole_functions.changeZXXThumbnail(os.path.join(drive, system, gamename), newCoverFileName)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(window, "Change ROM Cover", "An error occurred.")
            return
        QMessageBox.about(window, "Change ROM Cover", "ROM cover successfully changed")
        

def viewThumbnail(rom_path):
    window.window_thumbnail = thumbnailWindow()  
    window.window_thumbnail.loadThumbnail(rom_path)
    window.window_thumbnail.show()
    
def BGM_change(source=""):
    # Check the selected drive looks like a Frog card
    drive = window.combobox_drive.currentText()
    
    if not tadpole_functions.checkDriveLooksFroggy(drive):
        QMessageBox.about(window, "Something doesn't Look Right", "The selected drive doesn't contain critical \
        SF2000 files. The action you selected has been aborted for your safety.")
        return
    
    msgBox = QMessageBox()
    msgBox.setWindowTitle("Downloading Background Music")
    msgBox.setText("Now downloading Background music. Depending on your internet connection speed this may take \
    some time, please wait patiently.")
    msgBox.show()
    if tadpole_functions.changeBackgroundMusic(drive,source):
        msgBox.close()
        QMessageBox.about(window,"Success", "Background music changed successfully")
    else:
        msgBox.close()
        QMessageBox.about(window,"Failure", "Something went wrong while trying to change the background music")


class BootLogoViewer(QLabel):
    """
    Args:
        parent (BootConfirmDialog): Parent widget. Used to enable/disable controls on parent.
        changeable (bool): If True, will allow importing new image. If False, will just allow static display.
    """
    def __init__(self, parent, changeable=False):
        super().__init__(parent)

        self.changeable = changeable
        self.path = ""  # Used to store path to the currently-displayed file

        self.setStyleSheet("background-color: white;")
        self.setMinimumSize(512, 200)  # resize to Froggy boot logo dimensions

        if self.changeable:
            self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.setText("Click to Select New Image")

    def mousePressEvent(self, ev):
        """
        Overrides built-in function to handle mouse click events. Prompts user for image path and loads same.
        """
        if self.changeable:  # only do something if image is changeable
            file_name = QFileDialog.getOpenFileName(self, 'Open file', '',
                                                    "Images (*.jpg *.png *.webp);;RAW (RGB565 Little Endian) Images (*.raw)")[0]
            if len(file_name) > 0:  # confirm if user selected a file
                self.load_image(file_name)

    def load_from_bios(self, drive: str):
        """
        Extracts image from the bios and passes to load image function.

        Args:
            drive (str):  Path to the root of the Froggy drive.
        """
        with open(os.path.join(drive, "bios", "bisrv.asd"), "rb") as bios_file:
            bios_content = bytearray(bios_file.read())

        offset = tadpole_functions.findSequence(tadpole_functions.offset_logo_presequence, bios_content) + 16
        with open(os.path.join(basedir, "bios_image.raw"), "wb") as image_file:
            image_file.write(bios_content[offset:offset+((512*200)*2)])

        self.load_image(os.path.join(basedir, "bios_image.raw"))

    def load_image(self, path: str) -> bool:
        """
        Loads an image into the viewer.  If the image is loaded successfully, may enable the parent Save button based
        on the changeable flag.

        Args:
            path (str): Path to the image.  Can be .raw or other format.  If .raw, assumed to be in RGB16 (RGB565 Little
                Endian) format used for Froggy boot logos.  Must be 512x200 pixels or it will not be accepted/displayed.

        Returns:
            bool: True if image was loaded, False if not.
        """
        if os.path.splitext(path)[1] == ".raw":  # if raw image, assume RGB16 (RGB565 Little Endian)
            with open(path, "rb") as f:
                img = QImage(f.read(), 512, 200, QImage.Format_RGB16)
        else:  # otherwise let QImage autodetection do its thing
            img = QImage(path)
            if (img.width(), img.height()) != (512, 200):  # check to determine if image is appropriate size
                self.setText("Image dimensions are wrong.  Should be 512x200.  Click to try again.")
                self.parent().button_save.setDisabled(True)  # disable saving
                return False
        self.path = path  # update path
        self.setPixmap(QPixmap().fromImage(img))

        if self.changeable:  # only enable saving for changeable dialogs; prevents enabling with load from bios
            self.parent().button_save.setDisabled(False)
        return True


class BootConfirmDialog(QDialog):
    """
    Dialog used to confirm boot logo selection with the ability to view existing selection and replacement.

    Args:
        drive (str): Path to root of froggy drive.
    """
    def __init__(self, drive):
        super().__init__()

        self.drive = drive

        self.setWindowTitle("Boot Image Selection")
        self.setWindowIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)))

        # Setup Main Layout
        self.layout_main = QVBoxLayout()
        self.setLayout(self.layout_main)

        # set up current image viewer
        self.layout_main.addWidget(QLabel("Current Image"))
        self.current_viewer = BootLogoViewer(self)
        self.layout_main.addWidget(self.current_viewer)

        self.layout_main.addWidget(QLabel(" "))  # spacer

        # set up new image viewer
        self.layout_main.addWidget(QLabel("New Image"))
        self.new_viewer = BootLogoViewer(self, changeable=True)
        self.layout_main.addWidget(self.new_viewer)

        # Main Buttons Layout (Save/Cancel)
        self.layout_buttons = QHBoxLayout()
        self.layout_main.addLayout(self.layout_buttons)

        # Save Button
        self.button_save = QPushButton("Save")
        self.button_save.setDefault(True)
        self.button_save.setDisabled(True)  # set disabled by default; need to wait for user to select new image
        self.button_save.clicked.connect(self.accept)
        self.layout_buttons.addWidget(self.button_save)

        # Cancel Button
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.reject)
        self.layout_buttons.addWidget(self.button_cancel)

        # Load Initial Image
        self.current_viewer.load_from_bios(self.drive)


class MusicConfirmDialog(QDialog):
    """Dialog used to confirm music selection with the ability to preview selection by listening to the music.

        Args:
            music_name (str) : Name of the music file; used only to show name in dialog
            music_url (str) : URL to a raw music file; should be formatted for use on SF2000 (raw signed 16-bit PCM,
                mono, little-endian, 22050 hz)
    """
    def __init__(self, music_name: str, music_url: str):
        super().__init__()

        # Save Arguments
        self.music_name = music_name
        self.music_url = music_url

        # Configure Window
        self.setWindowTitle("Confirm Music Change")
        self.setWindowIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)))
        self.sound = QSoundEffect(self)  # Used to Play Music File

        # Setup Main Layout
        self.layout_main = QVBoxLayout()
        self.setLayout(self.layout_main)

        # Main Text
        self.label_confirm = QLabel("<h3>Change Background Music</h3><em>{}</em>".format(self.music_name),
                                    self)
        self.label_confirm.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.layout_main.addWidget(self.label_confirm)

        # Music Preview Button
        self.button_play = QPushButton(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)),
                                       " Preview",
                                       self)
        self.layout_main.addWidget(self.button_play)
        self.button_play.clicked.connect(self.toggle_audio)

        # Main Buttons Layout (Save/Cancel)
        self.layout_buttons = QHBoxLayout()
        self.layout_main.addLayout(self.layout_buttons)

        # Save Button
        self.button_save = QPushButton("Save")
        self.button_save.setDefault(True)
        self.button_save.clicked.connect(self.accept)
        self.layout_buttons.addWidget(self.button_save)

        # Cancel Button
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.reject)
        self.layout_buttons.addWidget(self.button_cancel)

    def toggle_audio(self) -> bool:
        """toggles music preview on or off

            Returns:
                bool: True if file is playing; false if not
        """
        if self.sound.isPlaying():
            self.sound.stop()
            self.button_play.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)))
            self.button_play.setText(" Preview")
            return False

        else:
            if not self.sound.source().path():  # download and convert raw file if not already done
                self.button_play.setDisabled(True)  # disable button while downloading
                file_name = self.get_and_format_music_file()
                if file_name:  # download and conversion succeeds
                    self.sound.setSource(QUrl.fromLocalFile(file_name))
                    self.button_play.setDisabled(False)
                else:  # download and conversion fails
                    self.button_play.setText(" Download Failed")
                    self.button_play.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)))
                    return False

            # format button and play
            self.button_play.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)))
            self.button_play.setText(" Stop")
            self.sound.setLoopCount(1000)
            self.sound.play()
            return True

    def get_and_format_music_file(self) -> str or bool:
        """Downloads and re-formats the raw music file as wav.

            Returns:
                str or bool: path to resulting temporary wav file, or False if download fails
        """
        try:
            r = requests.get(self.music_url)
            if r.status_code == 200:  # download succeeds
                raw_data = BytesIO(r.content)  # read raw file into memory
                wav_filename = os.path.join(basedir, "preview.wav")
                with wave.open(wav_filename, "wb") as wav_file:
                    wav_file.setparams((1, 2, 22050, 0, 'NONE', 'NONE'))
                    wav_file.writeframes(raw_data.read())
                return wav_filename
            return False
        except requests.exceptions.RequestException:  # catches exceptions for multiple reasons
            return False


# SubClass QMainWindow to create a Tadpole general interface
class MainWindow (QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tadpole - SF2000 Tool")
        self.setWindowIcon(QIcon(os.path.join(basedir, 'frog.ico')))

        widget = QWidget()
        self.setCentralWidget(widget)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Load the Menus
        self.create_actions()
        self.loadMenus()

        # Create Layouts
        layout = QVBoxLayout(widget)
        selector_layout = QHBoxLayout(widget)
        layout.addLayout(selector_layout)

        # Drive Select Widgets
        self.lbl_drive = QLabel(text="Drive:")
        self.lbl_drive.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.combobox_drive = QComboBox()
        self.combobox_drive.activated.connect(loadROMsToTable)
        self.btn_refreshDrives = QPushButton()
        self.btn_refreshDrives.setIcon(self.style().standardIcon(getattr(QStyle, "SP_BrowserReload")))
        self.btn_refreshDrives.clicked.connect(reloadDriveList)
        selector_layout.addWidget(self.lbl_drive)
        selector_layout.addWidget(self.combobox_drive, stretch=1)
        selector_layout.addWidget(self.btn_refreshDrives)

        # Spacer
        selector_layout.addWidget(QLabel(" "), stretch=2)

        # Console Select Widgets
        self.lbl_console = QLabel(text="Console:")
        self.lbl_console.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.combobox_console = QComboBox()
        self.combobox_console.activated.connect(loadROMsToTable)
        selector_layout.addWidget(self.lbl_console)
        selector_layout.addWidget(self.combobox_console, stretch=1)
        
        # Update Button Widget
        self.btn_update = QPushButton("Update!")
        selector_layout.addWidget(self.btn_update)
        self.btn_update.clicked.connect(RunFrogTool)

        # Game Table Widget
        self.tbl_gamelist = QTableWidget()
        self.tbl_gamelist.setColumnCount(4)
        self.tbl_gamelist.setHorizontalHeaderLabels(["Name", "Size", "Thumbnail", "Actions"])
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_gamelist.cellClicked.connect(catchTableCellClicked)
        layout.addWidget(self.tbl_gamelist)

        # Reload Drives Timer
        self.timer = QTimer()
        self.timer.timeout.connect(reloadDriveList)
        self.timer.start(1000)
    
    def create_actions(self):
        # File Menu
        self.about_action = QAction("&About", self, triggered=self.about)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q",triggered=self.close)

        # OS Menu
        self.action_updateToV1_5  = QAction("V1.5", self, triggered=self.UpdatetoV1_5)                                                                              
        self.action_changeBootLogo  = QAction("&Boot Logo", self, triggered=self.changeBootLogo)
        self.GBABIOSFix_action = QAction("&GBA BIOS Fix", self, triggered=self.GBABIOSFix)
        self.action_changeShortcuts = QAction("Change Game Shortcuts", self, triggered=self.changeGameShortcuts)
        self.action_removeShortcutLabels = QAction("Remove Shortcut Labels", self, triggered=self.removeShortcutLabels)

        # Console Logos
        self.action_consolelogos_Default = QAction("Restore Default", self, triggered=self.ConsoleLogos_RestoreDefault)
        self.action_consolelogos_Western = QAction("Western Logos", self, triggered=self.ConsoleLogos_WesternLogos)

    def loadMenus(self):
        self.menu_file = self.menuBar().addMenu("&File")
        self.menu_file.addAction(self.about_action)
        self.menu_file.addAction(self.exit_action)
        
        self.menu_os = self.menuBar().addMenu("&OS")
        self.menu_os.menu_update = self.menu_os.addMenu("Update")
        self.menu_os.menu_update.addAction(self.action_updateToV1_5)                                                         
        self.menu_os.addAction(self.action_changeBootLogo)
        self.menu_os.addAction(self.GBABIOSFix_action)
        self.menu_os.addAction(self.action_changeShortcuts)
        self.menu_os.addAction(self.action_removeShortcutLabels)

        # Background Music Menu
        self.menu_bgm = self.menuBar().addMenu("&Background Music")
        try:
            self.music_options = tadpole_functions.get_background_music()
        except (ConnectionError, requests.exceptions.ConnectionError):
            self.status_bar.showMessage("Error loading external music resources.", 20000)
            error_action = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)),
                                   "Error Loading External Resources!",
                                   self)
            error_action.setDisabled(True)
            self.menu_bgm.addAction(error_action)
        else:
            for music in self.music_options:
                self.menu_bgm.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)),
                                                music,
                                                self,
                                                triggered=self.change_background_music))

        self.menu_consoleLogos = self.menuBar().addMenu("Console Logos")
        self.menu_consoleLogos.addAction(self.action_consolelogos_Default)
        self.menu_consoleLogos.addAction(self.action_consolelogos_Western)

    def change_background_music(self):
        """event to change background music"""
        d = MusicConfirmDialog(self.sender().text(), self.music_options[self.sender().text()])
        if d.exec():
            BGM_change(self.music_options[self.sender().text()])

    def about(self):
        QMessageBox.about(self, "About Tadpole", 
                                "Tadpole was created by EricGoldstein based on the original work \
from tzlion on frogtool. Special thanks also goes to wikkiewikkie for many amazing improvements")

    def GBABIOSFix(self):
        drive = window.combobox_drive.currentText()
        try:
            tadpole_functions.GBABIOSFix(drive)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(self, "GBA BIOS Fix", "An error occurred. Please ensure that you have the right drive \
            selected and <i>gba_bios.bin</i> exists in the <i>bios</i> folder")
            return
        QMessageBox.about(self, "GBA BIOS Fix", "BIOS successfully copied")
        
    def changeBootLogo(self):
        dialog = BootConfirmDialog(window.combobox_drive.currentText())
        change = dialog.exec()
        if change:
            newLogoFileName = dialog.new_viewer.path
            print(f"user tried to load image: {newLogoFileName}")
            if newLogoFileName is None or newLogoFileName == "":
                print("user cancelled image select")
                return

            try:
                tadpole_functions.changeBootLogo(os.path.join(window.combobox_drive.currentText(),
                                                              "bios",
                                                              "bisrv.asd"),
                                                 newLogoFileName)
            except tadpole_functions.Exception_InvalidPath:
                QMessageBox.about(self, "Change Boot Logo", "An error occurred. Please ensure that you have the right \
                drive selected and <i>bisrv.asd</i> exists in the <i>bios</i> folder")
                return
            QMessageBox.about(self, "Change Boot Logo", "Boot logo successfully changed")
      
    def changeGameShortcuts(self):
        drive = window.combobox_drive.currentText()
        # Check the selected drive looks like a Frog card
        
        # Open a new modal to change the shortcuts for a specific gamename
        window.window_shortcuts = changeGameShortcutsWindow()
        window.window_shortcuts.setDrive(drive)
        window.window_shortcuts.show()
    
    def removeShortcutLabels(self):
        self.UnderDevelopmentPopup()
        
    def ConsoleLogos_RestoreDefault(self):
        self.ConsoleLogos_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/ConsoleLogos/default/sfcdr.cpl")
    
    def ConsoleLogos_WesternLogos(self):
        self.ConsoleLogos_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/ConsoleLogos/western_console_logos/sfcdr.cpl")

    def UnderDevelopmentPopup(self):
        QMessageBox.about(self, "Development", "This feature is still under development")
        
    def ConsoleLogos_change(self, url):
        drive = window.combobox_drive.currentText()
        
        if not tadpole_functions.checkDriveLooksFroggy(drive):
            QMessageBox.about(window, "Something doesn't Look Right", "The selected drive doesn't contain critical \
            SF2000 files. The action you selected has been aborted for your safety.")
            return
    
        msgBox = QMessageBox()
        msgBox.setWindowTitle("Downloading Console Logos")
        msgBox.setText("Now downloading Console Logos. Depending on your internet connection speed this may take some \
        time, please wait patiently.")
        msgBox.show()
        if tadpole_functions.changeConsoleLogos(drive, url):
            msgBox.close()
            QMessageBox.about(self, "Success", "Console logos successfully changed")
        else:
            msgBox.close()
            QMessageBox.about(self, "Failure", "ERROR: Something went wrong while trying to change the console logos")

    def UpdatetoV1_5(self):
        drive = window.combobox_drive.currentText()
        url = "https://api.github.com/repos/EricGoldsteinNz/SF2000_Resources/contents/OS/V1.5"
        
        msgBox = QMessageBox()
        msgBox.setWindowTitle("Downloading Console Logos")
        msgBox.setText("Now downloading Console Logos. Depending on your internet connection speed this may take some time, please wait patiently.")
        msgBox.show()
        if tadpole_functions.downloadDirectoryFromGithub(drive, url):
            msgBox.close()
            QMessageBox.about(self, "Success","Update successfully Downloaded")
        else:
            msgBox.close()
            QMessageBox.about(self, "Failure","ERROR: Something went wrong while trying to download the update")
            
        
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
        # self.thumbnail.setPixmap(QPixmap.fromImage(tadpole_functions.getThumbnailFromZXX(filepath)))


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
        # Console select
        self.lbl_console = QLabel(text="Console:")
        self.combobox_console = QComboBox()
        
        layout.addWidget(self.lbl_console, 0, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_console, 0, colCounter)
        colCounter += 1 
        
        # Position select
        self.lbl_shortcut = QLabel(text="Shortcut:")
        self.combobox_shortcut = QComboBox()
        layout.addWidget(self.lbl_shortcut, 0, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_shortcut, 0, colCounter)
        colCounter += 1
        
        # Game Select
        self.lbl_game = QLabel(text="Game:")
        self.combobox_games = QComboBox()
        layout.addWidget(self.lbl_game, 0, colCounter)
        colCounter += 1
        layout.addWidget(self.combobox_games, 0, colCounter)
        layout.setColumnStretch(colCounter,1)
        colCounter += 1 
        
        # Update Button Widget
        self.btn_update = QPushButton("Update!")
        layout.addWidget(self.btn_update, 0, colCounter)
        self.btn_update.clicked.connect(self.changeShortcut) 
        colCounter += 1
        
        self.setLayout(layout)
        self.setWindowTitle(f"Change System Shortcuts") 
        for console in frogtool.systems.keys():
            self.combobox_console.addItem(QIcon(), console,console)
        
        for i in range(1,5):
            self.combobox_shortcut.addItem(QIcon(), f"{i}", i)
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
        roms_path = os.path.join(self.drive, system)
        try:
            files = frogtool.getROMList(roms_path)
            self.combobox_games.clear()
            for file in files:
                self.combobox_games.addItem(QIcon(),file,file)
            # window.window_shortcuts.combobox_games.adjustSize()
        except frogtool.StopExecution:
            # Empty the table
            window.tbl_gamelist.setRowCount(0)
            
    def changeShortcut(self):
        console = self.combobox_console.currentText()
        position = int(self.combobox_shortcut.currentText()) - 1 
        game = self.combobox_games.currentText()
        if console == "" or position == "" or game == "":
            print("ERROR: There was an error due to one of the shortcut parameters being blank!")
            QMessageBox.about(self, "ERROR", "One of the shortcut parameters was blank. That's not allowed for your \
            safety.")
            return
        tadpole_functions.changeGameShortcut(f"{self.drive}", console, position,game)
        print(f"changed {console} shortcut {position} to {game} successfully")
        QMessageBox.about(window, "Success", f"changed {console} shortcut {position} to {game} successfully")
        

# Initialise the Application
app = QApplication(sys.argv)

# Build the Window
window = MainWindow()

# Update list of drives
window.combobox_drive.addItem(QIcon(), static_NoDrives, static_NoDrives)
reloadDriveList()

# Update list of consoles
available_consoles_placeholder = "???"
window.combobox_console.addItem(QIcon(), available_consoles_placeholder, available_consoles_placeholder)
window.combobox_console.clear()
# Add ALL to the list to add this fucntionality from frogtool
window.combobox_console.addItem(QIcon(), static_AllSystems, static_AllSystems)
for console in frogtool.systems.keys():
    window.combobox_console.addItem(QIcon(), console, console)
    
window.show()
app.exec()
