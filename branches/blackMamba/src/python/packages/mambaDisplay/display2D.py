"""
This module provides functions, classes and methods to display mamba images
using the Tkinter library.
"""

import constants
import mamba.core as core
import mamba.utils as utils
from mamba.error import *
from mamba.miscellaneous import downscale

try:
    import tkinter as tk
    import tkinter.ttk as ttk
except ImportError:
    try:
        import Tkinter as tk
        import ttk
    except ImportError:
        print("Missing Tkinter library")
        raise
try:
    from PIL import ImageTk
    from PIL import Image
except ImportError:
    print("Missing PIL library (pillow) - https://pypi.python.org/pypi/Pillow/")
    raise

###############################################################################
#  Utilities functions
#
# These functions do not perform computations but allow you to load, save or 
# convert mamba image structures easily. They also allow you to set the global
# variables used for computations.
# 
# Some of these functions are made public and some are restrained to this module
# use only (they are encapsulated into easier-to-use functions or methods).
    
    
def _copyFromClipboard(size=None):
    """
    Looks into the clipboard to see if an image is present and extract it if 
    this is the case.
    
    WARNING! Under Linux, this function uses pygtk and gtk ! The function may
    not work to your liking. Under Windows, it uses the ImageGrab module present
    with the PIL distribution.
    
    Returns a mamba image structure or None if no image was found.
    """
    import platform
        
    im = None

    if platform.system()=='Windows':
        # Under Windows
        from PIL import ImageGrab
        # The image is extracted from the clipboard.
        # !! There is a bug in PIL 1.1.6 with the clipboard:
        # !! it is not closed if there is no image in it
        # !! and thus this can have very bad effects on Windows
        # !! copy/paste operations.
        im_clipbd = ImageGrab.grabclipboard()
    
        if im_clipbd!=None:
            im = utils.loadFromPILFormat(im_clipbd, size=size)
    
    return im

