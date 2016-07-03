#!/usr/bin/env python3

import os
import configparser
from natsort import natsorted
from Interface import Interface

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import GdkPixbuf

import pyinotify

OPEN_NEXT = 0
OPEN_PREV = 1

CONFIG_SECTION_DEFAULT = 'DEFAULT'
CONFIG_SECTION_PREFS = 'Preferences'

CONFIG_WINDOW_WIDTH = 'Window_width'
CONFIG_WINDOW_HEIGHT = 'Window_height'
CONFIG_WINDOW_FULLSCREEN = 'Window_fullscreen'
CONFIG_BG_COLOUR = 'BG_colour'
CONFIG_IMAGE_BG_TYPE = 'BG_image_type'
CONFIG_IMAGE_BG_COLOUR = 'BG_image_colour'

IMAGE_BG_TYPE_COLOUR = 'colour'
IMAGE_BG_TYPE_PATTERN = 'pattern'
IMAGE_BG_TYPE_AS_APP = 'same_main'

DEFAULT_CONFIG = {CONFIG_WINDOW_WIDTH : '100',
                  CONFIG_WINDOW_HEIGHT : '100',
                  CONFIG_WINDOW_FULLSCREEN : 'False',
                  CONFIG_BG_COLOUR : 'rgb(0,0,0)',
                  CONFIG_IMAGE_BG_TYPE : IMAGE_BG_TYPE_PATTERN,
                  CONFIG_IMAGE_BG_COLOUR : 'rgb(0,0,0)'}

SUPPORTED_STATIC = ['.png', '.jpg', '.jpeg', '.bmp']
SUPPORTED_ANIMATION = ['.gif']

ANIMATION_RATE = 60.0 # 60 FPS (too high?)

ANIMATION_DELAY = 1 / ANIMATION_RATE

INOTIFY_TIMEOUT = 10 # Keep this number low

SIZE_DIFF = 112 # This size diff is due to the HeaderBar

## Inotify Handler
class InotifyEventHandler(pyinotify.ProcessEvent):
  def __init__(self, image_viewer):
    pyinotify.ProcessEvent.__init__(self)
    self.image_viewer = image_viewer
  
  def process_IN_CREATE(self, event):
    self.image_viewer.addToFilelist(event.pathname)
  
  def process_IN_DELETE(self, event):
    self.image_viewer.removeFromFilelist(event.pathname)
    
  def process_IN_MOVED_FROM(self, event):
    # file moved from the folder
    self.process_IN_DELETE(event)
  
  def process_IN_MOVED_IN(self, event):
    # file moved in the folder
    self.process_IN_CREATE(event)

## IWImage
class IWImage():

  def __init__(self, path):
    self.path = path
    self.position = -1
    _, extension = os.path.splitext(self.path)
    self.extension = extension.lower()
    self.name = os.path.basename(self.path)
    self.folder = os.path.dirname(self.path)
    self.is_static = True
    self.setError()
    self.load()
  
  def setError(self):
    self.pixbuf = None
    self.size = None
    self.is_resizable = False
    self.error_loading = True
  
  def load(self):
    if self.extension in SUPPORTED_STATIC:
      self.loadStaticImage()
    elif self.extension in SUPPORTED_ANIMATION:
      self.loadAnimation()
    else:
      self.setError()
  
  def loadStaticImage(self):
    try:
      self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.path)
      self.size = (self.pixbuf.get_width(), self.pixbuf.get_height())
      self.is_resizable = True
      self.error_loading = False
      self.is_static = True
    except Exception:
      self.setError()
  
  def loadAnimation(self):
    try:
      self.animation = GdkPixbuf.PixbufAnimation.new_from_file(self.path)
      if self.animation.is_static_image():
        self.loadStaticImage()
      else:
        self.animation_iter = self.animation.get_iter()
        self.size = (self.animation.get_width(), self.animation.get_height())
        self.animation_size = self.size
        self.is_resizable = True
        self.error_loading = False
        self.is_static = False
    except Exception:
      self.setError()
  
  def isAnimation(self):
    return not self.error_loading and not self.is_static
  
  def isStatic(self):
    return not self.error_loading and self.is_static
  
  def isError(self):
    return self.error_loading
  
  def scale(self, width, height):
    if self.isStatic():
      return self.pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    elif self.isAnimation():
      self.animation_size = (width, height)
      return None
    else:
      return None
  
  def getAnimationPixbuf(self):
    self.animation_iter.advance()
    pixbuf = self.animation_iter.get_pixbuf()
    width, height = self.animation_size
    return self.animation_iter, pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
  
  def isResizable(self):
    return self.is_resizable
    
  def getSize(self):
    return self.size
  
  def getFilepath(self):
    return self.path
  
  def getName(self):
    return self.name
  
  def getPixbuf(self):
    return self.pixbuf
  
  def getFolder(self):
    return self.folder
  
  def getFolderName(self):
    return os.path.basename(self.folder)
  
  def setPosition(self, position):
    self.position = position
  
  def getPosition(self):
    return self.position
    
