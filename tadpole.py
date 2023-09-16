# GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize
# OS imports - these should probably be moved somewhere else
import os
import sys
import string
import threading
import queue
import shutil
import hashlib
# Feature imports
import frogtool
import tadpole_functions
import requests
import wave
from io import BytesIO
import psutil
import json
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from datetime import datetime
from pathlib import Path
import configparser
import webbrowser
import logging

basedir = os.path.dirname(__file__)
static_NoDrives = "N/A"
static_AllSystems = "ALL"
static_LoggingPath = "tadpole.log" # Log to the local directory that tadpole is being run from.
static_TadpoleConfigFile = os.path.join("Tadpole","tapdole.ini")

def RunFrogTool(console):
    drive = window.combobox_drive.currentText()
    print(f"Running frogtool with drive ({drive}) and console ({console})")
    logging.info(f"Running frogtool with drive ({drive}) and console ({console})")
    try:
        #TODO: should probably replace this with rebuilding the favourites list at some point
        #NOTE: Eric, I think its a better experience to not nuke these.  
        #NOTE: if the user deletes a favorited ROM, the system fails gravcefully.  Deleting each time is rough on user
        #tadpole_functions.emptyFavourites(drive)
        #tadpole_functions.emptyHistory(drive)
        if(console == static_AllSystems):
            #Give progress to user if rebuilding has hundreds of ROMS
            rebuildingmsgBox = DownloadMessageBox()
            rebuildingmsgBox.progress.reset()
            rebuildingmsgBox.setText("Rebuilding roms...")
            progress = 20
            rebuildingmsgBox.showProgress(progress, True)
            rebuildingmsgBox.show()
            for console in frogtool.systems.keys():
                result = frogtool.process_sys(drive, console, False)
                #Update Progress
                progress += 10
                rebuildingmsgBox.showProgress(progress, True)
            #TODO: eventually we could return a total roms across all systems, but not sure users will care
            rebuildingmsgBox.close()
            QMessageBox.about(window, "Result", "Rebuilt all ROMS for all systems")
        else:
            result = frogtool.process_sys(drive, console, False)
            print("Result " + result)      
        #Always reload the table now that the folders are all cleaned up
        loadROMsToTable()
    except frogtool.StopExecution:
        pass

def processGameShortcuts():
    drive = window.combobox_drive.currentText()
    console = window.combobox_console.currentText()
    for i in range(window.tbl_gamelist.rowCount()):
        comboBox = window.tbl_gamelist.cellWidget(i, 3)
        #if its blank, it doesn't have a position so move on
        if comboBox.currentText() == '':
            continue
        else:
            position = int(comboBox.currentText())
            #position is 0 based
            position = position - 1
            game = window.tbl_gamelist.item(i, 0).text()
            #print(drive + " " + console + " " + str(position) + " "+ game)
            tadpole_functions.changeGameShortcut(drive, console, position, game)

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
        #Eric: Need to check in with Jason on why this was removed.
        if(current_drive == static_NoDrives):
            print("New drive detected")
            logging.info(f"Automatically triggering drive change because a new drive connected")
            window.combobox_drive_change()
    else:
        # disable functions
        window.combobox_drive.addItem(QIcon(), static_NoDrives, static_NoDrives)
        window.status_bar.showMessage("No SF2000 Drive Detected. Please insert SD card and try again.", 20000)
        toggle_features(False)

    window.combobox_drive.setCurrentText(current_drive)

def toggle_features(enable: bool):
    """Toggles program features on or off"""
    features = [window.btn_update_thumbnails,
                window.btn_update,
                window.btn_update_shortcuts_images,
                window.combobox_console,
                window.combobox_drive,
                window.menu_os,
                #window.menu_bgm,
                #window.menu_consoleLogos,
                #window.menu_boxart,
                window.menu_roms,
                window.tbl_gamelist]
    for feature in features:
        feature.setEnabled(enable)

#NOTE: this function refreshes the ROM table.  If you run this AND NOT FROG_TOOL, you can get your window out of sync
#NOTE: So don't run loadROMsToTable, instead run FrogTool
def loadROMsToTable():
    drive = window.combobox_drive.currentText()
    system = window.combobox_console.currentText()
    print(f"loading roms to table for ({drive}) ({system})")
    logging.info(f"loading roms to table for ({drive}) ({system})")
    msgBox = DownloadMessageBox()
    msgBox.setText(" Loading "+ system + " ROMS...")
    if drive == static_NoDrives or system == "???" or system == static_AllSystems:
        #TODO: should load ALL ROMs to the table rather than none
        window.tbl_gamelist.setRowCount(0)
        return
    roms_path = os.path.join(drive, system)
    try:
        files = frogtool.getROMList(roms_path)
        msgBox.progress.reset()
        msgBox.progress.setMaximum(len(files))
        msgBox.show()
        QApplication.processEvents()
        window.tbl_gamelist.setRowCount(len(files))
        print(f"found {len(files)} ROMs")
        #sort the list aphabetically before we go through it
        files = sorted(files)
        for i,game in enumerate(files):
            filesize = os.path.getsize(os.path.join(roms_path, game))
            humanReadableFileSize = tadpole_functions.getHumanReadableFileSize(filesize)
            # Filename
            cell_filename = QTableWidgetItem(f"{game}")
            cell_filename.setTextAlignment(Qt.AlignVCenter)
            cell_filename.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
            window.tbl_gamelist.setItem(i, 0, cell_filename)  
            #Filesize
            cell_fileSize = QTableWidgetItem(f"{humanReadableFileSize}")
            cell_fileSize.setTextAlignment(Qt.AlignCenter)
            cell_fileSize.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
            window.tbl_gamelist.setItem(i, 1, cell_fileSize) 
            # View Thumbnail 
            #Show picture if thumbnails in View is selected
            config = configparser.ConfigParser()
            config.read(drive + "/Resources/tadpole.ini")
            if config.getboolean('thumbnails', 'view'):
                cell_viewthumbnail = QTableWidgetItem()
                cell_viewthumbnail.setTextAlignment(Qt.AlignCenter)
                pathToROM = os.path.join(roms_path, game)
                extension = Path(pathToROM).suffix
                #only show thumbnails of the .z** files 
                sys_zxx_ext = '.' + frogtool.zxx_ext[system]
                if(extension == sys_zxx_ext):
                    with open(pathToROM, "rb") as rom_file:
                        rom_content = bytearray(rom_file.read())
                    with open(os.path.join(basedir, "temp_rom_cover.raw"), "wb") as image_file:
                        image_file.write(rom_content[0:((144*208)*2)])
                        with open(pathToROM, "rb") as f:
                            img = QImage(f.read(), 144, 208, QImage.Format_RGB16)
                    pimg = QPixmap()
                    icon = QIcon()
                    QPixmap.convertFromImage(pimg, img)
                    QIcon.addPixmap(icon, pimg)
                    cell_viewthumbnail.setIcon(icon)
                    size = QSize(144, 208)
                    window.tbl_gamelist.setIconSize(size)
                    cell_viewthumbnail.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
                    window.tbl_gamelist.setItem(i, 2, cell_viewthumbnail)
                else:
                    cell_viewthumbnail = QTableWidgetItem(f"\nNo thumbnail\n Click to edit\n")
                    cell_viewthumbnail.setTextAlignment(Qt.AlignCenter)
                    cell_viewthumbnail.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
                    window.tbl_gamelist.setItem(i, 2, cell_viewthumbnail)   
                    #except OSError:
                    #logging.exception("main crashed. Error: %s", OSError)
            else:
                cell_viewthumbnail = QTableWidgetItem(f"View")
                cell_viewthumbnail.setTextAlignment(Qt.AlignCenter)
                cell_viewthumbnail.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
                window.tbl_gamelist.setItem(i, 2, cell_viewthumbnail)   
            # Add to Shortcuts-
            shortcut_comboBox = QComboBox()
            shortcut_comboBox.addItem("")
            shortcut_comboBox.addItem("1")
            shortcut_comboBox.addItem("2")
            shortcut_comboBox.addItem("3")
            shortcut_comboBox.addItem("4")
            # set previously saved shortcuts
            position = tadpole_functions.getGameShortcutPosition(drive, system, game)
            shortcut_comboBox.setCurrentIndex(position)
            # get a callback to make sure the user isn't setting the same shortcut twice
            window.tbl_gamelist.setCellWidget(i, 3, shortcut_comboBox)
            shortcut_comboBox.activated.connect(window.validateGameShortcutComboBox)

            # View Delete Button 
            cell_delete = QTableWidgetItem(f"Delete")
            cell_delete.setTextAlignment(Qt.AlignCenter)
            cell_delete.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
            window.tbl_gamelist.setItem(i, 4, cell_delete)
            # Update progressbar
            msgBox.showProgress(i, False)
        window.tbl_gamelist.resizeRowsToContents()

        print("finished loading roms to table")    
    except frogtool.StopExecution:
        # Empty the table
        window.tbl_gamelist.setRowCount(0)
        print("frogtool stop execution on table load caught")
    msgBox.close()  
    window.tbl_gamelist.scrollToTop()
    window.tbl_gamelist.show()

def RebuildClicked(self):
    console = window.combobox_console.currentText()
    RunFrogTool(console)
    return

def catchTableCellClicked(clickedRow, clickedColumn):
    print(f"clicked view thumbnail for {clickedRow},{clickedColumn}")
    drive = window.combobox_drive.currentText()
    system = window.combobox_console.currentText()
    gamename = window.tbl_gamelist.item(clickedRow, 0)

    if window.tbl_gamelist.horizontalHeaderItem(clickedColumn).text() == "Thumbnail":  
        #gamename = window.tbl_gamelist.item(clickedRow, 0).text()
        viewThumbnail(os.path.join(drive + system, gamename.text()))
    elif window.tbl_gamelist.horizontalHeaderItem(clickedColumn).text() == "Delete ROM": 
        #gamename = window.tbl_gamelist.item(clickedRow, 0).text()
        deleteROM(os.path.join(drive + system, gamename.text()))
    #Only enable deleting when selcted
    if clickedColumn == 0:
        selected = window.tbl_gamelist.selectedItems()
        if selected:
            window.btn_delete_roms.setEnabled(True)
        else:
            window.btn_delete_roms.setEnabled(False)
    else:
        window.btn_delete_roms.setEnabled(False)


