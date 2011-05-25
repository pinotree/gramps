# -*- coding: utf-8 -*-
#!/usr/bin/python
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2011 Rob G. Healey <robhealey1@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# $Id$

# *****************************************************************************
# Python Modules
# *****************************************************************************
import os, sys
from datetime import datetime, date
from calendar import monthrange as _mr
import time

# abilty to escape certain characters from output...
from xml.sax.saxutils import escape as _html_escape

from itertools import chain

from decimal import *
getcontext().prec = 4
from fractions import Fraction

import subprocess

# -----------------------------------------------------------------------------
# GTK modules
# -----------------------------------------------------------------------------
import gtk

# -----------------------------------------------------------------------------
# GRAMPS modules
# -----------------------------------------------------------------------------
import GrampsDisplay
from QuestionDialog import WarningDialog, QuestionDialog, OptionDialog

from gen.ggettext import gettext as _

from gen.plug import Gramplet
from DateHandler import displayer as _dd

import gen.lib
import gen.mime
import Utils
from PlaceUtils import conv_lat_lon
from ListModel import ListModel, NOSORT

#####################################################################
#               Check for pyexiv2 library...
#####################################################################
# pyexiv2 download page (C) Olivier Tilloy
_DOWNLOAD_LINK = "http://tilloy.net/dev/pyexiv2/download.html"

# make sure the pyexiv2 library is installed and at least a minimum version
software_version = False
Min_VERSION = (0, 1, 3)
Min_VERSION_str = "pyexiv2-%d.%d.%d" % Min_VERSION
Pref_VERSION_str = "pyexiv2-%d.%d.%d" % (0, 3, 0)

try:
    import pyexiv2
    software_version = pyexiv2.version_info

except ImportError, msg:
    WarningDialog(_("You need to install, %s or greater, for this addon to work...\n"
                    "I would recommend installing, %s, and it may be downloaded from here: \n%s") % (
                        Min_VERSION_str, Pref_VERSION_str, _DOWNLOAD_LINK), str(msg))
    raise Exception(_("Failed to load 'Edit Image Exif Metadata'..."))
               
# This only happends if the user has pyexiv2-0.1.3 installed on their computer...
except AttributeError:
    pass

# v0.1 has a different API to v0.2 and above...
if hasattr(pyexiv2, 'version_info'):
    LesserVersion = False
else:
    # version_info attribute does not exist prior to v0.2.0
    LesserVersion = True

# the library is either not installed or does not meet minimum required version for this addon....
if (software_version and (software_version < Min_VERSION)):
    msg = _("The minimum required version for pyexiv2 must be %s \n"
        "or greater.  Or you do not have the python library installed yet.  "
        "You may download it from here: %s\n\n  I recommend getting, %s") % (
         Min_VERSION_str, _DOWNLOAD_LINK, Pref_VERSION_str)
    WarningDialog(msg)
    raise Exception(msg)

# *******************************************************************
# Determine if we have access to outside Programs installed on this computer,
#     which will extend the functionality of this addon?
#
# The programs are ImageMagick, and jhead
# * ImageMagick -- Convert and Delete all Exif metadata...
# * jhead       -- re-initialize a jpeg, and other features...
# * del/ rm     -- delete old files from the convert command...
#********************************************************************
# Windows 32bit systems
system_platform = os.sys.platform
if system_platform == "win32":
    _MAGICK_FOUND = "convert.exe" if Utils.search_for("convert.exe") else False
    _JHEAD_FOUND = "jhead.exe" if Utils.search_for("jhead.exe") else False
    _DEL_FOUND = "del.exe" if Utils.search_for("del.exe") else False

elif system_platform == "linux2":
    _MAGICK_FOUND = "convert" if Utils.search_for("convert") else False
    _JHEAD_FOUND = "jhead" if Utils.search_for("jhead") else False
    _DEL_FOUND = "rm" if Utils.search_for("rm") else False

else:
    _MAGICK_FOUND = "convert" if Utils.search_for("convert") else False
    _JHEAD_FOUND = "jhead" if Utils.search_for("jhead") else False
    _DEL_FOUND = "del" if Utils.search_for("del") else False

# if external programs are not found, let the user know about the missing functionality?
if not _MAGICK_FOUND:
    print(_("ImageMagick's convert program was not found on this computer.\n"
        "You may download it from here: %s...") % (
            "http://www.imagemagick.org/script/index.php"))

if not _JHEAD_FOUND:
    print(_("Jhead program was not found on this computer.\n"
        "You may download it from: %s...") % (
            "http://www.sentex.net/~mwandel/jhead/"))

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
# available image types for exiv2 and pyexiv2
_vtypes = [".jpeg", ".jpg", ".jfif", ".exv", ".tiff", ".dng", ".nef", ".pef", ".pgf",
    ".png", ".psd", ".jp2"]

# set up Exif keys for Image.exif_keys
_DATAMAP = {
    "Xmp.xmp.Label"                : "ExifLabel",
    "Exif.Image.ImageDescription"  : "Description",
    "Exif.Image.DateTime"          : "Modified",
    "Exif.Image.Artist"            : "Artist",
    "Exif.Image.Copyright"         : "Copyright",
    "Exif.Photo.DateTimeOriginal"  : "Original",
    "Exif.Photo.DateTimeDigitized" : "Digitized",
    "Exif.Image.XResolution"       : "Xresolution",
    "Exif.Image.YResolution"       : "YResolution",
    "Exif.Image.ResolutionUnit"    : "ResolutionUnit",
    "Exif.GPSInfo.GPSLatitudeRef"  : "LatitudeRef",
    "Exif.GPSInfo.GPSLatitude"     : "Latitude",
    "Exif.GPSInfo.GPSLongitudeRef" : "LongitudeRef",
    "Exif.GPSInfo.GPSLongitude"    : "Longitude",
    "Exif.GPSInfo.GPSAltitudeRef"  : "AltitudeRef",
    "Exif.GPSInfo.GPSAltitude"     : "Altitude"}
_DATAMAP  = dict( (key, val) for key, val in _DATAMAP.items() )
_DATAMAP.update( (val, key) for key, val in _DATAMAP.items()  )

# define tooltips for all data entry fields...
_TOOLTIPS = {

    "Description" : _("Provide a short descripion for this image."),

    "Artist" : _("Enter the Artist/ Author of this image.  The person's name or "
        "the company who is responsible for the creation of this image."),

    "Copyright" : _("Enter the copyright information for this image. \n"),

    "Year" : _("Enter the year for the date of this image.\n"
        "Example: 1826 - 2100, You can either spin the up and down arrows by clicking on them or enter it manually."),

    "Month" : _("Enter the month for the date of this image.\n"
        "Example: 0 - 12, You can either spin the up and down arrows by clicking on them or enter it manually."),

    "Day" : _("Enter the day for the date of this image.\n"
        "Example: 1 - 31, You can either spin the up and down arrows by clicking on them or enter it manually."),

    "Hour" : _("Enter the hour for the time of this image.\n"
        "Example: 0 - 23, You can either spin the up and down arrows by clicking on them or enter it manually.\n\n"
        "The hour is represented in 24-hour format."),

    "Minutes" : _("Enter the minutes for the time of this image.\n"
        "Example: 0 - 59, You can either spin the up and down arrows by clicking on them or enter it manually."),

    "Seconds" : _("Enter the seconds for the time of this image.\n"
        "Example: 0 - 59, You can either spin the up and down arrows by clicking on them or enter it manually."),

    "Latitude" : _("Enter the Latitude GPS Coordinates for this image,\n"
        "Example: 43.722965, 43 43 22 N, 38° 38′ 03″ N, 38 38 3"),

    "Longitude" : _("Enter the Longitude GPS Coordinates for this image,\n"
        "Example: 10.396378, 10 23 46 E, 105° 6′ 6″ W, -105 6 6") }
_TOOLTIPS  = dict( (key, tip) for key, tip in _TOOLTIPS.items() )

