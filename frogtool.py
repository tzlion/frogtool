import os
import sys
import re
import binascii
import shutil
import struct

try:
    from PIL import Image
    from PIL import ImageDraw
    image_lib_avail = True
except ImportError:
    Image = None
    ImageDraw = None
    image_lib_avail = False

from sys import platform
if platform == "win32":
    import ctypes
    if ctypes.windll:
        ctypes.windll.kernel32.SetConsoleTitleW("frogtool")

systems = {
    "ARCADE": ["mswb7.tax", "msdtc.nec", "mfpmp.bvs"],
    "FC":     ["rdbui.tax", "fhcfg.nec", "nethn.bvs"],
    "GB":     ["vdsdc.tax", "umboa.nec", "qdvd6.bvs"],
    "GBA":    ["vfnet.tax", "htuiw.nec", "sppnp.bvs"],
    "GBC":    ["pnpui.tax", "wjere.nec", "mgdel.bvs"],
    "MD":     ["scksp.tax", "setxa.nec", "wmiui.bvs"],
    "SFC":    ["urefs.tax", "adsnt.nec", "xvb6c.bvs"]
}

supported_rom_ext = [
    "bkp", "zip", "zfc", "zsf", "zmd", "zgb", "zfb", "smc", "fig", "sfc", "gd3", "gd7", "dx2", "bsx", "swc", "nes",
    "nfc", "fds", "unf", "gba", "agb", "gbz", "gbc", "gb", "sgb", "bin", "md", "smd", "gen", "sms"
]
zxx_ext = {
    "ARCADE": "zfb", "FC": "zfc", "GB": "zgb", "GBA": "zgb", "GBC": "zgb", "MD": "zmd", "SFC": "zsf"
}
supported_img_ext = [
    "png", "jpg", "jpeg", "gif"
]
supported_zip_ext = [
    "bkp", "zip"
]


class StopExecution(Exception):
    pass


def int_to_4_bytes_reverse(src_int):
    hex_string = format(src_int, "x").rjust(8, "0")[0:8]
    return binascii.unhexlify(hex_string)[::-1]  # reverse it


def file_entry_to_name(file_entry):
    return file_entry.name


def check_file(file_entry, supported_exts):
    file_regex = ".+\\.(" + "|".join(supported_exts) + ")$"
    return file_entry.is_file() and re.search(file_regex, file_entry.name.lower())


def check_rom(file_entry):
    return check_file(file_entry, supported_rom_ext)


def check_img(file_entry):
    return check_file(file_entry, supported_img_ext)


def check_zip(file_entry):
    return check_file(file_entry, supported_zip_ext)


def strip_file_extension(name):
    parts = name.split(".")
    parts.pop()
    return ".".join(parts)


def sort_normal(unsorted_list):
    return sorted(unsorted_list)


def sort_without_file_ext(unsorted_list):
    stripped_names = list(map(strip_file_extension, unsorted_list))
    sort_map = dict(zip(unsorted_list, stripped_names))
    return sorted(sort_map, key=sort_map.get)


def process_sys(drive, system, test_mode):
    print(f"Processing {system}")

    roms_path = f"{drive}/{system}"
    if not os.path.isdir(roms_path):
        print(f"! Couldn't find folder {roms_path}")
        print("  Check the provided path points to an SF2000 SD card!")
        raise StopExecution

    index_path_files = f"{drive}/Resources/{systems[system][0]}"
    index_path_cn = f"{drive}/Resources/{systems[system][1]}"
    index_path_pinyin = f"{drive}/Resources/{systems[system][2]}"
    check_and_back_up_file(index_path_files)
    check_and_back_up_file(index_path_cn)
    check_and_back_up_file(index_path_pinyin)

    print(f"Looking for files in {roms_path}")

    if system != "ARCADE":
        convert_zip_image_pairs_to_zxx(roms_path, system)

    files = os.scandir(roms_path)
    files = list(filter(check_rom, files))
    no_files = len(files)
    if no_files == 0:
        print("No ROMs found! Type Y to confirm you want to save an empty game list, or anything else to cancel")
        conf = input()
        if conf.upper() != "Y":
            print("Cancelling, game list not modified")
            return
    else:
        print(f"Found {no_files} ROMs")

    filenames = list(map(file_entry_to_name, files))
    stripped_names = list(map(strip_file_extension, filenames))

    # prepare maps of filenames to index name for the 3 index files
    # for "files" we just want the actual filenames as both key and value, the menu will strip the extensions
    name_map_files = dict(zip(filenames, filenames))
    # for the Chinese names and pinyin initials, i'm not supporting that at the moment, so use the English titles
    # but use the stripped versions because the menu will not strip them here
    name_map_cn = dict(zip(filenames, stripped_names))
    name_map_pinyin = dict(zip(filenames, stripped_names))

    write_index_file(name_map_files, sort_without_file_ext, index_path_files, test_mode)
    write_index_file(name_map_cn, sort_normal, index_path_cn, test_mode)
    write_index_file(name_map_pinyin, sort_normal, index_path_pinyin, test_mode)

    print("Done\n")


