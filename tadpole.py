# GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize
from dialogs.BootConfirmDialog import BootConfirmDialog
from dialogs.DownloadProgressDialog import DownloadProgressDialog
from dialogs.ThumbnailDialog import ThumbnailDialog
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
import subprocess

basedir = os.path.dirname(__file__)
static_NoDrives = "N/A"
static_AllSystems = "ALL"
static_LoggingPath = "tadpole.log" # Log to the local directory that tadpole is being run from.
#TODO: Eric, with multiple drives, having multiple Tadpole settings will get annoying. 
static_TadpoleConfigFile = os.path.join("Tadpole","tapdole.ini")

#Use this to poll for SD cards, turn it to False to stop polling
poll_drives = True

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
            rebuildingmsgBox = DownloadProgressDialog()
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

#Trigger is optional and will force a reload
#TODO: Eric, sorry its an optional argument and I couldn't find a better way to foce the polling
#forcing polling to only go through its flow with new user selected drive
def reloadDriveList(trigger = False):
    #If polling is disabled don't do anything
    if poll_drives == True:
        current_drive = window.combobox_drive.currentText()

        # Iterate through the ComboBox in reverse order to safely remove items
        for index in reversed(range(window.combobox_drive.count())):
            user_data = window.combobox_drive.itemData(index)
            #let's add if any new ones showed up
            #If the user created their own, don't remove it
            if isinstance(user_data, str) and user_data != "localDrive":
                window.combobox_drive.removeItem(index)

        for drive in psutil.disk_partitions():
            if os.path.exists(os.path.join(drive.mountpoint, "bios", "bisrv.asd")):
                window.combobox_drive.addItem(QIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)),
                                            drive.mountpoint,
                                            drive.mountpoint)

        if len(window.combobox_drive) > 0:
            toggle_features(True)
            window.btn_coppy_user_selected_button.setEnabled(False)
            window.status_bar.showMessage("SF2000 Drive(s) Detected.", 20000)
            #Eric: Need to check in with Jason on why this was removed.
            #TODO: Eric, not sure why it was originally, but I think the refactor should say != ?
            #In other words, if the drive changes, and its not N/A, let's process it to get things like config file, etc.
            if(current_drive == static_NoDrives or trigger == True):
                print("New drive detected")
                logging.info(f"Automatically triggering drive change because a new drive connected")
                window.combobox_drive_change()
            #Turn on ability to copy if there is at least one other drive selected
            if len(window.combobox_drive) > 1:
                window.btn_coppy_user_selected_button.setEnabled(True)
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
    TadpoleConfigPath = os.path.join(drive, static_TadpoleConfigFile)
    print(f"loading roms to table for ({drive}) ({system})")
    logging.info(f"loading roms to table for ({drive}) ({system})")
    msgBox = DownloadProgressDialog()
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
        print(f"Found {len(files)} ROMs")
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
            config.read(TadpoleConfigPath)
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
                    img = QImage(rom_content[0:((144*208)*2)], 144, 208, QImage.Format_RGB16)
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
    window.window_thumbnail = ThumbnailDialog(rom_path)  
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

    msg_box = DownloadProgressDialog()
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

def FirstRun():
    #Setup settings
    CreateTadpoleFiles()
    drive = window.combobox_drive.currentText()
    logging.info("First Run started.  This means its either brand new, deleted ini file, or something else")
    qm = QMessageBox()
    ret = qm.information(window,'Welcome', "Welcome to Tadpole!\n\n\
Either this is your first time, you've pointed to a new directory for Tadpole, or it is a new version of Tadpole.  However you go here, we are glad you are here!\n\n\
It is advised to update the bootloader to avoid bricking the SF2000 when changing anything on the SD card.\n\n\
Do you want to download and apply the bootloader fix? (Select No if you have already applied the fix previously)", qm.Yes | qm.No)
    if ret == qm.Yes:
        bootloaderPatch()
    else:
        config['bootloader'] = {'patchskipped': True}
        logging.info("User skipped bootloader")

