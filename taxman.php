<?php

$systems = [
    "ARCADE" => ["mswb7.tax","msdtc.nec","mfpmp.bvs"],
    "FC" => ["rdbui.tax","fhcfg.nec","nethn.bvs"],
    "GB" => ["vdsdc.tax","umboa.nec","qdvd6.bvs"],
    "GBA" => ["vfnet.tax","htuiw.nec","sppnp.bvs"],
    "GBC" => ["pnpui.tax","wjere.nec","mgdel.bvs"],
    "MD" => ["scksp.tax","setxa.nec","wmiui.bvs"],
    "SFC" => ["urefs.tax","adsnt.nec","xvb6c.bvs"]
];


$drive = $argv[1] ?? null;
$sys = $argv[2] ? strtoupper($argv[2]) : null;
$syskeys = array_keys($systems);
$isValidSys = $sys && (in_array($sys,$syskeys) || $sys === "ALL");
$skipConf = ($argv[3] ?? null) === "-sc";

if (!$drive || !$isValidSys) {
    echo "Usage: php taxman.php drive system [-sc]" . PHP_EOL;
    echo "  drive:  the location of your SF2000 SD card" . PHP_EOL;
    echo "  system:  the system to rebuild, one of ARCADE, FC, GB, GBA, GBC, MD, SFC or ALL" . PHP_EOL;
    echo "  -sc:  skip confirmation" . PHP_EOL;
    echo "Example: php taxman.php H: GB" . PHP_EOL;
    die;
}

if (!is_dir($drive)) {
    die("Specified drive is not accessible");
}


echo PHP_EOL;
echo "=== DISCLAIMER ===" . PHP_EOL;
echo PHP_EOL;
echo "This program is experimental and you should proceed with caution!" . PHP_EOL;
echo "Although it will back up the files it modifies, you should make your own backup of the " . PHP_EOL;
echo "Resources folder and ideally your whole SD card so you can restore the original state of" . PHP_EOL;
echo "your device if anything goes wrong." . PHP_EOL;
echo PHP_EOL;
echo "The following functionality from the stock system will be lost by using this program:" . PHP_EOL;
echo "1. Chinese translations of game names (including searching by pinyin initials)." . PHP_EOL;
echo "   Game names will be taken from the filename regardless of language setting." . PHP_EOL;
echo "2. Any custom sorting of games in the menu (e.g. popular games placed at the top)." . PHP_EOL;
echo "   All games will be sorted alphabetically instead." . PHP_EOL;
echo PHP_EOL;
if (!$skipConf) {
    echo "Type Y to continue";
    echo PHP_EOL;
    echo PHP_EOL;
    $conf = trim(fgets(STDIN));
    echo PHP_EOL;
    if (strtoupper($conf)!=="Y") {
        die("Cancelling, no files modified");
    }
}


$drive = $argv[1];
$sys = strtoupper($argv[2]);
if ($sys === "ALL") {
    foreach ($syskeys as $syskey) {
        processSys($syskey);
    }
} else {
    processSys($sys);
}


function processSys($sys) 
{
    global $drive, $systems;
    echo "Processing $sys" . PHP_EOL;
        
    $path = "{$drive}/{$sys}";
    if (!is_dir($path)) {
        echo "Couldn't find folder $path" . PHP_EOL;
        die;
    }

    list($fileIndex, $cnIndex, $pinyinIndex) = $systems[$sys];
    $fileIndexPath = "{$drive}/Resources/{$fileIndex}";
    $cnIndexPath = "{$drive}/Resources/{$cnIndex}";
    $pinyinIndexPath = "{$drive}/Resources/{$pinyinIndex}";

    checkAndBackUpFile($fileIndexPath);
    checkAndBackUpFile($cnIndexPath);
    checkAndBackUpFile($pinyinIndexPath);

    echo "Looking for roms in $path" . PHP_EOL;

    $files = scandir($path,SCANDIR_SORT_NONE); 
    $freg = "/.+\\.(bkp|zip|zfc|zsf|zmd|zgb|zfb|smc|fig|sfc|gd3|gd7|dx2|bsx|swc|nes|nfc|fds|unf|gba|agb|gbz|gbc|gb|sgb|bin|md|smd|gen|sms)/i";
    $files = array_filter($files, function($fn) use ($freg) {return preg_match($freg, $fn);});
    if (!$files) {
        die("No roms found, aborting");
    }
    echo "Found " . count($files) . " roms" . PHP_EOL;

    $strippedNames = array_map(function($name) {return stripFileExtension($name);}, $files);
    $strippedByFilename = array_combine($files, $strippedNames);
    asort($strippedByFilename); // always sort the files without file extensions since that is how they appear in the menu
    // then prepare the maps for the 3 index files
    // for "files" we just want the actual filenames as both key and value, the menu will strip the extensions
    $nameMapFiles = array_combine(array_keys($strippedByFilename), array_keys($strippedByFilename));
    // for the Chinese names and pinyin initials, i'm not supporting that at the moment, so use the English titles
    // but use the stripped versions because the menu will not strip them here
    $nameMapCn = $strippedByFilename;
    $nameMapPinyin = $strippedByFilename;

    writeFile($files, $nameMapFiles, $fileIndexPath);
    writeFile($files, $nameMapCn, $cnIndexPath);
    writeFile($files, $nameMapPinyin, $pinyinIndexPath);

    echo "Done" . PHP_EOL . PHP_EOL;

}

function stripFileExtension($name)
{
    $parts = explode(".", $name);
    array_pop($parts);
    return implode(".",$parts);
}

function checkAndBackUpFile($filePath)
{
    if (!file_exists($filePath)) {
        echo "Couldn't find index file $filePath" . PHP_EOL;
        die;
    }

    if (!file_exists("{$filePath}_orig")) {
        echo "Backing up $filePath as {$filePath}_orig" . PHP_EOL;
        copy($filePath,"{$filePath}_orig") || die("Failed to copy file");
    }
}

function writeFile($files, $nameMap, $indexPath)
{
    $sortPositions = array_flip(array_values($nameMap));
    $positionsBySortPos = [];
    $allFilesStr = "";
    foreach($files as $file) {
        $name = $nameMap[$file];
        $pos = strlen($allFilesStr);
        $sortpos = $sortPositions[$name];
        $positionsBySortPos[$sortpos] = $pos;
        $allFilesStr .= $name . chr(0);
    }

    ksort($positionsBySortPos);
    $posstr = strrev(pack("H*",str_pad(dechex(count($files)),8,"0",STR_PAD_LEFT)));
    foreach($positionsBySortPos as $pos) {
        $hex = strrev(pack("H*",str_pad(dechex($pos),8,"0",STR_PAD_LEFT)));
        $posstr .= $hex;
    }

    echo "Overwriting $indexPath" . PHP_EOL;
    file_put_contents($indexPath, $posstr . $allFilesStr) || die("Failed overwriting file");
}
