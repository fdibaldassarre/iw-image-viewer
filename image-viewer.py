#!/usr/bin/env python3

import os
import argparse
from src import ImageViewer

parser = argparse.ArgumentParser(description="IWImageViewer")
parser.add_argument("address", nargs="*", help="Image address")
parser.add_argument("--shuffle", action="store_true", help="Shuffle")

args = parser.parse_args()

if len(args.address) > 0:
  address = os.path.realpath(args.address[0])
else:
  address = None

config_folder = os.path.join(os.environ['HOME'], ".config/iw-image-viewer/")

iw = ImageViewer.new(config_folder, shuffle=args.shuffle)
iw.start(address)