def headerClicked(column):
    #Only enable deleting when selcted
    if column == 0:
        selected = window.tbl_gamelist.selectedItems()
        if selected:
            window.btn_delete_roms.setEnabled(True)
        else:
            window.btn_delete_roms.setEnabled(False)
    else:
        window.btn_delete_roms.setEnabled(False)

def viewThumbnail(rom_path):
    window.window_thumbnail = thumbnailWindow(rom_path)  
    result = window.window_thumbnail.exec()
    system = window.combobox_console.currentText()
    if result:
        newLogoFileName = window.window_thumbnail.new_viewer.path
        print(f"user tried to load image: {newLogoFileName}")
        if newLogoFileName is None or newLogoFileName == "":
            print("user cancelled image select")
            return
        try:
            if(rom_path.endswith('.zip')):
                tadpole_functions.changeZIPThumbnail(rom_path, newLogoFileName, system)
            else:
                tadpole_functions.changeZXXThumbnail(rom_path, newLogoFileName)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(window, "Change ROM Cover", "An error occurred.")
            return
        QMessageBox.about(window, "Change ROM Logo", "ROM cover successfully changed")
        RunFrogTool(window.combobox_console.currentText())

def deleteROM(rom_path):
    qm = QMessageBox
    ret = qm.question(window,'Delete ROM?', "Are you sure you want to delete " + rom_path +" and rebuild the ROM list? " , qm.Yes | qm.No)
    if ret == qm.Yes:
        try:
            os.remove(rom_path)
        except Exception:
            QMessageBox.about(window, "Error","Could not delete file.")
        RunFrogTool(window.combobox_console.currentText())
    return

def addToShortcuts(rom_path):
    qm = QMessageBox
    qm.setText("Time to set the rompath!")

def BGM_change(source=""):
    # Check the selected drive looks like a Frog card
    drive = window.combobox_drive.currentText()
    
    if not tadpole_functions.checkDriveLooksFroggy(drive):
        QMessageBox.about(window, "Something doesn't Look Right", "The selected drive doesn't contain critical \
        SF2000 files. The action you selected has been aborted for your safety.")
        return

    msg_box = DownloadMessageBox()
    msg_box.setText("Downloading background music.")
    msg_box.show()
    msg_box.showProgress(25, True)

    if source[0:4] == "http":  # internet-based
        result = tadpole_functions.changeBackgroundMusic(drive, url=source)
    else:  # local resource
        result = tadpole_functions.changeBackgroundMusic(drive, file=source)

    if result:
        msg_box.close()
        QMessageBox.about(window, "Success", "Background music changed successfully")
    else:
        msg_box.close()
        QMessageBox.about(window, "Failure", "Something went wrong while trying to change the background music")

def FirstRun(self):

    #Setup settings
    config = configparser.ConfigParser()
    drive = window.combobox_drive.currentText()
    logging.info("First Run started.  This means its either brand new, deleted ini file, or something else")
    bootloaderPatchDir = os.path.join(drive,"/UpdateFirmware/")
    bootloaderPatchPathFile = os.path.join(drive,"/UpdateFirmware/Firmware.upk")
    bootloaderChecksum = "eb7a4e9c8aba9f133696d4ea31c1efa50abd85edc1321ce8917becdc98a66927"
    if drive == "N/A":
        QMessageBox().about(window, "Insert SD Card", "Your SD card must be plugged into the computer on first launch of Tadpole.\n\n\
Please insert the SD card and relaunch Tadpole.exe.  The application will now close.")
        sys.exit()
    qm = QMessageBox()
    ret = qm.information(window,'Welcome', "Welcome to Tadpole!\n\n\
Either this is your first time or this is a new version of Tadpole.  Either way, we are glad you are here!\n\n\
It is advised to update the bootloader to avoid bricking the SF2000 when changing anything on the SD card.\n\n\
Do you want to download and apply the bootloader fix? (Select No if you have already applied the fix previously.)", qm.Yes | qm.No)
    if ret == qm.Yes:
        #Let's delete old stuff if it exits incase they tried this before and failed
        if Path(bootloaderPatchDir).is_dir():
            shutil.rmtree(bootloaderPatchDir)
        os.mkdir(bootloaderPatchDir)
        #Download file, and continue if its successful
        if tadpole_functions.downloadFileFromGithub(bootloaderPatchPathFile, "https://github.com/EricGoldsteinNz/SF2000_Resources/blob/60659cc783263614c20a60f6e2dd689d319c04f6/OS/Firmware.upk?raw=true"):
            #check file correctly download
            with open(bootloaderPatchPathFile, 'rb', buffering=0) as f:
                downloadedchecksum = hashlib.file_digest(f, 'sha256').hexdigest()
            #check if the hash matches
            print("Checking if " + bootloaderChecksum + " matches " + downloadedchecksum)
            if bootloaderChecksum != downloadedchecksum:
                QMessageBox().about(window, "Update not successful", "The downloaded file did not download correctly.\n\
Please try the instructions again.\
Consult https://github.com/vonmillhausen/sf2000#bootloader-bug\n\
or ask for help on Discord https://discord.gg/retrohandhelds.  The app will now close.")
                sys.exit()
            ret = QMessageBox().warning(window, "Bootloader Fix", "Downloaded bootloader to SD card.\n\n\
You can keep this window open while you appy the fix:\n\
1. Eject the SD card from your computer\n\
2. Put the SD back in the SF2000)\n\
3. Turn the SF2000 on\n\
4. You should see a message in the lower-left corner of the screen indicating that patching is taking place.\n\
5. The process will only last a few seconds\n\
6. You should see the main menu on the SF2000\n\
7. Power off the SF2000\n\
8. Remove the SD card \n\
9. Connect the SD card back to your computer \n\n\
Did the update complete successfully?", qm.Yes | qm.No)
            if Path(bootloaderPatchDir).is_dir():
                shutil.rmtree(bootloaderPatchDir)
            if ret == qm.Yes:
                QMessageBox().about(window, "Update complete", "Your SF2000 should now be safe to use with \
Tadpole. Major thanks to osaka#9664 on RetroHandhelds Discords for this fix!\n\n\
Tadpole will not ask you again to fix the bootloader. If you want to reset Tadpole, delete the file 'Resources/tadpole.ini")
                logging.info("Bootloader installed correctly...or so the user says")
                config['bootloader'] = {'patchapplied': True}
            else:
                QMessageBox().about(window, "Update not successful", "Please try the instructions again.\
Consult https://github.com/vonmillhausen/sf2000#bootloader-bug\n\
or ask for help on Discord https://discord.gg/retrohandhelds.  The app will now close.")
                logging.error("Bootloader failed to install...or so the user says")
                sys.exit()
        else:
            QMessageBox().about(window, "Download did not complete", "Please ensure you have internet and re-open the app")
            logging.error("Bootloader failed to download")
            sys.exit()
    else:
        config['bootloader'] = {'patchskipped': True}
        logging.info("User skipped bootloader")
    #Write default values on first run
    tadpole_functions.writeDefaultSettings(drive)

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
            if (img.width(), img.height()) != (512, 200): 
                img = img.scaled(512, 200, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) #Rescale new boot logo to correct size
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

