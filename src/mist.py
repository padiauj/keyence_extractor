# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost
# Copyright: California Institute of Technology

import PIL
import subprocess
import logging
import os
import glob
from ast import literal_eval as make_tuple
import re
logger = logging.getLogger()

TILE_IMAGE_EXTENSION = ".tif"

ZFILL_SIZE = 5

# Default command line options for MIST
DEFAULT_STITCHING_OPTIONS = {
    "headless": "true",
    "numberingPattern": "HORIZONTALCONTINUOUS",
    "gridOrigin": "UL",
    "filenamePatternType": "SEQUENTIAL",
    "gridWidth": "12",
    "gridHeight": "8",
    "startTile": "1",
    "filenamePattern": "\"\"",
    "imageDir": "",
    "outputFullImage": "false",
    "startRow": "0",
    "startCol": "0",
    "extentWidth": "12",
    "extentHeight": "8",
    "blendingMode": "linear",
    "blendingAlpha": "0.5",
}
JAR_PATH = "fft2d-wdeps.jar"


def from_colon_format(s):
    """
    Extracts the <value> from a string formatted thusly:
    "<field>: <value>"
    """
    return s.split(":")[1].strip()


def filename_to_number(s):
    """ Extracts a tile number from its filename. """
    match = re.search("([0-9]{{{0}}}).tif".format(ZFILL_SIZE), s)
    assert len(match.groups()) == 1
    return int(match.groups()[0])


def extract_corners(positions_path):
    """ Extracts position information from a MIST global positions file.

    Args:
        positions_path: path to MIST global positions file.
    Returns:
        A dictionary indexed by tile number containing the corners of the tile.
    """
    corners = {}
    with open(positions_path, 'r') as f:
        for line in f:
            line = line.strip()
            fields = line.split(";")
            number = filename_to_number(from_colon_format(fields[0]))
            position = make_tuple(from_colon_format(fields[2]))
            corners[number] = position
    return corners


def stitch(image_dir, out_dir, rows, cols, shelloutput=True, remove=True):
    """ Executes MIST against an image directory containing images to be stitched.

    MIST uses phase correlation and peak refinement methods to determine the 
    translations of adjacent images, and ultimately determine absolute 
    positions for unstitched images. 

    Args:
        image_dir: directory containing unstitched images (of filename form 
            00001.tif, 00002.tif, ...)
        out_dir: directory to store MIST output
        rows: Rows in image grid
        cols: Columns in image grid
        shelloutput: `True` if shell output is desired, `False` otherwise
        remove: `True` if MIST output is to be deleted after data extraction, 
            `False` otherwise
    
    Returns:
        A dictionary indexed by image number containing the top-right 
        coordinate of the absolute position in the stitching.
    """

    options = DEFAULT_STITCHING_OPTIONS
    options["imageDir"] = image_dir
    options["outputPath"] = out_dir
    options["gridWidth"] = str(cols)
    options["gridHeight"] = str(rows)
    options["extentWidth"] = str(cols)
    options["extentHeight"] = str(rows)
    options["filenamePattern"] = "{ppppp}" + TILE_IMAGE_EXTENSION
    args = []
    for switch in options:
        args.append("--" + switch)
        args.append(options[switch])

    logger.info("Calling MIST with: {}".format(args))
    if (shelloutput):
        subprocess.call(["java", "-jar", JAR_PATH] + args)
    else:
        subprocess.call(["java", "-jar", JAR_PATH] + args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

    # TODO check success

    corners = extract_corners(
        os.path.join(out_dir, "img-global-positions-1.txt"))
    logger.debug("Extracted corners: {}".format(corners))

    # remove output files
    if (remove):
        for f in glob.glob(os.path.join(out_dir, "img-*.txt")):
            os.remove(f)

    return corners