# Image Viewer
class ImageViewer():
  
  def __init__(self, config_folder):
    self.config_folder = config_folder
    if not os.path.exists(self.config_folder):
      os.mkdir(self.config_folder)
    self.loadConfig()
    self.setupInterface()
    self.current_image = None
    self.files_in_folder = []
    # Inotify
    self.pyinotify_wm = pyinotify.WatchManager()
    self.pyinotify_mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO
    handler = InotifyEventHandler(self)
    self.pyinotify_notifier = pyinotify.Notifier(self.pyinotify_wm, handler, timeout=INOTIFY_TIMEOUT)
    self.pyinotify_wdd = {}
  
  def loadConfig(self):
    self.config = configparser.SafeConfigParser(DEFAULT_CONFIG)
    self.config_file = os.path.join(self.config_folder, 'config.txt')
    self.config.read(self.config_file)
  
  def getConfig(self, param):
    return self.config.get(CONFIG_SECTION_DEFAULT, param)
  
  def getConfigInt(self, param):
    return int(self.config.get(CONFIG_SECTION_DEFAULT, param))
  
  def getConfigColour(self, param):
    col_str = self.getConfig(param)
    colour = Gdk.RGBA()
    colour.parse(col_str)
    return colour
  
  def getConfigBool(self, param):
    if self.config.get(CONFIG_SECTION_DEFAULT, param).lower() == 'true':
      return True
    else:
      return False
  
  def setConfig(self, param, value):
    self.config[CONFIG_SECTION_DEFAULT][param] = str(value)
  
  def saveConfig(self):
    self.config.write(open(self.config_file, 'w'))
  
  def setupInterface(self):
    width = self.getConfigInt(CONFIG_WINDOW_WIDTH)
    height = self.getConfigInt(CONFIG_WINDOW_HEIGHT)
    request_size = (width, height)
    self.interface = Interface(self)
    self.interface.resize(request_size)
    if self.getConfigBool(CONFIG_WINDOW_FULLSCREEN):
      self.interface.modeFullscreen(True)
    self.interface.show()
  
  ## CONFIG INTERFACE GET
  def getInterfaceBGColour(self):
    return self.getConfigColour(CONFIG_BG_COLOUR)
  
  def isInterfaceImageBGPattern(self):
    return self.getConfig(CONFIG_IMAGE_BG_TYPE) == IMAGE_BG_TYPE_PATTERN
  
  def isInterfaceImageBGAsMain(self):
    return self.getConfig(CONFIG_IMAGE_BG_TYPE) == IMAGE_BG_TYPE_AS_APP
  
  def isInterfaceImageBGColour(self):
    return self.getConfig(CONFIG_IMAGE_BG_TYPE) == IMAGE_BG_TYPE_COLOUR
  
  def getInterfaceImageBGColour(self):
    return self.getConfigColour(CONFIG_IMAGE_BG_COLOUR)
  
  ## CONFIG INTERFACE SET
  def setInterfaceBGColour(self, colour):
    self.setConfig(CONFIG_BG_COLOUR, colour.to_string())
    
  def setInterfaceImageBGTypePattern(self):
    self.setConfig(CONFIG_IMAGE_BG_TYPE, IMAGE_BG_TYPE_PATTERN)
  
  def setInterfaceImageBGTypeAsMain(self):
    self.setConfig(CONFIG_IMAGE_BG_TYPE, IMAGE_BG_TYPE_AS_APP)
  
  def setInterfaceImageBGTypeColour(self):
    self.setConfig(CONFIG_IMAGE_BG_TYPE, IMAGE_BG_TYPE_COLOUR)
  
  def setInterfaceImageBGColour(self, colour):
    self.setConfig(CONFIG_IMAGE_BG_COLOUR, colour.to_string())
  
  ## START
  def start(self, imagepath=None):
    if imagepath is not None:
      current_folder = os.path.dirname(imagepath)
      self.files_in_folder = self.readFolder(current_folder)
      self.current_image = self.openImage(imagepath)
      self.inotifyAdd(current_folder)
      self.setCurrentImagePosition()
    self.interface.start(self.current_image)
  
  def close(self):
    # save last window size
    width, height = self.interface.getSize()
    fullscreen = self.interface.getFullscreen()
    self.setConfig(CONFIG_WINDOW_WIDTH, width)
    self.setConfig(CONFIG_WINDOW_HEIGHT, height)
    self.setConfig(CONFIG_WINDOW_FULLSCREEN, fullscreen)
    # save config
    self.saveConfig()
  
  def stop(self):
    self.interface.close()
  
  def inotifyAdd(self, path):
    self.pyinotify_wdd = self.pyinotify_wm.add_watch(path, self.pyinotify_mask, rec=False)
    
  def inotifyRemove(self, path):
    if self.pyinotify_wdd[path] > 0:
      self.pyinotify_wm.rm_watch(self.pyinotify_wdd[path])
  
  def openNextImage(self):
    self.openNearImage(OPEN_NEXT)
  
  def openPrevImage(self):
    self.openNearImage(OPEN_PREV)
  
  def openNearImage(self, open_type):
    current_name = self.current_image.getName()
    current_folder = self.current_image.getFolder()
    current_position = self.current_image.getPosition()
    # set up new image variables
    new_image = None
    if open_type == OPEN_NEXT:
      new_position = current_position + 1
    else:
      new_position = current_position - 1
    
    # get new image
    if new_position >= 0 and new_position < len(self.files_in_folder):
      new_image = os.path.join(current_folder, self.files_in_folder[new_position])
    else:
      new_image = None
      new_position = -1
    
    # open pallel folder if necessary
    if new_image is None:
      new_image, new_position = self.openUpperFolder(open_type)
      if new_image is not None:
        # update inotify
        self.inotifyRemove(current_folder)
        self.inotifyAdd(os.path.dirname(new_image))
    
    # set new current image and open with the interface
    if new_image is not None:
      self.current_image = self.openImage(new_image, new_position)
      self.interface.openImage(self.current_image)
      
  
  def openUpperFolder(self, get):
    # Get all the files/folders
    folder = os.path.dirname(self.current_image.getFolder())
    current_folder_name = os.path.basename(self.current_image.getFolder())
    files = self.readFolder(folder, True)
    # Reverse the array if get prev
    if get == OPEN_PREV:
      files.reverse()
    # Get the first valid element
    next = False
    element = None
    for filename in files:
      if filename == current_folder_name:
        next = True
      elif next:
        # check if the element is valid
        candidate_path = os.path.join(folder, filename)
        if os.path.isdir(candidate_path):
          # read folder
          el_files = self.readFolder(candidate_path)
          if len(el_files) > 0:
            self.files_in_folder = el_files
            position = 0 if get == OPEN_NEXT else -1
            element = os.path.join(candidate_path, el_files[position])
            break
        '''
        # Note: I do not consider files while reading the upper folder
        # because I read only files on the same level
        # i.e. files in the folders ~/Pictures/ and ~/Documents
        # are on the same level, pictures in
        # ~/Pictures and ~/Pictures/ex1 are not.
        else:
          # reorder the files correctly
          if get == OPEN_PREV:
            files.reverse()
          self.files_in_folder = self.removeFoldersFromArray(files)
          element = candidate_path
        break
        '''
    # get element position
    if element is None:
      position = -1
    elif get == OPEN_NEXT:
      position = 0
    elif get == OPEN_PREV:
      position = len(self.files_in_folder) - 1
    # element is the new image,
    # position is its index in the folder files
    return element, position
    
  def openImage(self, path, position=None):
    img = IWImage(path)
    if position is None:
      # get image position
      position = self.getFilePosition(path)
    img.setPosition(position)
    return img
  
  def getFilePosition(self, path):
    # NOTE: assume self.files_in_folder is correct
    basename = os.path.basename(path)
    if basename in self.files_in_folder:
      return self.files_in_folder.index(basename)
    else:
      # error
      return -1
    
  
  def isSupportedExtension(self, ext):
    return ext.lower() in SUPPORTED_STATIC or ext.lower() in SUPPORTED_ANIMATION
  
  def readFolder(self, folder, include_folders=False):
    all_files = os.listdir(folder)
    folders = {}
    folders_keys = []
    if include_folders:
      for filename in all_files:
        if filename[0] == '.':
          continue
        filepath = os.path.join(folder, filename)
        if os.path.isdir(filepath):
          f_lower = filename.lower()
          if f_lower in folders:
            folders[f_lower].append(filename)
          else:
            folders[f_lower] = [filename]
      folders_keys = natsorted(folders.keys())
    valid_files = {}
    valid_files_keys = []
    for filename in all_files:
      if filename[0] == '.':
        continue
      _, ext = os.path.splitext(filename)
      if self.isSupportedExtension(ext):
        f_lower = filename.lower()
        if f_lower in valid_files:
          valid_files[f_lower].append(filename)
        else:
          valid_files[f_lower] = [filename]
    valid_files_keys = natsorted(valid_files.keys())
    # Compose
    sorted_files = []
    for el in folders_keys:
      fls = folders[el]
      fls.sort()
      sorted_files.extend(fls)
    for el in valid_files_keys:
      fls = valid_files[el]
      fls.sort()
      sorted_files.extend(fls)
    return sorted_files
  
  '''
  def removeFoldersFromArray(self, files):
    # NOTE: the input must be in the format given by
    # self.readFolder
    new_array = []
    for el in files:
      if os.path.isdir(el):
        break
      else:
        new_array.append(el)
    return new_array
  '''
  
  def setCurrentImagePosition(self):
    basename = self.current_image.getName()
    if basename in self.files_in_folder:
      position = self.files_in_folder.index(basename)
      self.current_image.setPosition(position)
    else:
      self.current_image.setPosition(-1)
  
  def getTotImages(self):
    return len(self.files_in_folder)
  
  def addToFilelist(self, path):
    # TODO: better, this is kinda lazy
    current_folder = os.path.dirname(path)
    self.files_in_folder = self.readFolder(current_folder)
    # update interface
    self.updateFolderData()
  
  def removeFromFilelist(self, path):
    filename = os.path.basename(path)
    if filename in self.files_in_folder:
      self.files_in_folder.remove(filename)
      # update interface
      self.updateFolderData()
  
  def updateFolderData(self):
    self.setCurrentImagePosition()
    self.interface.fillInfo()
  
  def folderIsEmpty(self, folder):
    return len(os.listdir(folder)) == 0
    
def new(*args, **kwargs):
  iw = ImageViewer(*args, **kwargs)
  return iw
