#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')

import os
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import GLib

DEFAULT_SIZE = (300, 300)
ZOOM_FACTOR = 0.9

MISSING_IMAGE_ICON = 'gtk-missing-image'

MOUSE_DELTA_INCREMENT = 1

MAX_ZOOM = 5.0
MIN_ZOOM = 0.02
MIN_CONTENT_SIZE = 10

MOVE_IMAGE_INCREMENT = 20

SCROLL_ADJUST_HORIZONTAL = 0
SCROLL_ADJUST_VERTICAL = 1

path = os.path.abspath( __file__ )
MAIN_FOLDER = os.path.dirname( path )

## Decorators
def imageIsResizable(method):
  def new(self, *args, **kwargs):
    if self.image is not None and self.image.isResizable():
      return method(self, *args, **kwargs)
    else:
      return False
  return new

def imageIsNotError(method):
  def new(self, *args, **kwargs):
    if self.image is not None and not self.image.isError():
      return method(self, *args, **kwargs)
    else:
      return False
  return new

def imageIsNotNone(method):
  def new(self, *args, **kwargs):
    if self.image is not None:
      return method(self, *args, **kwargs)
    else:
      return False
  return new
  

## Signals Handler
class SHandler():

  def __init__(self, interface):
    self.interface = interface
  
  ## Main
  def closeMain(self, *args):
    self.interface.close()
  
  def monitorKeyboard(self, *args):
    self.interface.monitorKeyboard(*args)
  
  def updateWindowSize(self, *args):
    self.interface.updateWindowSize(*args)
  
  def onMainWindowChange(self, *args):
    self.interface.onMainWindowChange(*args)
  
  ## Image
  def imageScroll(self, *args):
    self.interface.scroll(*args)
  
  def imageStartDrag(self, *args):
    self.interface.startDrag(*args)
  
  def imageStopDrag(self, *args):
    self.interface.stopDrag(*args)
  
  def imageDrag(self, *args):
    self.interface.mouseDrag(*args)
  
  ## Settings
  def settingsChangeMainBG(self, widget):
    color = widget.get_rgba()
    self.interface.modifyMainBG(color)
    # apply
    self.interface.applyColourSettings()
  
  def settingsToggleTrasparency(self, widget):
    if widget.get_active():
      self.interface.setImageBGCheckPattern()
      # apply
      self.interface.applyColourSettings()
      
  def settingsToggleAsMain(self, widget):
    if widget.get_active():
      self.interface.setImageBgAsMain()
      # apply
      self.interface.applyColourSettings()
    
  def settingsToggleImageBGColor(self, widget):
    if widget.get_active():
      self.interface.setImageBGAsCustom()
      # apply
      self.interface.applyColourSettings()
  
  def settingsChangeImageBGColor(self, widget):
    color = widget.get_rgba()
    self.interface.modifyImageBG(color)
    # apply
    self.interface.applyColourSettings()
  
  def settingsClose(self, *args):
    self.interface.hideSettings()


## Interface class