def bootloaderPatch():
    qm = QMessageBox
    ret = qm.question(window, "Download fix", "This will require your SD card and that the SF2000 is well charged.  Do you want to download the fix?")
    if ret == qm.No:
        return
    #cleanup previous files
    drive = window.combobox_drive.currentText()
    if drive == "N/A":
        ret = QMessageBox().question(window, "Insert SD Card", "To fix the bootloader, you must have your SD card plugged in as it downloads critical \
updates to the SD card to update the bootlaoder.  Do you want to plug it in and try detection agian?")
        if ret == qm.Yes:
            bootloaderPatch()
        elif ret == qm.No:
            QMessageBox().about("Update skipped", "No problem.  Just remember if you change any files on the SD card without the bootlaoder \
The SF2000 may not boot.  You can always try this fix again in the Firmware options")
            logging.info("User skipped bootloader")
            return
    bootloaderPatchDir = os.path.join(drive,"/UpdateFirmware/")
    bootloaderPatchPathFile = os.path.join(drive,"/UpdateFirmware/Firmware.upk")
    bootloaderChecksum = "eb7a4e9c8aba9f133696d4ea31c1efa50abd85edc1321ce8917becdc98a66927"
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
Tadpole will try the process again. For more help consult https://github.com/vonmillhausen/sf2000#bootloader-bug\n\
or ask for help on Discord https://discord.gg/retrohandhelds.")
            bootloaderPatch()
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
Remember, you only need to apply the bootloader fix once to your SF2000.  Unlike other changes affecting the SD card, this changes the code running on the SF2000.")
            logging.info("Bootloader installed correctly...or so the user says")
            config['bootloader'] = {'patchapplied': True}
            return
        else:
            QMessageBox().about(window, "Update not successful", "Based on your answer, the update did not complete successfully.\n\n\
Consult https://github.com/vonmillhausen/sf2000#bootloader-bug or ask for help on Discord https://discord.gg/retrohandhelds. ")
            logging.error("Bootloader failed to install...or so the user says")
            config['bootloader'] = {'patchapplied': False}
            return
    else:
        QMessageBox().about(window, "Download did not complete", "Please ensure you have internet and retry the fix")
        logging.error("Bootloader failed to download")
        config['bootloader'] = {'patchapplied': False}
        return

def FixSF2000Boot():
        qm = QMessageBox
        ret = qm.question(window, "SF2000 not booting", "If your SF2000 won't boot, you likely hit the bootloader bug or have broken some critical files.  This process attempts to restore your SF2000.\n\n\
This process will delete ALL SAVES AND ROMS, so if you want to save those, cancel out and do so.\n\n\
This process is only tested on Windows and will not work on Linux/Mac.\n\nDo you want to proceed?")
        if ret == qm.No:
            return
        # ret = qm.question(window,"Save backups?", "Do you want to backup your save files first?")
        # if ret == qm.Yes:
        #     MainWindow.createSaveBackup()    
        #Turn off polling since we are going to mess with the SD card
        turn_off_polling()
        #Stop access to the drives
        window.combobox_drive.addItem(QIcon(), static_NoDrives, static_NoDrives)
        window.status_bar.showMessage("No SF2000 Drive Detected. Please insert SD card and try again.", 20000)
        toggle_features(False)
        formatAndDownloadOSFiles()
        turn_on_polling()

def turn_off_polling():
        global poll_drives 
        poll_drives = False

def turn_on_polling():
        global poll_drives 
        poll_drives = True

def formatAndDownloadOSFiles():
        foundSD = False
        QMessageBox.about(window, "Formatting", "First format your SD card. After pressing OK the partition tool will come up enabling you to format it.\n\n\
Format it to with a drive letter and to FAT32.  It may say the drive is in use; that is Normal as Tadpole is looking for it.")
        try:
            subprocess.Popen('diskmgmt.msc', shell=True)
        except:
            logging.error("Can't run diskpart.  Wrong OS?")
        qm = QMessageBox()
        ret = qm.question(window, "Formatting", "Did you finish formatting it to FAT32?  Tadpole will now try to detect it.")
        if ret == qm.No:
            QMessageBox.about(window, "Formatting", "Please try formating the SD card and trying again.")
            return False
        for drive in psutil.disk_partitions():
            dir = os.listdir(drive.mountpoint)
            #Windows puts in a System inFormation item that is hidden
            if len(dir) > 1:
                continue
            if(drive.mountpoint != f'C:\\'):
                ret = qm.question(window, "Empty SD card found", "Is the right SD card: " + drive.mountpoint + "?")
                if ret == qm.Yes:
                    correct_drive = drive.mountpoint
                    foundSD = True
                    logging.info("SD card was formatted and is empty")
                    break
                if ret == qm.No:
                    continue
        if foundSD == False:
            QMessageBox.about(window, "Empty SD card not found", "Looks like none of the mounted drives in Windows are empty SD cards. Are you sure you formatted it and it is empty?")
            return False
        DownloadOSFiles(correct_drive)
        ret = QMessageBox.question(window, "Try booting",  "Try putting the SD card in the SF2000 and starting it.  Did it work?")
        if ret == qm.No:
            QMessageBox.about(window, "Not booting", "Sorry it didn't work; Consult https://github.com/vonmillhausen/sf2000#bootloader-bug or ask for help on Discord https://discord.gg/retrohandhelds.")
            return False
        ret = QMessageBox.about(window, "Success",  "Congrats!  Now put the SD card back into the computer.  Tadpole will go through its first time setup again.\n\n\
It is going to ask you to patch the bootloader.  Please do so to avoid getting into this state again.")        
        return True