# define tooltips for all buttons...
# common buttons for all images...
_BUTTONTIPS = {
    # Clear Edit Area button... 
    "Clear" : _("Clears the Exif metadata from the Edit area."),

    # Wiki Help button...
    "Help" : _("Displays the Gramps Wiki Help page for 'Edit Image Exif Metadata' in your web browser."),

    # Edit screen button...
    "Edit" : _("This will open up a new window to allow you to edit/ modify this image's Exif metadata.\n"
        "It will also allow you to be able to Save the modified metadata.") }

if (_MAGICK_FOUND or _JHEAD_FOUND):
    _BUTTONTIPS.update( {
        # Thumbnail Viewing Window button...
        "ThumbnailView" : _("Will produce a Popup window showing a Thumbnail Viewing Area"),

        # Convert to .Jpeg button...
        "Convert" : _("If your image is not a .jpg image, convert it to a .jpg image?"),

        # Delete/ Erase/ Wipe Exif metadata button...
        "Delete" : _("WARNING:  This will completely erase all Exif metadata "
            "from this image!  Are you sure that you want to do this?") } )

# ------------------------------------------------------------------------
# Gramplet class
# ------------------------------------------------------------------------
class EditExifMetadata(Gramplet):

    def init(self):

        self.exif_widgets = {}

        self.orig_image    = False
        self.image_path    = False
        self.plugin_image  = False

        vbox = self.build_gui()
        self.connect_signal("Media", self.update)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)

    def build_gui(self):
        """
        will display all exif metadata and all buttons.
        """

        main_vbox = gtk.VBox(False, 0)
        main_vbox.set_border_width(10)

        # Displays the file name...
        medialabel = gtk.HBox(False)
        label = gtk.Label()
        label.set_alignment(0.0, 0.0)
        label.set_line_wrap(True)
        medialabel.pack_start(label, expand =False)
        self.exif_widgets["MediaLabel"] = label
        main_vbox.pack_start(medialabel, expand =False, fill =False, padding =5)
        label.show()

        # Displays mime type information...
        mimetype = gtk.HBox(False)
        label = gtk.Label()
        label.set_alignment(0.0, 0.0)
        label.set_line_wrap(True)
        mimetype.pack_start(label, expand =False)
        self.exif_widgets["MimeType"] = label
        main_vbox.pack_start(mimetype, expand =False, fill =False, padding =5)
        label.show()

        # Displays all plugin messages...
        messagearea = gtk.HBox(False)
        label = gtk.Label()
        label.set_alignment(0.5, 0.0)
        label.set_line_wrap(True)
        messagearea.pack_start(label, expand =False)
        self.exif_widgets["MessageArea"] = label
        main_vbox.pack_start(messagearea, expand =False, fill =False, padding =5)
        label.show()

        # Clear, Thumbnail View, Convert horizontal box
        ctc_box = gtk.HButtonBox()
        ctc_box.set_layout(gtk.BUTTONBOX_START)
        main_vbox.pack_start(ctc_box, expand =False, fill =False, padding =5)

        # Clear button...
        ctc_box.add( self.__create_button(
            "Clear", False, [self.clear_display], gtk.STOCK_CLEAR) )

        # Thumbnail View button...
        ctc_box.add( self.__create_button(
            "ThumbnailView", _("Thumbnail"), [self.thumbnail_view] ) )

        # is ImageMagick installed?
        if _MAGICK_FOUND:

            # Convert button...
            ctc_box.add( self.__create_button(
                "Convert", False, [self.__convert_dialog], gtk.STOCK_CONVERT) )

        # Help, Edit, and Delete horizontal box
        hed_box = gtk.HButtonBox()
        hed_box.set_layout(gtk.BUTTONBOX_START)
        main_vbox.pack_start(hed_box, expand =False, fill =False, padding =5)

        # Help button...
        hed_box.add( self.__create_button(
            "Help", False, [self.__help_page], gtk.STOCK_HELP, True) )

        # Edit button...
        hed_box.add( self.__create_button(
            "Edit", False, [self.display_edit_window], gtk.STOCK_EDIT) )

        if _MAGICK_FOUND:
            # Delete All Metadata button...
            hed_box.add(self.__create_button(
                "Delete", False, [self.__wipe_dialog], gtk.STOCK_DELETE ) )

        # greyed- shaded lines display area...
        new_vbox = self.build_shaded_display()
        main_vbox.pack_start(new_vbox, expand =False, fill =False, padding =10)

        main_vbox.show_all()
        return main_vbox

    def main(self): # return false finishes
        """
        get the active media, mime type, and reads the image metadata
        """
        db = self.dbstate.db

        # clears all labels...
        for widget in ["MediaLabel", "MimeType", "MessageArea"]:
            self.exif_widgets[widget].set_text("")
        self.model.clear()

        # set Message Ares to Select...
        self.exif_widgets["MessageArea"].set_text(_("Select an image to view it's Exif metadata..."))

        active_handle = self.get_active("Media")
        if not active_handle:
            self.set_has_data(False)
            return

        self.orig_image = db.get_object_from_handle(active_handle)
        self.image_path = Utils.media_path_full(db, self.orig_image.get_path() )
        if (not self.orig_image or not os.path.isfile(self.image_path)):
            self.exif_widgets["MessageArea"].set_text(_("Image is either missing or deleted,\n"
                "Please choose a different image..."))
            return

        # disable all data fields and buttons if NOT an exiv2 image type?
        basename, self.extension = os.path.splitext(self.image_path)
        self._setup_buttons(self.extension)

        # check image read privileges...
        _readable = os.access(self.image_path, os.R_OK)
        if not _readable:
            self.exif_widgets["MessageArea"].set_text(_("Image is NOT readable,\n"
                "Please choose a different image..."))
            return

        # check image write privileges...
        _writable = os.access(self.image_path, os.W_OK)
        if not _writable:
            self.exif_widgets["MessageArea"].set_text(_("Image is NOT writable,\n"
                "You will NOT be able to save Exif metadata...."))

        # display file description/ title...
        self.exif_widgets["MediaLabel"].set_text(_html_escape(
            self.orig_image.get_description() ) )

        # Mime type information...
        mime_type = self.orig_image.get_mime_type()
        self.exif_widgets["MimeType"].set_text(gen.mime.get_description(mime_type) )

        # display all button tooltips only...
        # False would be for the data fields also...
        self._setup_widget_tips([False, True])

        # determine if it is a mime image object?
        if mime_type:
            if mime_type.startswith("image"):

                # Checks to make sure that ImageMagick is installed on this computer and
                # the image is NOT a (".jpeg", ".jfif", or ".jpg") image...
                # if not, then activate the Convert button?
                if (_MAGICK_FOUND and self.extension not in [".jpeg", ".jpg", ".jfif"] ):
                    self.activate_buttons(["Convert"])

                # creates, and reads the plugin image instance...
                self.plugin_image = self.setup_image(self.image_path)

                # Check for Thumbnails...
                previews = self.plugin_image.previews
                if (len(previews) > 0):
                    self.activate_buttons(["ThumbnailView"])

                # display all exif metadata...
                self.display_metadata(_get_exif_keypairs(self.plugin_image) )

            else:
                self.exif_widgets["MessageArea"].set_text(_("Please choose a different image..."))
                return
        else:
            self.exif_widgets["MessageArea"].set_text(_("Please choose a different image..."))
            return

    def _setup_buttons(self, extension):
        """
        disable all buttons...
            * if file extension is NOT an exiv2 image type?

        do NOT disable the Help button...
        *** do NOT affect the sensitivity of the "Thumbnail", "Convert", "Delete" buttons
            as they take care of themselves
        """

        # _vtypes is a list of valid exiv2 image types...
        # if False, then disable the buttons?
        goodextension = (extension in _vtypes)

        _EXCEPTIONS =["Help"]
        if _MAGICK_FOUND:
            _EXCEPTIONS.append(["Thumbnail", "Convert", "Delete"])
  
        for widget, tooltip in _BUTTONTIPS.items():
            if widget not in _EXCEPTIONS:
                self.exif_widgets[widget].set_sensitive(goodextension)

    def _setup_widget_tips(self, _ttypes):
        """
        set up widget tooltips...
            * data fields
            * buttons
        """
        fields, buttons = _ttypes

        # if True, setup tooltips for all Data Entry Fields...
        if fields:
            for widget, tooltip in _TOOLTIPS.items():
                self.exif_widgets[widget].set_tooltip_text(tooltip)

        # if True, setup tooltips for all Buttons...
        if buttons:
            for widget, tooltip in _BUTTONTIPS.items():
                self.exif_widgets[widget].set_tooltip_text(tooltip)

    def setup_image(self, full_path):
        """
        This will:
            * create the plugin image instance if needed,
            * setup the tooltips for the data fields,
            * setup the tooltips for the buttons,
        """

        if LesserVersion:  # prior to pyexiv2-0.2.0
            metadata = pyexiv2.Image(full_path)
            try:
                metadata.readMetadata()
            except (IOError, OSError):
                self.set_has_data(False)
                return 

        else:  # pyexiv2-0.2.0 and above
            metadata = pyexiv2.ImageMetadata(full_path)
            try:
                metadata.read()
            except (IOError, OSError):
                self.set_has_data(False)
                return
        return metadata

    def update_has_data(self):
        active_handle = self.get_active('Media')
        active = self.dbstate.db.get_object_from_handle(active_handle)
        self.set_has_data(self.get_has_data(active))

    def get_has_data(self, media):
        """
        Return True if the gramplet has data, else return False.
        """
        db = self.dbstate.db

        if media is None:
            return False

        full_path = Utils.media_path_full(db, media.get_path() )
        if not os.path.isfile(full_path):
            return False

        if LesserVersion: # prior to pyexiv2-0.2.0
            metadata = pyexiv2.Image(full_path)
            try:
                metadata.readMetadata()
            except (IOError, OSError):
                return False

        else: # pyexiv2-0.2.0 and above
            metadata = pyexiv2.ImageMetadata(full_path)
            try:
                metadata.read()
            except (IOError, OSError):
                return False

        # update image Exif metadata...
        MediaDataTags = _get_exif_keypairs(self.plugin_image)
        if MediaDataTags:
            return True

        return False

    def display_metadata(self, metadatatags):
        """
        displays all of the image's Exif metadata in a grey-shaded tree view...
        """

        if not metadatatags:
            return

        # set Message Area to Display...
        self.exif_widgets["MessageArea"].set_text(_("Displaying all Exif metadata keypairs..."))

        # activate clear and edit buttons...
        self.activate_buttons(["Clear", "Edit"])

        for KeyTag in metadatatags:
            if LesserVersion:  # prior to pyexiv2-0.2.0...

                label = self.plugin_image.tagDetails(KeyTag)[0]
                if KeyTag in ("Exif.Image.DateTime",
                              "Exif.Photo.DateTimeOriginal",
                              "Exif.Photo.DateTimeDigitized"):
                    human_value = _format_datetime(self.plugin_image[KeyTag])
                else:
                    human_value = self.plugin_image.interpretedExifValue(KeyTag)
            else:  # pyexiv2-0.2.0 and above...
                human_value = False
                try:
                    tag = self.plugin_image[KeyTag]

                    if KeyTag in ("Exif.Image.DateTime",
                                  "Exif.Photo.DateTimeOriginal",
                                  "Exif.Photo.DateTimeDigitized"):
                        label = tag.label
                        human_value = _format_datetime(tag.value)
                    elif ("Xmp" in KeyTag or "Iptc" in KeyTag):
                        label = KeyTag
                        human_value = tag.value
                    else:
                        label = tag.label
                        human_value = tag.human_value
                    self.model.add((label, human_value))
                except AttributeError:
                    pass

    def __create_button(self, pos, text, callback =[], icon =False, sensitive =False):
        """
        creates and returns a button for display
        """

        if (icon and not text):
            button = gtk.Button(stock=icon)
        else:
            button = gtk.Button(text)

        if callback is not []:
            for _call in callback:
                button.connect("clicked", _call)

        if not sensitive:
            button.set_sensitive(False)
        self.exif_widgets[pos] = button

        return button

    def build_shaded_display(self):
        """
        Build the GUI interface.
        """

        top = gtk.TreeView()
        titles = [(_('Key'), 1, 190),
                  (_('Value'), 2, 360)]
        self.model = ListModel(top, titles)

        return top

    def clear_display(self, obj):
        """
        clears all data fields to nothing
        """

        for widgetsName in ["MediaLabel", "MimeType", "MessageArea"]:
            self.exif_widgets[widgetsName].set_text("")

        # Clears the display area...
        self.model.clear()

        # De-activate the buttons except for Help...
        self.deactivate_buttons(["ThumbnailView"])

        if _MAGICK_FOUND:
            self.deactivate_buttons(["Convert"])

        if (_MAGICK_FOUND or _HEAD_FOUND): 
            self.deactivate_buttons(["Delete"])

    def thumbnail_view(self, obj):
        """
        will allow a display area for a thumbnail pop-up window.
        """
 
        tip = _("Click Close to close this ThumbnailView Viewing Area.")

        tbarea = gtk.Window(gtk.WINDOW_TOPLEVEL)
        tbarea.tooltip = tip
        tbarea.set_title(_("ThumbnailView Viewing Area"))
        tbarea.set_default_size(250, 200)
        tbarea.set_border_width(10)

        tbarea.connect('destroy', lambda tbarea: tbarea.destroy() )

        # extract the thumbnail data
        previews = self.plugin_image.previews
        if not previews:
            print(_("This image doesn't contain any ThumbnailViews..."))
            tbarea.destroy()
        else:

            # Get the largest preview available...
            preview = previews[-1]

            # Create a pixbuf loader to read the thumbnail data...
            pbloader = gtk.gdk.PixbufLoader()
            pbloader.write(preview.data)

            # Get the resulting pixbuf and build an image to be displayed...
            pixbuf = pbloader.get_pixbuf()
            pbloader.close()
            imgwidget = gtk.Image()
            imgwidget.set_from_pixbuf(pixbuf)

            # Show the application's main window...
            tbarea.add(imgwidget)
            imgwidget.show()
            tbarea.show()

    def __convert_dialog(self, obj):
        """
        Handles the Convert question Dialog...
        """

        # if ImageMagick and delete has been found on this computer?
        if (_MAGICK_FOUND and _DEL_FOUND):
            OptionDialog(_("Edit Image Exif Metadata"), _("WARNING: You are about to convert this "
                "image into a .jpeg image.  Are you sure that you want to do this?"), 
                _("Convert and Delete original"), self.convertdelete, 
                _("Convert"), self.convert2Jpeg)

        # is ImageMagick is installed?
        elif _MAGICK_FOUND:

            QuestionDialog(_("Edit Image Exif Metadata"), _("Convert this image to a .jpeg image?"),
                _("Convert"), self.convert2Jpeg)

    def convertdelete(self, object):
        """
        will convert2Jpeg and delete original non-jpeg image.
        """

        self.convert2Jpeg()

        if system_platform == "linux2":
            delete = subprocess.check_call( [_DEL_FOUND, "-rf", self.image_path] )
        else:
            delete = subprocess.check_call( [_DEL_FOUND, "-y", self.image_path] )
        delete_result = str(delete)

        if delete_result:
            self.exif_widgets["MessageArea"].set_text(_("Image has been converted to a .jpg image,\n"
                "and original image has been deleted!"))

    def convert2Jpeg(self):
        """
        Will attempt to convert an image to jpeg if it is not?
        """

        filepath, basename = os.path.split(self.image_path)
        basename, oldext = os.path.splitext(self.image_path)
        newextension = ".jpeg"

        convert = subprocess.check_call(["convert", self.image_path, 
                os.path.join(filepath, basename + newextension) ] )
        if str(convert):

            # set Message Area to Convert...
            self.exif_widgets["MessageArea"].set_text(_("Converting image,\n"
                "You will need to delete the original image file..."))

            self.deactivate_buttons(["Convert"])

    def __help_page(self, object):
        """
        will bring up a Wiki help page.
        """

        GrampsDisplay.help(webpage = "Edit Image Exif Metadata")

    def activate_buttons(self, ButtonList):
        """
        Enable/ activate the buttons that are in ButtonList
        """

        for ButtonName in ButtonList:
            self.exif_widgets[ButtonName].set_sensitive(True)

    def deactivate_buttons(self, ButtonList):
        """
        disable/ de-activate buttons in ButtonList
        """
        for ButtonName in ButtonList:
            self.exif_widgets[ButtonName].set_sensitive(False)

    def active_buttons(self, obj):
        """
        will handle the toggle action of the Edit button.

        If there is no Exif metadata, then the data fields are connected to the 
        'changed' signal to be able to activate the Edit button once data has been entered
        into the data fields...

        Activate these buttons once info has been entered into the data fields...
        """

        if not self.exif_widgets["Edit"].get_sensitive():
            self.activate_buttons(["Edit"])

            # set Message Area to Entering Data...
            self.exif_widgets["MessageArea"].set_text(_("Entering data..."))

        if not self.exif_widgets["Clear"].get_sensitive():
            self.activate_buttons(["Clear"])

        if _MAGICK_FOUND:
            if not self.exif_widgets["Delete"].get_sensitive():
                self.activate_buttons(["Delete"])

    def display_edit_window(self, obj):
        """
        creates the editing area fields.
        """

        tip = _("Click the close button when you are finished modifying this image's Exif metadata.")

        self.edtarea = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.edtarea.tooltip = tip
        self.edtarea.set_title( self.orig_image.get_description() )
        self.edtarea.set_default_size(550, 582)
        self.edtarea.set_border_width(10)
        self.edtarea.connect("destroy", lambda w: self.edtarea.destroy() )

        # create a new scrolled window.
        scrollwindow = gtk.ScrolledWindow()
        scrollwindow.set_border_width(10)
        scrollwindow.set_size_request(490, 528)
        scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        # The dialog window is created with a vbox packed into it.
        self.edtarea.add(scrollwindow)
        scrollwindow.show()

        vbox = self.build_edit_gui()
        scrollwindow.add_with_viewport(vbox)
        self.edtarea.show()

        # display all fields and button tooltips...
        # need to add Save and Close over here...
        _TOOLTIPS.update( (key, tip) for key, tip in {
            "Save" : _("Saves a copy of the data fields into the image's Exif metadata."),

            "Close" : _("Closes this popup Edit window.\n"
                "WARNING: This action will NOT Save any changes/ modification made to this "
                "image's Exif metadata.") }.items() )
        self._setup_widget_tips([True, True])
 
        # display all Exif metadata if they are in _DATAMAP, see line #151...
        self.EditArea([KeyTag for KeyTag in _get_exif_keypairs(self.plugin_image) if KeyTag in _DATAMAP])

    def build_edit_gui(self):
        """
        will build the edit screen ...
        """

        main_vbox = gtk.VBox()
        main_vbox.set_border_width(10)
        main_vbox.set_size_request(480, 518)

        # Displays Last Change/ Modified DateStamp...
        datestamp = gtk.HBox(False)
        label = gtk.Label()
        label.set_alignment(0.0, 0.0)
        label.set_line_wrap(True)
        datestamp.pack_start(label, expand =False, fill =False, padding =0)
        self.exif_widgets["DateStamp"] = label
        label.show()
        main_vbox.pack_start(datestamp, expand =False, fill =False, padding =10)
        datestamp.show()

        # create the data fields...
        # ***Label/ Title, Description, Artist, and Copyright
        gen_frame = gtk.Frame(_("General Data"))
        gen_frame.set_size_request(460, 200)
        main_vbox.pack_start(gen_frame, expand =False, fill =True, padding =10)
        gen_frame.show()

        new_vbox = gtk.VBox(False, 0)
        gen_frame.add(new_vbox)
        new_vbox.show()

        textNames = list( (text) for text in [_("Exif Title :"), _("Description :"), _("Artist :"), _("Copyright :") ] )
        widgetsNames = list( (widget) for widget in ["ExifLabel", "Description", "Artist", "Copyright"] )
        while (textNames and widgetsNames):
            text = textNames[0]
            widget = widgetsNames[0] 

            new_hbox = gtk.HBox(False, 0)
            new_vbox.pack_start(new_hbox, expand =False, fill =False, padding =5)
            new_hbox.show()

            label = gtk.Label(text)
            label.set_alignment(0.0, 0.0)
            label.set_size_request(80, 25)
            new_hbox.pack_start(label, expand =False, fill =False, padding =0)
            label.show()

            event_box = gtk.EventBox()
            event_box.set_size_request(380, 30)
            new_hbox.pack_start(event_box, expand =False, fill =False, padding =0)
            event_box.show()
            self.exif_widgets[widget + "Box"] = event_box

            entry = gtk.Entry(max =50)
            event_box.add(entry)
            entry.show()
            self.exif_widgets[widget] = entry

            # remove text and widget from their list...
            textNames.remove(text)
            widgetsNames.remove(widget)
         
        # get current date and time from this computer...
        now = time.localtime()

        # iso format: Year, Month, Day spinners...
        datetime_frame = gtk.Frame(_("Original Date/ Time"))
        datetime_frame.set_size_request(460, 110)
        main_vbox.pack_start(datetime_frame, expand =False, fill =False, padding =0)
        datetime_frame.show()

        new_vbox = gtk.VBox(False, 0)
        new_vbox.set_border_width(5)
        datetime_frame.add(new_vbox)
        new_vbox.show()

        new_hbox = gtk.HBox(False, 0)
        new_vbox.pack_start(new_hbox, expand =False, fill =False, padding =5)
        new_hbox.show()

        # create the adjustment for each of the SpinButtons for Date/ Time
        datetime_adj = [ [value, lower, upper, step, page] for (value, lower, upper, step, page) in [
                (now[0], 1826, 2100, 1, 100), # Year
                (now[1], 1, 12, 1, 1),        # Month
                (now[2], 1, 31, 1, 1),        # Day
                (now[3], 0, 23, 1, 1),        # Hour
                (now[4], 0, 59, 1, 1),        # Minutes
                (now[5], 0, 59, 1, 1) ] ]     # Seconds
        textNames = [_("Year :"), _("Month :"), _("Day :"), _("Hour :"), _("Minutes :"), _("Seconds :")]
        widgetNames = ["Year", "Month", "Day", "Hour", "Minutes", "Seconds"]

        index = 0
        for (value, lower, upper, step, page) in datetime_adj:
            text, widget = textNames[index], widgetNames[index]

            vbox2 = gtk.VBox(False, 0)
            new_hbox.pack_start(vbox2, expand =False, fill =False, padding =5)
            vbox2.show()

            label = gtk.Label(text)
            label.set_alignment(0.0, 0.0)
            label.set_size_request(70, 25)
            vbox2.pack_start(label, expand =False, fill =False, padding =0)
            label.show()
  
            event_box = gtk.EventBox()
            event_box.set_border_width(2)
            event_box.set_size_request(70, 40)
            vbox2.pack_start(event_box, expand =False, fill =False, padding =0)
            event_box.show()
            self.exif_widgets[widget + "Box"] = event_box 

            adj = gtk.Adjustment(value, lower, upper, step, page)
            spinner = self.__create_spinner("Year", adj, False, False)
            event_box.add(spinner)
            spinner.show()
            self.exif_widgets[widget] = spinner

            index += 1

        # GPS Coordinates...
        latlong_frame = gtk.Frame(_("Latitude/ Longitude/ Altitude GPS Coordinates"))
        latlong_frame.set_size_request(460, 100)
        main_vbox.pack_start(latlong_frame, expand =False, fill =False, padding =0)
        latlong_frame.show()

        new_vbox = gtk.VBox(False, 0)
        latlong_frame.add(new_vbox)
        new_vbox.show()

        new_hbox = gtk.HBox(False, 0)
        new_vbox.pack_start(new_hbox, expand =False, fill =False, padding =0)
        new_hbox.show()

        # Latitude/ Longitude/ Altitude GPS Coordinates...
        widget_text = [ (text) for text in [_("Latitude"), _("Longitude"), _("Altitude") ] ]
        while widget_text:
            text = widget_text[0] + " :"
            widget = widget_text[0]

            vbox2 = gtk.VBox(False, 0)
            new_hbox.pack_start(vbox2, expand =False, fill =False, padding =5)
            vbox2.show()

            label = gtk.Label(text)
            label.set_alignment(0.0, 0.0)
            label.set_size_request(150, 25)
            vbox2.pack_start(label, expand =False, fill =False, padding =0)
            label.show()

            event_box = gtk.EventBox()
            event_box.set_border_width(2)
            event_box.set_size_request(150, 40)

            # set eventbox background color to "blue"
            event_box.modify_bg(gtk.STATE_NORMAL,
                                event_box.get_colormap().alloc_color("blue"))
            vbox2.pack_start(event_box, expand =False, fill =False, padding =0)
            event_box.show()
            self.exif_widgets[widget + "Box"] = event_box

            entry = gtk.Entry(max =18)
            event_box.add(entry)
            entry.show()
            self.exif_widgets[widget] = entry

            # remove the entries one by one after displaying... 
            widget_text.remove(widget)

        # Help, Save, Clear, and Close horizontal box
        hscc_box = gtk.HButtonBox()
        hscc_box.set_layout(gtk.BUTTONBOX_START)
        main_vbox.pack_start(hscc_box, expand =False, fill =False, padding =10)
        hscc_box.show()

        # Help button...
        button = self.__create_button(
            "Help", False, [self.__help_page], gtk.STOCK_HELP, True)
        hscc_box.add(button)
        button.show()

        # Save button...
        button = self.__create_button("Save", False, [self.save_metadata, self.update, 
                self.display_metadata], gtk.STOCK_SAVE, True)
        hscc_box.add(button)
        button.show()

        # Clear button...
        button = self.__create_button("Clear", False, [self.clear_edit_area], gtk.STOCK_CLEAR, True)
        hscc_box.add(button)
        button.show()

        # Close button...
        button = self.__create_button("Close", False, [lambda w: self.edtarea.destroy()], gtk.STOCK_CLOSE, True)
        hscc_box.add(button)
        button.show()

        main_vbox.show_all()
        return main_vbox

    def __wipe_dialog(self, obj):
        """
        Handles the Delete Dialog...
        """

        QuestionDialog(_("Edit Image Exif Metadata"), _("WARNING!  You are about to completely "
            "delete the Exif metadata from this image?"), _("Delete"),
                self.strip_metadata)

    def _get_value(self, KeyTag):
        """
        gets the value from the Exif Key, and returns it...

        @param: KeyTag -- image metadata key
        """

        KeyValue = ""
        if LesserVersion:
            KeyValue = self.plugin_image[KeyTag]
        else:
            try:
                KeyValue = self.plugin_image[KeyTag].value

            except (KeyError, ValueError, AttributeError):
                pass

        return KeyValue

    def clear_edit_area(self, object):
        """
        will clear the Edit Area display...
        """

        for widget in ["DateStamp", "ExifLabel", "Description", "Artist", "Copyright", "Latitude", "Longitude"]:
            self.exif_widgets[widget].set_text()

        index = 0
        now = time.localtime()
        for widget in ["Year", "Month", "Day", "Hour", "Minutes", "Seconds"]:
            self.exif_widgets[widget].set_value(now[index])

            index += 1
 
    def clear_display(self, object):
        """
        clears all data fields to nothing
        """

        for widgetsName in ["DateStamp"]:
            self.exif_widgets[widgetsName].set_text("")

        for widget, tooltip in _TOOLTIPS.items():
            self.exif_widgets[widget].set_text("")

        # De-activate the buttons except for Help...
        self.deactivate_buttons(["ThumbnailView"])

        if _MAGICK_FOUND:
            self.deactivate_buttons(["Convert"])

        if (_MAGICK_FOUND or _HEAD_FOUND): 
            self.deactivate_buttons(["Delete"])

    def __create_spinner(self, pos, adjustment, climb =True, wrap =True, numdigits =0):
        """
        Creates and returns the Date/ Time spinners...
        """

        if climb:
            spin_button = gtk.SpinButton(adjustment, climb_rate =0.0, digits =numdigits)
        else:
            spin_button = gtk.SpinButton(adjustment, climb_rate =1.0, digits =numdigits)

        spin_button.set_wrap(wrap)
        spin_button.set_numeric(True)
        spin_button.update()
        self.exif_widgets[pos] = spin_button

        return spin_button

    def EditArea(self, MediaDataTags):
        """
        displays the image Exif metadata in the Edit Area...
        """

        # if no Exif metadata, disable the has_data() functionality?
        if MediaDataTags:

            # update has_data() functionality...
            self.update_has_data()

            # activate Save button...
            self.activate_buttons(["Save"])

            # Activate Delete button if ImageMagick or jhead is found?...
            if (_MAGICK_FOUND or _JHEAD_FOUND):
                self.activate_buttons(["Delete"])

            for KeyTag in MediaDataTags:

                # name for matching to exif_widgets 
                widgetsName = _DATAMAP[KeyTag]

                tagValue = self._get_value(KeyTag)
                if tagValue:

                    if widgetsName in ["ExifLabel", "Description", "Artist", "Copyright"]:
                        self.exif_widgets[widgetsName].set_text(tagValue)

                    # Last Changed/ Modified...
                    elif widgetsName == "Modified":
                        use_date = self._get_value(_DATAMAP["Modified"])
                        use_date = _process_datetime(use_date) if use_date else False
                        if use_date:
                            self.exif_widgets["DateStamp"].set_text(
                                _("Last Changed: %s") % use_date)

                    # Original Creation Date/ Time...
                    elif widgetsName == "Original":
                        date1 = self._get_value(_DATAMAP["Original"])
                        date2 = self._get_value(_DATAMAP["Digitized"])
                        date3 = self.orig_image.get_date_object()
                        use_date = date1 or date3 or date3 or False
                        if use_date:
                            if isinstance(use_date, str):
                                use_date = _get_date_format(use_date)
                                if use_date:
                                    year, month, day, hour, minutes, seconds = use_date[0:6]

                            elif isinstance(use_date, datetime):
                                year, month, day = use_date.year, use_date.month, use_date.day
                                hour, minutes, seconds = use_date.hour, use_date.minute, use_date.second

                            else:
                                year = False
                            if year:

                                # update Date/ Time spin buttons...
                                self.update_spinners(year, month, day, hour, minutes, seconds)

                                use_date = False
                                if year < 1900:
                                    use_date = "%04d-%s-%02d %02d:%02d:%02d" % (
                                        year, _dd.long_months[month], day, hour, minutes, seconds)
                                else:
                                    try:
                                        use_date = datetime(year, month, day, hour, minutes, seconds)
                                    except ValueError:
                                        use_date = False 
                     
                    # LatitudeRef, Latitude, LongitudeRef, Longitude...
                    elif widgetsName == "Latitude":

                        latitude  =  self._get_value(KeyTag)
                        longitude = self._get_value(_DATAMAP["Longitude"])

                        # if latitude and longitude exist, display them?
                        if (latitude and longitude):

                            # split latitude metadata into (degrees, minutes, and seconds)
                            latdeg, latmin, latsec = rational_to_dms(latitude)

                            # split longitude metadata into degrees, minutes, and seconds
                            longdeg, longmin, longsec = rational_to_dms(longitude)

                            # check to see if we have valid GPS Coordinates?
                            latfail = any(coords == False for coords in [latdeg, latmin, latsec])
                            longfail = any(coords == False for coords in [longdeg, longmin, longsec])
                            if (not latfail and not longfail):

                                # Latitude Direction Reference
                                LatRef = self._get_value(_DATAMAP["LatitudeRef"] )

                                # Longitude Direction Reference
                                LongRef = self._get_value(_DATAMAP["LongitudeRef"] )

                                # set display for Latitude GPS Coordinates
                                self.exif_widgets["Latitude"].set_text(
                                    """%s° %s′ %s″ %s""" % (latdeg, latmin, latsec, LatRef) )

                                # set display for Longitude GPS Coordinates
                                self.exif_widgets["Longitude"].set_text(
                                    """%s° %s′ %s″ %s""" % (longdeg, longmin, longsec, LongRef) )

                    elif widgetsName == "Altitude":
                        altitude = self._get_value(_DATAMAP["Altitude"] )
                        AltRef = self._get_value(_DATAMAP["AltitudeRef"] )

                        if (altitude and AltRef):
                            altdeg, altmin, altsec = rational_to_dms(altitude)

                            altfail = any(coords == False for coords in [altdeg, altmin, altsec])
                            if not altfail:

                                # set display for Altitude GPS Coordinates
                                self.exif_widgets["Altitude"].set_text(
                                    """%s° %s′ %s″ %s""" % (altdeg, altmin, altsec, AltRef) )

        else:

            # set Message Area to None...
            self.exif_widgets["MessageArea"].set_text(_("There is NO Exif "
                "metadata for this image yet..."))

            for widgetsName in ["Description", "Artist", "Copyright", "Latitude",
                    "Longitude", "Altitude"]:

                # once the user types in that field,
                # the Edit, Clear, and Delete buttons will become active...
                self.exif_widgets[widgetsName].connect("changed", self.active_buttons)

                # once the user presses [Enter] in that field,
                # the Edit, Clear, and Delete buttons will become active...
                self.exif_widgets[widgetsName].connect("active", self.active_buttons)

    def _set_value(self, KeyTag, KeyValue):
        """
        sets the value for the metadata KeyTags
        """

        if LesserVersion:
            self.plugin_image[KeyTag] = KeyValue

        else:
            if "Exif" in KeyTag:
                try: # tag is being modified...
                    self.plugin_image[KeyTag].value = KeyValue

                except KeyError:  # tag is being created...
                    self.plugin_image[KeyTag] = pyexiv2.ExifTag(KeyTag, KeyValue)

                except (ValueError, AttributeError):  # there is an error
                                                      # with either KeyTag or KeyValue
                    pass

            elif "Xmp" in KeyTag:
                try:
                    self.plugin_image[KeyTag].value = KeyValue

                except KeyError:
                    self.plugin_image[KeyTag] = pyexiv2.XmpTag(KeyTag, KeyValue)

                except (ValueError, AttributeError):
                    pass

            else:
                try:
                    self.plugin_image[KeyTag].value = KeyValue

                except KeyError:
                    self.plugin_image[KeyTag] = pyexiv2.IptcTag(KeyTag, KeyValue)

                except (ValueError, AttributeError):
                    pass

    def write_metadata(self, plugininstance):
        """
        writes the Exif metadata to the image.

        LesserVersion -- prior to pyexiv2-0.2.0
                      -- pyexiv2-0.2.0 and above... 
        """
        if LesserVersion:
            plugininstance.writeMetadata()

        else:
            plugininstance.write()

