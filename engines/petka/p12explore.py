#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# romiq.kh@gmail.com, 2014

import sys, os
import tkinter
from tkinter import ttk, font
from idlelib.WidgetRedirector import WidgetRedirector
import traceback

try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

import petka

APPNAME = "P1&2 Explorer"

def hlesc(value):
    return value.replace("\\", "\\\\").replace("<", "\\<").replace(">", "\\>")

# thanx to http://effbot.org/zone/tkinter-text-hyperlink.htm
class HyperlinkManager:
    def __init__(self, text):
        self.text = text
        self.text.tag_config("hyper", foreground = "blue", underline = 1)
        self.text.tag_bind("hyper", "<Enter>", self._enter)
        self.text.tag_bind("hyper", "<Leave>", self._leave)
        self.text.tag_bind("hyper", "<Button-1>", self._click)
        bold_font = font.Font(text, self.text.cget("font"))
        bold_font.configure(weight = "bold")
        self.text.tag_config("bold", font = bold_font)
        italic_font = font.Font(text, self.text.cget("font"))
        italic_font.configure(slant = "italic")
        self.text.tag_config("italic", font = italic_font)
        underline_font = font.Font(text, self.text.cget("font"))
        underline_font.configure(underline = 1)
        self.text.tag_config("underline", font = underline_font)
        self.reset()

    def reset(self):
    	self.links = {}

    def add(self, action):
        # add an action to the manager.  returns tags to use in
        # associated text widget
        tag = "hyper-{}".format(len(self.links))
        self.links[tag] = action
        return "hyper", tag

    def _enter(self, event):
        self.text.config(cursor = "hand2")

    def _leave(self, event):
        self.text.config(cursor = "")

    def _click(self, event):
        for tag in self.text.tag_names(tkinter.CURRENT):
            if tag[:6] == "hyper-":
                self.links[tag]()
                return
		
		
# thanx http://tkinter.unpythonic.net/wiki/ReadOnlyText
class ReadOnlyText(tkinter.Text):
    def __init__(self, *args, **kwargs):
        tkinter.Text.__init__(self, *args, **kwargs)
        self.redirector = WidgetRedirector(self)
        self.insert = \
            self.redirector.register("insert", lambda *args, **kw: "break")
        self.delete = \
            self.redirector.register("delete", lambda *args, **kw: "break")
		
