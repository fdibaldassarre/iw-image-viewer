
import os
import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gio, Gtk

from . import ImageViewer


APPLICATION_ID = "org.fdibaldassarre.imageviewer"


class ImageViewerApplication(Gtk.Application):

    def __init__(self, command_line_args, *args, **kwargs):
        super().__init__(*args,
                         application_id=APPLICATION_ID,
                         flags=Gio.ApplicationFlags.NON_UNIQUE,
                         **kwargs)
        self.command_line_args = command_line_args
        self.image_viewer = None
        self.main_window = None
        self.inhibit_cookie = None

    def start_image_viewer(self):
        if len(self.command_line_args.address) > 0:
            address = os.path.realpath(self.command_line_args.address[0])
        else:
            address = None

        config_folder = os.path.join(os.environ['HOME'], ".config/iw-image-viewer/")

        iw = ImageViewer.new(self,
                             config_folder,
                             shuffle=self.command_line_args.shuffle,
                             slideshow=self.command_line_args.slideshow)
        iw.start(address)
        return iw

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.image_viewer = self.start_image_viewer()

    def do_activate(self):
        self.main_window = self.image_viewer.interface.main_window
        self.add_window(self.main_window)

    def inhibit_sleep(self, inhibit: bool = True):
        if inhibit:
            if self.inhibit_cookie is None:
                self.inhibit_cookie = Gtk.Application.inhibit(self, self.main_window, Gtk.ApplicationInhibitFlags.IDLE, "No idle")
        else:
            Gtk.Application.uninhibit(self, self.inhibit_cookie)
            self.inhibit_cookie = None

