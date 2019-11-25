# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost
# Copyright: California Institute of Technology

import PIL
import subprocess
import logging
import os
import mist
import numpy as np
import cv2

logger = logging.getLogger()

TILE_IMAGE_EXTENSION = ".tif"

ZFILL_SIZE = 5


class Tile:
    """ A single image (multi-channel) taken by the microscope.

    A Tile represents an image (with possibly multiple channels) taken in one 
    physical location on the stage. The Tile stores a variable number of named
    channels and stores a path to the file for each channel in the tile.

    Attributes:
        channels: A dictionary indexed on the channel name that provides the 
            path to the underlying image data for that channel
        quant: A dictionary indexed on the coordinate (x,y) contains 
            quantifications (cell count) at x,y positions
    """
    def __init__(self):
        """ Initializes channel data and quantification data. """
        self.channels = {}
        self.quant = {}

    def add_channel(self, name, path):
        """ Adds a channel to this tile.

        Given a path to the image-channel and a name for the channel, the 
        information is added to the unordered channel dictionary

        Args:
            name: A string with the channel name
            path: path to the file representing the image and channel for this
                Tile
        """
        # TODO validate image, incl size
        self.channels[name] = path

    def get_channel(self, name):
        return self.channels[name]


class TileSequence:
    """ A sequence of tiles that are organized in an overlapping grid pattern. 

    A TileSequence represents a sequence of Tile (multi-channel images) objects
    that are overlapping with each other, which is indicative of a microscope
    that takes images as the stage moves. 

    Attributes:
        path: Path to the standardized folder structure for tile sequences
        tile_size: A tuple of the size of each tile (width, height)
        rows: Number of rows in the tiled grid pattern (rows of overlapping 
            images)
        cols: Number of columns in the tiled grid pattern (columns of 
            overlapping images)
        channels: The channels that are present for each of the Tile objects in
            this sequence
    """
    def __init__(self, path, tile_size, rows, cols, channels):
        """ Initializes a TileSequence given metadata and the folder structure. """
        self.path = path
        self.rows = rows
        self.cols = cols
        self.channels = channels
        self.corners = {}
        self.tile_size = tile_size
        self.tiles = {}
        self.assemble_tiles()

    @staticmethod
    def tile_fname(num):
        """ Convert a tile number into an image filename.

        A tile file has a standard filename (e.g. 00001.tif). The format uses 
        ZFILL_SIZE zero padding and tile numbers starting at 1.

        Args:
            num: An integer representing the tile number
        Returns:
            A string representing the file basename for this tile number
        """

        return str(num).zfill(ZFILL_SIZE) + TILE_IMAGE_EXTENSION

    def assemble_tiles(self):
        """ Traverse TileSequence path for new Tiles from images."""
        for i in range(1, self.rows * self.cols + 1):
            tile = Tile()
            for channel in self.channels:
                tile.add_channel(
                    channel,
                    os.path.join(self.path, channel, self.tile_fname(i)))
            self.tiles[i] = tile

    def stitch(self, channel):
        """ Use MIST to discover positions (corners) for each of the Tiles according to a single channel

        MIST uses phase correlation between images to determine the amount of 
        translation between images. This is used to determine the absolute 
        position of each image tile in a larger 'stitched' image. 

        Args:
            channel: A string channel name, the images of which will be used 
                to determine the position of each tile. 
        """
        channel_dir = os.path.join(self.path, channel)
        # TODO check if channel exists
        self.corners = mist.stitch(channel_dir, channel_dir, self.rows,
                                   self.cols)
        self.__set_full_image_size()

    def __set_full_image_size(self):
        """ Determines the minimum size of a full-stitched image given the positions of the Tiles """
        x = 0
        y = 0
        for corner in self.corners.values():
            x = max(corner[0] + self.tile_size[0], x)
            y = max(corner[1] + self.tile_size[1], y)
        self.full_size = (y, x)
        logger.info("Stitched image size {}".format(str(self.full_size)))

    def blend(self, channel):
        """ Blends images of a channel according to the Tile positions.

        The corners from the stitching are used to position the tiles in the 
        composite. Tiles are blended using averaging. Note that blended images
        probably should not be used for quantification because of blending.

        Args:
            channel: channel to be blended.
        
        Returns:
            An image representing the blended composite of the Tiles.
        """
        output = np.zeros(self.full_size, dtype=np.uint16)
        logger.debug("Blend output size {}".format(output.shape))
        for i in range(1, self.rows * self.cols + 1):
            path = self.tiles[i].get_channel(channel)
            corner = self.corners[i]
            im = cv2.imread(path, -1)
            section = output[corner[1]:corner[1] +
                             self.tile_size[1], corner[0]:corner[0] +
                             self.tile_size[0]]
            section[section == 0] = im[section == 0]
            section[section != 0] = (section[section != 0] +
                                     im[section != 0]) / 2
        return output