# -------------------------------------------------------------------
#          GPS Coordinates functions
# -------------------------------------------------------------------
    def addsymbols2gps(self, latitude =False, longitude =False):
        """
        converts a degrees, minutes, seconds representation of Latitude/ Longitude
        without their symbols to having them...

        @param: latitude -- Latitude GPS Coordinates
        @param: longitude -- Longitude GPS Coordinates
        """
        LatitudeRef, LongitudeRef = "N", "E"

        # check to see if Latitude/ Longitude exits?
        if (latitude and longitude):

            if (latitude.count(".") == 1 and longitude.count(".") == 1):
                self.convert2dms(self.plugin_image)

                # get Latitude/ Longitude from data fields
                # after the conversion
                latitude  =  self.exif_widgets["Latitude"].get_text()
                longitude = self.exif_widgets["Longitude"].get_text()

            # add DMS symbols if necessary?
            # the conversion to decimal format, require the DMS symbols
            elif ( (latitude.count("°") == 0 and longitude.count("°") == 0) and
                (latitude.count("′") == 0 and longitude.count("′") == 0) and
                (latitude.count('″') == 0 and longitude.count('″') == 0) ):

                # is there a direction element here?
                if (latitude.count("N") == 1 or latitude.count("S") == 1):
                    latdeg, latmin, latsec, LatitudeRef = latitude.split(" ", 3)
                else:
                    atitudeRef = "N"
                    latdeg, latmin, latsec = latitude.split(" ", 2)
                    if latdeg[0] == "-":
                        latdeg = latdeg.replace("-", "")
                        LatitudeRef = "S"

                # is there a direction element here?
                if (longitude.count("E") == 1 or longitude.count("W") == 1):
                    longdeg, longmin, longsec, LongitudeRef = longitude.split(" ", 3)
                else:
                    ongitudeRef = "E"
                    longdeg, longmin, longsec = longitude.split(" ", 2)
                    if longdeg[0] == "-":
                        longdeg = longdeg.replace("-", "")
                        LongitudeRef = "W"

                latitude  = """%s° %s′ %s″ %s""" % (latdeg, latmin, latsec, LatitudeRef)
                longitude = """%s° %s′ %s″ %s""" % (longdeg, longmin, longsec, LongitudeRef)

        return latitude, longitude

    def convert2decimal(self, obj):
        """
        will convert a decimal GPS Coordinates into decimal format.

        @param: latitude  -- GPS Latitude Coordinates from data field...
        @param: longitude -- GPS Longitude Coordinates from data field...
        """

        # get Latitude/ Longitude from the data fields
        latitude  =  self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # if latitude and longitude exist?
        if (latitude and longitude):

            # is Latitude/ Longitude are in DMS format?
            if (latitude.count(" ") >= 2 and longitude.count(" ") >= 2): 

                # add DMS symbols if necessary?
                # the conversion to decimal format, require the DMS symbols 
                if ( (latitude.count("°") == 0 and longitude.count("°") == 0) and
                    (latitude.count("′") == 0 and longitude.count("′") == 0) and
                    (latitude.count('″') == 0 and longitude.count('″') == 0) ):

                    latitude, longitude = self.addsymbols2gps(latitude, longitude)

                # convert degrees, minutes, seconds w/ symbols to an 8 point decimal
                latitude, longitude = conv_lat_lon( unicode(latitude),
                                                    unicode(longitude), "D.D8")

                self.exif_widgets["Latitude"].set_text(latitude)
                self.exif_widgets["Longitude"].set_text(longitude)

    def convert2dms(self, obj):
        """
        will convert a decimal GPS Coordinates into degrees, minutes, seconds
        for display only
        """

        # get Latitude/ Longitude from the data fields
        latitude = self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # if Latitude/ Longitude exists?
        if (latitude and longitude):

            # if coordinates are in decimal format?
            if (latitude.count(".") == 1 and longitude.count(".") == 1):

                # convert latitude and longitude to a DMS with separator of ":"
                latitude, longitude = conv_lat_lon(latitude, longitude, "DEG-:")
 
                # remove negative symbol if there is one?
                LatitudeRef = "N"
                if latitude[0] == "-":
                    latitude = latitude.replace("-", "")
                    LatitudeRef = "S"
                latdeg, latmin, latsec = latitude.split(":", 2)

               # remove negative symbol if there is one?
                LongitudeRef = "E"
                if longitude[0] == "-":
                    longitude = longitude.replace("-", "")
                    LongitudeRef = "W"
                longdeg, longmin, longsec = longitude.split(":", 2)

                self.exif_widgets["Latitude"].set_text(
                    """%s° %s′ %s″ %s""" % (latdeg, latmin, latsec, LatitudeRef) )

                self.exif_widgets["Longitude"].set_text(
                    """%s° %s′ %s″ %s""" % (longdeg, longmin, longsec, LongitudeRef) )

    def destroy(self, widget):
        self.window.destroy()

    def save_metadata(self, object):
        """
        gets the information from the plugin data fields
        and sets the KeyTag = keyvalue image metadata
        """

        # determine if there has been something entered in the data fields?
        datatags = (
            len(self.exif_widgets["ExifLabel"].get_text() ) +
            len(self.exif_widgets["Description"].get_text() ) + 
            len(self.exif_widgets["Artist"].get_text() ) + 
            len(self.exif_widgets["Copyright"].get_text() ) +
            len(self.exif_widgets["Latitude"].get_text() ) + 
            len(self.exif_widgets["Longitude"].get_text() ) )

        # Exif Label/ Title
        exiflabel = self.exif_widgets["ExifLabel"].get_text()
        self._set_value(_DATAMAP["ExifLabel"], exiflabel)

        # Description data field...
        description = self.exif_widgets["Description"].get_text()
        self._set_value(_DATAMAP["Description"],  description)

        # Modify Date/ Time... not a data field, but saved anyway...
        modified = datetime.now()
        self._set_value(_DATAMAP["Modified"], modified)

        # display modified Date/ Time...
        self.exif_widgets["MessageArea"].set_text(_("Last Changed: %s") % _format_datetime(modified) )
 
        # Artist/ Author data field...
        artist = self.exif_widgets["Artist"].get_text()
        self._set_value(_DATAMAP["Artist"], artist)

        # Copyright data field...
        copyright = self.exif_widgets["Copyright"].get_text()
        self._set_value(_DATAMAP["Copyright"], copyright)

        # Original Date/ Time
        year    = self._get_spin_value("Year"),
        month   = self._get_spin_value("Month"),
        day     = self._get_spin_value("Day"),
        hour    = self._get_spin_value("Hour"),
        minutes = self._get_spin_value("Minutes"),
        seconds = self._get_spin_value("Seconds")
        print(year, month, day, hour, minutes, seconds)

        use_date = False
        if year < 1900:
            use_date = "%04d-%s-%02d %02d:%02d:%02d" % (year, _dd.long_months[month], day,
                                                        hour, minutes, seconds)
        else:
            use_date = datetime(year, month, day, hour, minutes, seconds)
        if use_date:
            self._set_value(_DATAMAP["Original"], use_date)

        # Latitude/ Longitude data fields
        latitude  =  self.exif_widgets["Latitude"].get_text()
        longitude = self.exif_widgets["Longitude"].get_text()

        # check to see if Latitude/ Longitude exists?
        if (latitude and longitude):

            # complete some error checking to prevent crashes...
            # if "?" character exist, remove it?
            if "?" in latitude:
                latitude = latitude.replace("?", "")
            if "?" in longitude:
                longitude = longitude.replace("?", "")

            # if "," character exists, remove it?
            if "," in latitude: 
                latitude = latitude.replace(",", "")
            if "," in longitude:
                longitude = longitude.replace(",", "") 

            # if it is in decimal format, convert it to DMS?
            # if not, then do nothing?
            self.convert2dms(self.plugin_image)

            # get Latitude/ Longitude from the data fields
            latitude  =  self.exif_widgets["Latitude"].get_text()
            longitude = self.exif_widgets["Longitude"].get_text()

            # will add (degrees, minutes, seconds) symbols if needed?
            # if not, do nothing...
            latitude, longitude = self.addsymbols2gps(latitude, longitude)

            # set up display
            self.exif_widgets["Latitude"].set_text(latitude)
            self.exif_widgets["Longitude"].set_text(longitude)

            LatitudeRef = " N"
            if "S" in latitude:
                LatitudeRef = " S"
            latitude = latitude.replace(LatitudeRef, "")
            LatitudeRef = LatitudeRef.replace(" ", "")

            LongitudeRef = " E"
            if "W" in longitude:
                LongitudeRef = " W"
            longitude = longitude.replace(LongitudeRef, "")
            LongitudeRef = LongitudeRef.replace(" ", "")

            # remove symbols for saving Latitude/ Longitude GPS Coordinates
            latitude, longitude = _removesymbols4saving(latitude, longitude) 

            # convert (degrees, minutes, seconds) to Rational for saving
            self._set_value(_DATAMAP["LatitudeRef"], LatitudeRef)
            self._set_value(_DATAMAP["Latitude"], coords_to_rational(latitude))

            # convert (degrees, minutes, seconds) to Rational for saving
            self._set_value(_DATAMAP["LongitudeRef"], LongitudeRef)
            self._set_value(_DATAMAP["Longitude"], coords_to_rational(longitude))

        if datatags:
            # set Message Area to Saved...
            self.exif_widgets["MessageArea"].set_text(_("Saving Exif metadata to this image..."))
        else:
            # set Message Area to Cleared...
            self.exif_widgets["MessageArea"].set_text(_("Image Exif metadata has been cleared "
                "from this image..."))

        # writes all Exif Metadata to image even if the fields are all empty...
        self.write_metadata(self.plugin_image)

    def strip_metadata(self):
        """
        Will completely and irrevocably erase all Exif metadata from this image.
        """

        # update the image Exif metadata...
        MediaDataTags = _get_exif_keypairs(self.plugin_image)
        if not MediaDataTags:
            return

        if _MAGICK_FOUND:
            erase = subprocess.check_call( ["convert", self.image_path, "-strip", self.image_path] )
            erase_results = str(erase)

        elif (_JHEAD_FOUND and self.extension in [".jpeg", ".jfif", ".jpg"]):
            erase = subprocess.check_call( ["jhead", "-purejpeg", self.image_path] )

        else:
            if MediaDataTags: 
                for KeyTag in MediaDataTags:
                    del self.plugin_image[KeyTag]
                erase_results = True

                # write wiped metadata to image...
                self.write_metadata(self.plugin_image)

        if erase_results:

            # set Message Area for deleting...
            self.exif_widgets["MessageArea"].set_text(_("Deleting all Exif metadata..."))

            # Clear the Edit Areas
            self.clear_display(self.plugin_image)

            # set Message Area to Delete...
            self.exif_widgets["MessageArea"].set_text(_("All Exif metadata has been "
                    "deleted from this image..."))

            self.update()

    def update_spinners(self, syear, smonth, day, hour, minutes, seconds):
        """
        update Date/ Time spinners.
        """

        # split the date/ time into its six pieces...
        datetimevalues = {  
            "Year"    : syear,
            "Month"   : smonth,
            "Day"     : day,
            "Hour"    : hour,
            "Minutes" : minutes,
            "Seconds" : seconds}.items()

        for widget, value in datetimevalues:

            # make sure that the amount of days for that year and month is not > than the number of days selected...
            if widget == "Day":
                numdays = [0] + [_mr(year, month)[1] for year in [syear] for month in range(1, 13) ]

                if value > numdays[smonth]:
                    value = numdays[smonth]

            # set the date/ time spin buttons...
            self.exif_widgets[widget].set_value(value)

    def _get_spin_value(self, pos):
        """
        will retrieve the spinner's value and format it as two digit integer...
        """

        value = self.exif_widgets[pos].get_value_as_int()

        if pos == "Day":
            syear  =  self._get_spin_value("Year")
            smonth = self._get_spin_value("Month")

            numdays = [0] + [_mr(year, month)[1] for year in [syear] for month in range(1, 13) ]

            if value > numdays[smonth]:
                value = numdays[smonth]
            elif value <= 0:
                value = 1

        return value

