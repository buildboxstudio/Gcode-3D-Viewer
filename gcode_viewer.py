"""
GCode 3D Viewer v3.0
Windows application for interactive 3D preview of .gcode files
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import base64
import io
import re
import os
import sys
import math
import json

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

try:
    import windnd
    HAS_DND = True
except ImportError:
    HAS_DND = False

from languages import LANGUAGES, get_text
from themes import THEMES, get_theme

APP_NAME = "GCode 3D Viewer"
APP_VERSION = "3.0.0"
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.gcode_viewer')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'settings.json')


def load_config():
    """Load settings from config file."""
    defaults = {'language': 'en', 'theme': 'dark'}
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                defaults.update(data)
    except Exception:
        pass
    return defaults


def save_config(config):
    """Save settings to config file."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


class GCodeParser:
    """Parse gcode file into 3D segments."""

    def __init__(self):
        self.segments = []
        self.layers = []
        self.bounds = {
            'min_x': float('inf'), 'max_x': float('-inf'),
            'min_y': float('inf'), 'max_y': float('-inf'),
            'min_z': float('inf'), 'max_z': float('-inf'),
        }
        self.layer_segments = {}

    def parse(self, filepath):
        self.segments = []
        self.layers = []
        self.layer_segments = {}
        self.bounds = {k: float('inf') if 'min' in k else float('-inf')
                       for k in self.bounds}

        cx, cy, cz, ce = 0.0, 0.0, 0.0, 0.0
        rel_e = False
        layer_heights = set()

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';'):
                        continue
                    if ';' in line:
                        line = line[:line.index(';')]
                    parts = line.split()
                    if not parts:
                        continue
                    cmd = parts[0].upper()
                    if cmd == 'M83':
                        rel_e = True
                    elif cmd == 'M82':
                        rel_e = False
                    elif cmd in ('G0', 'G1'):
                        nx, ny, nz, ne, has_e = cx, cy, cz, ce, False
                        for p in parts[1:]:
                            c = p[0].upper()
                            try:
                                v = float(p[1:])
                            except (ValueError, IndexError):
                                continue
                            if c == 'X': nx = v
                            elif c == 'Y': ny = v
                            elif c == 'Z': nz = v
                            elif c == 'E':
                                has_e = True
                                ne = (ce + v) if rel_e else v
                        if nz != cz and nz not in layer_heights:
                            layer_heights.add(nz)
                        if nx != cx or ny != cy or nz != cz:
                            st = 'extrude' if (has_e and ne > ce) else 'travel'
                            self.segments.append((cx, cy, cz, nx, ny, nz, st))
                            for x in (cx, nx):
                                self.bounds['min_x'] = min(self.bounds['min_x'], x)
                                self.bounds['max_x'] = max(self.bounds['max_x'], x)
                            for y in (cy, ny):
                                self.bounds['min_y'] = min(self.bounds['min_y'], y)
                                self.bounds['max_y'] = max(self.bounds['max_y'], y)
                            for z in (cz, nz):
                                self.bounds['min_z'] = min(self.bounds['min_z'], z)
                                self.bounds['max_z'] = max(self.bounds['max_z'], z)
                        cx, cy, cz, ce = nx, ny, nz, ne
        except Exception as e:
            print(f"Parse error: {e}")

        self.layers = sorted(layer_heights)
        for idx, seg in enumerate(self.segments):
            li = self._find_layer(max(seg[2], seg[5]))
            self.layer_segments.setdefault(li, []).append(idx)
        return len(self.segments) > 0

    def _find_layer(self, z):
        if not self.layers:
            return 0
        lo, hi = 0, len(self.layers) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.layers[mid] <= z:
                lo = mid + 1
            else:
                hi = mid - 1
        return max(hi, 0)

    def get_center(self):
        return tuple((self.bounds[f'min_{a}'] + self.bounds[f'max_{a}']) / 2
                     for a in 'xyz')

    def get_size(self):
        return max(self.bounds['max_x'] - self.bounds['min_x'],
                   self.bounds['max_y'] - self.bounds['min_y'],
                   self.bounds['max_z'] - self.bounds['min_z'], 1.0)


