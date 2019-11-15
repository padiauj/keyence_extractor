# Author: Umesh Padia
# Gradinaru Lab + Office of the Provost

import zipfile
import glob
import os

JAR_PATH = "MIST-wdeps"

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
    "outputFullImage": "true",
    "startRow": "0",
    "startCol": "0",
    "extentWidth": "12",
    "extentHeight": "8"
}

options = DEFAULT_STITCHING_OPTIONS
TEMP_IMG_DIR = "/home/padiauj/image_analysis/XY02/CH1/cleaned/gray"
TEMP_UNST_DIR = "/home/padiauj/image_analysis/XY02/"


for bcf in glob.glob(os.path.join(TEMP_UNST_DIR, "*.bcf")):
    bcfzip = zipfile.ZipFile(bcf)
    print(bcfzip.namelist())
    if ("GroupFileProperty/ImageJoint" in bcfzip.namelist()):
        print("yeah")