def DownloadOSFiles(correct_drive):
        msgBox = DownloadProgressDialog()
        msgBox.setText("Downloading Firmware Update.")
        msgBox.show()
        #TODO: creating folders as the refactors directory mkdirs isn't working
        os.mkdir(os.path.join(correct_drive,"Resources"))
        os.mkdir(os.path.join(correct_drive,"bios"))
        tadpole_functions.downloadDirectoryFromGithub(correct_drive,"https://api.github.com/repos/EricGoldsteinNz/SF2000_Resources/contents/OS/V1.6", msgBox.progress)
        #Make a bunch of the other directories at github doesn't let you create empty ones
        os.mkdir(os.path.join(correct_drive,"ARCADE"))
        os.mkdir(os.path.join(correct_drive,"ARCADE","bin"))
        os.mkdir(os.path.join(correct_drive,"ARCADE","save"))
        os.mkdir(os.path.join(correct_drive,"ARCADE","skp"))
        os.mkdir(os.path.join(correct_drive,"FC"))
        os.mkdir(os.path.join(correct_drive,"FC","Saves"))
        os.mkdir(os.path.join(correct_drive,"GB"))
        os.mkdir(os.path.join(correct_drive,"GB","Saves"))
        os.mkdir(os.path.join(correct_drive,"GBC"))
        os.mkdir(os.path.join(correct_drive,"GBC","Saves"))
        os.mkdir(os.path.join(correct_drive,"GBA"))
        os.mkdir(os.path.join(correct_drive,"GBA","Saves"))
        os.mkdir(os.path.join(correct_drive,"MD"))
        os.mkdir(os.path.join(correct_drive,"MD","Saves"))
        os.mkdir(os.path.join(correct_drive,"SFC"))
        os.mkdir(os.path.join(correct_drive,"SFC","Saves"))
        os.mkdir(os.path.join(correct_drive,"ROMS"))
        os.mkdir(os.path.join(correct_drive,"ROMS","Saves")) 
        #Need to delete bisrv.asd again to prevent bootloader bug      
        if os.path.exists(os.path.join(correct_drive,"bios","bisrv.asd")):
            os.remove(os.path.join(correct_drive,"bios","bisrv.asd"))
        #Re-add biserv.asd
        #TODO: Review why we are doing this
        tadpole_functions.downloadFileFromGithub(os.path.join(correct_drive,"bios","bisrv.asd"), "https://raw.githubusercontent.com/EricGoldsteinNz/SF2000_Resources/main/OS/V1.6/bios/bisrv.asd")
        msgBox.close()    
        return True

def CreateTadpoleFiles():
    TadpoleFolder = os.path.join(window.combobox_drive.currentText(), "Tadpole")
    TadpoleConfigPath = os.path.join(window.combobox_drive.currentText(), static_TadpoleConfigFile)
    if not os.path.exists(TadpoleFolder):
        os.mkdir(TadpoleFolder)
    if not os.path.isfile(TadpoleConfigPath):
        Path(TadpoleConfigPath).touch()
    tadpole_functions.writeDefaultSettings(window.combobox_drive.currentText())