class GameShortcutIconsDialog(QDialog):
    """
    Dialog used to upload game shortcut with the ability to view existing selection and replacement.

    Args:
        drive (str): Path to root of froggy drive.
    """
    def __init__(self):
        super().__init__()
        self.drive = window.combobox_drive.currentText()
        self.console = window.combobox_console.currentText()
        self.roms_path = os.path.join(self.drive, self.console)
        #This is the file we will use while modifying the existing resource file
        self.workingPNGPath = 'currentBackground.temp.png'
        #This is the working image we will use while modifying existing resource files
        self.backgroundImage = QLabel(self)
        #Setup a variable to access the current game shortcuts on the system
        self.game_shortcut_list = ["No Game", "No Game", "No Game", "No Game"]
        #Set UI on dialog
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.setWindowTitle("Game Shortcut Icon Selection")
        self.setWindowIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)))
        # Load game shortcuts
        files = frogtool.getROMList(self.roms_path)
        # need a temp list for us to work while iterating
        temp_game_shortcut_list = [''] * 4
        #found = False
        window.tbl_gamelist.setRowCount(len(files))
        files.sort()
        for i, shortcut in enumerate(self.game_shortcut_list): 
            for j, game in enumerate(files):
                # set previously saved shortcuts
                position = tadpole_functions.getGameShortcutPosition(self.drive, self.console, game)
                # save this list globally beacuse we want to use it in other places
                if position != 0:
                    temp_game_shortcut_list[position-1] = game.rsplit( ".", 1 )[ 0 ]
                    #found = True
                    #break
        #Just scan through and replace  
            for i, shortcut in enumerate(temp_game_shortcut_list):
                if shortcut == '':
                    temp_game_shortcut_list[i] = "No Game Shortcut"
            #if it didn't find a current game, it must be blank
        #save temp to final list
        self.game_shortcut_list = temp_game_shortcut_list.copy()

        # Now load Current Preview image before we do anything else
        self.load_from_Resources()
        
        #ask user if they want to use this list to find files automatically
        qm = QMessageBox()
        ret = qm.question(self, "Find shorcuts?", "Do you want Tadpole to try to find your game shortcut icons automatically \
by matching the name of the game and a folder you select?  You can change the icons it finds before it gets saved.")
        if ret == qm.Yes:
            directory = QFileDialog.getExistingDirectory()
            if len(directory) > 0:  # confirm if user selected a file
                for i, gameName in enumerate(self.game_shortcut_list):
                    gameName = os.path.basename(gameName)
                    for file in os.listdir(directory):
                        file_stripped = frogtool.strip_file_extension(file)
                        if gameName == file_stripped:
                            gameIcon = os.path.join(directory, file)
                            self.ovewrite_background_and_reload(gameIcon, i+1)
                            continue

        # Setup Main Layout
        # TODO...I should have used Grid but here we are
        self.layout_main_vertical = QVBoxLayout()
        self.layout_current_viewer = QVBoxLayout()
        self.setLayout(self.layout_main_vertical)
        self.layout_main_vertical.addLayout(self.layout_current_viewer)
        # set up the main preview
        self.layout_current_viewer.addWidget(self.backgroundImage)
        # Setup Game Shortcut Name Labels
        self.shortcut_game_labels = QHBoxLayout()
        self.layout_main_vertical.addLayout(self.shortcut_game_labels)
        # Setup buttons to change the icons
        self.shortcut_buttons = QHBoxLayout()
        self.layout_main_vertical.addLayout(self.shortcut_buttons)
        #Gameshortcut Icons 1
        self.button_icon1 = QPushButton("Change Icon 1")
        self.button_icon1.setFixedSize(100,100)
        self.button_icon1.clicked.connect(self.addShortcut)
        self.shortcut_buttons.addWidget(self.button_icon1)

        self.label1 = QLabel((self.game_shortcut_list[0]), self)
        self.label1.setWordWrap(True)  
        self.label1.setAlignment(Qt.AlignCenter)
        self.shortcut_game_labels.addWidget(self.label1, Qt.AlignCenter)
        #Gameshortcut Icons 2
        self.button_icon2 = QPushButton("Change Icon 2")
        self.button_icon2.setFixedSize(100,100)
        self.button_icon2.clicked.connect(self.addShortcut)
        self.shortcut_buttons.addWidget(self.button_icon2)

        self.label2 = QLabel((self.game_shortcut_list[1]), self)
        self.label2.setWordWrap(True)  
        self.label2.setAlignment(Qt.AlignCenter)
        self.shortcut_game_labels.addWidget(self.label2, Qt.AlignCenter)
        #Gameshortcut Icons 3
        self.button_icon3 = QPushButton("Change Icon 3")
        self.button_icon3.setFixedSize(100,100)
        self.button_icon3.clicked.connect(self.addShortcut)
        self.shortcut_buttons.addWidget(self.button_icon3)

        self.label3 = QLabel((self.game_shortcut_list[2]), self)
        self.label3.setWordWrap(True)  
        self.label3.setAlignment(Qt.AlignCenter)
        self.shortcut_game_labels.addWidget(self.label3, Qt.AlignCenter)
        
        #Gameshortcut Icons 4
        self.button_icon4 = QPushButton("Change Icon 4")
        self.button_icon4.setFixedSize(100,100)
        self.button_icon4.clicked.connect(self.addShortcut)
        self.shortcut_buttons.addWidget(self.button_icon4)

        self.label4 = QLabel((self.game_shortcut_list[3]), self)
        self.label4.setWordWrap(True)  
        self.label4.setAlignment(Qt.AlignCenter)
        self.shortcut_game_labels.addWidget(self.label4, Qt.AlignCenter)
        # Main Buttons Layout (Save/Cancel)
        self.layout_buttons = QHBoxLayout()
        self.layout_main_vertical.addLayout(self.layout_buttons)
        # Save Button
        self.button_save = QPushButton("Save")
        self.button_save.setDefault(True)
        #self.button_save.setDisabled(True)  # set disabled by default; need to wait for user to select at least new image
        self.button_save.clicked.connect(self.Finish)
        self.layout_buttons.addWidget(self.button_save)
        # Cancel Button
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.reject)
        self.layout_buttons.addWidget(self.button_cancel)
    
    #thanks to doggyworld from discord Retro Handhelds to imrpove the icon shapes and sizes
    def round_corner(self, radius, fill):
        """Draw a round corner"""
        corner = Image.new('RGBA', (radius, radius), (0, 0, 0, 0))
        draw = ImageDraw.Draw(corner)
        draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
        return corner
    
    def round_rectangle(self, size, radius, fill):
        """Draw a rounded rectangle"""
        width, height = size
        rectangle = Image.new('RGBA', size, fill)
        corner = self.round_corner(radius, fill)
        rectangle.paste(corner, (0, 0))
        rectangle.paste(corner.rotate(90), (0, height - radius)) # Rotate the corner and paste it
        rectangle.paste(corner.rotate(180), (width - radius, height - radius))
        rectangle.paste(corner.rotate(270), (width - radius, 0))
        return rectangle
    
    def resize_for_shortcut(self, game):
        # Crop off to be square instead of just resizing.
        x, y = game.size
        crop_size = min(x,y)
        x_offset = (x-crop_size)/2
        y_offset = (y-crop_size)/2
        game = game.crop((x_offset, y_offset, crop_size+x_offset, crop_size+y_offset))
        game = game.resize((120,120), Image.Resampling.LANCZOS)

        # Create rectangles for white borders with fillet
        white_rounded_rect = self.round_rectangle((124,124), 8, "white")

        white_rounded_rect.paste(game, (2,2))
        game = white_rounded_rect

        white_rounded_rect2 = self.round_rectangle((124,124), 8, "white")
        black_rounded_rect2 = self.round_rectangle((120,120), 8, "black")
        white_rounded_rect2.paste(black_rounded_rect2, (2,2), black_rounded_rect2)

        datas = white_rounded_rect2.getdata()

        img_data = white_rounded_rect.getdata()

        newData = []
        new_imgData = []
        for idx,item in enumerate(datas):
            if item[3] == 0:
                new_imgData.append((255, 255, 255, 0))
            else:
                new_imgData.append(img_data[idx])

            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)

        white_rounded_rect2.putdata(newData)
        game.putdata(new_imgData)
        game.paste(white_rounded_rect2, (0,0), white_rounded_rect2)
        return game

    def ovewrite_background_and_reload(self, path, icon):
        #Following techniques by Zerter at view-source:https://zerter555.github.io/sf2000-collection/mainMenuIcoEditor.html
        #Add this to the temporary PNG
        game = Image.open(path, 'r')
        game = self.resize_for_shortcut(game)
        #game = game.resize((124,124), Image.Resampling.LANCZOS)
        workingPNG = Image.open(self.workingPNGPath)
        if icon == 1:
            workingPNG.paste(game, (42,290))
        if icon == 2:
            workingPNG.paste(game, (186,290))
        if icon == 3:
            workingPNG.paste(game, (330,290))
        if icon == 4:
            workingPNG.paste(game, (474,290))
        #Add to preview and save it
        workingPNG.save(self.workingPNGPath)
        img = QImage(self.workingPNGPath)
        #Update image
        self.backgroundImage.setPixmap(QPixmap().fromImage(img))
        return True

    def load_from_Resources(self):
        ResourcePath = tadpole_functions.getBackgroundResourceFileforConsole(self.drive, self.console)
        tadpole_functions.convertRGB565toPNG(ResourcePath)
        self.workingPNGPath
        img = QImage(self.workingPNGPath)
        if (img.width(), img.height()) != (640, 480): 
            img = img.scaled(640, 480, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) #Rescale new boot logo to correct size
        #Update image
        self.backgroundImage.setPixmap(QPixmap().fromImage(img))
        return True
    
    def addShortcut(self):
        sending_button = self.sender()
        #get the icon number
        file_path = QFileDialog.getOpenFileName(self, 'Open file', '',
                                            "Images (*.jpg *.png *.webp);;RAW (RGB565 Little Endian) Images (*.raw)")[0]
        if len(file_path) > 0:  # confirm if user selected a file
            #TODO: it was nice to disable but now its messing with other features, KISS
            #set save state to true so user can save this
            #self.button_save.setEnabled(True)
            #Add it to be processed
            if sending_button.text() == "Change Icon 1":
                #load into preview image
                self.ovewrite_background_and_reload(file_path, 1)
            elif sending_button.text() == "Change Icon 2":
                #load into preview image
                self.ovewrite_background_and_reload(file_path, 2)
            elif sending_button.text() == "Change Icon 3":
                #load into preview image
                self.ovewrite_background_and_reload(file_path, 3)           
            elif sending_button.text() == "Change Icon 4":
                #load into preview image
                self.ovewrite_background_and_reload(file_path, 4)   
            else:
                print(sending_button.text() + ": icon not found")
            return True #it completed
        return False #User cancelled
                
    def Finish(self):
        #Save this working TMP PNG to the right resource file
        if self.console == "SFC":
            resourceFile = "drivr.ers"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        elif self.console == "FC":
            resourceFile = "fixas.ctp"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        elif self.console == "MD":
            resourceFile = "icuin.cpl"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        elif self.console == "GB":
            resourceFile = "xajkg.hsp"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        elif self.console == "GBC":
            resourceFile = "qwave.bke"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        elif self.console == "GBA":
            resourceFile = "irftp.ctp"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        elif self.console == "ARCADE":
            resourceFile = "hctml.ers"
            tadpole_functions.convertPNGtoResourceRGB565(self.workingPNGPath, resourceFile, self.drive)
        #Last thing, let's get rid of the text under the icons.
        #The user has confirmed they want these and now they aren't the same
        #TODO: Confirm users are happy removing shortcut labels some beta testing
        #If so, just leave this
        tadpole_functions.stripShortcutText(self.drive)
        #Close dialog as we're all done
        self.accept()

