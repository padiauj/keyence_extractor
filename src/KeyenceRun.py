# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost
# Copyright: California Institute of Technology

import xml.etree.ElementTree as ET
import zipfile
import glob
import os
import re
import sys
import ntpath
import logging
import subprocess
import cv2
import numpy as np

from tile import TileSequence

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

# The path within the BCF zip file containing the grid pattern of the
# tiles
BCF_GRID_PROPERTIES = "GroupFileProperty/ImageJoint/properties.xml"
BCF_CHANNEL_NAMES = [("Channel" + str(x), "CH" + str(x + 1)) for x in range(5)]
BCF_CHANNEL_PROPERTIES = "GroupFileProperty/{}/properties.xml"
BCF_IMAGE_SIZE_PROPERTIES = "GroupFileProperty/Image/OriginalImageSize/properties.xml"

TILE_IMAGE_EXTENSION = ".tif"

KEYENCE_TILE_PATTERN = "(.*)_([0-9]{5})_(.*)" + TILE_IMAGE_EXTENSION

ZFILL_SIZE = 5

DEBUG = True


class KeyenceRun():
    """ A class to extract experimental information from a run on the Keyence BZ-X style microscope. 

    Keyence stores imaging data from an experiment in a directory containing 
    images for each position and each channel. In addition, in this directory,
    Keyence stores a .bcf file (truly a .zip file) containing many important 
    properties in an experiment. This class contains methods to interpret the
    data in this directory and generate a TileSequence from the data.

    Attributes:
        path: path to the Keyence data for this run.
        bcfzip: A ZipFile object of the .bcf file
        rows: An integer describing number of rows in the image grid
        cols: An integer describing the number of columns in the image grid
        tile_size: A tuple representing size (in pixels) of a single image in 
            the grid (width, height)
        images: A dictionary indexed on filenames representing valid images 
            from the image grid 
        channels: A list of valid channels (containing rows*cols images)
        channel_names: A dictionary indexed on generic channel names into the 
            ones specified on the Keyence machine 
    """
    def __init__(self, path):
        """ Initializes a KeyenceRun object at the path specified. """

        self.path = path
        self.bcfzip = zipfile.ZipFile(self.__get_bcf(self.path))

        self.__get_grid()
        self.__get_channels()
        self.__get_tile_size()
        self.__get_images()

    def prepare(self, iris_dir=None):
        """ Prepares a compliant TileSequence directory. 

        Uses the images in the Keyence data path along with metadata discovered
        from .bcf file. This involves converting any single channel images into
        16-bit single channel grayscale images to standardize analysis. 

        Args:
            iris_dir: A directory to output converted images 
        Returns:
            Directory where standardized images were outputted
        """
        if (iris_dir):
            self.iris_dir = iris_dir
        else:
            self.iris_dir = os.path.join(self.path, "iris")
        # verify this path doesn't already exist
        if (not os.path.exists(self.iris_dir)):
            os.mkdir(self.iris_dir)

        for channel in self.channels:
            channel_dir = os.path.join(self.iris_dir, channel)
            if (not os.path.exists(channel_dir)):
                os.mkdir(os.path.join(channel_dir))
            logger.info(
                "Converting {} images to 16-bit grayscale images at {}".format(
                    channel, channel_dir))
            for key in self.images:
                if (self.images[key]['channel'] == channel):
                    inpath = os.path.join(self.path, key)
                    outpath = os.path.join(
                        channel_dir,
                        str(self.images[key]['number']).zfill(ZFILL_SIZE) +
                        TILE_IMAGE_EXTENSION)
                    logger.debug(
                        "Converting {} to 16-bit grayscale image {}".format(
                            inpath, outpath))
                    self.gray(inpath, outpath)

        return self.iris_dir

    def gray(self, infile, outfile):
        """ Converts a single channel image to 16-bit grayscale.

        Checks which channel, if any, has the data, and uses this channel as 
        the grayscale channel

        Args:
            infile: path to file to be converted
            outfile: path to file for converted file to be written
        """
        if (DEBUG):
            if (os.path.exists(outfile)):
                return
        im = cv2.imread(infile, -1)
        # take the sums of each of the channels independently and figure out which is the greatest
        # almost always, one channel will have data the others will be 0
        # TODO figure out how to do Cy5 (what the proper behavior should be)
        sums = [np.sum(im[:, :, x]) for x in range(im.shape[2])]
        argmin = max(range(len(sums)), key=lambda x: sums[x])

        # only one channel should have data
        # TODO deprecate with support for Cy5
        assert sums.count(0) == 2

        # output the image
        cv2.imwrite(outfile, im[:, :, argmin])

    @staticmethod
    def __get_bcf(path):
        """ Finds .bcf file within path. 

        Args:
            path: Path to search for .bcf file 
        """
        bcffiles = glob.glob(os.path.join(path, "*.bcf"))
        assert (len(bcffiles) == 1)
        logger.info("Discovered BCF file: {}".format(bcffiles[0]))
        return bcffiles[0]

    @staticmethod
    def __get_tag(root, tag):
        """ Gets the value from a tag in an XML object. 
        Ensures that only one of these tags exist in the provided XML

        Args:
            root: root XML object
            tag: A string representing the tag, whose value is to be extracted
        
        Returns:
            string value encapsulated by tag
        """
        val = None
        for idx, elem in enumerate(root.findall(tag)):
            # should only be one of these tags
            assert idx == 0
            val = elem.text
        return val

    def __get_tile_size(self):
        """ Gets image size information from .bcf file. """
        if (BCF_IMAGE_SIZE_PROPERTIES in self.bcfzip.namelist()):
            root = ET.fromstring(self.bcfzip.read(BCF_IMAGE_SIZE_PROPERTIES))
            self.tile_size = (int(self.__get_tag(root, "Width")),
                              int(self.__get_tag(root, "Height")))
        else:
            raise FileNotFoundError(
                "Image properties {} not found within BCF file {}".format(
                    BCF_IMAGE_SIZE_PROPERTIES, self.path))
        logger.info("Tile size: {}".format(str(self.tile_size)))

    def __get_channels(self):
        """ Gets channel information from .bcf file. """
        self.channel_names = {}
        for channel in BCF_CHANNEL_NAMES:
            if (BCF_CHANNEL_PROPERTIES.format(
                    channel[0]) in self.bcfzip.namelist()):
                root = ET.fromstring(
                    self.bcfzip.read(BCF_CHANNEL_PROPERTIES.format(
                        channel[0])))
                self.channel_names[channel[1]] = self.__get_tag(
                    root, "Comment")
        logger.info("Discovered channel information: [{}]".format(",".join(
            [str((k, self.channel_names[k])) for k in self.channel_names])))

    def __get_grid(self):
        """ Retrieves the row / column information from the .bcf file. """
        if (BCF_GRID_PROPERTIES in self.bcfzip.namelist()):
            root = ET.fromstring(self.bcfzip.read(BCF_GRID_PROPERTIES))
            self.rows = int(self.__get_tag(root, "Row"))
            self.cols = int(self.__get_tag(root, "Column"))
        else:
            raise FileNotFoundError(
                "Grid properties %s not found within BCF file %s" %
                (BCF_GRID_PROPERTIES, self.path))
        logger.info("Image grid: {} rows, {} columns".format(
            self.rows, self.cols))

    def __get_images(self):
        """ Searches Keyence data path for image files.

        The Keyence data path contains *.tif files with one image per channel 
        and per grid position. If a channel has an image for each grid 
        position, it is considered a valid channel.
        """
        images = {}
        for imagepath in glob.glob(
                os.path.join(self.path, "*" + TILE_IMAGE_EXTENSION)):
            image = ntpath.basename(imagepath)
            match = re.search(KEYENCE_TILE_PATTERN, image)
            if (len(match.groups()) == 3):
                images[image] = {
                    "prefix": match.group(1),
                    "number": int(match.group(2)),
                    "channel": match.group(3),
                }

        if (len(set([image['prefix'] for image in images.values()])) != 1):
            logger.warn("Some Keyence *.tif files have different prefixes")

        # expecting rows*cols keyence images
        image_numbers = {
            c: set()
            for c in [image['channel'] for image in images.values()]
        }
        for image in images.values():
            image_numbers[image['channel']].add(image['number'])

        valid_channels = [
            k for k in image_numbers
            if image_numbers[k] == set(range(1, self.rows * self.cols + 1))
        ]
        if (len(valid_channels) == 0):
            raise ValueError("No channels with {} tiles".format(
                len(self.rows * self.cols)))

        self.channels = set(valid_channels).intersection(
            set([x[1] for x in BCF_CHANNEL_NAMES]))
        logger.info("Channels with valid number of tiles: %s" %
                    (",".join(self.channels)))
        self.images = images
