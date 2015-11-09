#!/usr/bin/env python3

import os
import argparse
import ImageViewer

parser = argparse.ArgumentParser(description="ImageViewer")
parser.add_argument( 'address', nargs='?', default=None, help = 'Image address' )

args = parser.parse_args()

address = args.address

config_folder = os.path.join(os.environ['HOME'], ".config/image-viewer/")

iw = ImageViewer.new(config_folder)
iw.start(address)
