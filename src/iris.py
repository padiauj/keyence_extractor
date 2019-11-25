# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost
# Copyright: California Institute of Technology

import os
import argparse
import logging
from KeyenceRun import KeyenceRun
from tile import TileSequence
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

logger = logging.getLogger()


def dir_path(d):
    """ Verifies validity of directory provided. 

    Args:
        d: A string representing a directory.
    """
    if os.path.isdir(d):
        return d
    else:
        raise NotADirectoryError(d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Iris: Stitch images from fluorescence microscopy")
    parser.add_argument(
        '--path',
        dest="SRC_DIR",
        type=dir_path,
        help="Path containing images to be analyzed (including a BCF file)",
        required=True)
    parser.add_argument('--stitch-channel',
                        dest="stitch_channel",
                        type=str,
                        help="Channel to use to stitch the images")

    args = parser.parse_args()

    k = KeyenceRun(args.SRC_DIR)
    iris_dir = k.prepare()
    ts = TileSequence(iris_dir, k.tile_size, k.rows, k.cols, k.channels)
    ts.stitch("CH1")
    ts.blend("CH1")