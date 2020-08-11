import xml.etree.ElementTree as ET
import glob
import mmap
import os
import re
import json
import unicodedata
import argparse
import cv2
import numpy as np
from collections import defaultdict

ALLOWABLE_CHANNELS = ["CH1", "CH2", "CH3", "CH4", "CH5"]

def extract_xml(path):
    """
    Extracts hidden XML metadata from Keyence BZ-X microscope TIFF images.

    Args:
        f (obj): A path to a TIFF file.
    
    Returns:
        Safe XML string in ASCII encoding
    """
    xml = ""
    with open(path, "r+") as tif:
        mm = mmap.mmap(tif.fileno(), 0)
        midx = mm.find(b"<?xml")
        xml = mm[midx:].decode('utf-8')

    # force any unicode character into some decent ASCII approximation
    return unicodedata.normalize('NFKD', xml).encode('ascii', 'ignore')


def position_info(path):
    """
    Extracts XY position of the top-left corner from XML metadata.

    Args:
        path (str): Path to TIFF tile file. 
    
    Returns: 
        (x,y) int tuple containing the coordinate of the top left corner in 
        the stitched image (normalized to pixel coordinates)
    """

    # grab the hidden XML data from the TIFF file
    xml = extract_xml(path)

    root = ET.fromstring(xml)

    try:
        orig_image_size = next(root.iter("OriginalImageSize"))
        orig_width = int(orig_image_size.find("Width").text)
        orig_height = int(orig_image_size.find("Height").text)

        xystageregion = next(root.iter("XyStageRegion"))
        x = int(xystageregion.find('X').text)
        y = int(xystageregion.find('Y').text)
        unscaled_height = int(xystageregion.find('Height').text)
        unscaled_width = int(xystageregion.find('Width').text)
    except ValueError:
        raise ValueError("Improper XML format in TIFF file.")

    width_scaling_factor = float(orig_width) / unscaled_width
    height_scaling_factor = float(orig_height) / unscaled_height

    # width_scaling_factor and height_scaling_factor usually the same
    norm_x = x * width_scaling_factor
    norm_y = y * height_scaling_factor

    return (norm_x, norm_y), (orig_width, orig_height)


def fix_origin(corner_dict):
    """
    Corrects the origin of the stitched image to 0,0 at the top left corner

    Args:
        A dictionary (keyed on the path) that specifies the uncorrected coordinates of each tile file
    
    Returns:
        Origin corrected dictionary of tile image positions
    """

    x_origin = max([corner_dict[k][0] for k in corner_dict.keys()])
    y_origin = max([corner_dict[k][1] for k in corner_dict.keys()])

    return {
        k:
        (int(x_origin - corner_dict[k][0]), int(y_origin - corner_dict[k][1]))
        for k in corner_dict.keys()
    }


def get_stitching(file_list):
    corner_dict = {}
    size_dict = {}
    for f in file_list:
        corner, size = position_info(f) 
        corner_dict[f] = corner
        size_dict[f] = size
    corner_dict = fix_origin(corner_dict)
    return corner_dict, size_dict

def get_blended_size(file_lst, corner_dict, size_dict):
    assert len(file_lst) > 0
    max_x_key = file_lst[0]
    max_y_key = file_lst[0]
    for f in file_lst:
        if (corner_dict[f][0] > corner_dict[max_x_key][0]):
            max_x_key = f

        if (corner_dict[f][1] > corner_dict[max_y_key][1]):
            max_y_key = f
    
    return (corner_dict[max_x_key][0] + size_dict[max_x_key][0], corner_dict[max_y_key][1] + size_dict[max_y_key][1])

def blend(file_lst, outpath, corner_dict, size_dict, channels=1):
    """
    Blend files through by averaging overlaps
    """
    full_size = get_blended_size(file_lst, corner_dict, size_dict)
    output = np.zeros(shape=(full_size[1], full_size[0]), dtype=np.uint16)
    # logger.debug("Blend output size {}".format(output.shape))
    for f in file_lst:
        im = None
        im = cv2.imread(f, -1)
        im = np.sum(im, axis=2)
        corner = corner_dict[f]
        size = size_dict[f]
        output[corner[1]:corner[1] + size[1], corner[0]:corner[0] + size[0]] = (output[corner[1]:corner[1] + size[1], corner[0]:corner[0] + size[0]] + im) / 2
    cv2.imwrite(outpath, output)


def get_channel_lists(file_lst):
    """
    Takes in a list of file paths and returns a dictionary of paths
    indexed by the channel name
    """
    channels = defaultdict(list)
    for f in file_lst:
        fields = f.split("_")[-1].split(".")
        
        if (len(fields) == 2 and fields[0] in ALLOWABLE_CHANNELS and (fields[1] == "TIF" or fields[1] == "tif")):
            channels[fields[0]].append(f)
    return channels

def dir_path(d):
    """ Verifies validity of directory provided. 

    Args:
        d: A string representing a directory.
    """
    if os.path.isdir(d):
        return d
    else:
        raise NotADirectoryError(d)

def output_stitching(corners, path):
    with open(path, 'w') as f:
        f.write(json.dumps(corners))

def main():
    parser = argparse.ArgumentParser(
        description="Iris: Stitch images from fluorescence microscopy")
    parser.add_argument(
        '--path',
        dest="IMAGE_DIR",
        type=dir_path,
        help="Path containing images to be analyzed",
        required=True)

    args = parser.parse_args()
    file_lst = glob.glob(args.IMAGE_DIR + "/*.tif")
    channels = get_channel_lists(file_lst) 
    verified_files = [item for sublist in channels.values() for item in sublist]
    corners, size = get_stitching(verified_files)
    output_stitching(corners, "stitching.json")
    print("Outputted stitching positions to stitching.json")
    for channel in channels:
        path = channel + "_stitched.tif"
        print("Outputting blended {channel} to {path}.".format(channel=channel, path=path))
        blend(channels[channel], path, corners, size)
        print("Outputted blended {channel} to {path}.".format(channel=channel, path=path))

if __name__ == "__main__":
    main()