class App(tkinter.Frame):
    def __init__(self, master):
        tkinter.Frame.__init__(self, master)
        master.title(APPNAME)
        self.pack(fill = tkinter.BOTH, expand = 1)
        self.pad = None
        self.sim = None
        # gui
        self.path_handler = {}
        self.curr_main = -1 # 0 - frame, 1 - canvas
        self.curr_path = []
        self.last_path = [None]
        self.curr_mode = 0
        self.curr_mode_sub = None
        self.curr_gui = []
        self.curr_lb_acts = None
        # canvas
        self.need_update = False
        self.canv_view_fact = 1
        self.main_image = tkinter.PhotoImage(width = 1, height = 1)
        self.after_idle(self.on_first_display)
        
    def create_widgets(self):
        
        ttk.Style().configure("Tool.TButton", width = -1) # minimal width
        ttk.Style().configure("TLabel", padding = self.pad)
        ttk.Style().configure('Info.TFrame', background = 'white', \
            foreground = "black")
        
        # main paned
        self.pan_main = ttk.PanedWindow(self, orient = tkinter.HORIZONTAL)
        self.pan_main.pack(fill = tkinter.BOTH, expand = 1)
        
        # leftpanel
        self.frm_left = ttk.Frame(self.pan_main)
        self.pan_main.add(self.frm_left)
        # main view
        self.frm_view = ttk.Frame(self.pan_main)
        self.pan_main.add(self.frm_view)
        self.frm_view.grid_rowconfigure(0, weight = 1)
        self.frm_view.grid_columnconfigure(0, weight = 1)
        self.scr_view_x = ttk.Scrollbar(self.frm_view, 
            orient = tkinter.HORIZONTAL)
        self.scr_view_x.grid(row = 1, column = 0, \
            sticky = tkinter.E + tkinter.W)
        self.scr_view_y = ttk.Scrollbar(self.frm_view)
        self.scr_view_y.grid(row = 0, column = 1, sticky = \
            tkinter.N + tkinter.S)
        # canvas
        self.canv_view = tkinter.Canvas(self.frm_view, height = 150, 
            bd = 0, highlightthickness = 0, 
            scrollregion = (0, 0, 50, 50),
            )
        # don't forget
        #   canvas.config(scrollregion=(left, top, right, bottom))
        self.canv_view.bind('<Configure>', self.on_resize_view)
        self.canv_view.bind('<ButtonPress-1>', self.on_mouse_view)
        
        # text
        self.text_view = ReadOnlyText(self.frm_view,
            highlightthickness = 0,
            )
        self.text_hl = HyperlinkManager(self.text_view)
        self.text_view.bind('<Configure>', self.on_resize_view)
        
        # bind path handlers
        self.path_handler["parts"] = self.path_parts
        self.path_handler["res"] = self.path_res
        self.path_handler["objs"] = self.path_objs_scenes
        self.path_handler["scenes"] = self.path_objs_scenes
        self.path_handler["names"] = self.path_names
        self.path_handler["invntr"] = self.path_invntr
        self.path_handler["test"] = self.path_test
        
        self.update_after()
        self.open_path("")
        #self.open_path(self.find_path_scene(36))
        #self.open_path(["res", "flt", "BMP", 7])

    def create_menu(self):
        self.menubar = tkinter.Menu(self.master)
        self.master.configure(menu = self.menubar)

        self.menufile = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menufile,
                label = "File")
        self.menufile.add_command(
                command = self.on_open_data,
                label = "Open data...")
        self.menufile.add_separator()
        self.menufile.add_command(
                command = self.on_exit,
                label = "Quit")    

        self.menuedit = tkinter.Menu(self.master, tearoff = 0)
        self.menubar.add_cascade(menu = self.menuedit,
                label = "Edit")
        self.menuedit.add_command(
                command = lambda: self.open_path([]),
                label = "Outline")
        self.menuedit.add_separator()
        self.menuedit.add_command(
                command = lambda: self.open_path(["parts"]),
                label = "Select part")
        self.menuedit.add_separator()
        self.menuedit.add_command(
                command = lambda: self.open_path(["res"]),
                label = "Resources")
        self.menuedit.add_command(
                command = lambda: self.open_path(["objs"]),
                label = "Objects")
        self.menuedit.add_command(
                command = lambda: self.open_path(["scenes"]),
                label = "Scenes")
        self.menuedit.add_command(
                command = lambda: self.open_path(["names"]),
                label = "Names")
        self.menuedit.add_command(
                command = lambda: self.open_path(["invntr"]),
                label = "Invntr")

    def update_after(self):
        if not self.need_update:
            self.after_idle(self.on_idle)
            self.need_update = True

    def on_idle(self):
        self.need_update = False
        self.update_canvas()

    def on_first_display(self):
        fnt = font.Font()
        try:
            self.pad = fnt.measure(":")
        except:
            self.pad = 5
        self.create_widgets()
        self.create_menu()

    def on_exit(self):
        self.master.destroy()

    def on_mouse_view(self, event):
        self.update_after()
        
    def on_resize_view(self, event):
        self.update_after()
 
    def open_path(self, loc):
        if isinstance(loc, str):
            path = []
            if loc[:1] == "/":
                loc = loc[1:]
            if loc != "":
                for item in loc.split("/"):
                    try:
                        path.append(int(item, 10))
                    except:
                        path.append(item)
        else:
            path = loc
        path = tuple(path)
        print("DEBUG: Open", path)
        self.curr_path = path
        if len(path) > 0:
            if path[0] in self.path_handler:
                return self.path_handler[path[0]](path)
        return self.path_default(path)

    def update_canvas(self):
        if self.curr_main == 0:          
            return
        # draw grahics
        c = self.canv_view
        c.delete(tkinter.ALL)
        if self.sim is None: return

        w = self.canv_view.winfo_width() 
        h = self.canv_view.winfo_height()
        if (w == 0) or (h == 0): 
            return
        
        scale = 0

        # Preview image
        if not isinstance(self.main_image, tkinter.PhotoImage):
            mw, mh = self.main_image.size
            if scale == 0: # Fit
                try:
                    psc = w / h
                    isc = mw / mh
                    if psc < isc:
                        fact = w / mw
                    else:
                        fact = h / mh
                except:
                    fact = 1.0
            else:
                fact = scale
            pw = int(mw * fact)
            ph = int(mh * fact)
            img = self.main_image.resize((pw, ph), Image.ANTIALIAS)
            self.canv_image = ImageTk.PhotoImage(img)
        else:
            mw = self.main_image.width()
            mh = self.main_image.height()
            if scale == 0: # Fit
                try:
                    psc = w / h
                    isc = mw / mh
                    if psc < isc:
                        if w > mw:
                            fact = w // mw
                        else:
                            fact = -mw // w
                    else:
                        if h > mh:
                            fact = h // mh
                        else:
                            fact = -mh // h
                except:
                    fact = 1
            else:
                fact = scale
            self.canv_image = self.main_image.copy()
            if fact > 0:
                self.canv_image = self.canv_image.zoom(fact)
            else:
                self.canv_image = self.canv_image.subsample(-fact)
            self.canv_image_fact = fact

            # place on canvas
            if fact > 0:
                pw = mw * fact
                ph = mh * fact
            else:
                pw = mw // -fact
                ph = mh // -fact

        cw = max(pw, w)
        ch = max(ph, h)
        c.config(scrollregion = (0, 0, cw - 2, ch - 2))
        #print("Place c %d %d, p %d %d" % (cw, ch, w, h))
        c.create_image(cw // 2, ch // 2, image = self.canv_image)
       
    def make_image(self, imgobj):
        if imgobj.image is not None:
            return imgobj.image
        width = imgobj.width
        height = imgobj.height
        data = imgobj.rgb
        # create P6
        phdr = ("P6\n{} {}\n255\n".format(width, height))
        rawlen = width * height * 3 # RGB
        #phdr = ("P5\n{} {}\n255\n".format(width, height))
        #rawlen = width * height
        phdr = phdr.encode("UTF-8")

        if len(data) > rawlen:
            # truncate
            pdata = data[:rawlen]
        if len(data) < rawlen:
            # fill gap
            gap = bytearray()
            data += b"\xff" * (rawlen - len(data))
        p = bytearray(phdr)
        # fix UTF-8 issue
        for ch in data:
            if ch > 0x7f:
                p += bytes((0b11000000 |\
                    ch >> 6, 0b10000000 |\
                    (ch & 0b00111111)))               
            else:
                p += bytes((ch,))
        image = tkinter.PhotoImage(width = width, height = height, \
            data = bytes(p))
        return image                
   
    def update_gui(self, text = "<Undefined>"):
        self.last_path = self.curr_path
        # cleanup
        for item in self.curr_gui:
            item()
        self.curr_gui = []
        # left listbox
        lab = tkinter.Label(self.frm_left, text = text)
        lab.pack()
        frm_lb = ttk.Frame(self.frm_left)
        frm_lb.pack(fill = tkinter.BOTH, expand = 1)
        frm_lb.grid_rowconfigure(0, weight = 1)
        frm_lb.grid_columnconfigure(0, weight = 1)
        scr_lb_x = ttk.Scrollbar(frm_lb, orient = tkinter.HORIZONTAL)
        scr_lb_x.grid(row = 1, column = 0, sticky = tkinter.E + tkinter.W)
        scr_lb_y = ttk.Scrollbar(frm_lb)
        scr_lb_y.grid(row = 0, column = 1, sticky = tkinter.N + tkinter.S)
        lb = tkinter.Listbox(frm_lb,
            xscrollcommand = scr_lb_x.set,
            yscrollcommand = scr_lb_y.set)
        lb.grid(row = 0, column = 0, \
            sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
        scr_lb_x.config(command = lb.xview)
        scr_lb_y.config(command = lb.yview)
        self.curr_gui.append(lambda:lb.grid_remove())
        self.curr_gui.append(lambda:lab.pack_forget())
        self.curr_gui.append(lambda:frm_lb.pack_forget())
        lb.bind("<Double-Button-1>", self.on_left_listbox)
        lb.bind("<Return>", self.on_left_listbox)
        # actions on listbox
        self.curr_lb = lb
        self.curr_lb_acts = []

    def switch_view(self, main):
        # main view
        if main == self.curr_main: return
        self.curr_main = main
        if main == 0:
            self.canv_view.delete(tkinter.ALL)
            self.canv_view.grid_forget()
            self.text_view.grid(row = 0, column = 0, \
                sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
            self.text_view.configure(
                xscrollcommand = self.scr_view_x.set,
                yscrollcommand = self.scr_view_y.set
            )
            self.scr_view_x.config(command = self.text_view.xview)
            self.scr_view_y.config(command = self.text_view.yview)
        else:
            self.canv_view.delete(tkinter.ALL)
            self.text_view.grid_forget()
            self.canv_view.grid(row = 0, column = 0, \
                sticky = tkinter.N + tkinter.S + tkinter.E + tkinter.W)
            self.canv_view.configure(
                xscrollcommand = self.scr_view_x.set,
                yscrollcommand = self.scr_view_y.set
            )
            self.scr_view_x.config(command = self.canv_view.xview)
            self.scr_view_y.config(command = self.canv_view.yview)

    def clear_info(self):
        self.text_view.delete(0.0, tkinter.END)

    def add_info(self, text):
        mode = 0 # 0 - normal, 1 - tag
        curr_tag = None
        curr_text = ""
        tags = []
        esc = False
        for ch in text:
            if mode == 0:
                if esc:
                    curr_text += ch
                    esc = False
                else:
                    if ch == "\\":
                        esc = True
                    elif ch == "<":
                        mode = 1
                        curr_tag = ""
                    else:
                        curr_text += ch
            else:
                if ch == ">":
                    if len(curr_text) > 0:                    
                        self.text_view.insert(tkinter.INSERT, curr_text, \
                            tuple([x for x in tags for x in x]))
                    if curr_tag[:7] == "a href=":
                        ref = curr_tag[7:]
                        if ref[:1] == "\"":
                            ref = ref[1:]
                        if ref[-1:] == "\"":
                            ref = ref[:-1]
                        def make_cb(path):
                            def cb():
                                return self.open_path(path)
                            return cb
                        tags.append(self.text_hl.add(make_cb(ref)))
                    elif curr_tag == "b":
                        tags.append(["bold"])
                    elif curr_tag == "i":
                        tags.append(["italic"])
                    elif curr_tag == "u":
                        tags.append(["underline"])
                    elif curr_tag[:1] == "/":
                        tags = tags[:-1]
                    curr_text = ""
                    mode = 0
                else:
                    curr_tag += ch
        if len(curr_text) > 0:                    
            self.text_view.insert(tkinter.INSERT, curr_text, \
                tuple([x for x in tags for x in x]))
        
    def insert_lb_act(self, name, act):
        self.curr_lb_acts.append((name, act))
        self.curr_lb.insert(tkinter.END, name)

    def select_lb_item(self, idx):
        idx = "{}".format(idx)
        need = True
        for sel in self.curr_lb.curselection():
            if sel == idx:
                need = False
            else:
                self.curr_lb.selection_clear(sel)
        if need:
            self.curr_lb.selection_set(idx)
        self.curr_lb.see(idx)
            
    def on_left_listbox(self, event):
        def currsel():
            try:
                num = self.curr_lb.curselection()[0]
                num = int(num)
            except:
                pass
            return num

        if self.curr_lb_acts:
            act = self.curr_lb_acts[currsel()]
            if act[1] is not None:
                self.open_path(act[1])

    def find_path_res(self, res):
        for idx, res_id in enumerate(self.sim.resord):
            if res_id == res:
                return "/res/all/{}".format(idx)
        return "/no_res/{}".format(res)

    def find_path_obj(self, obj_idx):
        for idx, rec in enumerate(self.sim.objects):
            if rec.idx == obj_idx:
                return "/objs/{}".format(idx)
        return "/no_obj/{}".format(obj_idx)

    def find_path_scene(self, scn_idx):
        for idx, rec in enumerate(self.sim.scenes):
            if rec.idx == scn_idx:
                return "/scenes/{}".format(idx)
        return "/no_scene/{}".format(scn_idx)

    def find_path_obj_scene(self, rec_idx):
        for idx, rec in enumerate(self.sim.objects):
            if rec.idx == rec_idx:
                return "/objs/{}".format(idx)
        for idx, rec in enumerate(self.sim.scenes):
            if rec.idx == rec_idx:
                return "/scenes/{}".format(idx)
        return "/no_obj_scene/{}".format(rec_idx)
        
    def find_path_name(self, key):
        for idx, name in enumerate(self.sim.namesord):
            if name == key:
                return "/names/{}".format(idx)
        return "/no_name/{}".format(key)

    def find_path_invntr(self, key):
        for idx, name in enumerate(self.sim.invntrord):
            if name == key:
                return "/invntr/{}".format(idx)
        return "/no_invntr/{}".format(key)

    def path_info_outline(self):
        self.add_info("Current part {} chapter {}\n\n".\
                format(self.sim.curr_part, self.sim.curr_chap))
        self.add_info("  Resources: <a href=\"/res\">{}</a>\n".\
            format(len(self.sim.res)))
        self.add_info("  Objects:   <a href=\"/objs\">{}</a>\n".\
            format(len(self.sim.objects)))
        self.add_info("  Scenes:    <a href=\"/scenes\">{}</a>\n".\
            format(len(self.sim.scenes)))
        self.add_info("  Names:     <a href=\"/names\">{}</a>\n".\
            format(len(self.sim.names)))
        self.add_info("  Invntr:    <a href=\"/invntr\">{}</a>\n".\
            format(len(self.sim.invntr)))
    

    def path_default(self, path):
        self.switch_view(0)
        self.update_gui("Outline")
        self.clear_info()
        if len(path) != 0:
            spath = ""
            for item in path:
                spath += "/" + str(item)
            self.add_info("Path {} not found\n\n".format(spath))
        self.add_info("Select from <b>outline</b>\n\n")
        self.path_info_outline()
        if self.sim is not None:
            acts = [
                ("Parts ({})".format(len(self.sim.parts)), ["parts"]),
                ("Resources ({})".format(len(self.sim.res)), ["res"]),
                ("Objects ({})".format(len(self.sim.objects)), ["objs"]),
                ("Scenes ({})".format(len(self.sim.scenes)), ["scenes"]),
                ("Names ({})".format(len(self.sim.names)), ["names"]),
                ("Invntr ({})".format(len(self.sim.invntr)), ["invntr"]),
                ("-", None),
                ("Test image", ["test", "image"]),
                ("Test info", ["test","info"]),
            ]
            for name, act in acts:
                self.insert_lb_act(name, act)

    def path_parts(self, path):
        self.switch_view(0)
        if self.last_path[:1] != ("parts",):
            self.update_gui("Parts ({})".format(len(self.sim.parts)))
            for idx, name in enumerate(self.sim.parts):
                self.insert_lb_act(name, ["parts", idx])
        # change                
        if len(path) > 1:
            # parts
            self.select_lb_item(path[1])
            part_id = self.sim.parts[path[1]]
            # parse
            pnum = part_id[5:]
            cnum = pnum.split("Chapter", 1)
            if len(cnum) > 1:
                pnum = int(cnum[0].strip(), 10)
                cnum = int(cnum[1].strip(), 10)
            else:
                cnum = 0
            self.sim.open_part(pnum, cnum)
        # display
        self.clear_info()
        self.add_info("Select <b>part</b>\n\n")
        self.path_info_outline()

    def path_res(self, path):
        # res - full list
        # res/flt/<ext> - list by <ext>
        # res/all/<id> - display res by id
        if path == ("res",):
            path = ("res", "all")
        if path[1] == "flt":
            return self.path_res_flt(path)
        elif path[1] == "all":
            return self.path_res_all(path)
        else:
            return self.path_default(path)
                        
        if self.last_path[:2] != path[:2]:
            # 
            self.switch_view(0)
            self.update_gui("Resources: {}".format(path[2]))
            for idx,res_id in self.sim.resord:
                if self.sim.res[res_id].upper().endswith("." + path[2]):
                    self.insert_lb_act("{} - {}".format(res_id))
        
        if len(self.last_path) == 0 or self.last_path[0] != "res":
            for idx, name in enumerate(self.sim.invntrord):
                self.insert_lb_act(name, ["invntr", idx])

        # list resources
        if self.curr_mode_sub is None:
            lb = self.update_gui_add_left_listbox("Resources") 
            for res_id in self.sim.resord:
                lb.insert(tkinter.END, "{} - {}".format(res_id, \
                    self.sim.res[res_id]))
        else:
            lb = self.update_gui_add_left_listbox("Resources: {}".\
                format(self.curr_mode_sub))
            for res_id in self.sim.resord:
                if self.sim.res[res_id].upper().endswith\
                    ("." + self.curr_mode_sub):
                    lb.insert(tkinter.END, "{} - {}".format(res_id, \
                        self.sim.res[res_id]))

    def path_res_open(self, res_id, mode):
        if len(mode) == 0:
            self.switch_view(0)
            fn = self.sim.res[res_id]
            self.clear_info()
            self.add_info("<b>Resource</b>: {} (0x{:X}) - \"{}\"\n\n".\
                format(res_id, res_id, hlesc(fn)))
            resref = self.find_path_res(res_id)
            self.add_info("<a href=\"{}/view\">View</a> "\
                "<a href=\"{}/used\">Used by</a>\n\n".\
                format(resref, resref))
            try:
                if fn[-4:].lower() == ".bmp":
                    self.add_info("<b>BMP image</b>: ")
                    bmpf = self.sim.fman.read_file_stream(fn)
                    bmp = petka.BMPLoader()
                    bmp.load_info(bmpf)
                    if bmp.image:
                        # PIL
                        self.add_info("Python Imaging\n")
                        self.add_info("  Mode: {}\n  Size: {}x{}".\
                            format(bmp.image.mode, \
                                bmp.image.size[0], bmp.image.size[1]))
                    else:    
                        self.add_info("internal BMP loader\n  "\
                            "Mode: 16-bit\n  Size: {}x{}".\
                            format(bmp.width, bmp.height))
                if fn[-4:].lower() == ".flc":
                    self.add_info("<b>FLC animation</b>: ")
                else:
                    self.add_info("No information availiable")
            except:
                self.add_info("Error loading {} - \"{}\" \n\n{}".\
                    format(res_id, hlesc(fn), hlesc(traceback.format_exc())))
                    
        elif mode[0] == "view":
            self.path_res_view(res_id)
        elif mode[0] == "used":
            self.switch_view(0)
            fn = self.sim.res[res_id]
            self.clear_info()
            resref = self.find_path_res(res_id)
            self.add_info("<b>Resource</b>: <a href=\"{}\">{}</a> (0x{:X}) "\
                "- \"{}\"\n\n".format(resref, res_id, res_id, hlesc(fn)))
            
            def usedby(lst, tp):
                for idx, rec in enumerate(lst):
                    ru = False
                    for act_id, act_cond, act_arg, ops in rec.acts:
                        if ru: break
                        for op_id, op_code, op_res, op4, op5 in ops:
                            if res_id == op_res:
                                self.add_info("  <a href=\"/{}/{}\">{}</a> "\
                                    "(0x{:X}) - {}\n".format(tp, idx, rec.idx, \
                                        rec.idx, hlesc(rec.name)))
                                ru = True
                                break
                            #print(op_id, op_code, op_res, op4, op5)
            self.add_info("<b>Used by objects</b>:\n")
            usedby(self.sim.objects, "objs")
            self.add_info("\n<b>Used by scenes</b>:\n")
            usedby(self.sim.scenes, "scenes")
        
        
    def path_res_view(self, res_id):
        fn = self.sim.res[res_id]
        if fn[-4:].lower() == ".bmp":
            try:
                bmpf = self.sim.fman.read_file_stream(fn)
                bmp = petka.BMPLoader()
                bmp.load_data(bmpf)
                self.main_image = \
                    self.make_image(bmp)
                self.switch_view(1)
                self.update_canvas()
            except:
                self.switch_view(0)
                self.clear_info()
                self.add_info("Error loading {} - \"{}\" \n\n{}".\
                    format(res_id, hlesc(fn), hlesc(traceback.format_exc())))
            finally:
                bmpf.close()
        else:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Resource {} - \"{}\" cannot be displayed\n".\
                format(res_id, hlesc(fn)))

    def path_res_status(self):
        self.switch_view(0)
        self.clear_info()
        self.add_info("<b>Resources</b>: <a href=\"/res\">{}</a>\n"\
            "Filetypes:\n".format(len(self.sim.res)))
        fts = {}
        for res in self.sim.res.values():
            fp = res.rfind(".")
            if fp >= 0:
                ft = res[fp + 1:].upper()
                fts[ft] = fts.get(ft, 0) + 1
        ftk = list(fts.keys())
        ftk.sort()
        for ft in ftk:
            self.add_info("  <a href=\"/res/flt/{}\">{}</a>: {}\n".format(\
                ft, ft, fts[ft]))

    def path_res_all(self, path):
        if self.last_path[:2] != ("res", "all",):
            self.update_gui("Resources ({})".format(len(self.sim.res)))
            for idx, res_id in enumerate(self.sim.resord):
                    self.insert_lb_act("{} - {}".format(\
                res_id, self.sim.res[res_id]), ["res", "all", idx])
        # change                
        if len(path) > 2:
            # parts
            self.select_lb_item(path[2])
            res_id = self.sim.resord[path[2]]
            self.path_res_open(res_id, path[3:])
        else:
            self.path_res_status()

    def path_res_flt(self, path):
        lst = []
        for idx, res_id in enumerate(self.sim.resord):
            if self.sim.res[res_id].upper().endswith("." + path[2]):
                lst.append(res_id)
        if self.last_path[:3] != ("res", "flt", path[2]):
            self.update_gui("Resources {} ({})".format(path[2], len(lst)))
            self.insert_lb_act("All", "/res")
            self.insert_lb_act("-", None)
            for idx, res_id in enumerate(lst):
                    self.insert_lb_act("{} - {}".format(\
                res_id, self.sim.res[res_id]), ["res", "flt", path[2], idx])
        # change                
        if len(path) > 3:
            # parts
            self.select_lb_item(path[3] + 2)
            res_id = lst[path[3]]
            self.path_res_open(res_id, path[4:])
        else:
            self.path_res_status()

    def path_objs_scenes(self, path):
        self.switch_view(0)
        isobj = (self.curr_path[0] == "objs")
        if isobj:
            lst = self.sim.objects
        else:
            lst = self.sim.scenes
        if self.last_path[:1] != (self.curr_path[0],):
            if isobj:
                self.update_gui("Objects ({})".format(len(lst)))
            else:
                self.update_gui("Scenes ({})".format(len(lst)))
            for idx, rec in enumerate(lst):
                self.insert_lb_act("{} - {}".format(rec.idx, rec.name), \
                    [self.curr_path[0], idx])
        # change                
        rec = None
        if len(path) > 1:
            # index
            self.select_lb_item(path[1])
            rec = lst[path[1]]
        # display
        self.clear_info()
        if not rec:
            self.add_info("Select item from list\n")
        else:
            # record info
            self.add_info(("<b>Object</b>" if isobj \
                else "<b>Scene</b>") + ":\n")
            self.add_info("  Index:  {} (0x{:X})\n  Name:   {}\n".\
                format(rec.idx, rec.idx, hlesc(rec.name)))
            if rec.name in self.sim.names:
                self.add_info("  <a href=\"{}\">Alias</a>:  {}\n".format(\
                    self.find_path_name(rec.name), \
                    hlesc(self.sim.names[rec.name])))
            if rec.name in self.sim.invntr:
                self.add_info("  <a href=\"{}\">Invntr</a>: {}\n".format(\
                    self.find_path_invntr(rec.name), \
                    hlesc(self.sim.invntr[rec.name])))

            # references / backreferences                    
            if isobj:
                # search where object used
                self.add_info("\n<b>Refered by scenes</b>:\n")
                for scn in self.sim.scenes:
                    for ref in scn.refs:
                        if ref[0].idx == rec.idx:
                            self.add_info("  <a href=\"{}\">{}</a> (0x{:X}) "\
                                "- {}\n".format(self.find_path_scene(scn.idx), \
                                scn.idx, scn.idx, scn.name))
                            break
            else:
                if len(rec.refs) == 0:
                    self.add_info("\nNo references\n")
                else:
                    self.add_info("\n<b>References</b>: {}\n".\
                        format(len(rec.refs)))
                for idx, ref in enumerate(rec.refs):
                    self.add_info("  {}) <a href=\"{}\">{}</a>".format(idx,\
                        self.find_path_obj(ref[0].idx), ref[0].idx))
                    msg = ""
                    for arg in ref[1:]:
                        msg += " "
                        if arg < 10:
                            msg += "{}".format(arg)
                        elif arg == 0xffffffff:
                            msg += "-1"
                        else:
                            msg += "0x{:X}".format(arg)
                    self.add_info(msg + " / {}\n".format(hlesc(ref[0].name)))

            resused = []
            self.add_info("\n<b>Handlers</b>: {}\n".format(len(rec.acts)))
            for idx, (act_id, act_cond, act_arg, ops) in enumerate(rec.acts):
                msg = petka.OPCODES.get(act_id, ["OP_{:X}".format(act_id)])[0]
                if act_cond != 0xff or act_arg != 0xffff:
                    msg += " 0x{:02X} 0x{:04X}".format(act_cond, act_arg)
                self.add_info("  {}) <u>on {}</u>, ops: {}\n".format(\
                    idx, msg, len(ops)))
                for oidx, op in enumerate(ops):
                    msg = petka.OPCODES.get(op[1], ["OP_{:X}".format(op[1])])[0]
                    self.add_info("    {}) {} ".format(oidx, msg))
                    if op[0] == rec.idx:
                        self.add_info("THIS")
                    else:
                        self.add_info("<a href=\"{}\">{}</a>".format(\
                            self.find_path_obj_scene(op[0]), op[0]))
                    msg = ""
                    if op[2] != 0xffff:
                        if op[2] not in resused and op[2] in self.sim.res:
                            resused.append(op[2])
                    for arg in op[2:]:
                        msg += " "
                        if arg < 10:
                            msg += "{}".format(arg)
                        elif arg == 0xffff:
                            msg += "-1"
                        else:
                            msg += "0x{:X}".format(arg)
                    self.add_info("{}\n".format(msg))
                    
            if len(resused) > 0:
                self.add_info("\n<b>Used resources</b>: {}\n".\
                    format(len(resused)))
                for res_id in resused:
                    self.add_info("  <a href=\"{}\">{}</a> (0x{:X}) - {}\n".\
                        format(self.find_path_res(res_id), res_id, res_id, \
                        hlesc(self.sim.res[res_id])))
            

    def path_names(self, path):
        self.switch_view(0)
        if self.last_path[:1] != ("names",):
            self.update_gui("Names ({})".format(len(self.sim.names)))
            for idx, name in enumerate(self.sim.namesord):
                self.insert_lb_act(name, ["names", idx])
        # change
        name = None
        if len(path) > 1:
            # parts
            self.select_lb_item(path[1])
            name = self.sim.namesord[path[1]]
        # display
        self.clear_info()
        if not name:
            self.add_info("Select <b>name</b>\n")
        else:
            # name info
            self.add_info("<b>Alias</b>: {}\n".format(hlesc(name)))
            self.add_info("Value: {}\n\n".format(self.sim.names[name]))
            # search for objects
            self.add_info("<b>Applied for</b>:\n")
            for idx, obj in enumerate(self.sim.objects):
                if obj.name == name:
                    self.add_info("  <a href=\"/objs/{}\">{}</a> (0x{:X}) "\
                        "- {}\n".format(idx, obj.idx, obj.idx, \
                        hlesc(obj.name)))

    def path_invntr(self, path):
        self.switch_view(0)
        if self.last_path[:1] != ("invntr",):
            self.update_gui("Invntr ({})".format(len(self.sim.invntr)))
            for idx, name in enumerate(self.sim.invntrord):
                self.insert_lb_act(name, ["invntr", idx])
        # change
        name = None
        if len(path) > 1:
            # parts
            self.select_lb_item(path[1])
            name = self.sim.invntrord[path[1]]
        # display
        self.clear_info()
        if not name:
            self.add_info("Select <b>invntr</b>\n")
        else:
            # invntr info
            self.add_info("<b>Invntr</b>: {}\n".format(name))
            self.add_info("{}\n\n".format(hlesc(self.sim.invntr[name])))
            # search for objects
            self.add_info("<b>Applied for</b>:\n")
            for idx, obj in enumerate(self.sim.objects):
                if obj.name == name:
                    self.add_info("  <a href=\"/objs/{}\">{}</a> (0x{:X}) "\
                        "- {}\n".format(idx, obj.idx, obj.idx, \
                        hlesc(obj.name)))

    def path_test(self, path):
        self.update_gui("Test {}".format(path[1]))
        self.insert_lb_act("Outline", [])
        self.insert_lb_act("-", None)
        for i in range(15):
            self.insert_lb_act("{} #{}".format(path[1], i), path[:2] + (i,))
        if path[1] == "image":
            self.switch_view(1)
            self.main_image = tkinter.PhotoImage(file = "img/splash.gif")
        else:
            self.switch_view(0)
            self.clear_info()
            self.add_info("Information panel for {}\n".format(path))
            for i in range(100):
                self.add_info("  Item {}\n".format(i))

    def on_open_data(self):
        # open data - select TODO
        pass
        
    def open_data_from(self, folder):
        self.sim = petka.Engine()
        self.sim.load_data(folder, "cp1251")
        self.sim.open_part(0, 0)

def main():
    root = tkinter.Tk()
    app = App(master = root)
    if len(sys.argv) > 1:
        fn = sys.argv[1]
    else:
        fn = "."
    app.open_data_from(fn)
    app.mainloop()

    
if __name__ == "__main__":
    main()