def _get_exif_keypairs(plugin_image):
    """
    Will be used to retrieve and update the Exif metadata from the image.
    """
    MediaDataTags = False

    if plugin_image:
        if LesserVersion:  # prior to pyexiv2-0.2.0
            # get all KeyTags for this image for diplay only...
            MediaDataTags = [KeyTag for KeyTag in chain(
                                plugin_image.exifKeys(), plugin_image.xmpKeys(),
                                plugin_image.iptcKeys() ) ]

        else:  # pyexiv2-0.2.0 and above
            # get all KeyTags for this image for diplay only...
            MediaDataTags = [KeyTag for KeyTag in chain(
                                plugin_image.exif_keys, plugin_image.xmp_keys,
                                plugin_image.iptc_keys) ]
    return MediaDataTags

def string_to_rational(coordinate):
    """
    convert string to rational variable for GPS
    """

    if '.' in coordinate:
        value1, value2 = coordinate.split('.')
        return pyexiv2.Rational(int(float(value1 + value2)), 10**len(value2))
    else:
        return pyexiv2.Rational(int(coordinate), 1)

def coords_to_rational(Coordinates):
    """
    returns the GPS coordinates to Latitude/ Longitude
    """

    return [string_to_rational(coordinate) for coordinate in Coordinates.split(" ")]

