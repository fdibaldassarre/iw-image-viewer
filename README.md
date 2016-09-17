# IW Image Viewer
Simple image viewer in Gtk.

## Features

  * Bilinear interpolation for zoom in-out
  
  * Inotify to monitor the folder changes

## Requirements

- Python 3
- Gtk 3.10 or higher is recommended but should work with 3.0
- PIL

Optional

- python3-natsort
- python3-pyinotify

## Usage

Controls:

  * Right/left arrow to navigate the images
  
  * Mouse scroll or +, - to zoom
  
  * f11 to fullscreen
  
  * ctrl+q to exit
  
  * ctrl+0 to reset the zoom (fit the image to the window)

## Todo

  * Better folder monitoring
  
  * Interface fixes depending on Gtk version
  