class ThumbnailExtractor:
    @staticmethod
    def extract(filepath):
        thumbnails = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return thumbnails
        for pat, tag in [(r'; thumbnail begin (\d+)x(\d+) \d+\n(.*?); thumbnail end', True),
                         (r'; thumbnail_QPix begin (\d+)x(\d+) \d+\n(.*?); thumbnail_QPix end', True)]:
            for m in re.finditer(pat, content, re.DOTALL):
                w, h = int(m.group(1)), int(m.group(2))
                b64 = ''.join(l.strip().lstrip(';').strip()
                              for l in m.group(3).split('\n') if l.strip())
                try:
                    thumbnails.append((w, h, base64.b64decode(b64)))
                except Exception:
                    pass
        thumbnails.sort(key=lambda x: x[0]*x[1], reverse=True)
        return thumbnails


class Viewport3D:
    """3D viewport with software rendering."""

    def __init__(self, parent, theme):
        self.parent = parent
        self.theme = theme
        self.width = 700
        self.height = 600
        self.rot_x, self.rot_z = 30.0, 45.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.zoom = 1.0
        self.last_mx, self.last_my = 0, 0
        self.dragging, self.panning = False, False
        self.segments = []
        self.center = (0, 0, 0)
        self.model_size = 100.0
        self.max_layer = -1
        self.show_travel = False
        self.layers = []
        self.layer_segments = {}
        self.placeholder_text = ""

        bg = self.theme['viewport_bg']
        self.canvas = tk.Canvas(parent, bg=self._rgb_to_hex(bg),
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._bind_events()
        self.photo_image = None

    def _rgb_to_hex(self, rgb):
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'

    def _bind_events(self):
        self.canvas.bind('<ButtonPress-1>', self._on_left_down)
        self.canvas.bind('<ButtonRelease-1>', self._on_left_up)
        self.canvas.bind('<B1-Motion>', self._on_left_drag)
        self.canvas.bind('<ButtonPress-3>', self._on_right_down)
        self.canvas.bind('<ButtonRelease-3>', self._on_right_up)
        self.canvas.bind('<B3-Motion>', self._on_right_drag)
        self.canvas.bind('<ButtonPress-2>', self._on_right_down)
        self.canvas.bind('<ButtonRelease-2>', self._on_right_up)
        self.canvas.bind('<B2-Motion>', self._on_right_drag)
        self.canvas.bind('<MouseWheel>', self._on_scroll)
        self.canvas.bind('<Configure>', self._on_resize)

    def set_theme(self, theme):
        self.theme = theme
        bg = self._rgb_to_hex(theme['viewport_bg'])
        self.canvas.configure(bg=bg)
        if self.segments:
            self.render()
        else:
            self.draw_placeholder()

    def draw_placeholder(self):
        self.canvas.delete('all')
        w = self.canvas.winfo_width() or self.width
        h = self.canvas.winfo_height() or self.height
        self.canvas.create_text(
            w // 2, h // 2, text=self.placeholder_text,
            fill=self.theme['placeholder_color'],
            font=('Segoe UI', 13), justify=tk.CENTER)

    def set_model(self, parser):
        self.segments = parser.segments
        self.center = parser.get_center()
        self.model_size = parser.get_size()
        self.max_layer = len(parser.layers) - 1
        self.layers = parser.layers
        self.layer_segments = parser.layer_segments
        self.rot_x, self.rot_z = 30.0, 45.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.zoom = 1.0
        self.render()

    def set_layer_range(self, ml):
        self.max_layer = ml
        self.render()

    def set_show_travel(self, s):
        self.show_travel = s
        self.render()

    def reset_camera(self):
        self.rot_x, self.rot_z = 30.0, 45.0
        self.pan_x, self.pan_y = 0.0, 0.0
        self.zoom = 1.0
        if self.segments: self.render()

    def view_top(self):
        self.rot_x, self.rot_z = 90.0, 0.0
        if self.segments: self.render()

    def view_front(self):
        self.rot_x, self.rot_z = 0.0, 0.0
        if self.segments: self.render()

    def view_side(self):
        self.rot_x, self.rot_z = 0.0, 90.0
        if self.segments: self.render()

    def render(self):
        if not self.segments:
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            w, h = self.width, self.height
        img = Image.new('RGB', (w, h), self.theme['viewport_bg'])
        self._render_scene(img, w, h)
        self.photo_image = ImageTk.PhotoImage(img)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, image=self.photo_image, anchor=tk.NW)

    def _render_scene(self, img, w, h):
        draw = ImageDraw.Draw(img)
        cx, cy, cz = self.center
        dist = self.model_size * 2.0 / self.zoom
        rx, rz = math.radians(self.rot_x), math.radians(self.rot_z)
        crx, srx = math.cos(rx), math.sin(rx)
        crz, srz = math.cos(rz), math.sin(rz)

        def proj(x, y, z):
            px, py, pz = x-cx+self.pan_x, y-cy+self.pan_y, z-cz
            nx = px*crz - py*srz
            ny = px*srz + py*crz
            fy = ny*crx - pz*srx
            fz = ny*srx + pz*crx
            s = dist / (dist + fy + 0.001)
            return (int(w/2 + nx*s*(w/self.model_size)*self.zoom),
                    int(h/2 - fz*s*(h/self.model_size)*self.zoom))

        # Grid
        gc = self.theme['grid_color']
        gs = 10
        gr = max(int(self.model_size/2), 50)
        gr = (gr // gs) * gs
        for i in range(-gr, gr+1, gs):
            draw.line([proj(cx+i, cy-gr, cz), proj(cx+i, cy+gr, cz)], fill=gc)
            draw.line([proj(cx-gr, cy+i, cz), proj(cx+gr, cy+i, cz)], fill=gc)

        # Segments
        segs = []
        for li in range(self.max_layer + 1):
            if li in self.layer_segments:
                segs.extend(self.layer_segments[li])
        if not self.layer_segments:
            segs = list(range(len(self.segments)))
        step = max(1, len(segs) // 100000)
        tc = self.theme['travel_color']

        for i in range(0, len(segs), step):
            seg = self.segments[segs[i]]
            x1, y1, z1, x2, y2, z2, st = seg
            if st == 'travel' and not self.show_travel:
                continue
            p1, p2 = proj(x1, y1, z1), proj(x2, y2, z2)
            if (p1[0] < -100 and p2[0] < -100) or (p1[0] > w+100 and p2[0] > w+100):
                continue
            if (p1[1] < -100 and p2[1] < -100) or (p1[1] > h+100 and p2[1] > h+100):
                continue
            if st == 'travel':
                color = tc
            else:
                zr = max(0.0, min(1.0, (max(z1,z2)-cz+self.model_size/2)/max(self.model_size,1)))
                if zr < 0.25:
                    t = zr/0.25
                    r,g,b = int(50*(1-t)), int(100+155*t), int(200+55*t)
                elif zr < 0.5:
                    t = (zr-0.25)/0.25
                    r,g,b = int(50*t), int(200+55*(1-t)), int(255*(1-t))
                elif zr < 0.75:
                    t = (zr-0.5)/0.25
                    r,g,b = int(50+200*t), int(255*(1-t*0.3)), int(50*(1-t))
                else:
                    t = (zr-0.75)/0.25
                    r,g,b = 250, int(180*(1-t)), int(50*(1-t))
                color = (max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)))
            draw.line([p1, p2], fill=color, width=1)

        # Axes
        ao = (50, h-50)
        al = 30
        ox, oy = proj(cx, cy, cz)
        for axis, clr in [((1,0,0),(255,80,80)),((0,1,0),(80,255,80)),((0,0,1),(80,130,255))]:
            ax, ay = proj(cx+axis[0]*al/(w/self.model_size),
                          cy+axis[1]*al/(w/self.model_size),
                          cz+axis[2]*al/(w/self.model_size))
            dx, dy = ax-ox, ay-oy
            ln = math.sqrt(dx*dx+dy*dy) or 1
            draw.line([ao, (ao[0]+int(dx/ln*al), ao[1]+int(dy/ln*al))], fill=clr, width=2)

    def _on_left_down(self, e): self.dragging = True; self.last_mx, self.last_my = e.x, e.y
    def _on_left_up(self, e): self.dragging = False
    def _on_left_drag(self, e):
        if self.dragging:
            self.rot_z += (e.x-self.last_mx)*0.5
            self.rot_x = max(-90, min(90, self.rot_x+(e.y-self.last_my)*0.5))
            self.last_mx, self.last_my = e.x, e.y
            self.render()
    def _on_right_down(self, e): self.panning = True; self.last_mx, self.last_my = e.x, e.y
    def _on_right_up(self, e): self.panning = False
    def _on_right_drag(self, e):
        if self.panning:
            ps = self.model_size/500.0/self.zoom
            self.pan_x += (e.x-self.last_mx)*ps
            self.pan_y -= (e.y-self.last_my)*ps
            self.last_mx, self.last_my = e.x, e.y
            self.render()
    def _on_scroll(self, e):
        self.zoom *= 1.15 if e.delta > 0 else (1/1.15)
        self.zoom = max(0.1, min(50.0, self.zoom))
        self.render()
    def _on_resize(self, e):
        self.width, self.height = e.width, e.height
        if self.segments: self.render()
        else: self.draw_placeholder()