def convert_value(value):
    """
    will take a value from the coordinates and return its value
    """

    if isinstance(value, (Fraction, pyexiv2.Rational)):

        return str( ( Decimal(value.numerator) / Decimal(value.denominator) ) )

def _removesymbols4saving(latitude, longitude):
    """
    will recieve a DMS with symbols and return it without them

    @param: latitude -- Latitude GPS Coordinates
    @param: longitude -- GPS Longitude Coordinates
    """

    # check to see if latitude/ longitude exist?
    if (latitude and longitude):

        # remove degrees symbol if it exist?
        latitude = latitude.replace("°", "")
        longitude = longitude.replace("°", "")

        # remove minutes symbol if it exist?
        latitude = latitude.replace("′", "")
        longitude = longitude.replace("′", "")

        # remove seconds symbol if it exist?
        latitude = latitude.replace('″', "")
        longitude = longitude.replace('″', "")

    return latitude, longitude

def rational_to_dms(coords):
    """
    takes a rational set of coordinates and returns (degrees, minutes, seconds)

    [Fraction(40, 1), Fraction(0, 1), Fraction(1079, 20)]
    """

    deg, min, sec =     False, False, False
    # coordinates look like:
    #     [Rational(38, 1), Rational(38, 1), Rational(150, 50)]
    # or [Fraction(38, 1), Fraction(38, 1), Fraction(318, 100)]   
    if isinstance(coords, list):
    
        if len(coords) == 3:
            return [convert_value(coordinate) for coordinate in coords]

    return deg, min, sec