class PleaseWaitDialog(QMainWindow):
    """
    Dialog used to stop interaction while something is happening from program root.
    """
    def __init__(self, message: str = ""):
        super().__init__()

        self.setWindowTitle("Please Wait")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        
        self.lbl = QLabel(self)
        #self.text_edit.setFixedSize(500, 500)
        self.setCentralWidget(self.lbl)
        self.lbl.setText(message)
        
    def setMessage(self, message: str = ""):
        self.lbl.setText(message)

class ReadmeDialog(QMainWindow):
    """
    Dialog used to display README.md file from program root.
    """
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Read Me")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarContextHelpButton))

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumSize(500, 500)
        self.setCentralWidget(self.text_edit)
        try:
            with open(os.path.join(basedir, "README.md"), "r") as readme_file:
                self.text_edit.setMarkdown(readme_file.read())
        except FileNotFoundError:  # gracefully fail if file not present
            self.text_edit.setText(f"Unable to locate README.md file in program root folder {basedir}.")


class MusicConfirmDialog(QDialog):
    """Dialog used to confirm or load music selection with the ability to preview selection by listening to the music.
    If neither music_name nor music_url are provided, allows import from local file.

        Args:
            music_name (str) : Name of the music file; used only to show name in dialog
            music_url (str) : URL to a raw music file; should be formatted for use on SF2000 (raw signed 16-bit PCM,
                mono, little-endian, 22050 hz)
    """
    def __init__(self, music_name: str = "", music_url: str = ""):
        super().__init__()

        # Save Arguments
        self.music_name = music_name
        self.music_url = music_url
        self.music_file = ""  # used to store filename for local files

        # Configure Window
        self.setWindowTitle("Change Background Music")
        self.setWindowIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)))
        self.sound = QSoundEffect(self)  # Used to Play Music File

        # Setup Main Layout
        self.layout_main = QVBoxLayout()
        self.setLayout(self.layout_main)

        # Main Text
        self.label_confirm = QLabel("<h3>Change Background Music</h3><a href='#'>Select File</a>", self)
        if self.music_name == "" and self.music_url == "":
            self.label_confirm.linkActivated.connect(self.load_from_file)
            pass
        self.label_confirm.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.layout_main.addWidget(self.label_confirm)

        # Music Preview Button
        self.button_play = QPushButton(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)),
                                       " Preview",
                                       self)
        self.button_play.setDisabled(True)  # disable by default

        self.layout_main.addWidget(self.button_play)
        self.button_play.clicked.connect(self.toggle_audio)

        # Main Buttons Layout (Save/Cancel)
        self.layout_buttons = QHBoxLayout()
        self.layout_main.addLayout(self.layout_buttons)

        # Save Button
        self.button_save = QPushButton("Save")
        self.button_save.setDisabled(True)  # disable by default
        self.button_save.clicked.connect(self.accept)
        self.layout_buttons.addWidget(self.button_save)

        # Cancel Button
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.reject)
        self.layout_buttons.addWidget(self.button_cancel)

        if music_name and music_url:  # enable features only if using preset options
            self.label_confirm.setText("<h3>Change Background Music</h3><em>{}</em>".format(self.music_name))
            self.button_save.setEnabled(True)
            self.button_play.setEnabled(True)

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
            if not self.sound.source().path():  # fetch and convert raw file if not already done
                self.button_play.setDisabled(True)  # disable button while processing
                file_data = self.get_and_format_music_file()
                if file_data[0]:  # fetch/conversion succeeds
                    self.sound.setSource(QUrl.fromLocalFile(file_data[1]))
                    self.button_play.setEnabled(True)
                    self.button_save.setEnabled(True)  # enable saving as well since file seems OK
                else:  # fetch/conversion fails
                    self.button_play.setText(file_data[1])
                    self.button_play.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)))
                    return False

            # format button and play
            self.button_play.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)))
            self.button_play.setText(" Stop")
            self.sound.setLoopCount(1000)
            self.sound.play()
            return True

    def get_and_format_music_file(self) -> (bool, str):
        """Downloads/loads and re-formats the raw music file as wav.

            Returns:
                tuple (bool, str): True or false based on success in fetching/converting file, and path to resulting
                    temporary wav file, error message if failed.
        """
        if self.music_url:  # handle internet downloads
            try:
                r = requests.get(self.music_url)
                if r.status_code == 200:  # download succeeds
                    raw_data = BytesIO(r.content)  # read raw file into memory
            except requests.exceptions.RequestException:  # catches exceptions for multiple reasons
                return False, "Download Failed"
        else:  # handle local files
            with open(self.music_file, "rb") as mf:
                raw_data = BytesIO(mf.read())

        wav_filename = os.path.join(basedir, "preview.wav")
        with wave.open(wav_filename, "wb") as wav_file:
            wav_file.setparams((1, 2, 22050, 0, 'NONE', 'NONE'))
            wav_file.writeframes(raw_data.read())
            if wav_file.getnframes() > (22050*90):  # check that file length does not exceed 90 seconds (max for Froggy)
                return False, "Duration Too Long (90s max)"
        return True, wav_filename

    def load_from_file(self) -> bool:
        file_name = QFileDialog.getOpenFileName(self, 'Open file', '',
                                                "Raw Signed 16-bit PCM - Mono, Little-Endian, 22050hz (*.*)")[0]
        if file_name:
            self.music_file = file_name
            self.music_name = os.path.split(file_name)[-1]
            self.label_confirm.setText("<h3>Change Background Music</h3><em>{}</em>".format(self.music_name))
            self.button_play.setEnabled(True)
            self.toggle_audio()
            return True
        return False


