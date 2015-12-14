#!/usr/bin/env python3

import os
import argparse
import ImageViewer

parser = argparse.ArgumentParser(description="IWImageViewer")
parser.add_argument( 'address', nargs='?', default=None, help = 'Image address' )

args = parser.parse_args()

address = os.path.realpath(args.address)

config_folder = os.path.join(os.environ['HOME'], ".config/iw-image-viewer/")

iw = ImageViewer.new(config_folder)
iw.start(address)
