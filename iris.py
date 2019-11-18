# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost
# Copyright: California Institute of Technology

import zipfile
import glob
import os
import xml.etree.ElementTree as ET
import subprocess
import re
import uuid 
import argparse
import shutil
import cv2
import ntpath
from ast import literal_eval as make_tuple

JAR_PATH = "MIST-wdeps.jar"
BCF_METADTA_FILENAME = "GroupFileProperty/ImageJoint/properties.xml"
IMAGE_EXTENSION = ".tif"

DEFAULT_STITCHING_OPTIONS = {
    "headless": "true",
    "numberingPattern": "HORIZONTALCONTINUOUS",
    "gridOrigin": "UL",
    "filenamePatternType": "SEQUENTIAL",
    "gridWidth": "12",
    "gridHeight": "8",
    "startTile": "1",
    "filenamePattern": "\"1_XY02_00{ppp}_CH1.tif\"",
    "imageDir": "",
    "outputFullImage": "false",
    "startRow": "0",
    "startCol": "0",
    "extentWidth": "12",
    "extentHeight": "8",
    "blendingMode": "linear",
    "blendingAlpha": "0.5",
}

def get_tag_value(root, tag):
    """
    Gets the value from a tag in an XML object

    Requires that there only be one of such tags in the XML
    """
    val = None
    for idx, elem in enumerate(root.findall(tag)):
        # should only be one of these tags
        assert idx == 0
        val = elem.text
    return val

def get_row_col(path):
    """
    Retrieves the row / column information from a BCF file found in this path
    """
    # TODO what to do if there are two?
    for bcf in glob.glob(os.path.join(path, "*.bcf")):
        bcfzip = zipfile.ZipFile(bcf)
        if (BCF_METADTA_FILENAME in bcfzip.namelist()):
            root = ET.fromstring(bcfzip.read(BCF_METADTA_FILENAME))
            rows = get_tag_value(root, "Row")
            cols = get_tag_value(root, "Column")

            return rows, cols
    # TODO throw error (file not found)
    return None, None

def prep_single_channel(file_list, output_dir):
    """
    Convert single channel images into the grayscale space

    NOTE: make sure the list of images has only a single channel! 
    Otherwise, the maximum of each channel will be taken. 

    """
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    subprocess.check_call([
        "mogrify", "-path", output_dir, "-colorspace", "Gray", "-separate",
        "-maximum"
    ] + [x + "[0]" for x in file_list])

def get_patterned_files(path, pattern):
    m = re.search("{[p]*}", pattern)
    padding = pattern[m.start():m.end()].count("p")
    file_set = set(glob.glob(os.path.join(path, "*" + IMAGE_EXTENSION)))
    patterned_files = []
    for i in range(1,500):
        fname = pattern[:m.start()] + str(i).zfill(padding) + pattern[m.end():]
        gen_path = os.path.join(path, fname)
        if (gen_path in file_set):
            patterned_files.append(gen_path)
        else:
            return patterned_files

def mist(image_dir, output_dir, rows, cols, pattern, positions=None):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    options = DEFAULT_STITCHING_OPTIONS
    options["imageDir"] = image_dir
    options["outputPath"] = output_dir
    options["gridWidth"] = cols
    options["gridHeight"] = rows
    options["extentWidth"] = cols
    options["extentHeight"] = rows
    options["filenamePattern"] = "\"%s\"" % (pattern)
    if (positions):
        options["globalPositionsFile"] = positions
    args = []
    for switch in options:
        args.append("--" + switch)
        args.append(options[switch])

    print(args)

    subprocess.call(["java", "-jar", JAR_PATH] + args)

def from_colon_format(s):
    """
    Extracts the <value> from a string formatted thusly:
    "<field>: <value>"
    """
    return s.split(":")[1].strip()

def add_positions_to_folders(positions, channels, stitch_dir):
    for channel in channels:
        encode_positions(positions, stitch_dir, original, channel)

def encode_positions(positions, out_path, channel):
    with open(out_path, 'w') as out:
        for p in positions:
            out.write("file: %s; corr: %s; position: %s; grid: %s;\n" % 
                    (p['file'] % (channel), p['corr'], p['position'], p['grid']))

def extract_positions(positions_path, channel):
    """
    Extracts position information from a global positions file
    """
    positions = []
    with open(positions_path, 'r') as f:
        for line in f:
            line = line.strip()
            fields = line.split(";")
            positions.append({
                "file":from_colon_format(fields[0]).replace(channel, "%s"),
                "corr": from_colon_format(fields[1]),
                "position": from_colon_format(fields[2]),
                "grid": from_colon_format(fields[3])
                })
    return positions

def prep_image_folders(src_dir, stitch_dir, pattern_format, channels):
    """
    Prepare the image files by moving them into their own directories
    and setting the images to the proper colorspace
    """

    for channel in channels:
        pattern = pattern_format % (channel)
        image_dir = os.path.join(stitch_dir, channel)
        os.mkdir(image_dir)
        patterned_files = get_patterned_files(src_dir, pattern)
        if (channel == "Overlay"):
            for f in patterned_files:
                shutil.copy(f, image_dir)
        else:
            prep_single_channel(patterned_files, image_dir)

def composite(image_dir, positions):
    if (os.path.exists(f)):
        subprocess.check_call([
            "composite", "-geometry", "-colorspace", "Gray", "-separate",])
    for pos in positions:
        f = os.path.join(image_dir, pos['file'])
        pos_tuple = make_tuple(pos['position'])
        magick_geometry = "+"
        if (os.path.exists(f)):
            subprocess.check_call([
                "composite", "-geometry", "-colorspace", "Gray", "-separate",])
        else:
            raise ValueError("Cannot find file %s" % (pos['file']))


prefix = "1_XY02"
channel_for_mist = "CH1"
channels = ["CH1", "CH2", "CH3", "CH4", "Overlay"]
pattern_format = prefix + "_{ppppp}_%s.tif"
SRC_DIR = "/home/padiauj/image_analysis/XY02/"

stitch_dir = os.path.join(SRC_DIR, "stitched")
if os.path.exists(stitch_dir):
    shutil.rmtree(stitch_dir)

os.mkdir(stitch_dir)

prep_image_folders(SRC_DIR, stitch_dir, pattern_format, channels)

rows, cols = get_row_col(SRC_DIR)
pattern = pattern_format % (channel_for_mist)
mist(SRC_DIR, stitch_dir, rows, cols, pattern)
positions = extract_positions(os.path.join(stitch_dir, "img-global-positions-1.txt"), channel_for_mist)

for channel in channels:
    if (channel_for_mist != channel):
        positions_path = os.path.join(stitch_dir, "positions.txt")
        encode_positions(positions, positions_path, channel)
        pattern = pattern_format % (channel)
        mist(SRC_DIR, os.path.join(stitch_dir, channel), rows, cols, pattern, positions=positions_path)