def find_matching_file_diff_ext(target, files):
    target_no_ext = strip_file_extension(target.name)
    for file in files:
        file_no_ext = strip_file_extension(file.name)
        if file_no_ext == target_no_ext:
            return file


def convert_zip_image_pairs_to_zxx(roms_path, system):

    img_files = os.scandir(roms_path)
    img_files = list(filter(check_img, img_files))
    zip_files = os.scandir(roms_path)
    zip_files = list(filter(check_zip, zip_files))
    sys_zxx_ext = zxx_ext[system]
    if not img_files or not zip_files:
        return
    print(f"Found image and zip files, looking for matches to combine to {sys_zxx_ext}")

    imgs_processed = 0
    for img_file in img_files:
        zip_file = find_matching_file_diff_ext(img_file, zip_files)
        if not zip_file:
            continue
        converted = convert_zip_image_to_zxx(roms_path, img_file, zip_file, sys_zxx_ext)
        if not converted:
            print("! Aborting image processing due to errors")
            break
        imgs_processed += 1

    if imgs_processed:
        print(f"Combined {imgs_processed} zip + image pairs into .{sys_zxx_ext} files")


def convert_zip_image_to_zxx(path, img_file, zip_file, zxx_ext):

    img_file_path = f"{path}/{img_file.name}"
    zip_file_path = f"{path}/{zip_file.name}"
    zxx_file_name = f"{strip_file_extension(img_file.name)}.{zxx_ext}"
    zxx_file_path = f"{path}/{zxx_file_name}"

    converted = rgb565_convert(img_file_path, zxx_file_path, (144, 208))
    if not converted:
        return False

    try:
        zxx_file_handle = open(zxx_file_path, "ab")
        zip_file_handle = open(zip_file_path, "rb")
        zxx_file_handle.write(zip_file_handle.read())
        zxx_file_handle.close()
        zip_file_handle.close()
    except (OSError, IOError):
        print(f"! Failed appending zip file to {zxx_file_name}")
        return False

    try:
        os.remove(img_file_path)
        os.remove(zip_file_path)
    except (OSError, IOError):
        print(f"! Failed deleting source file(s) after creating {zxx_file_name}")
        return False

    return True


def rgb565_convert(src_filename, dest_filename, dest_size=None):

    if not image_lib_avail:
        print("! Pillow module not found, can't do image conversion")
        return False
    try:
        image = Image.open(src_filename)
    except (OSError, IOError):
        print(f"! Failed opening image file {src_filename} for conversion")
        return False
    try:
        dest_file = open(dest_filename, "wb")
    except (OSError, IOError):
        print(f"! Failed opening destination file {dest_filename} for conversion")
        return False

    if dest_size and image.size != dest_size:
        image = image.resize(dest_size)

    image_height = image.size[1]
    image_width = image.size[0]
    pixels = image.load()

    for h in range(image_height):
        for w in range(image_width):
            r = pixels[w, h][0] >> 3
            g = pixels[w, h][1] >> 2
            b = pixels[w, h][2] >> 3
            rgb = (r << 11) | (g << 5) | b
            dest_file.write(struct.pack('H', rgb))

    dest_file.close()

    return True


def check_and_back_up_file(file_path):
    if not os.path.exists(file_path):
        print(f"! Couldn't find game list file {file_path}")
        print("  Check the provided path points to an SF2000 SD card!")
        raise StopExecution

    if not os.path.exists(f"{file_path}_orig"):
        print(f"Backing up {file_path} as {file_path}_orig")
        try:
            shutil.copyfile(file_path, f"{file_path}_orig")
        except (OSError, IOError):
            print("! Failed to copy file.")
            print("  Check the SD card and Resources directory are writable.")
            raise StopExecution