def SetUserSelectedDirectory(directory, supressed=False):
    qm = QMessageBox()
    old_path = window.combobox_drive.currentText()
    #Supressed means we know its all good, don't give an user prompts/confirmation
    if not supressed:
        #See if it has all folders/files we need
        #TODO: Do more than bios?
        if not os.path.exists(os.path.join(directory, "bios", "bisrv.asd")):
            ret = qm.question(window,'Working location', "This folder doesn't contain the bios folder or bisrv.as file, so it doens't look \
like the root of the SD card.  Do you want us to download all the most up to date files to this folder instead?" , qm.Yes | qm.No)
            #If not, we need them to fix this, start over
            if ret == qm.No:
                directory = QFileDialog.getExistingDirectory()
                if directory != '':
                    SetUserSelectedDirectory(directory)
                return False
            #Add all these in via the FixSF2000 function
            if ret == qm.Yes:
                DownloadOSFiles(directory)
                CreateTadpoleFiles()
        QMessageBox().about(window, "Working location", "When you want to go back to using an SD card, select it in the dropdown list of drives.\n\n\
When you are ready to ovewrite that SD card, press the 'Copy to SD' button")
    window.combobox_drive.addItem(QIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)),
                                        directory + f'/', 'localDrive')
    #TODO: why are some functions failing without the '/'
    # window.combobox_drive.addItem(QIcon(window.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)),
    #                                 directory + f'/', 'localDrive')
    # Set the current index to the newly added item
    new_item_index = window.combobox_drive.count() - 1
    window.combobox_drive.setCurrentIndex(new_item_index)

    # force a reload to build tadpole settings and such
    reloadDriveList(True)

    new_drive = window.combobox_drive.currentText()
    # save this directory to Tadpole...in both places.... :( 
    config = configparser.ConfigParser()
    TadpoleConfigPath = os.path.join(new_drive, static_TadpoleConfigFile)
    config.read(TadpoleConfigPath)
    if config.has_option('file', 'user_directory'):
        config['file']['user_directory'] = new_drive
        with open(os.path.join(new_drive, static_TadpoleConfigFile), 'w') as configfile:
            config.write(configfile)   
    #TODO: Eric maybe we should just keep Tadpole.ini in the Tadpole.exe directory :(...)    
    TadpoleConfigPath = os.path.join(old_path, static_TadpoleConfigFile)
    config.read(TadpoleConfigPath)
    if config.has_option('file', 'user_directory'):
        config['file']['user_directory'] = new_drive
        with open(os.path.join(old_path, static_TadpoleConfigFile), 'w') as configfile:
            config.write(configfile)   
    return True