# SubClass QMainWindow to create a Tadpole general interface
class MainWindow (QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tadpole - SF2000 Tool")
        self.setWindowIcon(QIcon(os.path.join(basedir, 'frog.ico')))
        self.resize(925,500)

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
        selector_layout = QHBoxLayout()
        layout.addLayout(selector_layout)

        # Drive Select Widgets
        self.lbl_drive = QLabel(text="Drive:")
        self.lbl_drive.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.combobox_drive = QComboBox()
        self.combobox_drive.activated.connect(self.combobox_drive_change)
        selector_layout.addWidget(self.lbl_drive)
        selector_layout.addWidget(self.combobox_drive, stretch=1)

        # Spacer
        selector_layout.addWidget(QLabel(" "), stretch=2)

        # Console Select Widgets
        self.lbl_console = QLabel(text="Console:")
        self.lbl_console.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.combobox_console = QComboBox()
        self.combobox_console.activated.connect(self.combobox_console_change)
        selector_layout.addWidget(self.lbl_console)
        selector_layout.addWidget(self.combobox_console, stretch=1)
        
        # Update Button Widget
        # self.btn_update = QPushButton("Update device")
        # selector_layout.addWidget(self.btn_update)
        # self.btn_update.clicked.connect(RebuildClicked)

        # Add ROMS button
        self.btn_update = QPushButton("Add ROMs...")
        selector_layout.addWidget(self.btn_update)
        self.btn_update.clicked.connect(self.copyRoms)
        
        # Add Thumbnails button
        self.btn_update_thumbnails = QPushButton("Add Thumbnails...")
        selector_layout.addWidget(self.btn_update_thumbnails )
        self.btn_update_thumbnails.clicked.connect(self.addBoxart)

        # Add Shortcut button
        self.btn_update_shortcuts_images = QPushButton("Change Game Shortcut Icons...")
        selector_layout.addWidget(self.btn_update_shortcuts_images )
        self.btn_update_shortcuts_images.clicked.connect(self.addShortcutImages)

        # Delete selected roms
        self.btn_delete_roms = QPushButton("Delete selcted ROMs...")
        self.btn_delete_roms.setEnabled(False)
        selector_layout.addWidget(self.btn_delete_roms)
        self.btn_delete_roms.clicked.connect(self.deleteROMs)

        # Game Table Widget
        self.tbl_gamelist = QTableWidget()
        self.tbl_gamelist.setColumnCount(5)
        self.tbl_gamelist.setHorizontalHeaderLabels(["Name", "Size", "Thumbnail", "Shortcut Slot", "Delete ROM"])
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tbl_gamelist.horizontalHeader().resizeSection(0, 300) 
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl_gamelist.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tbl_gamelist.cellClicked.connect(catchTableCellClicked)
        self.tbl_gamelist.horizontalHeader().sectionClicked.connect(headerClicked)

        layout.addWidget(self.tbl_gamelist)
        
        self.readme_dialog = ReadmeDialog()

        # Reload Drives Timer
        # This is run once per second to check if any new SD cards have been inserted.
        # Ideally we would hook this into a trigger rather than polling for changes.
        # The resource cost of polling seems to be quite low though
        self.timer = QTimer()
        self.timer.timeout.connect(reloadDriveList)
        self.timer.start(1000)

    
    def create_actions(self):
        # File Menu
        self.about_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
                                    "&About",
                                    self,
                                    triggered=self.about)
        self.exit_action = QAction("E&xit", self, shortcut="Ctrl+Q",triggered=self.close)

    def loadMenus(self):
        self.menu_file = self.menuBar().addMenu("&File")
        Settings_action = QAction("Settings...", self, triggered=self.Settings)
        self.menu_file.addAction(Settings_action)
        self.menu_file.addAction(self.exit_action)

        # OS Menu
        self.menu_os = self.menuBar().addMenu("&OS")
            #Sub-menu for updating Firmware
        self.menu_os.menu_update = self.menu_os.addMenu("Firmware")
        action_detectOSVersion = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Detect and update firmware", self, triggered=self.detectOSVersion)
        self.menu_os.menu_update.addAction(action_detectOSVersion)
        action_updateTo20230803  = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Manually change to 2023.08.03 (V1.6)", self, triggered=self.Updateto20230803)                                                                              
        self.menu_os.menu_update.addAction(action_updateTo20230803)   
        self.action_updateToV1_5  = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Manually change to 2023.04.20 (V1.5)  - Not recommended", self, triggered=self.UpdatetoV1_5)                                                                              
        self.menu_os.menu_update.addAction(self.action_updateToV1_5)
        self.menu_os.menu_update.addSeparator()
        action_battery_fix  = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Battery Fix - Built by commnity (Improves battery life & shows low power warning)", self, triggered=self.Battery_fix)                                                                              
        self.menu_os.menu_update.addAction(action_battery_fix)   
            #Sub-menu for updating themes
        self.menu_os.menu_change_theme = self.menu_os.addMenu("Theme")
        try:
            self.theme_options = tadpole_functions.get_themes()
        except (ConnectionError, requests.exceptions.ConnectionError):
            self.status_bar.showMessage("Error loading external theme resources.  Reconnect to internet and try restarting tadpole.", 20000)
            error_action = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)),
                                   "Error Loading External Resources!",
                                   self)
            error_action.setDisabled(True)
            self.menu_os.menu_change_theme.addAction(error_action)
        else:
            for theme in self.theme_options:
                self.menu_os.menu_change_theme.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)),
                                                theme,
                                                self,
                                                triggered=self.change_theme))
        self.menu_os.menu_change_theme.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)),
                                        "Check out theme previews and download more themes...",
                                        self,
                                        triggered=lambda: webbrowser.open(("https://zerter555.github.io/sf2000-collection/"))))
        self.menu_os.menu_change_theme.addSeparator()
        self.menu_os.menu_change_theme.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)),
                                        "Update From Local File...",
                                        self,
                                        triggered=self.change_theme)) 
           # Sub-menu for changing background music
        self.menu_os.menu_change_music = self.menu_os.addMenu("Background Music")
        try:
            self.music_options = tadpole_functions.get_background_music()
        except (ConnectionError, requests.exceptions.ConnectionError):
            self.status_bar.showMessage("Error loading external music resources. Reconnect to internet and try restarting tadpole.", 20000)
            error_action = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)),
                                   "Error Loading External Resources!",
                                   self)
            error_action.setDisabled(True)
            self.menu_os.menu_change_music.addAction(error_action)
        else:
            for music in self.music_options:
                self.menu_os.menu_change_music.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)),
                                                music,
                                                self,
                                                triggered=self.change_background_music))
        self.menu_os.menu_change_music.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)),
                                        "Check out more background music to download...",
                                        self,
                                        triggered=lambda: webbrowser.open(("https://zerter555.github.io/sf2000-collection/"))))
        self.menu_os.menu_change_music.addSeparator()
        self.menu_os.menu_change_music.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)),
                                        "Upload from Local File...",
                                        self,
                                        triggered=self.change_background_music))

        #Menus for boot logo
        self.menu_os.menu_boot_logo = self.menu_os.addMenu("Boot Logo")
        self.menu_os.menu_boot_logo.addAction(QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)),
                                            "Check out and download boot logos...",
                                            self,
                                            triggered=lambda: webbrowser.open(("https://zerter555.github.io/sf2000-collection/"))))
        UpdateBootLogoAction  = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)), 
                                        "Upload from Local File...", 
                                        self, 
                                        triggered=self.changeBootLogo)
        self.menu_os.menu_boot_logo.addAction(UpdateBootLogoAction)

        #Menus for console logos
        # self.menu_consoleLogos = self.menu_os.addMenu("Console Logos")
        # self.action_consolelogos_Default = QAction("Restore Default", self, triggered=self.ConsoleLogos_RestoreDefault)
        # self.menu_consoleLogos.addAction(self.action_consolelogos_Default)
        # self.action_consolelogos_Western = QAction("Use Western Logos", self, triggered=self.ConsoleLogos_WesternLogos)
        # self.menu_consoleLogos.addAction(self.action_consolelogos_Western)
        self.menu_os.menu_bios = self.menu_os.addMenu("Emulator BIOS")
        self.GBABIOSFix_action = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Update GBA BIOS", self, triggered=self.GBABIOSFix)
        self.menu_os.menu_bios.addAction(self.GBABIOSFix_action)

        # Consoles Menu
        self.menu_roms = self.menuBar().addMenu("Consoles")
        RebuildAll_action = QAction("Refresh all thumbnails and ROMs", self, triggered=self.rebuildAll)
        self.menu_roms.addAction(RebuildAll_action)
        BackupAllSaves_action = QAction("Backup All Consoles ROMs saves...", self, triggered=self.createSaveBackup)
        self.menu_roms.addAction(BackupAllSaves_action)     
        # Help Menu
        self.menu_help = self.menuBar().addMenu("&Help")
        self.readme_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarContextHelpButton),
                                     "Read Me",
                                     triggered=self.show_readme)
        self.menu_help.addAction(self.readme_action)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.about_action)

    def testFunction(self):
        print("Called test function. Remember to disable this before publishing")
        try:
            tadpole_functions.bisrv_getFirmwareVersion("C:\\Users\\OEM\\Downloads\\bisrv (1).asd")
        except tadpole_functions.InvalidURLError:
            print("URL did not return a valid file")
    
    def Settings(self):
        window_settings = SettingsWindow()
        window_settings.exec()
        RunFrogTool(window.combobox_console.currentText())

    def detectOSVersion(self):
        print("Tadpole~DetectOSVersion: Trying to read bisrv hash")
        drive = window.combobox_drive.currentText()
        msg_box = DownloadMessageBox()
        msg_box.setText("Detecting firmware version")
        msg_box.show()
        try:
            msg_box.showProgress(50, True)
            detectedVersion = tadpole_functions.bisrv_getFirmwareVersion(os.path.join(drive,"bios","bisrv.asd"))
            if not detectedVersion:
                detectedVersion = "Version Not Found"
                return False
            #TODO: move this from string base to something else...or at lesat make sure this gets updated when/if new firmware gets out there
            if detectedVersion == "2023.04.20 (V1.5)":
                msg_box.close()
                qm = QMessageBox
                ret = qm.question(self,"Detected OS Version", f"Detected version: "+ detectedVersion + "\nDo you want to update to the latest firmware?" , qm.Yes | qm.No)
                if ret == qm.Yes:
                    MainWindow.Updateto20230803(self)
                else:
                    return False
            elif detectedVersion == "2023.08.03 (V1.6)":
                msg_box.close()
                QMessageBox.about(self, "Detected OS Version", f"You are already on the latest firmware: {detectedVersion}")
                return True
            else:
                msg_box.close()
                QMessageBox.about(self, "Detected OS Version", f"Cannot update from: {detectedVersion}")
                return True

        except Exception as e:
            msg_box.close()
            QMessageBox.about("tadpole~detectOSVersion: Error occured while trying to find OS Version" + str(e))
            return
    
    def addBoxart(self):
        drive = window.combobox_drive.currentText()
        user_selected_console = window.combobox_console.currentText()
        rom_path = os.path.join(drive,user_selected_console)
        msgBox = DownloadMessageBox()
        msgBox.progress.reset()
        #Check what the user has configured; upload or download
        config = configparser.ConfigParser()
        config.read(drive + "/Resources/tadpole.ini")
        if config.get('thumbnails', 'download',fallback="0") == "0":
            thumbnailDialog = QFileDialog()
            thumbnailDialog.setDirectory('')
            thumbnailDialog.setFileMode(QFileDialog.Directory)
            thumbnailDialog.setOption(QFileDialog.ShowDirsOnly)
            if thumbnailDialog.exec_():
                for dir in thumbnailDialog.selectedFiles():
                    #In the directory, grab all the imagess and copy them over to our console folder
                    files = os.listdir(dir)
                    savedFiles = []
                    #Setup progress as these can take a while
                    msgBox.progress.setMaximum(len(files)*2)
                    progress = 0
                    msgBox.setText("Copying thumbnails for zips")
                    msgBox.showProgress(progress, True)
                    msgBox.show()
                    for file in files:
                        #Only copy images over from that folder
                        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                            img_path = os.path.join(dir,file)
                            shutil.copy(img_path,rom_path)
                            #Save a copy of this file for us to delete later
                            savedFiles.append(os.path.join(rom_path, file))
                            progress += 1
                            msgBox.showProgress(progress, True)
                    #New run through frogtool to match all zips...
                    frogtool.convert_zip_image_pairs_to_zxx(rom_path, user_selected_console)
                    #Now run through all .ZBB files IF the user has this setup
                    if config.get('thumbnails', 'ovewrite',fallback="0") == "True":
                        msgBox.setText("Copying more thumbnails...")
                        msgBox.progress.reset()
                        tadpole_functions.overwriteZXXThumbnail(rom_path, user_selected_console, msgBox.progress)
                    msgBox.close()
                    QMessageBox.about(self, "Downloaded Thumbnails", "Adding thumbnails complete for "
                        + user_selected_console + "\n\nPro tip: Turn on 'View thumbnails in Viewer' in Settings to scroll through all ROMs the thumbanils shown in the viewer.\n\n\
Missing some thumbnails? Check to make sure you selected the right image folder, the names are the same, and you are in the right console in Tadpole.")
                    #Cleanup all thoes PNG's that didn't get converted
                    for file in savedFiles:
                        if os.path.isfile(file):
                            os.remove(file)
        if config.get('thumbnails', 'download',fallback="0") == "1":
            QMessageBox.about(self, "Add Thumbnails", "You have Tadpole configured to download thumbnails automatically. \
For this to work, your roms must be in ZIP files and the name of that zip must match their common released English US localized \
name.  Please refer to https://github.com/EricGoldsteinNz/libretro-thumbnails/tree/master if Tadpole isn't finding \
the thumbnail for you. ")
            #ARCADE can't get ROM art, so just return
            if user_selected_console == "ARCADE":
                QMessageBox.about(self, "Add Thumbnails", "Custom Arcade ROMs cannot have thumbnails at this time.")
                return
            #Need the url for scraping the png's, which is different
            ROMART_baseURL_parsing = "https://github.com/EricGoldsteinNz/libretro-thumbnails/tree/master/"
            
            ROMArt_console = {  
                "FC":     "Nintendo - Nintendo Entertainment System",
                "SFC":    "Nintendo - Super Nintendo Entertainment System",
                "MD":     "Sega - Mega Drive - Genesis",
                "GB":     "Nintendo - Game Boy",
                "GBC":    "Nintendo - Game Boy Color",
                "GBA":    "Nintendo - Game Boy Advance", 
                "ARCADE": ""
            }
            msgBox.setText("Downloading thumbnails...")
            msgBox.show()
            #TODO: I shouldn't base this on strings incase it gets localized, should base it on the item clicked with "sender" obj but I can't figure out where that data is in that object 
            art_Selection = self.sender().text()
            if('Titles' in art_Selection):
                art_Type = "/Named_Titles/"
            elif('Snaps'in art_Selection):
                art_Type = "/Named_Snaps/"
            else:
                art_Type = "/Named_Boxarts/"
            console = user_selected_console
            zip_files = os.scandir(os.path.join(drive,console))
            zip_files = list(filter(frogtool.check_zip, zip_files))
            msgBox.setText("Trying to find thumbnails for " + str(len(zip_files)) + " ROMs\n" + ROMArt_console[console])
            #reset progress bar for next console
            games_total = 0
            msgBox.progress.reset()
            msgBox.progress.setMaximum(len(zip_files)+1)
            msgBox.progress.setValue(0)
            QApplication.processEvents()
            #Scrape the url for .png files
            url_for_scraping = ROMART_baseURL_parsing + ROMArt_console[console] + art_Type
            response = requests.get(url_for_scraping)
            # BeautifulSoup magically find ours PNG's and ties them up into a nice bow
            soup = BeautifulSoup(response.content, 'html.parser')
            json_response = json.loads(soup.contents[0])
            png_files = []
            for value in json_response['payload']['tree']['items']:
                png_files.append(value['name'])

            for file in zip_files:
                game = os.path.splitext(file.name)
                outFile = os.path.join(os.path.dirname(file.path),f"{game[0]}.png")

                msgBox.progress.setValue(games_total)
                QApplication.processEvents()
                if not os.path.exists(outFile):
                    url_to_download = ROMART_baseURL_parsing + ROMArt_console[console] + art_Type + game[0]
                    for x in png_files:
                        if game[0] in x:
                            tadpole_functions.downloadROMArt(console,file.path,x,art_Type,game[0])
                            games_total += 1
                            break
            QApplication.processEvents()
            QMessageBox.about(self, "Downloaded Thumbnails", "Downloaded " + str(games_total) + " thumbnails")
        msgBox.close()
        RunFrogTool(window.combobox_console.currentText())

    def change_background_music(self):
        """event to change background music"""
        if self.sender().text() == "Upload from Local File...":  # handle local file option
            d = MusicConfirmDialog()
            local = True
        else:  # handle preset options
            d = MusicConfirmDialog(self.sender().text(), self.music_options[self.sender().text()])
            local = False
        if d.exec():
            if local:
                BGM_change(d.music_file)
            else:
                BGM_change(self.music_options[self.sender().text()])

    def about(self):
        QMessageBox.about(self, "About Tadpole", 
                                "Tadpole was created by EricGoldstein based on the original work \
from tzlion on frogtool. Special thanks also goes to wikkiewikkie & Jason Grieves for many amazing improvements")

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
        msgBox = DownloadMessageBox()
        msgBox.setText(" Loading current boot logo...")
        msgBox.show()
        msgBox.showProgress(50, True)
        dialog = BootConfirmDialog(window.combobox_drive.currentText())
        msgBox.close()
        change = dialog.exec()
        if change:
            newLogoFileName = dialog.new_viewer.path
            print(f"user tried to load image: {newLogoFileName}")
            if newLogoFileName is None or newLogoFileName == "":
                print("user cancelled image select")
                return
            try:
                msgBox = DownloadMessageBox()
                msgBox.setText("Updating boot logo...")
                msgBox.show()
                msgBox.showProgress(10, True)
                success = tadpole_functions.changeBootLogo(os.path.join(window.combobox_drive.currentText(),
                                                              "bios",
                                                              "bisrv.asd"),
                                                 newLogoFileName, msgBox)
                msgBox.close()
            except tadpole_functions.Exception_InvalidPath:
                QMessageBox.about(self, "Change Boot Logo", "An error occurred. Please ensure that you have the right \
                drive selected and <i>bisrv.asd</i> exists in the <i>bios</i> folder")
                return
            if success:
                QMessageBox.about(self, "Change Boot Logo", "Boot logo successfully changed")
            else:
                QMessageBox.about(self, "Change Boot Logo", "Could not update boot logo.  Have you changed the firmware with another tool?  Tadpole only supports stock firmware files")

      
    # def changeGameShortcuts(self):
    #     drive = window.combobox_drive.currentText()
    #     # Open a new modal to change the shortcuts for a specific gamename
    #     window.window_shortcuts = changeGameShortcutsWindow()
    #     window.window_shortcuts.setDrive(drive)
    #     window.window_shortcuts.show()
    
    # def removeShortcutLabels(self):
    #     drive = window.combobox_drive.currentText()
    #     if tadpole_functions.stripShortcutText(drive):
    #         QMessageBox.about(window, "Success", "Successfully removed Shortcut Labels")
    #     else:
    #         QMessageBox.about(window, "Something went wrong", "An error occured. Please contact EricGoldstein via the RetroHandheld Discord to look into it.")
        
    # def ConsoleLogos_RestoreDefault(self):
    #     self.ConsoleLogos_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/ConsoleLogos/default/sfcdr.cpl")
    
    # def ConsoleLogos_WesternLogos(self):
    #     self.ConsoleLogos_change("https://github.com/EricGoldsteinNz/SF2000_Resources/raw/main/ConsoleLogos/western_console_logos/sfcdr.cpl")

    def UnderDevelopmentPopup(self):
        QMessageBox.about(self, "Development", "This feature is still under development")
        

    def changeThumbnailView(self, state):
        drive = window.combobox_drive.currentText()
        config = configparser.ConfigParser()
        config.read(drive + "/Resources/tadpole.ini")
        if not config.has_section('view'):
            config.add_section('view')
        if config.has_option('view', 'thumbnails'):
            config['view']['thumbnails'] = str(state)
        else:
            config.set('view', 'thumbnails', str(state))

        with open(drive + "/Resources/tadpole.ini", 'w') as configfile:
            config.write(configfile)
        RunFrogTool(self.combobox_console.currentText())

    def combobox_drive_change(self):
        newDrive = self.combobox_drive.currentText()
        console = self.combobox_console.currentText()
        logging.info(f"Dialog for drive changed to ({newDrive})")
        #Check if the Tadpole config file exists, if not then create it.
        configPath = os.path.join(newDrive, static_TadpoleConfigFile)
        if os.path.isfile(configPath):
            config.read(configPath)
            #TODO every release let's be ultra careful for now and delete tadpole settings...
            #if it has defualt, then it doesn't exist
            TadpoleVersion = config.get('versions', 'tadpole')
            if TadpoleVersion != "0.3.9.15":
                os.remove(configPath)
                FirstRun(window)         
        else:
            #Run First Run to create config, check bootloader, etc.
            FirstRun(window)
        
        loadROMsToTable()

    def combobox_console_change(self):
        console = self.combobox_console.currentText()
        logging.info(f"Dialog for console changed to ({console})")
        # ERIC: We shouldnt run frogtool as soon as the drive is opened. This is a lot of unnecessary processing.  
        RunFrogTool(console)

    def show_readme(self):
        self.readme_dialog.show()

    def UpdatetoV1_5(self):
        url = "https://api.github.com/repos/EricGoldsteinNz/SF2000_Resources/contents/OS/V1.5"
        self.UpdateDevice(url)
    
    def Updateto20230803(self):
        url = "https://api.github.com/repos/EricGoldsteinNz/SF2000_Resources/contents/OS/20230803"
        self.UpdateDevice(url)

    def Battery_fix(self):
        qm = QMessageBox()
        ret = qm.question(window,'Patch Firmware?', "Are you sure you want to patch the firmware? The system will also check if the latest firmware is on the SD card, so make sure you are up to date." , qm.Yes | qm.No)
        if ret == qm.No:
            return
        Drive = window.combobox_drive.currentText()
        BisrvLocation = Drive + "/bios/bisrv.asd"
        battery_patcher = tadpole_functions.BatteryPatcher(BisrvLocation, BisrvLocation)

        with open(BisrvLocation, 'rb') as f:
                bisrv_data = bytearray(f.read())
                print("File '%s' opened successfully." % BisrvLocation)
        if battery_patcher.check_patch_applied(bisrv_data):
            QMessageBox.about(self, "Status","You already have the battery patch applied")
            return
        #Order matters, if they are on patch, they will fail so do this second
        elif not battery_patcher.check_latest_firmware(bisrv_data):
            qm = QMessageBox()
            ret = qm.question(window,'Status', "You need to be on the latest released firmware for the patched battery.  Do you want to downlaod it now?" , qm.Yes | qm.No)
            if ret == qm.No:
                return
            else:
                window.Updateto20230803()
        #get some progress for the user
        UpdateMsgBox = DownloadMessageBox()
        UpdateMsgBox.setText("Patching firmware...")
        UpdateMsgBox.showProgress(1, True)
        UpdateMsgBox.show()
        if battery_patcher.patch_firmware(UpdateMsgBox.progress):
            QMessageBox.about(self, "Status","Firmware patched with the battery improvements")
        else:
            QMessageBox.about(self, "Failure","Firmware was not patched with the battery improvements.  Are you already up to date?")
        UpdateMsgBox.close()

    def UpdateDevice(self, url):
        drive = window.combobox_drive.currentText()
        msgBox = QMessageBox()

        msgBox = DownloadMessageBox()
        msgBox.setText("Downloading Firmware Update.")
        msgBox.show()
        msgBox.showProgress(0, True)
        if tadpole_functions.downloadDirectoryFromGithub(drive, url, msgBox.progress):
            msgBox.close()
            QMessageBox.about(self, "Success","Update successfully downloaded")
        else:
            msgBox.close()
            QMessageBox.about(self, "Failure","ERROR: Something went wrong while trying to download the update")

    def change_theme(self, url):
        qm = QMessageBox()
        ret = qm.question(window,'Heads up', "Changing themes will ovewrite your game shortcut icons.  You can change them again after the theme is applied.  Are you suer you want to change your theme?" , qm.Yes | qm.No)
        if ret == qm.No:
            return
        drive = window.combobox_drive.currentText()
        #TODO error handling
        if not self.sender().text() == "Update From Local File...":
            url =  self.theme_options[self.sender().text()]
        msgBox = DownloadMessageBox()
        msgBox.setText("Updating Theme...")
        msgBox.show()
        progress = 1
        msgBox.showProgress(progress, True)
        """event to change theme"""
        if self.sender().text() == "Update From Local File...":  # handle local file option
            theme_zip = filename, _ = QFileDialog.getOpenFileName(self,"Select Theme ZIP File",'',"Theme ZIP file (*.zip)")
            if filename:
                result = tadpole_functions.changeTheme(drive, "", theme_zip[0], msgBox.progress)
                msgBox.close()
                if result:
                    QMessageBox.about(window, "Success", "Theme changed successfully")
                else:
                    QMessageBox.about(window, "Failure", "Something went wrong while trying to change the theme")

        elif url[0:4] == "http":  # internet-based
                result = tadpole_functions.changeTheme(drive,url, "", msgBox.progress)
                msgBox.close()
                QMessageBox.about(window, "Success", "Theme changed successfully")
        else:
            QMessageBox.about(window, "Failure", "Something went wrong while trying to change the theme")

    def rebuildAll(self):
        RunFrogTool("ALL")
        return

    def createSaveBackup(self):
        drive = window.combobox_drive.currentText()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        QMessageBox.about(self, "Select location",f"Select where you want to save your backup, \
or cancel to save in the same directory as Tadpole.\n\n\
It is recommended to save it somewhere other than your SD card used with the SF2000.")
        path = QFileDialog.getExistingDirectory()
        msgBox = QMessageBox()
        msgBox.setWindowTitle("Creating Save Backup")
        msgBox.setText("Please Wait")
        msgBox.show()
        if path == '':
            savefilename = f"SF2000SaveBackup_{timestamp}.zip"
        else:
            savefilename = os.path.join(path, f"SF2000SaveBackup_{timestamp}.zip")

        if tadpole_functions.createSaveBackup(drive,savefilename):   
            msgBox.close()
            if path == '':
                QMessageBox.about(self, "Success",f"Save backup created in:\n\r{savefilename}, located in the same folder you have Tadpole.")
            else:
                QMessageBox.about(self, "Success",f"Save backup created at:\n\r{savefilename}")
        else:
            msgBox.close()
            QMessageBox.about(self, "Failure","ERROR: Something went wrong while trying to create the save backup")    
        
    def copyRoms(self):
        drive = window.combobox_drive.currentText()
        console = window.combobox_console.currentText()

        if(console == "ALL"):
            QMessageBox.about(self, "Action needed",f"Please select a console in the dropdown")
            return
        filenames, _ = QFileDialog.getOpenFileNames(self,"Select ROMs",'',"ROM files (*.zip *.bkp \
                                                    *.zfc *.zsf *.zmd *.zgb *.zfb *.smc *.fig *.sfc *.gd3 *.gd7 *.dx2 *.bsx *.swc \
                                                    *.nes *.nfc *.fds *.unf *.gbc *.gb *.sgb *.gba *.agb *.gbz *.bin *.md *.smd *.gen *.sms)")
        if filenames:
            msgBox = DownloadMessageBox()
            msgBox.setText(" Copying "+ console + " Roms...")
            games_copied = 1
            msgBox.progress.reset()
            msgBox.progress.setMaximum(len(filenames)+1)
            msgBox.show()
            QApplication.processEvents()
            for filename in filenames:
                games_copied += 1
                msgBox.showProgress(games_copied, True)
                #Additoinal safety to make sure this file exists...
                if os.path.isfile(filename):
                    shutil.copy(filename, drive + console)
                print (filename + " added to " + drive + console)
            msgBox.close()
            qm = QMessageBox
            ret = qm.question(self,'Add Thumbnails?', f"Added " + str(len(filenames)) + " ROMs to " + drive + console + "\n\nDo you want to add thumbnails?\n\n\
Note: You can change in settings to either pick your own or try to downlad automatically.", qm.Yes | qm.No)
            if ret == qm.Yes:
                MainWindow.addBoxart(self)
        RunFrogTool(window.combobox_console.currentText())

            
    def validateGameShortcutComboBox(self):
        currentComboBox = self.sender() 
        if currentComboBox.currentText() == '':
            QMessageBox.about(window, "Game Shortcut","You can't really remove a game shortcut slot on SF2000.\n\nIf you don't pick another game, this game will stay as a shortcut when you switch systems or make other changes.")
        if currentComboBox.currentText() != '':
            for i in range(self.tbl_gamelist.rowCount()):
                comboBox = window.tbl_gamelist.cellWidget(i, 3)
                if comboBox == currentComboBox:
                    continue
                if comboBox.currentText() == currentComboBox.currentText():
                    QMessageBox.about(window, "Error","You had the shortcut: " + comboBox.currentText() + " assigned to " + window.tbl_gamelist.item(i, 0).text()+ "\nChanging it to the newly selected game.")
                    comboBox.setCurrentIndex(0)
        processGameShortcuts()
        return
    
    def addShortcutImages(self):
        dialog = GameShortcutIconsDialog()
        status = dialog.exec()
        if status:
            QMessageBox.about(self, "Game Shortcuts",f"Updated your game shortcut icons.")
        else:
            print("user cancelled")
        #let's get the temp PNG out if for some reason it didn't get cleaned up
        if os.path.exists('currentBackground.temp.png'):
            os.remove('currentBackground.temp.png')

    def deleteROMs(self):
        qm = QMessageBox
        ret = qm.question(window,'Delete ROMs?', "Are you sure you want to delete all selected ROMs?" , qm.Yes | qm.No)
        if ret == qm.No:
            return
        for item in window.tbl_gamelist.selectedItems():
            try:
                os.remove(self.combobox_drive.currentText() + self.combobox_console.currentText() + "/" + item.text())
            except Exception:
                QMessageBox.about(window, "Error","Could not delete ROM.")
        QMessageBox.about(self, "Success",f"Successfully deleted selected ROMs.")
        RunFrogTool(self.combobox_console.currentText())

