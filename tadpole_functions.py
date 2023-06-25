import os
import sys
import shutil

def GBABIOSFix(drive):
    if drive == "???":
        raise Exception_InvalidPath
    GBABIOSPath = f"{drive}/bios/gba_bios.bin"
    if not os.path.exists(GBABIOSPath):
        print(f"! Couldn't find game list file {GBABIOSPath}")
        print("  Check the provided path points to an SF2000 SD card!")
        raise Exception_InvalidPath
    try:
        GBAFolderPath = f"{drive}/GBA/mnt/sda1/bios/"
        ROMSFolderPath = f"{drive}/ROMS/mnt/sda1/bios/"
        os.makedirs(os.path.dirname(GBAFolderPath), exist_ok=True)       
        os.makedirs(os.path.dirname(ROMSFolderPath), exist_ok=True)
        shutil.copyfile(GBABIOSPath, f"{GBAFolderPath}/gba_bios.bin")
        shutil.copyfile(GBABIOSPath, f"{ROMSFolderPath}/gba_bios.bin")
    except (OSError, IOError) as error:
        print("! Failed to copy GBA BIOS.")
        print(error)
        raise Exception_InvalidPath
    
    
    
class Exception_InvalidPath(Exception):
    pass    