class GCodeViewerApp:
    """Main application."""

    def __init__(self):
        self.config = load_config()
        self.lang = self.config.get('language', 'en')
        self.theme_name = self.config.get('theme', 'dark')
        self.theme = get_theme(self.theme_name)

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1050x750")
        self.root.minsize(800, 600)

        self.parser = GCodeParser()
        self.thumbnails = []
        self.current_filepath = None

        self._apply_theme()
        self._setup_menu()
        self._setup_ui()
        self._setup_dnd()

    def t(self, key):
        """Get translated text."""
        return get_text(self.lang, key)

    def _apply_theme(self):
        self.root.configure(bg=self.theme['bg'])

    def _setup_menu(self):
        menubar = tk.Menu(self.root, bg=self.theme['bg_alt'], fg=self.theme['text'],
                          activebackground=self.theme['accent'],
                          activeforeground=self.theme['bg'], relief=tk.FLAT)
        self.root.config(menu=menubar)

        mc = {'bg': self.theme['panel'], 'fg': self.theme['text'],
              'activebackground': self.theme['accent'],
              'activeforeground': self.theme['bg']}

        # File
        fm = tk.Menu(menubar, tearoff=0, **mc)
        menubar.add_cascade(label=self.t('file'), menu=fm)
        fm.add_command(label=self.t('open_file'), command=self._open_file,
                       accelerator="Ctrl+O")
        fm.add_separator()
        fm.add_command(label=self.t('save_screenshot'), command=self._save_screenshot,
                       accelerator="Ctrl+S")
        fm.add_command(label=self.t('save_thumbnail'), command=self._save_thumbnail_file)
        fm.add_separator()
        fm.add_command(label=self.t('exit'), command=self.root.quit, accelerator="Alt+F4")

        # View
        vm = tk.Menu(menubar, tearoff=0, **mc)
        menubar.add_cascade(label=self.t('view'), menu=vm)
        vm.add_command(label=self.t('reset_view'), command=self._reset_view, accelerator="R")
        vm.add_separator()
        vm.add_command(label=self.t('view_top'), command=self._view_top, accelerator="7")
        vm.add_command(label=self.t('view_front'), command=self._view_front, accelerator="1")
        vm.add_command(label=self.t('view_side'), command=self._view_side, accelerator="3")
        vm.add_separator()
        vm.add_command(label=self.t('zoom_in'), command=self._zoom_in)
        vm.add_command(label=self.t('zoom_out'), command=self._zoom_out)
        vm.add_separator()
        self.travel_var = tk.BooleanVar(value=False)
        vm.add_checkbutton(label=self.t('show_travel'), variable=self.travel_var,
                           command=self._on_travel_toggle)

        # Thumbnail
        tm = tk.Menu(menubar, tearoff=0, **mc)
        menubar.add_cascade(label=self.t('thumbnail'), menu=tm)
        tm.add_command(label=self.t('view_thumbnail'), command=self._show_thumbnail)
        tm.add_command(label=self.t('save_thumbnail'), command=self._save_thumbnail_file)

        # Settings
        sm = tk.Menu(menubar, tearoff=0, **mc)
        menubar.add_cascade(label=self.t('settings'), menu=sm)

        # Language submenu
        lang_menu = tk.Menu(sm, tearoff=0, **mc)
        sm.add_cascade(label=self.t('language'), menu=lang_menu)
        for code, data in LANGUAGES.items():
            lang_menu.add_radiobutton(
                label=data['name'],
                command=lambda c=code: self._change_language(c),
                value=code
            )

        # Theme submenu
        theme_menu = tk.Menu(sm, tearoff=0, **mc)
        sm.add_cascade(label=self.t('theme'), menu=theme_menu)
        theme_menu.add_radiobutton(label=self.t('theme_dark'),
                                   command=lambda: self._change_theme('dark'))
        theme_menu.add_radiobutton(label=self.t('theme_light'),
                                   command=lambda: self._change_theme('light'))

        # Help
        hm = tk.Menu(menubar, tearoff=0, **mc)
        menubar.add_cascade(label=self.t('help'), menu=hm)
        hm.add_command(label=self.t('shortcuts'), command=self._show_shortcuts)
        hm.add_separator()
        hm.add_command(label=self.t('about'), command=self._show_about)

        # Bindings
        self.root.bind('<Control-o>', lambda e: self._open_file())
        self.root.bind('<Control-O>', lambda e: self._open_file())
        self.root.bind('<Control-s>', lambda e: self._save_screenshot())
        self.root.bind('<Control-S>', lambda e: self._save_screenshot())
        self.root.bind('<r>', lambda e: self._reset_view())
        self.root.bind('<R>', lambda e: self._reset_view())
        self.root.bind('<KP_7>', lambda e: self._view_top())
        self.root.bind('<KP_1>', lambda e: self._view_front())
        self.root.bind('<KP_3>', lambda e: self._view_side())

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        th = self.theme
        style.configure('TLabel', background=th['bg'], foreground=th['text'],
                        font=('Segoe UI', 10))
        style.configure('Panel.TLabel', background=th['panel'],
                        foreground=th['text'], font=('Segoe UI', 10))
        style.configure('PanelTitle.TLabel', background=th['panel'],
                        font=('Segoe UI', 11, 'bold'), foreground=th['accent'])
        style.configure('PanelInfo.TLabel', background=th['panel'],
                        font=('Segoe UI', 9), foreground=th['text_dim'])
        style.configure('Info.TLabel', font=('Segoe UI', 9),
                        foreground=th['text_dim'], background=th['bg_alt'])

        # Main
        main = tk.Frame(self.root, bg=th['bg'])
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Left panel
        lp = tk.Frame(main, bg=th['panel'], width=210, padx=12, pady=12)
        lp.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        lp.pack_propagate(False)

        ttk.Label(lp, text=f"\U0001f4c4 {self.t('file_info')}",
                  style='PanelTitle.TLabel').pack(anchor=tk.W)
        self.file_info = ttk.Label(lp, text=self.t('no_file'),
                                   style='PanelInfo.TLabel', wraplength=185)
        self.file_info.pack(anchor=tk.W, pady=(2, 15))

        ttk.Label(lp, text=f"\U0001f4d0 {self.t('layer')}",
                  style='PanelTitle.TLabel').pack(anchor=tk.W)
        self.layer_var = tk.IntVar(value=0)
        self.layer_slider = ttk.Scale(lp, from_=0, to=100, orient=tk.HORIZONTAL,
                                      variable=self.layer_var,
                                      command=self._on_layer_change)
        self.layer_slider.pack(fill=tk.X, pady=(5, 2))
        self.layer_label = ttk.Label(lp, text="Layer: — / —",
                                     style='PanelInfo.TLabel')
        self.layer_label.pack(anchor=tk.W)
        self.z_label = ttk.Label(lp, text="Z: — mm", style='PanelInfo.TLabel')
        self.z_label.pack(anchor=tk.W, pady=(0, 15))

        ttk.Label(lp, text=f"\u2699\ufe0f {self.t('options')}",
                  style='PanelTitle.TLabel').pack(anchor=tk.W)
        self.show_travel_var = tk.BooleanVar(value=False)
        tk.Checkbutton(lp, text=self.t('show_travel_cb'),
                       variable=self.show_travel_var, command=self._on_travel_toggle,
                       bg=th['panel'], fg=th['text'], selectcolor=th['select'],
                       activebackground=th['panel'], activeforeground=th['text'],
                       font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 15))

        ttk.Label(lp, text=f"\U0001f4ca {self.t('statistics')}",
                  style='PanelTitle.TLabel').pack(anchor=tk.W)
        self.stats_label = ttk.Label(lp, text="—", style='PanelInfo.TLabel',
                                     wraplength=185)
        self.stats_label.pack(anchor=tk.W, pady=(2, 15))

        ttk.Label(lp, text=f"\U0001f5b1\ufe0f {self.t('controls')}",
                  style='PanelTitle.TLabel').pack(anchor=tk.W)
        ctrl = f"{self.t('ctrl_rotate')}\n{self.t('ctrl_pan')}\n{self.t('ctrl_zoom')}\n{self.t('ctrl_reset')}\n{self.t('ctrl_open')}"
        ttk.Label(lp, text=ctrl, style='PanelInfo.TLabel').pack(anchor=tk.W, pady=(2, 0))

        # Viewport
        vf = tk.Frame(main, bg=th['surface'], relief=tk.SUNKEN, bd=1)
        vf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.viewport = Viewport3D(vf, th)
        self.viewport.placeholder_text = self.t('placeholder')
        self.viewport.draw_placeholder()

        # Status bar
        sb = tk.Frame(self.root, bg=th['bg_alt'], pady=4, padx=12)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(sb, text=self.t('ready'), style='Info.TLabel')
        self.status_label.pack(side=tk.LEFT)
        dnd_txt = self.t('dnd_active') if HAS_DND else self.t('dnd_inactive')
        ttk.Label(sb, text=dnd_txt, style='Info.TLabel').pack(side=tk.RIGHT)

    def _setup_dnd(self):
        if HAS_DND:
            windnd.hook_dropfiles(self.root, func=self._on_drop)

    def _on_drop(self, files):
        if files:
            fp = files[0]
            if isinstance(fp, bytes):
                fp = fp.decode('utf-8')
            ext = os.path.splitext(fp)[1].lower()
            if ext in ('.gcode', '.gco', '.g'):
                self._load_gcode(fp)
            else:
                messagebox.showwarning(self.t('unsupported_fmt'),
                                       self.t('unsupported_msg'))

    def _open_file(self):
        fp = filedialog.askopenfilename(
            title=self.t('open_file'),
            filetypes=[("GCode", "*.gcode *.gco *.g"), ("All", "*.*")])
        if fp:
            self._load_gcode(fp)

    def _load_gcode(self, filepath):
        if not os.path.isfile(filepath):
            messagebox.showerror(self.t('error'), self.t('file_not_found'))
            return
        self.current_filepath = filepath
        fn = os.path.basename(filepath)
        fs = os.path.getsize(filepath) / (1024*1024)
        self.root.title(f"{APP_NAME} — {fn}")
        self.status_label.config(text=f"\u23f3 {self.t('loading')} {fn}...")
        self.root.update()
        self.thumbnails = ThumbnailExtractor.extract(filepath)
        self.status_label.config(text=f"\u23f3 {self.t('parsing')} {fn}...")
        self.root.update()
        if self.parser.parse(filepath):
            self.file_info.config(text=f"{fn}\n{fs:.1f} MB")
            nl = len(self.parser.layers)
            self.layer_slider.config(from_=0, to=max(0, nl-1))
            self.layer_var.set(nl-1)
            self.layer_label.config(text=f"Layer: {nl} / {nl}")
            if self.parser.layers:
                self.z_label.config(text=f"Z: {self.parser.layers[-1]:.2f} mm")
            ec = sum(1 for s in self.parser.segments if s[6] == 'extrude')
            tc = len(self.parser.segments) - ec
            self.stats_label.config(
                text=f"{self.t('layers_lbl')}: {nl}\n"
                     f"{self.t('segments_lbl')}: {len(self.parser.segments):,}\n"
                     f"{self.t('extrude_lbl')}: {ec:,}\n"
                     f"{self.t('travel_lbl')}: {tc:,}\n"
                     f"{self.t('thumb_lbl')}: {self.t('yes') if self.thumbnails else self.t('no')}")
            self.viewport.set_model(self.parser)
            self.status_label.config(
                text=f"\u2705 {fn} — {nl} layers, {len(self.parser.segments):,} segments")
        else:
            self.status_label.config(text=f"\u26a0\ufe0f {self.t('no_path')} {fn}")
            messagebox.showwarning(self.t('warning'), self.t('no_path_msg'))

    def _on_layer_change(self, val):
        layer = int(float(val))
        total = len(self.parser.layers)
        self.layer_label.config(text=f"Layer: {layer+1} / {total}")
        if self.parser.layers and layer < len(self.parser.layers):
            self.z_label.config(text=f"Z: {self.parser.layers[layer]:.2f} mm")
        self.viewport.set_layer_range(layer)

    def _on_travel_toggle(self):
        s = self.show_travel_var.get()
        self.travel_var.set(s)
        self.viewport.set_show_travel(s)

    def _reset_view(self): self.viewport.reset_camera()
    def _view_top(self): self.viewport.view_top()
    def _view_front(self): self.viewport.view_front()
    def _view_side(self): self.viewport.view_side()

    def _zoom_in(self):
        self.viewport.zoom = min(50.0, self.viewport.zoom * 1.3)
        if self.viewport.segments: self.viewport.render()

    def _zoom_out(self):
        self.viewport.zoom = max(0.1, self.viewport.zoom / 1.3)
        if self.viewport.segments: self.viewport.render()

    def _save_screenshot(self):
        if not self.viewport.segments:
            messagebox.showinfo(self.t('info'), self.t('no_model'))
            return
        fp = filedialog.asksaveasfilename(title=self.t('save_screenshot'),
                                          defaultextension=".png",
                                          filetypes=[("PNG","*.png"),("JPEG","*.jpg")])
        if fp:
            w, h = self.viewport.canvas.winfo_width(), self.viewport.canvas.winfo_height()
            img = Image.new('RGB', (w, h), self.theme['viewport_bg'])
            self.viewport._render_scene(img, w, h)
            img.save(fp)
            messagebox.showinfo(self.t('success'), self.t('saved_to').format(fp))

    def _save_thumbnail_file(self):
        if not self.thumbnails:
            messagebox.showinfo(self.t('info'), self.t('no_thumbnail'))
            return
        img = Image.open(io.BytesIO(self.thumbnails[0][2]))
        fp = filedialog.asksaveasfilename(title=self.t('save_thumbnail'),
                                          defaultextension=".png",
                                          filetypes=[("PNG","*.png"),("JPEG","*.jpg")])
        if fp:
            img.save(fp)
            messagebox.showinfo(self.t('success'), self.t('saved_to').format(fp))

    def _show_thumbnail(self):
        if not self.thumbnails:
            messagebox.showinfo(self.t('info'), self.t('no_thumbnail'))
            return
        popup = tk.Toplevel(self.root)
        popup.title(self.t('thumbnail'))
        popup.configure(bg=self.theme['bg'])
        for i, (w, h, data) in enumerate(self.thumbnails):
            try:
                img = Image.open(io.BytesIO(data))
            except Exception:
                continue
            frame = tk.Frame(popup, bg=self.theme['panel'], padx=10, pady=10)
            frame.pack(padx=10, pady=5, fill=tk.X)
            tk.Label(frame, text=f"Thumbnail {i+1}: {w}x{h}px",
                     bg=self.theme['panel'], fg=self.theme['text_dim'],
                     font=('Segoe UI', 9)).pack(anchor=tk.W)
            dw, dh = img.size
            mx = 350
            if dw < mx and dh < mx:
                sc = min(mx // max(dw, 1), 4)
                img_d = img.resize((dw*sc, dh*sc), Image.NEAREST)
            elif dw > mx or dh > mx:
                r = min(mx/dw, mx/dh)
                img_d = img.resize((int(dw*r), int(dh*r)), Image.LANCZOS)
            else:
                img_d = img
            photo = ImageTk.PhotoImage(img_d)
            lbl = tk.Label(frame, image=photo, bg=self.theme['panel'])
            lbl.image = photo
            lbl.pack(pady=5)

    def _change_language(self, code):
        self.lang = code
        self.config['language'] = code
        save_config(self.config)
        messagebox.showinfo(self.t('info'), self.t('restart_msg'))

    def _change_theme(self, name):
        self.theme_name = name
        self.theme = get_theme(name)
        self.config['theme'] = name
        save_config(self.config)
        # Apply immediately
        self._apply_theme()
        self.viewport.set_theme(self.theme)
        # Rebuild UI requires restart for full effect
        messagebox.showinfo(self.t('info'), self.t('restart_msg'))

    def _show_shortcuts(self):
        txt = ("Ctrl+O = Open file\nCtrl+S = Save screenshot\n"
               "R = Reset view\nNumpad 7 = Top\nNumpad 1 = Front\n"
               "Numpad 3 = Side\n\nMouse:\nLeft drag = Rotate\n"
               "Right drag = Pan\nScroll = Zoom")
        messagebox.showinfo(self.t('shortcuts'), txt)

    def _show_about(self):
        about_win = tk.Toplevel(self.root)
        about_win.title(self.t('about'))
        about_win.configure(bg=self.theme['bg'])
        about_win.resizable(False, False)
        about_win.geometry("360x320")

        # Center on parent
        about_win.transient(self.root)
        about_win.grab_set()

        tk.Label(about_win, text=APP_NAME, font=('Segoe UI', 16, 'bold'),
                 bg=self.theme['bg'], fg=self.theme['accent']).pack(pady=(20, 2))
        tk.Label(about_win, text=f"v{APP_VERSION}", font=('Segoe UI', 10),
                 bg=self.theme['bg'], fg=self.theme['text_dim']).pack()

        info = ("3D GCode preview viewer\n"
                "with multi-language & theme support.\n\n"
                "Supported slicers:\n"
                "PrusaSlicer, SuperSlicer, Cura, Elegoo\n\n"
                "Built with Python + Tkinter + Pillow")
        tk.Label(about_win, text=info, font=('Segoe UI', 9),
                 bg=self.theme['bg'], fg=self.theme['text'],
                 justify=tk.CENTER).pack(pady=(10, 15))

        # Separator
        tk.Frame(about_win, bg=self.theme['text_dim'], height=1).pack(
            fill=tk.X, padx=40, pady=5)

        tk.Label(about_win, text="Developed by", font=('Segoe UI', 9),
                 bg=self.theme['bg'], fg=self.theme['text_dim']).pack()

        # Clickable hyperlink
        link = tk.Label(about_win, text="BuildBox Studio",
                        font=('Segoe UI', 11, 'bold', 'underline'),
                        bg=self.theme['bg'], fg=self.theme['accent'],
                        cursor='hand2')
        link.pack(pady=(2, 15))
        link.bind('<Button-1>', lambda e: __import__('webbrowser').open(
            'https://www.instagram.com/buildbox.studio/'))

    def run(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth()//2) - (w//2)
        y = (self.root.winfo_screenheight()//2) - (h//2)
        self.root.geometry(f'+{x}+{y}')
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.root.after(200, lambda: self._load_gcode(sys.argv[1]))
        self.root.mainloop()


def main():
    GCodeViewerApp().run()

if __name__ == '__main__':
    main()