class Interface():

  def __init__(self, image_viewer):
    self.image_viewer = image_viewer
    
    # set program class
    Gdk.set_program_class("IW Image Viewer")
    
    # setup ui builder
    self.builder = Gtk.Builder.new()
    ui_file = os.path.join(MAIN_FOLDER, 'ui/Main.glade')
    self.builder.add_from_file(ui_file)
    self.loadHeaderBar()
    
    self.main_window = self.builder.get_object('MainWindow')
    self.image_widget = self.builder.get_object('Image')
    #self.image_widget.set_name('image-checked')
    #self.main_window.add_events(Gdk.EventMask.STRUCTURE_MASK)
    self.main_window.set_size_request(*DEFAULT_SIZE)
    self.main_window.set_title('Image Viewer')
    
    self.width = 0
    self.height = 0
    
    scrolled_window = self.builder.get_object('ScrolledWindow')
    scrolled_window.set_min_content_width(MIN_CONTENT_SIZE)
    scrolled_window.set_min_content_height(MIN_CONTENT_SIZE)
    scrolled_window.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
    
    self.setErrorImage()
    
    self.loadCss()
    self.loadAccels()
    self.setupHeaderBar()
    self.applyColourSettings()
    self.setupSettingsWindow()
    
    self.main_window_fullscreen = False
    
    self.image = None
    self.current_factor = None
    self.user_set_zoom = False
    # Zoom
    self.mouse_delta = 0
    self.scroll_zoom_number = 0
    self.scroll_position_x = 0
    self.scroll_position_y = 0
    adjust_h = scrolled_window.get_hadjustment()
    adjust_h.connect('changed', self.scrollRelativeToMouse, SCROLL_ADJUST_HORIZONTAL)
    adjust_v = scrolled_window.get_vadjustment()
    adjust_v.connect('changed', self.scrollRelativeToMouse, SCROLL_ADJUST_VERTICAL)
    # Drag
    self.drag = False
    self.drag_x = 0
    self.drag_y = 0
    # Mouse fade
    self.last_move_time = GLib.get_current_time()
    self.fade_timeout = GObject.timeout_add(500, self.checkMouseFade)
    # Timeouts
    self.open_image_timeout = None
    self.inotify_timeout = None
    self.animation_update_timeout = None
    
    # Connect signals
    self.builder.connect_signals(SHandler(self))
  
  ######################
  ## Setup header bar ##
  ######################
  def loadHeaderBar(self):
    if Gtk.get_major_version() == 3 and Gtk.get_minor_version() >= 10:
      header_file = os.path.join(MAIN_FOLDER, 'ui/HeaderBar.glade')
      self.builder.add_from_file(header_file)
      self.legacy_header = False
    else:
      # Show legacy header bar
      old_header = self.builder.get_object('HeaderBarLegacy')
      old_header.show()
      # Setup settings button
      button = self.builder.get_object('SettingsButtonLegacy')
      pixbuf = Gtk.IconTheme.get_default().load_icon(Gtk.STOCK_PREFERENCES, 16, 0)
      icon = Gtk.Image()
      icon.set_from_pixbuf(pixbuf)
      button.add(icon)
      button.show_all()
      self.legacy_header = True
  
  def setupHeaderBar(self):
    if self.legacy_header:
      btn = self.builder.get_object('SettingsButtonLegacy')
      btn.connect('clicked', self.openSettings)
    else:
      btn = self.builder.get_object('SettingsButton')
      btn.connect('clicked', self.openSettings)
      header_bar = self.builder.get_object('HeaderBar')
      self.main_window.set_titlebar(header_bar)
  
  ###########################
  ## Setup settings window ##
  ###########################
  def setupSettingsWindow(self):
    # change color buttons
    ## main
    main_btn = self.builder.get_object('BGColourButton')
    col = self.image_viewer.getInterfaceBGColour()
    main_btn.set_rgba(col)
    ## image
    img_btn = self.builder.get_object('ImageBGColourButton')
    col = self.image_viewer.getInterfaceImageBGColour()
    img_btn.set_rgba(col)
    # toggle preferences
    if self.image_viewer.isInterfaceImageBGAsMain():
      btn = self.builder.get_object('ImageBGTypeSameMain')
    elif self.image_viewer.isInterfaceImageBGPattern():
      btn = self.builder.get_object('ImageBGTypeCheck')
    else:
      btn = self.builder.get_object('ImageBGTypeColour')
    btn.set_active(True)
    
  def openSettings(self, *args):
    settings_win = self.builder.get_object('SettingsWindow')
    settings_win.show_all()
  
  def hideSettings(self):
    settings_win = self.builder.get_object('SettingsWindow')
    settings_win.hide()
  
  ################
  ## Load style ##
  ################
  def loadCss(self):
    provider = self._addCssProvider()
    css_file = os.path.join(MAIN_FOLDER, 'css/style.css')
    provider.load_from_path(css_file)

  def _addCssProvider(self):
    display = Gdk.Display.get_default()
    screen = Gdk.Display.get_default_screen(display)
    provider = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return provider
  
  def applyColourSettings(self):
    col = self.image_viewer.getInterfaceBGColour()
    self.changeMainBG(col)
    if self.image_viewer.isInterfaceImageBGAsMain():
      self.changeImageBgAsMain()
    elif self.image_viewer.isInterfaceImageBGPattern():
      self.changeImageBGCheckPattern()
    else:
      colour = self.image_viewer.getInterfaceImageBGColour()
      self.changeImageBGAsCustom(colour)
  
  ############################################
  ## Change BG colours and memorize changes ##
  ############################################
  def modifyMainBG(self, colour):
    self.image_viewer.setInterfaceBGColour(colour)
  
  def setImageBGCheckPattern(self):
    self.image_viewer.setInterfaceImageBGTypePattern()
  
  def setImageBgAsMain(self):
    self.image_viewer.setInterfaceImageBGTypeAsMain()
  
  def setImageBGAsCustom(self):
    self.image_viewer.setInterfaceImageBGTypeColour()
  
  def modifyImageBG(self, colour):
    self.image_viewer.setInterfaceImageBGColour(colour)
  
  #######################
  ## Change BG colours ##
  #######################
  def changeMainBG(self, colour):
    self.changeClassBGColour('MainView', colour)
    
  def changeImageBGCheckPattern(self):
    self.image_widget.set_name('image-checked')
  
  def changeImageBgAsMain(self):
    col = self.image_viewer.getInterfaceBGColour()
    self.changeImageBG(col)
  
  def changeImageBGAsCustom(self, colour):
    self.changeImageBG(colour)
  
  def changeImageBG(self, colour):
    self.changeClassBGColour('image', colour)
    self.image_widget.set_name('image')
  
  def changeClassBGColour(self, class_name, colour):
    # colour should be Gdk.RGBA
    colour_rgb = colour.to_string() 
    # get style provider
    provider = self._addCssProvider()
    # set class
    data = '#' + class_name + '{background-color: ' + colour_rgb + ';}'
    provider.load_from_data(bytes(data.encode()))
  
  ###################
  ## Main controls ##
  ###################
  def start(self, image):
    self.inotify_timeout = GObject.timeout_add(500, self.checkInotify)
    # Wait for the widget to be completely drawn
    GObject.timeout_add(200, self.openImage, image)
    Gtk.main()
  
  def close(self, *args):
    self.stopAnimationUpdate()
    GObject.source_remove(self.fade_timeout)
    GObject.source_remove(self.inotify_timeout)
    self.image_viewer.close()
    Gtk.main_quit()
  
  def resize(self, size):
    self.main_window.resize(*size)
  
  def show(self):
    self.main_window.show()
  
  #############
  ## Inotify ##
  #############
  def checkInotify(self):
    notifier = self.image_viewer.pyinotify_notifier
    notifier.process_events()
    while notifier.check_events():
      notifier.read_events()
      notifier.process_events()
    return True
  
  #########################
  ## Window size changes ##
  #########################
  def onMainWindowChange(self, widget, event):
    if event.get_event_type() == Gdk.EventType.WINDOW_STATE:
      if event.changed_mask == Gdk.WindowState.FULLSCREEN:
        # wait for the window changes to have taken effect
        GObject.timeout_add(100, self.fitImageToWindow)
    return False
  
  def toggleFullscreen(self):
    if self.main_window_fullscreen:
      self.modeFullscreen(False)
    else:
      self.modeFullscreen(True)
  
  def modeFullscreen(self, fullscreen):
    info_grid = self.builder.get_object("InfoGrid")
    if fullscreen:
      self.main_window.fullscreen()
      info_grid.hide()
      if self.legacy_header:
        header = self.builder.get_object('HeaderBarLegacy')
        header.hide()
      self.main_window_fullscreen = True
    else:
      self.main_window.unfullscreen()
      info_grid.show()
      if self.legacy_header:
        header = self.builder.get_object('HeaderBarLegacy')
        header.show()
      self.main_window_fullscreen = False
  
  def updateWindowSize(self, widget, event):
    if self.width != event.width or self.height != event.height:
      self.width = event.width
      self.height = event.height
    return False
  
  #####################
  ## Get window size ##
  #####################
  def getSize(self):
    if self.width == 0 or self.height == 0:
      return self.main_window.get_size()
    else:
      return self.width, self.height
  
  def getFullscreen(self):
    return self.main_window_fullscreen
  
  ################
  ## Open image ##
  ################
  def openImage(self, image):
    self.stopAnimationUpdate()
    # Set image
    self.image = image
    # Check
    if self.image is None:
      # show error widget
      self.main_window.set_title('Image viewer - No image')
      self.image_widget.show()
      return True
    self.imageQuickSetup()
    self.current_factor = 1.0
    self.user_set_zoom = False
    if self.open_image_timeout is not None:
      GObject.source_remove(self.open_image_timeout)
    self.open_image_timeout = GObject.timeout_add(20, self.openImageReal)
    return False
  
  def imageQuickSetup(self):
    # set title
    title = self.image.getFolderName() + '/' + self.image.getName()
    self.main_window.set_title(title)
    # edit bottom line
    # FIXME: it's not working as expected
    # NOTE: It works only sometimes, it seems to depend
    # from the version of libgtk used. 
    self.setEmptyInfo()
    self.fillNavigatorInfo()
    
  def openImageReal(self):
    self.image_widget.show()
    if self.image.isStatic():
      self.openStaticImage()
    elif self.image.isAnimation():
      self.openAnimation()
    else:
      self.setErrorImage()
    if not self.image.isError():
      self.fitImageToWindow()
      self.fillInfo()
    self.open_image_timeout = None
    return False # Stop timeout
  
  def setErrorImage(self):
    pixbuf = Gtk.IconTheme.get_default().load_icon(MISSING_IMAGE_ICON, 64, 0)
    self.image_widget.set_from_pixbuf(pixbuf)
    self.setEmptyInfo()
    
  def openStaticImage(self):
    self.image_widget.set_from_pixbuf(self.image.getPixbuf())
  
  def openAnimation(self):
    self.updateAnimation()
  
  @imageIsNotNone
  def nextImage(self):
    self.image_viewer.openNextImage()
  
  @imageIsNotNone
  def prevImage(self):
    self.image_viewer.openPrevImage()
  
  ####################
  ## Load Animation ##
  ####################
  def updateAnimation(self):
    # Get pixbuf
    aiter, pixbuf = self.image.getAnimationPixbuf()
    # Set image
    self.image_widget.set_from_pixbuf(pixbuf)
    # Wait for the next update
    delay = aiter.get_delay_time()
    self.animation_update_timeout = GObject.timeout_add(delay, self.updateAnimation)
    return False
  
  def stopAnimationUpdate(self):
    if self.animation_update_timeout is not None:
      GObject.source_remove(self.animation_update_timeout)
      self.animation_update_timeout = None
  
  ########################
  ## Keyboard shortcuts ##
  ########################
  def loadAccels(self):
    accels = Gtk.AccelGroup()
    accelerator = '<control>q'
    key, mod = Gtk.accelerator_parse(accelerator)
    accels.connect(key, mod, Gtk.AccelFlags.LOCKED, self.close)
    accelerator = '<control>0'
    key, mod = Gtk.accelerator_parse(accelerator)
    accels.connect(key, mod, Gtk.AccelFlags.LOCKED, self.forceFitImageToWindow)
    self.main_window.add_accel_group(accels)
  
  def monitorKeyboard(self, widget, event):
    _, key_val = event.get_keyval()
    if key_val == Gdk.KEY_Right:
      self.nextImage()
    elif key_val == Gdk.KEY_Left:
      self.prevImage()
    elif key_val == Gdk.KEY_Up:
      self.scrollVertical(-1*MOVE_IMAGE_INCREMENT)
    elif key_val == Gdk.KEY_Down:
      self.scrollVertical(MOVE_IMAGE_INCREMENT)
    elif key_val == Gdk.KEY_plus or key_val == Gdk.KEY_equal:
      self.zoomIn()
    elif key_val == Gdk.KEY_minus:
      self.zoomOut()
    elif key_val == Gdk.KEY_space:
      self.nextImage()
    elif key_val == Gdk.KEY_F11:
      self.toggleFullscreen()
    elif key_val == Gdk.KEY_Escape:
      self.modeFullscreen(False)
    return False
  
  ##########
  ## Drag ##
  ##########
  def startDrag(self, widget, event):
    self.drag = True
    self.drag_x = event.x
    self.drag_y = event.y
    self.setPointerDrag(True)
  
  def stopDrag(self, widget, event):
    self.drag = False
    self.setPointerDrag(False)
  
  def mouseDrag(self, widget, event):
    self.last_move_time = GLib.get_current_time()
    if not self.drag:
      # show mouse
      self.showPointer(True)
    else:
      scrolled_window = self.builder.get_object('ScrolledWindow')
      # x drag
      offset_x = event.x - self.drag_x
      adjust_x = scrolled_window.get_hadjustment()
      new_value = adjust_x.get_value() - offset_x
      adjust_x.set_value(new_value)
      # y drag
      offset_y = event.y - self.drag_y
      adjust_y = scrolled_window.get_vadjustment()
      new_value = adjust_y.get_value() - offset_y
      adjust_y.set_value(new_value)
      # update drag
      self.drag_x = event.x
      self.drag_y = event.y
  
  def setPointerDrag(self, set_drag):
    if set_drag:
      self.changeCursorType(Gdk.CursorType.FLEUR)
    else:
      self.changeCursorType(Gdk.CursorType.LEFT_PTR)
  
  ##################
  ## Mouse cursor ##
  ##################
  def showPointer(self, show):
    if show:
      if not self.drag:
        self.changeCursorType(Gdk.CursorType.LEFT_PTR)
      else:
        self.changeCursorType(Gdk.CursorType.FLEUR)
    else:
      self.changeCursorType(Gdk.CursorType.BLANK_CURSOR)
  
  def changeCursorType(self, cursor_type):
    window = self.main_window.get_window()
    display = Gdk.Display.get_default()
    cursor = Gdk.Cursor.new_for_display(display, cursor_type)
    window.set_cursor(cursor)
  
  def checkMouseFade(self):
    if self.main_window_fullscreen:
      now = GLib.get_current_time()
      if now - self.last_move_time >= 1.0:
        self.showPointer(False)
    return True
  
  ###############
  ## Scrolling ##
  ###############
  def scrollVertical(self, increment):
    scrolled_window = self.builder.get_object('ScrolledWindow')
    adjust = scrolled_window.get_vadjustment()
    adjust.set_value( adjust.get_value() + increment )
  
  def scrollRelativeToMouse(self, widget, position_type):
    self.scroll_zoom_number = 0
    if position_type == SCROLL_ADJUST_HORIZONTAL and self.scroll_position_x > -1:
      position = self.scroll_position_x
      self.scroll_position_x = -1
    elif position_type == SCROLL_ADJUST_VERTICAL and self.scroll_position_y > -1:
      position = self.scroll_position_y
      self.scroll_position_y = -1
    else:
      position = -1
    if position > -1:
      widget.set_value(position)
    return False
  
  def scroll(self, widget, scroll_event):
    if self.image_widget is None:
      return True
    is_scroll_direction, direction = scroll_event.get_scroll_direction()
    zoom_in = None
    zoomed = False
    if is_scroll_direction:
      if direction == Gdk.ScrollDirection.UP:
        zoom_in = True
        zoomed = self.zoomIn()
      elif direction == Gdk.ScrollDirection.DOWN:
        zoom_in = False
        zoomed = self.zoomOut()
    else:
      _, _, delta_y = scroll_event.get_scroll_deltas()
      self.mouse_delta += delta_y
      if self.mouse_delta <= -1 * MOUSE_DELTA_INCREMENT:
        zoom_in = True
        self.mouse_delta += MOUSE_DELTA_INCREMENT
        zoomed = self.zoomIn()
      elif self.mouse_delta >= MOUSE_DELTA_INCREMENT:
        zoom_in = False
        self.mouse_delta -= MOUSE_DELTA_INCREMENT
        zoomed = self.zoomOut()
    if zoomed and zoom_in is not None:
      self.scroll_zoom_number += 1
      # Get mouse position relative to img
      x_img, y_img = self.image_widget.translate_coordinates(widget, 0, 0)
      x_m, y_m = scroll_event.get_coords()
      start_x = x_m - x_img
      start_y = y_m - y_img
      # Get zoomed position
      zoom_factor = ZOOM_FACTOR ** self.scroll_zoom_number 
      zoomed_x = start_x / zoom_factor if zoom_in else start_x * zoom_factor
      zoomed_y = start_y / zoom_factor if zoom_in else start_y * zoom_factor
      # Offset
      self.scroll_position_x = zoomed_x - x_m
      self.scroll_position_y = zoomed_y - y_m
    return True
  
  ##########
  ## Zoom ##
  ##########
  @imageIsResizable
  def forceFitImageToWindow(self, *args):
    self.user_set_zoom = False
    self.fitImageToWindow()
  
  @imageIsResizable
  def fitImageToWindow(self, *args):
    scrolled_window = self.builder.get_object('ScrolledWindow')
    adjust = scrolled_window.get_hadjustment()
    width = adjust.get_page_size()
    adjust = scrolled_window.get_vadjustment()
    height = adjust.get_page_size()
    img_width, img_height = self.image.getSize()
    if not self.user_set_zoom:
      if img_width > width-5 or img_height > height-5:
        # zoom to window size
        self.zoom((width-5, height-5))
      else:
        # zoom to image size
        self.zoom((img_width, img_height))
  
  @imageIsResizable
  def zoomIn(self):
    self.user_set_zoom = True
    factor = self.current_factor / ZOOM_FACTOR 
    return self.zoomImage(factor)
  
  @imageIsResizable
  def zoomOut(self):
    self.user_set_zoom = True
    factor = self.current_factor * ZOOM_FACTOR
    return self.zoomImage(factor)
  
  @imageIsResizable
  def zoom(self, size):
    # Fit image to size
    width, height = size
    img_width, img_height = self.image.getSize()
    factor_w = width / img_width
    factor_h = height / img_height
    factor = min(factor_w, factor_h)
    return self.zoomImage(factor)
  
  @imageIsResizable  
  def zoomImage(self, factor):
    factor = max(min(factor, MAX_ZOOM), MIN_ZOOM)
    if self.current_factor is not None and factor == self.current_factor:
      # No need to update the image
      return False
    self.current_factor = factor
    img_width, img_height = self.image.getSize()
    width = max(int(img_width * self.current_factor), 1)
    height = max(int(img_height * self.current_factor), 1)
    zoom_pix = self.image.scale(width, height)
    self.fillZoomInfo()
    if self.image.isStatic():
      self.image_widget.set_from_pixbuf(zoom_pix)
    elif self.image.isAnimation():
      self.stopAnimationUpdate()
      self.updateAnimation()
    else:
      self.setErrorImage()
    # Image updated
    return True
  
  ##############
  ## Info bar ##
  ##############
  def fillInfo(self):
    # Fill image navigator
    self.fillNavigatorInfo()
    # Fill image size / zoom
    self.fillZoomInfo()
  
  def fillNavigatorInfo(self):
    label = self.builder.get_object('InfoNavigator')
    tot = self.image_viewer.getTotImages()
    label_str = str(self.image.getPosition() + 1) + '/' + str(tot)
    label.set_text(label_str)
  
  def fillZoomInfo(self):
    label = self.builder.get_object('InfoSize')
    width, height = self.image.getSize()
    label_str = str(width) + 'x' + str(height) + ' (' + str(round(self.current_factor*100, 1)) + '%)'
    label.set_text(label_str)
  
  def setEmptyInfo(self):
    label = self.builder.get_object('InfoNavigator')
    label.set_text('')
    label = self.builder.get_object('InfoSize')
    label.set_text('')