def setupUserSelectedDrive(config):
    TadpoleConfigPath = os.path.join(window.combobox_drive.currentText(), static_TadpoleConfigFile)
    config.read(TadpoleConfigPath)
    if config.has_option('file', 'user_directory'):
        saved_directory = config.get('file', 'user_directory')
    else:
        return
    #Setup the drive with this directory, we know its good
    #Supress on the user dialogs
    SetUserSelectedDirectory(saved_directory, True)

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
        logging.info("User opened ReadMeDialog")
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
        self.resize(1200,500)

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
        selector_layout.addWidget(self.combobox_drive, stretch=3)

        #User defined
        self.btn_user_dir = QPushButton("Select your own directory...")
        selector_layout.addWidget(self.btn_user_dir)
        self.btn_user_dir.clicked.connect(self.userSelectedDirectoryButton)
        #CopyButton
        self.btn_coppy_user_selected_button = QPushButton("Copy to SD...")
        self.btn_coppy_user_selected_button.setEnabled(False)
        selector_layout.addWidget(self.btn_coppy_user_selected_button)
        self.btn_coppy_user_selected_button.clicked.connect(self.copyUserSelectedDirectoryButton)

        # Spacer
        selector_layout.addWidget(QLabel(" "), stretch=3)

        # Console Select Widgets
        self.lbl_console = QLabel(text="Console:")
        self.lbl_console.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.combobox_console = QComboBox()
        self.combobox_console.activated.connect(self.combobox_console_change)
        selector_layout.addWidget(self.lbl_console)
        selector_layout.addWidget(self.combobox_console, stretch=1)

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
        action_bootloader_patch  = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Bootloader Fix - Built by commnity (Prevents device from not booting and corrupting SD card when changing files on SD card)", self, triggered=bootloaderPatch)                                                                              
        self.menu_os.menu_update.addAction(action_bootloader_patch)   
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
        action_sf2000_boot  = QAction(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)), "Fix SF2000 not booting - Reformats SD card and reinstalls all OS files", self, triggered=FixSF2000Boot)                                                                              
        self.menu_help.addAction(action_sf2000_boot)
        self.menu_help.addSeparator()
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
        msg_box = DownloadProgressDialog()
        msg_box.setText("Detecting firmware version")
        msg_box.show()
        try:
            msg_box.showProgress(50, True)
            detectedVersion = tadpole_functions.bisrv_getFirmwareVersion(os.path.join(drive,"bios","bisrv.asd"))
            if not detectedVersion:
                detectedVersion = "Version Not Found"
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
        msgBox = DownloadProgressDialog()
        msgBox.progress.reset()
        #Check what the user has configured; upload or download
        config = configparser.ConfigParser()
        config.read(drive + static_TadpoleConfigFile)
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
        msgBox = DownloadProgressDialog()
        msgBox.setText(" Loading current boot logo...")
        msgBox.show()
        msgBox.showProgress(50, True)
        dialog = BootConfirmDialog(window.combobox_drive.currentText(), basedir)
        msgBox.close()
        change = dialog.exec()
        if change:
            newLogoFileName = dialog.new_viewer.path
            print(f"user tried to load image: {newLogoFileName}")
            if newLogoFileName is None or newLogoFileName == "":
                print("user cancelled image select")
                return
            try:
                msgBox = DownloadProgressDialog()
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
        TadpoleConfigPath = os.path.join(drive, static_TadpoleConfigFile)
        config.read(TadpoleConfigPath)
        if not config.has_section('view'):
            config.add_section('view')
        if config.has_option('view', 'thumbnails'):
            config['view']['thumbnails'] = str(state)
        else:
            config.set('view', 'thumbnails', str(state))

        with open(TadpoleConfigPath, 'w') as configfile:
            config.write(configfile)
        RunFrogTool(self.combobox_console.currentText())

    def combobox_drive_change(self):
        newDrive = self.combobox_drive.currentText()
        console = self.combobox_console.currentText()
        index = self.combobox_drive.currentIndex()

        logging.info(f"Dialog for drive changed to ({newDrive})")

        
        #Check if the Tadpole config file exists, if not then create it.
        configPath = os.path.join(newDrive, static_TadpoleConfigFile)
        if os.path.isfile(configPath):
            config.read(configPath)
            #TODO every release let's be ultra careful for now and delete tadpole settings...
            #if it has defualt, then it doesn't exist
            try:
                TadpoleVersion = config.get('versions', 'tadpole')
                if TadpoleVersion != "0.3.9.16":
                    os.remove(configPath)
                    FirstRun()
            except:
                os.remove(configPath)
                FirstRun()
        else:
            #Run First Run to create config, check bootloader, etc.
            FirstRun()
        
        loadROMsToTable()

    def combobox_console_change(self):
        console = self.combobox_console.currentText()
        logging.info(f"Dialog for console changed to ({console})")
        # ERIC: We shouldnt run frogtool as soon as the drive is opened. This is a lot of unnecessary processing.  
        RunFrogTool(console)

    def show_readme(self):
        self.readme_dialog = ReadmeDialog()
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
        BisrvLocation = os.path.join(Drive,"bios","bisrv.asd")
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
        UpdateMsgBox = DownloadProgressDialog()
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

        msgBox = DownloadProgressDialog()
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
        msgBox = DownloadProgressDialog()
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
            msgBox = DownloadProgressDialog()
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

    def userSelectedDirectoryButton(self):
        qm = QMessageBox
        ret = qm.question(window,'Working location', "Instead of an SD card, you can define your own working location on your drive.\n\
Once you finish working there, you'll need to 'Copy' everything over to your SD card.  Do you want to use this mode?  If so, click Yes and select the folder that has the \
same contents as the SF2000." , qm.Yes | qm.No)
        if ret == qm.No:
            return
        directory = QFileDialog.getExistingDirectory()
        config = configparser.ConfigParser()
        TadpoleConfigPath = os.path.join(window.combobox_drive.currentText(), static_TadpoleConfigFile)
        config.read(TadpoleConfigPath)
        if config.has_option('file', 'user_directory'):
            saved_directory = config.get('file', 'user_directory')
            if directory == saved_directory:
                QMessageBox.about(self, "Same directory", "You already have this folder set as your local directory.")
                return False
        if directory != '':
            return SetUserSelectedDirectory(directory)
        return False

    def copyUserSelectedDirectoryButton(self):
        source_directory = window.combobox_drive.currentText()
        qm = QMessageBox()
        ret = qm.question(window, "Copy?", "Do you want to copy your entire folder over to the SD?\n\n\
All files will be overriden, INCLUDING game saves.  Are you sure you want to continue?")
        if ret == qm.No:
            return
        for drive in psutil.disk_partitions():
            #TODO: should we check if it has more?
            if os.path.exists(os.path.join(drive.mountpoint, "bios", "bisrv.asd")):
                #TODO: should we copy everything in this folder or what?
                #TODO: what happens if we run out of space?
                ret = qm.question(window, "SD Card", "Froggy files found on " + drive.mountpoint + "\n\nAre you sure you want to copy and overwrite all files, including saves?")
                if ret == qm.No:
                    return
                destination_directory = drive.mountpoint

                #show indeterminite progress bar
                progressMsgBox = DownloadProgressDialog()
                progressMsgBox.setText("Copying files")
                progressMsgBox.progress.setMinimum(0)
                progressMsgBox.progress.setMaximum(0)
                progressMsgBox.show()
                QApplication.processEvents()
                #copy everything over
                shutil.copytree(source_directory, destination_directory, dirs_exist_ok=True)
                progressMsgBox.close()
                QMessageBox.about(window, "Success", "Files copied successfully.")
                return