# Subclass Qidget to create a thumbnail viewing window        
class SettingsWindow(QDialog):
    """
        This window should be called without a parent widget so that it is created in its own window.
    """
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        self.setWindowIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)))
        self.setWindowTitle(f"Tadpole Settings")
        
        # Setup Main Layout
        self.layout_main = QVBoxLayout()
        self.setLayout(self.layout_main)

        #Thumbnail options
        self.layout_main.addWidget(QLabel("Thumbnail options"))
        #Viewer
        thubmnailViewCheckBox = QCheckBox("View Thumbnails in ROM list")
        ViewerCheckValue = self.GetKeyValue('thumbnails', 'view')
        thubmnailViewCheckBox.setChecked(ViewerCheckValue == 'True')
        thubmnailViewCheckBox.toggled.connect(self.thumbnailViewClicked)
        self.layout_main.addWidget(thubmnailViewCheckBox)
        
        #Thumbnail upload style
        self.layout_main.addWidget(QLabel("Add thumbnails by: "))
        thubmnailAddCombo = QComboBox()
        thubmnailAddCombo.addItems(["uploading a folder from your PC", "automatically downloading over the internet"])
        if self.GetKeyValue('thumbnails', 'download') == '0':
            thubmnailAddCombo.setCurrentIndex(0)
        else:
            thubmnailAddCombo.setCurrentIndex(1)
        thubmnailAddCombo.currentTextChanged.connect(self.thumbnailAddChanged)
        self.layout_main.addWidget(thubmnailAddCombo)

        #Thumbnail upload style
        self.layout_main.addWidget(QLabel("When adding thumbnails: "))
        thubmnailAddCombo = QComboBox()
        thubmnailAddCombo.addItems(["always overwrite all thumbnails", "Only add new thumbnails to zip files"])
        if self.GetKeyValue('thumbnails', 'ovewrite') == 'True':
            thubmnailAddCombo.setCurrentIndex(0)
        else:
            thubmnailAddCombo.setCurrentIndex(1)
        thubmnailAddCombo.currentTextChanged.connect(self.thumbnailOverwriteChanged)
        self.layout_main.addWidget(thubmnailAddCombo)

        self.layout_main.addWidget(QLabel(" "))  # spacer
        #self.layout_main.addWidget(QLabel("Select Type of ))
        # Thmbnail Type
        # self.layout_main.addWidget(QLabel("Type of Thumbnails to use"))
        # thumbnail_view = QWidget(self)  # central widget
        # thumbnail_view.setLayout(self.layout_main)
        # view_group = QButtonGroup(thumbnail_view) # Number group
        # thumbnailIcons = QRadioButton("0")
        # number_group.addButton(r0)
        # r1=QtGui.QRadioButton("1")
        # number_group.addButton(r1)
        # layout.addWidget(r0)
        # layout.addWidget(r1)
        #TODO add a bunch more help to users
        """
        QMessageBox.about(self, "Add Thumbnails", "You have Tadpole configured to upload your own thumbnails. \
        In the open file dialog, select the directory where the images are located.  For this to work, \
        The picture names must be the same as the ROM names. A great tool for this is Skraper combined \
        with the 'Full Height Mix' style here: https://github.com/ebzero/garlic-onion-skraper-mix/tree/main#full-height-mix.")
        """
        # Main Buttons Layout (Save/Cancel)
        self.layout_buttons = QHBoxLayout()
        self.layout_main.addLayout(self.layout_buttons)
        
        #Save Existing Cover To File Button
        self.button_write = QPushButton("Continue")
        self.button_write.clicked.connect(self.accept)
        self.layout_buttons.addWidget(self.button_write)     

    def thumbnailAddChanged(self):
        ccombo = self.sender()
        index = ccombo.currentIndex()
        self.WriteValueToFile('thumbnails','download', str(index))
    
    def thumbnailOverwriteChanged(self):
        ccombo = self.sender()
        if ccombo.currentIndex() == 0:
            index = "True"
        else:
            index = "False"
        self.WriteValueToFile('thumbnails','ovewrite', str(index))

    def thumbnailViewClicked(self):
        cbutton = self.sender()
        self.WriteValueToFile('thumbnails', 'view', str(cbutton.isChecked()))

    def GetKeyValue(self, section, key):
        drive = window.combobox_drive.currentText()
        configPath = os.path.join(drive,"Resources","tadpole.ini")
        config.read(configPath)
        if config.has_option(section, key):
            return config.get(section, key)

    def WriteValueToFile(self, section, key, value):
        drive = window.combobox_drive.currentText()
        configPath = os.path.join(drive,"Resources","tadpole.ini")
        if config.has_option(section, key):
            config[section][key] = str(value)
            with open(configPath, 'w') as configfile:
                config.write(configfile)   

