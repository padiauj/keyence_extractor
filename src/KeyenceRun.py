# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost
# Copyright: California Institute of Technology

from PIL import Image
import xml.etree.ElementTree as ET
import zipfile
import glob
import os
import re
import sys
import ntpath
import logging

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger()

# The path within the BCF zip file containing the grid pattern of the
# tiles
BCF_GRID_PROPERTIES = "GroupFileProperty/ImageJoint/properties.xml"
BCF_CHANNEL_NAMES = [("Channel" + str(x), "CH" + str(x + 1)) for x in range(5)]
BCF_CHANNEL_PROPERTIES = "GroupFileProperty/{}/properties.xml"
BCF_IMAGE_SIZE_PROPERTIES = "GroupFileProperty/Image/OriginalImageSize/properties.xml"

TILE_IMAGE_EXTENSION = ".tif"

KEYENCE_TILE_PATTERN = "(.*)_([0-9]{5})_(.*)" + TILE_IMAGE_EXTENSION


class KeyenceRun():
    def __init__(self, path):
        self.path = path
        self.bcfzip = zipfile.ZipFile(self.__get_bcf(self.path))

        self.__get_grid()
        self.__get_channels()
        self.__get_image_size()
        self.__get_images()

    def prep_folders(self):
        self.iris_dir = os.path.join(self.path, "iris")
        # verify this path doesn't already exist
        if (not os.path.exists(self.iris_dir)):
            os.mkdir(self.iris_dir)

        for channel in self.channels:
            channel_dir = os.path.join(self.iris_dir, channel)
            if (not os.path.exists(channel_dir)):
                os.mkdir(os.path.join(channel_dir))
            for key in self.images:
                if (self.images[key]['channel'] == self.images[key]['channel']
                    ):
                    self.gray(
                        os.path.join(self.path, key),
                        os.path.join(
                            channel_dir,
                            self.images[key]['number'] + TILE_IMAGE_EXTENSION))

    @staticmethod
    def __get_bcf(path):
        bcffiles = glob.glob(os.path.join(path, "*.bcf"))
        assert (len(bcffiles) == 1)
        logger.info("Discovered BCF file: {}".format(bcffiles[0]))
        return bcffiles[0]

    @staticmethod
    def __get_tag(root, tag):
        """
        Gets the value from a tag in an XML object. 
        Ensures that only one of these tags exist in the provided XML
        """
        val = None
        for idx, elem in enumerate(root.findall(tag)):
            # should only be one of these tags
            assert idx == 0
            val = elem.text
        return val

    def __get_image_size(self):
        """
        Gets image size information from .bcf file 
        """
        if (BCF_IMAGE_SIZE_PROPERTIES in self.bcfzip.namelist()):
            root = ET.fromstring(self.bcfzip.read(BCF_IMAGE_SIZE_PROPERTIES))
            self.image_size = (int(self.__get_tag(root, "Height")),
                               int(self.__get_tag(root, "Width")))
        else:
            raise FileNotFoundError(
                "Image properties {} not found within BCF file {}".format(
                    BCF_IMAGE_SIZE_PROPERTIES, self.path))
        logger.info("Image size: {}".format(str(self.image_size)))

    def __get_channels(self):
        """
        Gets channel information from .bcf file 
        """
        self.channels = {}
        for channel in BCF_CHANNEL_NAMES:
            if (BCF_CHANNEL_PROPERTIES.format(
                    channel[0]) in self.bcfzip.namelist()):
                root = ET.fromstring(
                    self.bcfzip.read(BCF_CHANNEL_PROPERTIES.format(
                        channel[0])))
                self.channels[channel[1]] = self.__get_tag(root, "Comment")
        logger.info("Discovered channel information: [{}]".format(",".join(
            [str((k, self.channels[k])) for k in self.channels])))

    def __get_grid(self):
        """
        Retrieves the row / column information from the .bcf file
        """
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

        logger.info("Channels with valid number of tiles: %s" %
                    (",".join(valid_channels)))

        for channel in self.channels:
            if (channel not in valid_channels):
                del channel
        self.images = images


if __name__ == "__main__":
    k = KeyenceRun("../XY02")
    k.prep_folders()