def _format_datetime(exif_date):
    """
    Convert a python datetime object into a string for display, using the
    standard Gramps date format.
    """

    if type(exif_date) is not datetime:
        return exif_date

    date_part = gen.lib.Date()
    date_part.set_yr_mon_day(exif_date.year, exif_date.month, exif_date.day)
    date_str = _dd.display(date_part)

    if exif_date.year < 1900:
        split_time = "%02d:%02d:%02d" % (exif_date.hour, exif_date.minute, exif_date.second)
        time_str = split_time.strftime('%H:%M:%S')
    else:
        time_str = exif_date.strftime('%H:%M:%S')

    return _('%(date)s %(time)s') % {'date': date_str, 'time': time_str}

def _get_date_format(datestr):
    """
    attempt to retrieve date format from date string
    """

    # attempt to determine the dateformat of the variable passed to it...
    tmpDate = False
    for dateformat in ["%Y-%m-%d %H:%M:%S", "%Y %m %d %H:%M:%S",
                       "%Y-%b-%d %H:%M:%S", "%Y %b %d %H:%M:%S",
                       "%Y-%B-%d %H:%M:%S", "%Y %B %d %H:%M:%S",
                       "%d-%m-%Y %H:%M:%S", "%d %m %Y %H:%M:%S",
                       "%d-%b-%Y %H:%M:%S", "%d %b %Y %H:%M:%S",
                       "%d-%B-%Y %H:%M:%S", "%d %B %Y %H:%M:%S",
                       "%m-%d-%Y %H:%M:%S", "%m %d %Y %H:%M:%S",
                       "%b-%d-%Y %H:%M:%S", "%b %d %Y %H:%M:%S",
                       "%B-%d-%Y %H:%M:%S", "%B %d %Y %H:%M:%S"]:

        # find date string format
        try:
            tmpDate = time.strptime(datestr, dateformat)
            break

        # datestring format  not found...
        except ValueError:
            pass

    return tmpDate