# Subclass Qidget to create a thumbnail viewing window        
class thumbnailWindow(QDialog):
    """
        This window should be called without a parent widget so that it is created in its own window.
    """
    def __init__(self, filepath):
        super().__init__()
        layout = QVBoxLayout()
        
        self.setWindowIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)))
        self.setWindowTitle(f"Thumbnail - {filepath}")
        
        # Setup Main Layout
        self.layout_main = QVBoxLayout()
        self.setLayout(self.layout_main)

        # set up current image viewer
        self.layout_main.addWidget(QLabel("Current Image"))
        self.current_viewer = ROMCoverViewer(self)
        self.layout_main.addWidget(self.current_viewer, Qt.AlignCenter)

        self.layout_main.addWidget(QLabel(" "))  # spacer

        # set up new image viewer
        self.layout_main.addWidget(QLabel("New Image"))
        self.new_viewer = ROMCoverViewer(self, changeable=True)
        self.layout_main.addWidget(self.new_viewer, Qt.AlignCenter)

        # Main Buttons Layout (Save/Cancel)
        self.layout_buttons = QHBoxLayout()
        self.layout_main.addLayout(self.layout_buttons)
        
        #Save Existing Cover To File Button
        self.button_write = QPushButton("Save Existing to File")
        self.button_write.clicked.connect(self.WriteImgToFile)
        self.layout_buttons.addWidget(self.button_write)     

        # Save Button
        self.button_save = QPushButton("Overwrite Cover")
        self.button_save.setDefault(True)
        self.button_save.setDisabled(True)  # set disabled by default; need to wait for user to select new image
        self.button_save.clicked.connect(self.accept)
        self.layout_buttons.addWidget(self.button_save)

        # Cancel Button
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.reject)
        self.layout_buttons.addWidget(self.button_cancel)

        # Load Initial Image
        self.current_viewer.load_from_ROM(filepath)
        
    def WriteImgToFile(self):
        newCoverFileName = QFileDialog.getSaveFileName(window,
                                                       'Save Cover',
                                                       'c:\\',
                                                       "Image files (*.png)")[0]
        
        if newCoverFileName is None or newCoverFileName == "":
            print("user cancelled save select")
            return      
        try:
            tadpole_functions.extractImgFromROM(self.current_viewer.path, newCoverFileName)
        except tadpole_functions.Exception_InvalidPath:
            QMessageBox.about(window, "Save ROM Cover", "An error occurred.")
            return
        QMessageBox.about(window, "Save ROM Cover", "ROM cover saved successfully")
       


