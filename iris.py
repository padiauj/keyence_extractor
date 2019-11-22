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
import argparse
from ast import literal_eval as make_tuple
from PIL import Image
import numpy as np
import math
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

logger = logging.getLogger()


JAR_PATH = "MIST-wdeps.jar"
BCF_METADTA_FILENAME = "GroupFileProperty/ImageJoint/properties.xml"
IMAGE_EXTENSION = ".tif"

DEFAULT_STITCHING_OPTIONS = {
    "headless": "true",
    "numberingPattern": "HORIZONTALCONTINUOUS",
    "gridOrigin": "UL", "filenamePatternType": "SEQUENTIAL",
    "gridWidth": "12",
    "gridHeight": "8",
    "startTile": "1",
    "filenamePattern": "\"1_XY02_00{ppp}_CH1.tif\"",
    "imageDir": "",
    "outputFullImage": "true",
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
    ] + [x + "[0]" for x in file_list], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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



def file_to_number(f):
    m = re.search('([0-9]{5})', f)
    return int(m.groups()[0])

def encode_positions(positions, out_path):
    with open(out_path, 'w') as out:
        out.write("file_number,x-corner,y-corner\n") 
        for p in positions:
            x =p['position'][0]
            y =p['position'][1]
            out.write("%d,%s,%s\n" % 
                    (p['number'], x, y))

def from_colon_format(s):
    """
    Extracts the <value> from a string formatted thusly:
    "<field>: <value>"
    """
    return s.split(":")[1].strip()

def extract_positions(positions_path):
    """
    Extracts position information from a global positions file
    """
    positions = []
    with open(positions_path, 'r') as f:
        for line in f:
            line = line.strip()
            fields = line.split(";")
            positions.append({
                "number":file_to_number(from_colon_format(fields[0])),
                "corr": from_colon_format(fields[1]),
                "position": make_tuple(from_colon_format(fields[2])),
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
            logger.info("Generating 16-bit grayscale images for channel %s ..." % (channel))
            prep_single_channel(patterned_files, image_dir)

def get_image_metadata(src_dir):
    ptn = "(.*)_[0-9]{5}_(.*)\.tif"
    prefixes = set()
    channels = set()
    for f in glob.glob(os.path.join(src_dir, "*")):
        match = re.search(ptn, ntpath.basename(f))
        if (match):
            prefixes.add(match.group(1))
            channels.add(match.group(2))
    assert len(prefixes) == 1
    return prefixes.pop(), list(channels)

def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

def mist(image_dir, output_dir, rows, cols, pattern):
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
    args = []
    for switch in options:
        args.append("--" + switch)
        args.append(options[switch])

    subprocess.call(["java", "-jar", JAR_PATH] + args)
    pos = extract_positions(os.path.join(output_dir, "img-global-positions-1.txt"))
    encode_positions(pos, os.path.join(output_dir, "stitching.csv"))
    for f in glob.glob(os.path.join(output_dir, "img-*txt")):
        os.remove(f)
        pass
    return pos

def number_to_file(stitch_dir, prefix, channel, number):
    pattern = prefix + "_"  + str(number).zfill(5) + "_" + channel + ".tif"
    return os.path.join(stitch_dir, channel, pattern)

def get_image_size(positions, stitch_dir, prefix, channel):
    x = 0
    y = 0
    sizes = set()
    for pos in positions:
        path = number_to_file(stitch_dir, prefix, channel, pos['number'])
        im = Image.open(path)
        x = max(pos['position'][0] + im.size[0], x)
        y = max(pos['position'][1] + im.size[1], y)
        sizes.add(im.size)
        im.close()

    assert len(sizes) == 1
    return sizes.pop(), (y, x)

def blend_images(positions, stitch_dir, prefix, channel):
    size, output_size = get_image_size(positions, stitch_dir, prefix, channel)
    output = np.zeros(output_size, dtype=np.uint16)
    logger.info("Blending images for channel %s ..." % (channel))
    for idx, pos in enumerate(positions):
        path = number_to_file(stitch_dir, prefix, channel, pos['number'])
        im = cv2.imread(path, -1)
        corner = pos['position']
        section = output[corner[1]:corner[1]+size[1], corner[0]:corner[0] + size[0]]
        section[section == 0] = im[section == 0]
        section[section != 0] = (section[section != 0] + im[section != 0]) / 2
    cv2.imwrite(os.path.join(stitch_dir, channel, channel+"_stitched.png"), output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Iris: Stitch images from fluorescence microscopy")
    parser.add_argument('--path', dest="SRC_DIR", type=dir_path, help="Path containing images to be analyzed (including a BCF file)", required=True)
    parser.add_argument('--stitch-channel', dest="stitch_channel", type=str, help="Channel to use to stitch the images")

    args = parser.parse_args()

    # TODO validate args, verify we have the correct files in number + channels

    stitch_dir = os.path.join(args.SRC_DIR, "iris")
    if os.path.exists(stitch_dir):
        shutil.rmtree(stitch_dir)
    os.mkdir(stitch_dir)

    prefix, channels = get_image_metadata(args.SRC_DIR) 
    rows, cols = get_row_col(args.SRC_DIR)
    logger.info("Discovered image sequence with %s rows and %s columns" % (rows, cols))
    pattern_format = prefix + "_{ppppp}_%s.tif"

    prep_image_folders(args.SRC_DIR, stitch_dir, pattern_format, channels)
    pattern = pattern_format % (args.stitch_channel)
    image_dir = os.path.join(stitch_dir, args.stitch_channel)
    positions = mist(image_dir, stitch_dir, rows, cols, pattern)
    for channel in channels:
        if (channel != "Overlay"):
            blend_images(positions, stitch_dir, prefix, channel)
