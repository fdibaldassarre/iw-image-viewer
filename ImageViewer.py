#!/usr/bin/env python3

import os
import configparser

from PIL import Image

# Import natsort if available
try:
    from natsort import natsorted
except ImportError:
    def natsorted(data):
        it = list(data)
        it.sort()
        return it

# Import pyinotify if possible
try:
    import pyinotify
    INOTIFY = True
except ImportError:
    INOTIFY = False

from Interface import Interface

from gi.repository import GObject
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import GdkPixbuf

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

SUPPORTED_STATIC = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
SUPPORTED_ANIMATION = ['.gif']

ANIMATION_RATE = 60.0 # 60 FPS (too high?)

ANIMATION_DELAY = 1 / ANIMATION_RATE

INOTIFY_TIMEOUT = 10 # Keep this number low

SIZE_DIFF = 112 # This size diff is due to the HeaderBar

## Inotify check
def ifInotify(method):
    def new(self, *args, **kwargs):
        if not self.has_inotify:
            return None
        else:
            return method(self, *args, **kwargs)
    return new

if INOTIFY:
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

## Animation cache

## TODO: Find a way to associate pixbuf -> resized
##             Note: The pixbufs are recycled in the animation
##                         hence subsequent calls to iter_advance()
##                         overwrite the memory of the old pixbufs

CACHE_MAX_SIZE = 50

class AnimationCache():

    def __init__(self):
        self.cache = {}

    def getPixbuf(self, pixbuf, width, height):
        if (pixbuf, width, height) in self.cache:
            return self.cache[pixbuf, width, height]
        else:
            return self.addPixbuf(pixbuf, width, height)

    def addPixbuf(self, pixbuf, width, height):
        res = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        self.addToCache(res, pixbuf, width, height)
        return res

    def addToCache(self, res, pixbuf, width, height):
        if len(self.cache) < CACHE_MAX_SIZE:
            self.cache[pixbuf, width, height] = res
        else:
            if self.cleanCache(width, height):
                self.cache[pixbuf, width, height] = res

    def cleanCache(self, width, height):
        # Delete a pixbuf with different size
        for el in self.cache:
            _, w, h = el
            if w != width or h != height:
                del self.cache[el]
                return True
        return False


class GIFFrame():

    def __init__(self, delay, pixbuf):
        self.delay = delay
        self.pixbuf = pixbuf

    def getDelay(self):
        return self.delay

    def getPixbuf(self):
        return self.pixbuf

# Calling pixbuf.scale_simple may cause a segmentation fault, see:
# https://bugzilla.gnome.org/show_bug.cgi?id=747431
def convertPilImageToGdkPixbuf(image, width=None, height=None):
    if width is None:
        width = image.size[0]
    if height is None:
        height = image.size[1]
    data = GLib.Bytes(image.tobytes())
    if len(image.getbands()) == 4:
        has_alpha = True
    else:
        has_alpha = False
    if has_alpha:
        row_stride = 4 * width
    else:
        row_stride = 3 * width
    return GdkPixbuf.Pixbuf.new_from_bytes(data, GdkPixbuf.Colorspace.RGB, has_alpha, 8, width, height, row_stride)

class GIFAnimation():

    def __init__(self, path):
        self.path = path
        self.img = Image.open(self.path)
        self.cache = AnimationCache()
        self.current_frame = -1
        self.start_time = -1

    def load(self):
        self.frames = []
        prev = None
        counter = 0
        try:
            while True:
                current_image, duration = self.composeImage(self.img, prev)
                counter += 1
                prev = current_image
                if duration > 0:
                    # Create pixbuf
                    pixbuf = convertPilImageToGdkPixbuf(current_image, self.image.size[0], self.image.size[1])
                    # Add frame
                    current_frame = GIFFrame(duration, pixbuf)
                    self.frames.append(current_frame)
                self.img.seek(self.img.tell() + 1)
        except EOFError:
            pass

    def composeImage(self, img, prev):
        # Extract data
        duration = img.info['duration']
        if 'background' in img.info:
            background = self.img.info['background']
        else:
            background = None
        if 'transparency' in img.info:
            transparency = img.info['transparency']
        else:
            transparency = None
        # Convert
        img = img.convert('RGBA')
        # Add transparency
        #if transparency is not None:
        #    img = self.addTransparency(img, transparency)
        # Add background
        if background is not None:
            img = self.addTransparency(img, background)
        # Stack with previous image
        if prev is not None:
            img = self.addBackground(img, prev)
        return img, duration

    def addBackground(self, img, background):
        background.paste(img, (0,0))
        return background

    def addTransparency(self, frame, trasparency):
        mask = self.findMask(frame, trasparency)
        img = frame.convert('RGBA')
        img.putalpha(mask)
        return img

    def findMask(self, frame, trasparency):
        img = frame.point(lambda x : 0 if x == trasparency else 255).convert('L')
        return img

    def isAnimated(self):
        return self.img.is_animated

    def getWidth(self):
        return self.img.size[0]

    def getHeight(self):
        return self.img.size[1]

    def getDelay(self):
        return self.frames[self.current_frame].getDelay()

    def getPixbuf(self, width, height):
        pixbuf = self.frames[self.current_frame].getPixbuf()
        return self.cache.getPixbuf(pixbuf, width, height)

    def advance(self, time=None):
        if time is None:
            time = GLib.get_current_time()
        if self.start_time == -1:
            self.start_time = time
            self.current_frame = 0
        else:
            elapsed = (time - self.start_time) * 1000
            diff = 0
            frame_id = -1
            while diff < elapsed:
                frame_id += 1
                frame_id = frame_id % len(self.frames)
                frame = self.frames[frame_id]
                diff += frame.getDelay()
            self.current_frame = frame_id

    ## Compatibility methods
    def is_static_image(self):
        return not self.isAnimated()

    def get_width(self):
        return self.getWidth()

    def get_height(self):
        return self.getHeight()

    def get_iter(self):
        return self

    def get_delay_time(self):
        return self.getDelay()


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
            self.pixbuf = self._loadPixbuf()
            self.size = (self.pixbuf.get_width(), self.pixbuf.get_height())
            self.is_resizable = True
            self.error_loading = False
            self.is_static = True
        except Exception as e:
            self.setError()

    def _loadPixbuf(self):
        if self.extension == '.webp':
            pixbuf = convertPilImageToGdkPixbuf(Image.open(self.path))
        else:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.path)
        return pixbuf

    def loadAnimation(self):
        try:
            self.animation = GdkPixbuf.PixbufAnimation.new_from_file(self.path) #GIFAnimation(self.path)
            if self.animation.is_static_image():
                self.loadStaticImage()
            else:
                #self.animation.load() # GIFAnimation
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
        width, height = self.animation_size
        # Get Pixbuf
        pixbuf = self.animation_iter.get_pixbuf()
        res_pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        #res_pixbuf = self.animation.getPixbuf(width, height) # GIFAnimation
        return self.animation_iter, res_pixbuf

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
        if INOTIFY:
            self.has_inotify = True
            self.pyinotify_wm = pyinotify.WatchManager()
            self.pyinotify_mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO
            handler = InotifyEventHandler(self)
            self.pyinotify_notifier = pyinotify.Notifier(self.pyinotify_wm, handler, timeout=INOTIFY_TIMEOUT)
            self.pyinotify_wdd = {}
        else:
            self.has_inotify = False

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

    @ifInotify
    def inotifyAdd(self, path):
        self.pyinotify_wdd = self.pyinotify_wm.add_watch(path, self.pyinotify_mask, rec=False)

    @ifInotify
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