def _create_datetime(pyear, pmonth, day, hour, minutes, seconds):
    """
    will create and retrun a str or datetime from (
        year, month, day, hour, minutes, and seconds) ...

    if the year is less than 1900, then it will return a string representation...
    """

    # do some error trapping...
    if pmonth > 12:
        pmonth = 12
    elif pmonth <= 0:
        pmonth = 1

    if hour >= 24:
        hour = 23
    elif hour < 0:
        hour = 0

    if minutes > 59:
        minutes = 59
    elif minutes < 0:
        minutes = 0
 
    if seconds > 59:
        seconds = 59
    elif seconds < 0:
        seconds = 0

    # get the number of days in year for all months
    numdays = [0] + [_mr(year, month)[1] for year in [pyear] for month in range(1, 13) ]
    if day > numdays[pmonth]:
        day = numdays[pmonth]
    elif day <= 0:
        day = 1

    if pyear < 1900:
        try:
            tmpDate = "%04d-%02d-%02d %02d:%02d:%02d" % (pyear, pmonth, day, hour, minutes, seconds)
        except ValueError:
            tmpDate = False

    else:
        try:
            tmpDate = datetime(pyear, pmonth, day, hour, minutes, seconds)

        except ValueError:
            tmpDate = False

    if tmpDate is False:
        tmpDate = ""

    return tmpDate

