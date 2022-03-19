#!/usr/bin/env python3

import os
import argparse
from src import ImageViewer

parser = argparse.ArgumentParser(description="IWImageViewer")
parser.add_argument( 'address', nargs='?', default=None, help = 'Image address' )

args = parser.parse_args()

if args.address is not None:
  address = os.path.realpath(args.address)
else:
  address = None

config_folder = os.path.join(os.environ['HOME'], ".config/iw-image-viewer/")

iw = ImageViewer.new(config_folder)
iw.start(address)