def write_index_file(name_map, sort_func, index_path, test_mode):
    # entries must maintain a consistent order between all indexes, but what that order actually is doesn't matter
    # so use alphabetised filenames for this
    sorted_filenames = sorted(name_map.keys())
    # build up the list of names in that order as a byte string, and also build a dict of pointers to each name
    names_bytes = b""
    pointers_by_name = {}
    for filename in sorted_filenames:
        display_name = name_map[filename]
        current_pointer = len(names_bytes)
        pointers_by_name[display_name] = current_pointer
        names_bytes += display_name.encode('utf-8') + chr(0).encode('utf-8')

    # build the metadata - first value is the total count of games in this list
    metadata_bytes = int_to_4_bytes_reverse(len(name_map))
    # the rest are pointers to the display names in the desired display order
    # so sort display names according to the display order, and build a list of pointers in that order
    sorted_display_names = sort_func(name_map.values())
    sorted_pointers = map(lambda name: pointers_by_name[name], sorted_display_names)
    for current_pointer in sorted_pointers:
        metadata_bytes += int_to_4_bytes_reverse(current_pointer)

    new_index_content = metadata_bytes + names_bytes

    if test_mode:
        print(f"Checking {index_path}")
        file_handle = open(index_path, 'rb')
        existing_index_content = file_handle.read(os.path.getsize(index_path))
        file_handle.close()
        if existing_index_content != new_index_content:
            print("! Doesn't match")
        return

    print(f"Overwriting {index_path}")
    try:
        file_handle = open(index_path, 'wb')
        file_handle.write(new_index_content)
        file_handle.close()
    except (IOError, OSError):
        print("! Failed overwriting file.")
        print("  Check the SD card and file are writable, and the file is not open in another program.")
        raise StopExecution


def check_sys_valid(system):
    return system and (system in systems.keys() or system == "ALL")


def run():

    print("frogtool v0.2.0")

    flags = ["-sc", "-tm"]
    drive = sys.argv[1] if len(sys.argv) >= 2 and sys.argv[1] not in flags else ""
    system = sys.argv[2].upper() if len(sys.argv) >= 3 and sys.argv[2] not in flags else ""
    skip_conf = "-sc" in sys.argv
    # -tm does a "dry run" and checks that the generated files would be the same as the ones on the card
    # this is mostly for development purposes to make sure code changes haven't unintentionally affected output
    test_mode = "-tm" in sys.argv

    while not drive or not os.path.isdir(drive):
        if drive and not os.path.isdir(drive):
            if len(drive) == 1 and os.path.isdir(f"{drive}:"):
                drive = f"{drive}:"
                continue
            else:
                print("! Specified drive or path is not accessible")
        print()
        print("Please enter the drive or path where your SF2000 SD card is located e.g. F:")
        drive = input()

    while not system or not check_sys_valid(system):
        if system and not check_sys_valid(system):
            print("! Specified system is not one of the accepted options")
        print()
        print("Please enter the system to rebuild game list for: ARCADE, FC, GB, GBA, GBC, MD, SFC or ALL")
        system = input().upper()

    print()
    print("=== DISCLAIMER ===")
    print()
    print("This program is experimental and you should proceed with caution!")
    print("Although it will back up the files it modifies, you should make your own backup of the ")
    print("Resources folder and ideally your whole SD card so you can restore the original state of")
    print("your device if anything goes wrong.")
    print()
    print("The following functionality from the stock system will be lost by using this program:")
    print("1. Chinese translations of game names (including searching by pinyin initials).")
    print("   Game names will be taken from the filename regardless of language setting.")
    print("2. Any custom sorting of games in the menu (e.g. popular games placed at the top).")
    print("   All games will be sorted alphabetically instead.")
    print()
    if not skip_conf:
        print("Type Y to continue, or anything else to cancel")
        conf = input()
        if conf.upper() != "Y":
            print("Cancelling, no files modified")
            return
        print()

    try:
        keys_to_process = systems.keys() if system == "ALL" else [system]
        for syskey in keys_to_process:
            process_sys(drive, syskey, test_mode)
    except StopExecution:
        pass

    if not skip_conf:
        # require user input before terminating to give a chance to read messages in case this was started from the GUI
        print()
        print("Press enter to exit")
        input()


try:
    run()
except KeyboardInterrupt:
    pass
