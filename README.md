# IW Image Viewer
Simple image viewer in Gtk.

## Installation

Install the .deb from the release page.


## Usage

Controls:

  * Right/left arrow to navigate the images
  
  * Mouse scroll or +, - to zoom
  
  * f11 to fullscreen
  
  * ctrl+q to exit
  
  * ctrl+0 to reset the zoom (fit the image to the window)


## Development

### Requirements

- Python 3
- Gtk 3.10 or higher is recommended but should work with 3.0
- PIL
- python3-natsort
- python3-pyinotify

```
apt install libgirepository1.0-dev
pip install -r requirements.txt
```

### Todo

  * Better folder monitoring
  
  * Interface fixes depending on Gtk version
  