# Subclass Qidget to create a Settings window        
class SettingsWindow(QDialog):
    """
        This window should be called without a parent widget so that it is created in its own window.
    """
    def __init__(self):
        super().__init__()
        
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

        #File options options
        self.layout_main.addWidget(QLabel("File Options"))
        UserSavedDirectory = self.GetKeyValue('file', 'user_directory')
        self.layout_main.addWidget(QLabel(f"User defined directory:"))
        self.user_directory = QLabel(UserSavedDirectory, self)
        self.layout_main.addWidget(self.user_directory)
        self.btn_change_user_dir = QPushButton("Select your own local directory...")
        self.layout_main.addWidget(self.btn_change_user_dir)
        self.btn_change_user_dir.clicked.connect(self.userSelectedDirectorySettingsButton)
        #Let's finish removing later...
        #self.btn_remove_user_dir = QPushButton("Remove your local directory from Tadpole")
        #self.layout_main.addWidget(self.btn_remove_user_dir)
        #self.btn_remove_user_dir.clicked.connect(self.userSelectedDirectoryResetSettingsButton)
                
        self.layout_main.addWidget(QLabel(" "))  # spacer

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

    def userSelectedDirectorySettingsButton(self):
        if window.userSelectedDirectoryButton():
            drive = window.combobox_drive.currentText()
            self.user_directory.setText(drive)

    def userSelectedDirectoryResetSettingsButton(self):
        self.WriteValueToFile('file','user_directory', 'None')
        self.user_directory.setText('None')
        self.user_directory.adjustSize()        

    def thumbnailViewClicked(self):
        cbutton = self.sender()
        self.WriteValueToFile('thumbnails', 'view', str(cbutton.isChecked()))

    def GetKeyValue(self, section, key):
        drive = window.combobox_drive.currentText()
        config.read(os.path.join(drive, static_TadpoleConfigFile))
        if config.has_option(section, key):
            return config.get(section, key)

    def WriteValueToFile(self, section, key, value):
        drive = window.combobox_drive.currentText()
        if config.has_option(section, key):
            config[section][key] = str(value)
            with open(os.path.join(drive, static_TadpoleConfigFile), 'w') as configfile:
                config.write(configfile)   
            
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
        # Jason: Yes...but if we need to pull settings to configure the window we'll need it pretty soon
        # Since polling comes right after the window is shown, I think that is the only place to put it...
        # It would need some rework and I don't know if it buys us anything we are pulling settings at launch
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

        setupUserSelectedDrive(config)

        app.exec()
    except Exception as e:
        print(f"ERROR: An Exception occurred. {e}")
        logging.exception("main crashed. Error: %s", e)