def _process_datetime(tmpDate, exif_type =True):
    """
    will attempt to parse the date/ time Exif metadata entry into its pieces...
        (year, month, day, hour, minutes, seconds)
    """

    if not tmpDate:
        return False

    datetype = type(tmpDate)

    # if variable is already in datetime.datetime() format, return it?
    if datetype == datetime:
        pyear, pmonth, day = tmpDate.year, tmpDate.month, tmpDate.day
        hour, minutes, seconds = tmpDate.hour, tmpDate.minute, tmpDate.second        

    elif any(datetype == value for value in [date, gen.lib.date.Date, list] ):
        hour, minutes, seconds = time.localtime()[3:6]

        # datetime.date format
        if isinstance(tmpDate, date):
            pyear, pmonth, day = tmpDate.year, tmpDate.month, tmpDate.day

        # gen.lib.date.Date format
        elif isinstance(tmpDate, gen.lib.date.Date):
            pyear, pmonth, day = tmpDate.get_year(), tmpDate.get_month(), tmpDate.get_day()

        # list format
        else:
            pyear, pmonth, day = tmpDate[0].year, tmpDate[0].month, tmpDate[0].day

    #  string format...
    elif datetype == str:

        datestr = _get_date_format(tmpDate)
        if datestr is not False:
            pyear, pmonth, day, hour, minutes, seconds = datestr[0:6]

        else:
            pyear, pmonth, day, hour, minutes, seconds = [False]*6

    if (not pyear and not pmonth):
        tmpDate = False

    else:

        # create datetime...
        tmpDate = _create_datetime(pyear, pmonth, day, hour, minutes, seconds)

    if tmpDate is not False:

        if isinstance(tmpDate, datetime):

            # for display only...
            # make datetime displayed as user has set in preferences...
            if exif_type:
                tmpDate = _format_datetime(tmpDate)

    return tmpDate
