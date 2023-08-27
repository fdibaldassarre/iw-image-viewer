#!/usr/bin/env python3

import os
import argparse
from src.application import ImageViewerApplication


def run():
    parser = argparse.ArgumentParser(description="IWImageViewer")
    parser.add_argument("address", nargs="*", help="Image address")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle")
    parser.add_argument("--slideshow", action="store_true", help="Slideshow")

    args = parser.parse_args()

    app = ImageViewerApplication(args)
    app.run(None)


if __name__ == "__main__":
    run()