class ROMCoverViewer(QLabel):
    """
    Args:
        parent (thumbnailWindow): Parent widget. Used to enable/disable controls on parent.
        changeable (bool): If True, will allow importing new image. If False, will just allow static display.
    """
    def __init__(self, parent, changeable=False):
        super().__init__(parent)

        self.changeable = changeable
        self.path = ""  # Used to store path to the currently-displayed file

        self.setStyleSheet("background-color: white;")
        self.setMinimumSize(144, 208)  # resize to Froggy ROM logo dimensions
        self.setFixedSize(144, 208)  # resize to Froggy ROM logo dimensions

        if self.changeable:
            self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.setText("Click to Select New Image")

    def mousePressEvent(self, ev):
        """
        Overrides built-in function to handle mouse click events. Prompts user for image path and loads same.
        """
        if self.changeable:  # only do something if image is changeable
            file_name = QFileDialog.getOpenFileName(self, 'Open file', '',
                                                    "Image files (*.gif *jpeg *.jpg *.png *.webp);;All Files (*.*)")[0]
            if len(file_name) > 0:  # confirm if user selected a file
                self.load_image(file_name)

    def load_from_ROM(self, pathToROM: str):
        """
        Extracts image from the bios and passes to load image function.

        Args:
            drive (str):  Path to the root of the Froggy drive.
        """
        print(f"loading cover from {pathToROM}")
        with open(pathToROM, "rb") as rom_file:
            rom_content = bytearray(rom_file.read())
        with open(os.path.join(basedir, "temp_rom_cover.raw"), "wb") as image_file:
            image_file.write(rom_content[0:((144*208)*2)])

        self.load_image(os.path.join(basedir, "temp_rom_cover.raw"))

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
                img = QImage(f.read(), 144, 208, QImage.Format_RGB16)
        else:  # otherwise let QImage autodetection do its thing
            img = QImage(path)
            if (img.width(), img.height()) != (144, 208): 
                img = img.scaled(144, 208, Qt.KeepAspectRatio, Qt.SmoothTransformation) #Rescale new boot logo to correct size
        self.path = path  # update path
        self.setPixmap(QPixmap().fromImage(img))

        if self.changeable:  # only enable saving for changeable dialogs; prevents enabling with load from bios
            self.parent().button_save.setDisabled(False)
        return True

class DownloadMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        grid_layout = self.layout()

        qt_msgboxex_icon_label = self.findChild(QLabel, "qt_msgboxex_icon_label")
        qt_msgboxex_icon_label.deleteLater()

        qt_msgbox_label = self.findChild(QLabel, "qt_msgbox_label")
        qt_msgbox_label.setAlignment(Qt.AlignCenter)
        grid_layout.removeWidget(qt_msgbox_label)

        qt_msgbox_buttonbox = self.findChild(QDialogButtonBox, "qt_msgbox_buttonbox")
        grid_layout.removeWidget(qt_msgbox_buttonbox)
        
        self.setStyleSheet("QLabel{min-width: 300px}")
        self.setWindowFlags(Qt.CustomizeWindowHint)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        # Create a dialog for progress
        self.progress = QProgressBar()
        self.progress.setFixedWidth(300)

        self.spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        grid_layout.addItem(self.spacer, 0, 0, 1, self.layout().columnCount())
        grid_layout.addWidget(qt_msgbox_label, 1, 0, alignment=Qt.AlignCenter)
        # Add the progress bar at the bottom (last row + 1) and first column with column span
        grid_layout.addWidget(self.progress,2, 0, 1, grid_layout.columnCount(), Qt.AlignCenter )
        grid_layout.addWidget(qt_msgbox_buttonbox, 3, 0, alignment=Qt.AlignCenter)
        qt_msgbox_buttonbox.hide()
    
    def setText(self, text):
        super().setText(text)
        
        longest = ""
        for part in text.split("\n"):
            if len(part) > len(longest):
                longest = part
        
        font_matrix = self.fontMetrics()
        width = font_matrix.boundingRect(longest).width() + 8 # Have to add ~20 as a buffer
        self.spacer = QSpacerItem(width, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout().addItem(self.spacer, 0, 0, 1, self.layout().columnCount())
        
    def showProgress(self, progressValue, refreshBoolean):
        #start_time = time.time()
        self.progress.setValue(progressValue)
        #TODO: This really is tough on long calls on performance, let's only do it when needed
        if refreshBoolean:
            QApplication.processEvents()

    def setDrive(self,drive):
        self.drive = drive
        self.setWindowTitle(f"Change System Shortcuts - {drive}") 
    
            
if __name__ == "__main__":
    try:     
        # Per logger documentation, create logging as soon as possible before other hreads    
        logging.basicConfig(filename=static_LoggingPath,
                        filemode='a',
                        format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.DEBUG)
        logging.info("Tadpole Started")
        #Setup config
        # ERIC: We should probably move this to launching the configParser when opening a drive rather than having it open here as it can delay startup
        config = configparser.ConfigParser()
        # Initialise the Application
        app = QApplication(sys.argv)
        
        # Build the Window
        window = MainWindow()
        window.show()

        # Clear and update the list of consoles. This has to happen before the drive loading in case a valid SD card is already connected
        window.combobox_console.clear()
        for console in tadpole_functions.systems.keys():
            window.combobox_console.addItem(QIcon(), console, console)
        
        # Update list of drives
        window.combobox_drive.addItem(QIcon(), static_NoDrives, static_NoDrives)
        #Check for Froggy SD cards
        reloadDriveList()
        
        app.exec()
    except Exception as e:
        print(f"ERROR: An Exception occurred. {e}")
        logging.exception("main crashed. Error: %s", e)
