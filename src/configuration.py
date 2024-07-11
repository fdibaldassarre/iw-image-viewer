#!/usr/bin/env python3

import configparser
import os

from gi.repository import Gdk


CONFIG_SECTION_DEFAULT = 'DEFAULT'
CONFIG_SECTION_PREFS = 'Preferences'

CONFIG_WINDOW_WIDTH = 'Window_width'
CONFIG_WINDOW_HEIGHT = 'Window_height'
CONFIG_WINDOW_FULLSCREEN = 'Window_fullscreen'
CONFIG_BG_COLOUR = 'BG_colour'
CONFIG_IMAGE_BG_TYPE = 'BG_image_type'
CONFIG_IMAGE_BG_COLOUR = 'BG_image_colour'
CONFIG_SLIDESHOW_SECONDS = 'Slideshow_seconds'

IMAGE_BG_TYPE_COLOUR = 'colour'
IMAGE_BG_TYPE_PATTERN = 'pattern'
IMAGE_BG_TYPE_AS_APP = 'same_main'

DEFAULT_CONFIG = {CONFIG_WINDOW_WIDTH: '100',
                  CONFIG_WINDOW_HEIGHT: '100',
                  CONFIG_WINDOW_FULLSCREEN: 'False',
                  CONFIG_BG_COLOUR: 'rgb(0,0,0)',
                  CONFIG_IMAGE_BG_TYPE: IMAGE_BG_TYPE_PATTERN,
                  CONFIG_IMAGE_BG_COLOUR: 'rgb(0,0,0)',
                  CONFIG_SLIDESHOW_SECONDS: '5',
                  }


class IWConfig:

    def __init__(self, config_file):
        self.config_file = config_file
        self.config = configparser.ConfigParser(DEFAULT_CONFIG)

    def init(self):
        self.config.read(self.config_file)

    def _getConfig(self, param):
        return self.config.get(CONFIG_SECTION_DEFAULT, param)

    def _getConfigInt(self, param):
        return int(self.config.get(CONFIG_SECTION_DEFAULT, param))

    def _getConfigColour(self, param):
        col_str = self._getConfig(param)
        colour = Gdk.RGBA()
        colour.parse(col_str)
        return colour

    def _getConfigBool(self, param):
        if self.config.get(CONFIG_SECTION_DEFAULT, param).lower() == 'true':
            return True
        else:
            return False

    def _setConfig(self, param, value):
        self.config[CONFIG_SECTION_DEFAULT][param] = str(value)

    def save(self):
        with open(self.config_file, 'w') as hand:
            self.config.write(hand)

    def getWindowLastStatus(self):
        width = self._getConfigInt(CONFIG_WINDOW_WIDTH)
        height = self._getConfigInt(CONFIG_WINDOW_HEIGHT)
        isFullscreen = self._getConfigBool(CONFIG_WINDOW_FULLSCREEN)
        return width, height, isFullscreen

    def setWindowLastStatus(self, width, height, isFullscreen):
        self._setConfig(CONFIG_WINDOW_WIDTH, width)
        self._setConfig(CONFIG_WINDOW_HEIGHT, height)
        self._setConfig(CONFIG_WINDOW_FULLSCREEN, isFullscreen)

    def getInterfaceBGColour(self):
        return self._getConfigColour(CONFIG_BG_COLOUR)

    def isInterfaceImageBGPattern(self):
        return self._getConfig(CONFIG_IMAGE_BG_TYPE) == IMAGE_BG_TYPE_PATTERN

    def isInterfaceImageBGAsMain(self):
        return self._getConfig(CONFIG_IMAGE_BG_TYPE) == IMAGE_BG_TYPE_AS_APP

    def isInterfaceImageBGColour(self):
        return self._getConfig(CONFIG_IMAGE_BG_TYPE) == IMAGE_BG_TYPE_COLOUR

    def getInterfaceImageBGColour(self):
        return self._getConfigColour(CONFIG_IMAGE_BG_COLOUR)

    def setInterfaceBGColour(self, colour):
        self._setConfig(CONFIG_BG_COLOUR, colour.to_string())

    def setInterfaceImageBGTypePattern(self):
        self._setConfig(CONFIG_IMAGE_BG_TYPE, IMAGE_BG_TYPE_PATTERN)

    def setInterfaceImageBGTypeAsMain(self):
        self._setConfig(CONFIG_IMAGE_BG_TYPE, IMAGE_BG_TYPE_AS_APP)

    def setInterfaceImageBGTypeColour(self):
        self._setConfig(CONFIG_IMAGE_BG_TYPE, IMAGE_BG_TYPE_COLOUR)

    def setInterfaceImageBGColour(self, colour):
        self._setConfig(CONFIG_IMAGE_BG_COLOUR, colour.to_string())

    def setSlideshowSeconds(self, seconds: str) -> None:
        self._setConfig(CONFIG_SLIDESHOW_SECONDS, seconds)

    def getSlideshowSeconds(self) -> int:
        return self._getConfigInt(CONFIG_SLIDESHOW_SECONDS)


def readConfig(config_folder):
    if not os.path.exists(config_folder):
        os.makedirs(config_folder)
    config_path = os.path.join(config_folder, 'config.txt')
    config = IWConfig(config_path)
    config.init()
    return config