###############################################################################
#  Classes
#
# This class is used to create windows for 2D image display.
# The class inherits Tkinter.Toplevel to do so.
# Functions are offered to update, retitle, show or hide the display.
class Display2D(tk.Toplevel):

    # Constructor ##############################################################
    def __init__(self, master, name):
    
        # Window creation
        tk.Toplevel.__init__(self,master)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas_vb = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.canvas_vb.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.canvas_hb = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        self.canvas_hb.grid(row=1, column=0, sticky=tk.E+tk.W)
        self.canvas = tk.Canvas(self,
                                bd=0,
                                xscrollcommand=self.canvas_hb.set,
                                yscrollcommand=self.canvas_vb.set)
        self.canvas_hb.config(command=self.canvas.xview)
        self.canvas_vb.config(command=self.canvas.yview)
        self.canvas.grid(row=0, column=0, sticky=tk.E+tk.W+tk.S+tk.N)
        self.createInfoBar()
        self.canvas_hb.grid_remove()
        self.canvas_vb.grid_remove()
        
        # Internal variables
        self.mbIm = None
        self.bplane = 4
        self.pal = None
        self.palactive = True
        self.frozen = False
        self.freezeids = []
        self.name = name
        self.imid = None
        self.mouse_x = 0
        self.mouse_y = 0
        self.std_geometry = ""
        
        # Context menu
        self.createContextMenu()
        
        # Events bindings
        self.canvas.bind("<Motion>", self.mouseMotionEvent)
        self.canvas.bind("<Configure>", self.resizeEvent)
        self.canvas.bind("<Button-3>", self.contextMenuEvent)
        self.canvas.bind("<Button-4>", self.mouseEvent)
        self.canvas.bind("<Button-5>", self.mouseEvent)
        self.bind("<MouseWheel>", self.mouseEvent)
        self.canvas.bind("<Button-1>", self.mouseEvent)
        self.canvas.bind("<ButtonRelease-1>", self.mouseEvent)
        self.bind("<KeyPress>", self.keyboardEvent)
        self.bind("<Control-v>", self.copyEvent)
        self.bind("<Control-f>", self.freezeEvent)
        self.bind("<Control-r>", self.restoreEvent)
        self.bind("<FocusIn>", self.focusEvent)
        
        # Upon creation, the image is automatically withdrawn.
        self.withdraw()
        
    # Sub-creation functions ###################################################
        
    def createContextMenu(self):
        # Creates the contextual menu.
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="save as..", command=self.saveImage)
        self.context_menu.add_command(label="load", command=self.loadImage)
        self.context_menu.add_command(label="paste..", 
                                      command=self.pasteFromClipBoard,
                                      state=tk.DISABLED)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="100%", command=self.resetZoom)
        self.context_menu.add_command(label="200%", command=self.doubleZoom)
        self.context_menu.add_separator()
        
    def createInfoBar(self):
        # Creates the info status bar.
        statusbar = ttk.Frame(self)
        statusbar.columnconfigure(0, weight=1)
        statusbar.columnconfigure(1, weight=1)
        statusbar.grid(row=2, column=0, columnspan=2, sticky=tk.E+tk.W)
        self.infos = []
        for i in range(3):
            v = tk.StringVar(self)
            ttk.Label(statusbar, anchor=tk.W, textvariable=v).grid(row=0, column=i, sticky=tk.E+tk.W)
            self.infos.append(v)
    
    # Events handling functions ################################################
    
    def focusEvent(self, event):
        # The window is activated.
        self.updateim()
        
    def resizeEvent(self, event):
        # Handles the resizing of the display window.
        self.csize = [event.width, event.height]
        self.drawImage()
        
        # For a zoom of only one, the scrollbar is removed.
        if self.dsize[0] <= self.csize[0]:
            self.canvas_hb.grid_remove()
        else:
            self.canvas_hb.grid()
        if self.dsize[1] <= self.csize[1]:
            self.canvas_vb.grid_remove()
        else:
            self.canvas_vb.grid()
        
    def mouseMotionEvent(self, event):
        # Indicates the position of the mouse inside the image.
        # Displays in the info bar the position inside the image along with the
        # pixel value.
        x = self.canvas.canvasx(event.x) - max((self.csize[0]-self.dsize[0])//2,0)
        y = self.canvas.canvasy(event.y) - max((self.csize[1]-self.dsize[1])//2,0)
        x = max(min(x,self.dsize[0]-1), 0)
        y = max(min(y,self.dsize[1]-1), 0)
        x = int((float(x)/self.dsize[0])*self.osize[0])
        y = int((float(y)/self.dsize[1])*self.osize[1])
        err, v = core.MB_GetPixel(self.mbIm, x, y)
        raiseExceptionOnError(err)
        v = str(v)
        self.infos[2].set("At ("+str(x)+","+str(y)+") = "+v)
        
        if event.state&0x0100==0x0100 :
            if not self.dsize[0] <= self.csize[0]:
                dx = event.x-self.mouse_x
                posx = self.canvas_hb.get()[0] - float(dx)/self.dsize[0]
                self.canvas.xview_moveto(posx)
            if not self.dsize[1] <= self.csize[1]:
                dy = event.y-self.mouse_y
                posy = self.canvas_vb.get()[0] - float(dy)/self.dsize[1]
                self.canvas.yview_moveto(posy)
            
        self.mouse_x = event.x
        self.mouse_y = event.y
    
    def mouseEvent(self, event):
        # Handles mouse events (except menu pop up)
        # Mainly zoom in or out using the mouse wheel, and moving the image
        if event.type=="4":
            if event.num==1:
                self.canvas.config(cursor="fleur")
            elif event.num==4:
                # Mouse wheel scroll up under linux
                # ZOOM IN
                if self.zoom<=0.25:
                    self.setZoom(self.zoom*2)
                else:
                    self.setZoom(self.zoom+0.25)
            elif event.num==5:
                # Mouse wheel scroll down under linux
                # ZOOM OUT
                if self.zoom<=0.25:
                    zoom = self.zoom/2
                    if not (int(self.zoom*self.osize[0])<10 or int(self.zoom*self.osize[0])<10):
                        self.setZoom(zoom)
                else:
                    self.setZoom(self.zoom-0.25)
            
        elif event.type=="5":
            if event.num==1:
                # Button 1 released
                self.canvas.config(cursor="arrow")
            
        elif event.type=="38":
            # Mouse wheel under windows
            if event.delta>0:
                # ZOOM IN
                for i in range(abs(event.delta)//120):
                    if self.zoom<=0.25:
                        self.setZoom(self.zoom*2)
                    else:
                        self.setZoom(self.zoom+0.25)
            else:
                # ZOOM OUT
                for i in range(abs(event.delta)//120):
                    if self.zoom<=0.25:
                        zoom = self.zoom/2
                        if not (int(self.zoom*self.osize[0])<10 or int(self.zoom*self.osize[0])<10):
                            self.setZoom(zoom)
                    else:
                        self.setZoom(self.zoom-0.25)

    def keyboardEvent(self, event):
        # Handles keyboard events,
        # such as zoom in (z) or out (a), activation of the color palette (p)
        # or restore original size (r).
        xo = max((self.csize[0]-self.dsize[0])/2, 0)
        yo = max((self.csize[1]-self.dsize[1])/2, 0)
        if event.char == "z":
            # ZOOM IN
            if self.zoom<=0.25:
                self.setZoom(self.zoom*2)
            else:
                self.setZoom(self.zoom+0.25)
        elif event.char == "a":
            # ZOOM OUT
            if self.zoom<=0.25:
                zoom = self.zoom/2
                if not (int(self.zoom*self.osize[0])<10 or int(self.zoom*self.osize[0])<10):
                    self.setZoom(zoom)
            else:
                self.setZoom(self.zoom-0.25)
        elif event.char == "p":
            # PALETTE ACTIVATION
            self.palactive = not self.palactive
            self.updateim()
        elif event.char == "b":
            # BYTE PLANE MODIFICATION (next)
            self.bplane = (self.bplane+1)%5
            self.updateim()
        elif event.char == "n":
            # BYTE PLANE MODIFICATION (previous)
            self.bplane = (self.bplane-1)%5
            self.updateim()
    
    def freezeEvent(self, event):
        # Freeze/Unfreeze event
        if self.frozen:
            self.unfreeze()
        else:
            self.freeze()
    
    def restoreEvent(self, event):
        # Restore original size event
        # The window size and parameter are reset.
        self.canvas_hb.grid_remove()
        self.canvas_vb.grid_remove()
        imsize = self.osize[:]
        self.zoom = 1.0
        while imsize[0]<constants._MINW or imsize[1]<constants._MINH:
            imsize[0] = imsize[0]*2
            imsize[1] = imsize[1]*2
            self.zoom = self.zoom*2
        while imsize[0]>constants._MAXW or imsize[1]>constants._MAXH:
            imsize[0] = imsize[0]/2
            imsize[1] = imsize[1]/2
            self.zoom = self.zoom/2
        self.csize = imsize[:]
        self.dsize = imsize[:]
        self.canvas.config(width=imsize[0],height=imsize[1],
                           scrollregion=(0,0,imsize[0]-1,imsize[1]-1))
        self.title((self.frozen and "Frozen - " or "") + self.name + 
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
        self.updateim()
        # Restoring the standard geometry.
        self.geometry(self.std_geometry)
        

    def copyEvent(self, event):
        # Handles copy shortcut event.
        # If an image is present into the clipboard we get it. 
        self._im_to_paste = _copyFromClipboard(size=self.osize)
        if self._im_to_paste and self.mbIm.depth==8:
            self.pasteFromClipBoard()
                             
    def contextMenuEvent(self, event):
        # Draws a contextual menu on a mouse right click.
        # If an image is present into the clipboard,
        # we get it. 
        self._im_to_paste = _copyFromClipboard(size=self.osize)
        
        # If an image was retrieved from the clipboard and the image is not a
        # 32-bit image, the paste menu is enabled.
        if self._im_to_paste and self.mbIm.depth==8:
            self.context_menu.entryconfigure(2, state=tk.ACTIVE)
        else:
            self.context_menu.entryconfigure (2, state=tk.DISABLED)
        
        self.context_menu.post(event.x_root, event.y_root)
        
    # Contextual Menu functions ################################################
    def resetZoom(self):
        self.setZoom(1.0)
    def doubleZoom(self):
        self.setZoom(2.0)
    def loadImage(self):
        # Loads the image from the selected file.
        # The name associated with the image will not be changed.
        import tkFileDialog
        f_name = tkFileDialog.askopenfilename()
        if f_name:
            im = utils.load(f_name, size=(self.mbIm.width,self.mbIm.height))
            if self.mbIm.depth==1:
                err = core.MB_Convert(im, self.mbIm)
                raiseExceptionOnError(err)
            elif self.mbIm.depth==8:
                err = core.MB_Copy(im, self.mbIm)
                raiseExceptionOnError(err)
            else:
                err = core.MB_CopyBytePlane(im, self.mbIm, 0)
                raiseExceptionOnError(err)
            self.updateim()
    def saveImage(self):
        # Saves the image into the selected file.
        import tkFileDialog
        filetypes=[("JPEG", "*.jpg"),("PNG", "*.png"),("BMP", "*.bmp"),("all files","*")]
        f_name = tkFileDialog.asksaveasfilename(defaultextension='.jpg', filetypes=filetypes)
        if f_name:
            utils.save(self.mbIm, f_name, self.palactive and self.pal)
    def pasteFromClipBoard(self):
        # Pastes the image obtained in the clipboard.
        err = core.MB_Copy(self._im_to_paste, self.mbIm)
        raiseExceptionOnError(err)
        self.title((self.frozen and "Frozen - " or "") + self.name + 
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
        self.updateim()
        del(self._im_to_paste)
        self._im_to_paste = None
        
    # Helper functions #########################################################
    
    def setZoom(self, zoom):
        # Sets the zoom value and changes the display accordingly.
        oz = self.zoom
        self.zoom = zoom
        self.dsize[0] = int(self.zoom*self.osize[0])
        self.dsize[1] = int(self.zoom*self.osize[1])
        self.canvas.config(scrollregion=(0,0,self.dsize[0]-1,self.dsize[1]-1))
        self.drawImage()
        self.title((self.frozen and "Frozen - " or "") + self.name + 
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
        
        # For a zoom of only one, the scrollbar is removed.
        if self.dsize[0] <= self.csize[0]:
            self.canvas_hb.grid_remove()
        else:
            self.canvas_hb.grid()
        if self.dsize[1] <= self.csize[1]:
            self.canvas_vb.grid_remove()
        else:
            self.canvas_vb.grid()
        
    def drawImage(self):
        # Draws the image inside the canvas.
        self.tkpi = ImageTk.PhotoImage(self.pilImage.resize(self.dsize, Image.NEAREST))
        if self.imid:
            self.canvas.delete(self.imid)
        self.imid = self.canvas.create_image(max((self.csize[0]-self.dsize[0])//2, 0),
                                             max((self.csize[1]-self.dsize[1])//2, 0),
                                             anchor=tk.NW,
                                             image=self.tkpi)
        
    # Public interface functions ###############################################
    
    def freeze(self):
        # freezes the display so that update has no effect
        self.frozen = True
        self.title((self.frozen and "Frozen - " or "") + self.name +
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
    
    def unfreeze(self):
        # Unfreezes the display
        self.frozen = False
        self.title((self.frozen and "Frozen - " or "") + self.name +
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
        self.updateim()
        
    def updateim(self):
        # Updates the display with the new contents of the mamba image.
        if self.mbIm and self.state()=="normal" and not self.frozen:
            if self.mbIm.depth==32:
                mbIm = utils.create(self.mbIm.width, self.mbIm.height, 8)
                if self.bplane==4:
                    wmbIm = utils.create(self.mbIm.width, self.mbIm.height, 32)
                    err, mi, ma = core.MB_Range(self.mbIm)
                    raiseExceptionOnError(err)
                    err = core.MB_ConSub(self.mbIm,mi,wmbIm)
                    raiseExceptionOnError(err)
                    err = core.MB_ConMul(wmbIm,255,wmbIm)
                    raiseExceptionOnError(err)
                    err = core.MB_ConDiv(wmbIm,ma-mi,wmbIm)
                    raiseExceptionOnError(err)
                    err = core.MB_CopyBytePlane(wmbIm,mbIm,0)
                    raiseExceptionOnError(err)
                    del(wmbIm)
                    self.infos[1].set("plane : all")
                else:
                    err = core.MB_CopyBytePlane(self.mbIm,mbIm,self.bplane)
                    raiseExceptionOnError(err)
                    self.infos[1].set("plane : %d" % (self.bplane))
                self.pilImage = utils.convertToPILFormat(mbIm, self.palactive and self.pal)
                del(mbIm)
            else:
                self.infos[1].set("")
                self.pilImage = utils.convertToPILFormat(self.mbIm, self.palactive and self.pal)
            err, volume = core.MB_Volume(self.mbIm)
            self.infos[0].set("volume : "+str(volume))
            self.icon = ImageTk.PhotoImage(self.pilImage.resize(self.icon_size, Image.NEAREST))
            self.tk.call('wm','iconphoto', self._w, self.icon)
            self.drawImage()
        
    def connect(self, im, pal):
        # "Connects" the window to a mamba image.
        
        self.pal = pal
        self.palactive = True
        # Size of the image, canvas and display
        self.osize = [im.width, im.height]
        imsize = self.osize[:]
        self.zoom = 1.0
        while imsize[0]<constants._MINW or imsize[1]<constants._MINH:
            imsize[0] = imsize[0]*2
            imsize[1] = imsize[1]*2
            self.zoom = self.zoom*2
        while imsize[0]>constants._MAXW or imsize[1]>constants._MAXH:
            imsize[0] = imsize[0]/2
            imsize[1] = imsize[1]/2
            self.zoom = self.zoom/2
        self.csize = imsize[:]
        self.dsize = imsize[:]
        self.canvas.config(width=imsize[0],height=imsize[1],
                           scrollregion=(0,0,imsize[0]-1,imsize[1]-1))
        
        # PIL image and icon
        m = max(self.osize)
        self.icon_size = ((constants._icon_max_size*self.osize[0])//m,(constants._icon_max_size*self.osize[1])//m)
        
        # Adding size info to menu.
        size_info = str(self.osize[0]) + " x " + str(self.osize[1])
        self.context_menu.add_command(label=size_info)
        
        self.mbIm = im
        self.pal = pal
        self.title((self.frozen and "Frozen - " or "") + self.name + 
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
        self.updateim()
        
    def colorize(self, pal, opa):
        # Changes the color palette associated with the window.
        self.pal = pal
        self.palactive = True
        self.updateim()
        
    def retitle(self, name):
        # Changes the title of the window.
        self.name = name
        self.title((self.frozen and "Frozen - " or "") + self.name + 
                   " - " + str(self.mbIm.depth) + 
                   " - [" + str(int(self.zoom*100)) + "%]")
        self.updateim()
            
    def show(self):
        # Shows the display (enabling update).
        if self.state()!="normal":
            self.deiconify()
            self.updateim()
            
    def hide(self):
        # Hides the display.
        self.withdraw()
