"""
GCode 3D Viewer
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
APP_VERSION = "3.2.0"
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.gcode_viewer')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'settings.json')

# GCode word: letter + number, with or without space ("G1 X10" or "G1X10")
WORD_RE = re.compile(r'([A-Za-z])\s*([-+]?\d*\.?\d+)')


def resource_path(rel):
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


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
        # Metadata
        self.layer_height = 0.0
        self.first_layer_height = 0.0
        self.fan_speeds = set()       # raw S values (0-255)
        self.print_time = None        # human readable string
        self.print_time_seconds = None
        self.filament_used = None
        self.slicer = None

    def parse(self, filepath):
        self.segments = []
        self.layers = []
        self.layer_segments = {}
        self.bounds = {k: float('inf') if 'min' in k else float('-inf')
                       for k in self.bounds}
        self.layer_height = 0.0
        self.first_layer_height = 0.0
        self.fan_speeds = set()
        self.print_time = None
        self.print_time_seconds = None
        self.filament_used = None
        self.slicer = None

        cx, cy, cz, ce = 0.0, 0.0, 0.0, 0.0
        rel_e = False
        layer_heights = set()

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(';'):
                        self._parse_comment(line)
                        continue
                    if ';' in line:
                        line = line[:line.index(';')]
                    words = WORD_RE.findall(line)
                    if words and words[0][0].upper() == 'N':
                        words = words[1:]  # line number prefix
                    if not words:
                        continue
                    cmd = (words[0][0] + words[0][1]).upper()
                    params = [(c.upper(), v) for c, v in words[1:]]
                    if cmd == 'M83':
                        rel_e = True
                    elif cmd == 'M82':
                        rel_e = False
                    elif cmd == 'G92':
                        if not params:
                            cx = cy = cz = ce = 0.0
                        for c, v in params:
                            if c == 'X': cx = float(v)
                            elif c == 'Y': cy = float(v)
                            elif c == 'Z': cz = float(v)
                            elif c == 'E': ce = float(v)
                    elif cmd in ('M106', 'M107'):
                        if cmd == 'M107':
                            self.fan_speeds.add(0.0)
                        else:
                            for c, v in params:
                                if c == 'S':
                                    try:
                                        self.fan_speeds.add(float(v))
                                    except ValueError:
                                        pass
                    elif cmd in ('G0', 'G1'):
                        nx, ny, nz, ne, has_e = cx, cy, cz, ce, False
                        for c, v in params:
                            if c == 'X': nx = float(v)
                            elif c == 'Y': ny = float(v)
                            elif c == 'Z': nz = float(v)
                            elif c == 'E':
                                has_e = True
                                ne = (ce + float(v)) if rel_e else float(v)
                        if nx != cx or ny != cy or nz != cz:
                            st = 'extrude' if (has_e and ne > ce) else 'travel'
                            # Layers come from extrusion Z only, so z-hops
                            # and nozzle lifts don't create phantom layers.
                            if st == 'extrude' and nz not in layer_heights:
                                layer_heights.add(nz)
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

        self._compute_layer_height()
        return len(self.segments) > 0

    def _compute_layer_height(self):
        """Determine typical layer height from Z deltas (mode).

        Slicer comment value (set during parsing) wins; this is fallback.
        """
        positive = [z for z in self.layers if z > 0.0]
        if len(self.layers) >= 2 and not self.layer_height:
            diffs = []
            for i in range(len(self.layers) - 1):
                d = round(self.layers[i + 1] - self.layers[i], 3)
                if d > 0:
                    diffs.append(d)
            if diffs:
                from collections import Counter
                self.layer_height = Counter(diffs).most_common(1)[0][0]
        # First layer height = first positive Z value
        if positive:
            self.first_layer_height = round(positive[0], 3)
        elif self.layer_height:
            self.first_layer_height = self.layer_height

    def _parse_comment(self, line):
        """Extract metadata from comment lines (print time, layer height, etc)."""
        low = line.lower()
        # Detect slicer
        if self.slicer is None:
            if 'prusaslicer' in low: self.slicer = 'PrusaSlicer'
            elif 'superslicer' in low: self.slicer = 'SuperSlicer'
            elif 'cura' in low: self.slicer = 'Cura'
            elif 'orca' in low: self.slicer = 'OrcaSlicer'
            elif 'bambu' in low: self.slicer = 'BambuStudio'
            elif 'ideamaker' in low: self.slicer = 'ideaMaker'

        # Print time — PrusaSlicer / SuperSlicer / Orca
        if self.print_time is None and 'estimated printing time' in low:
            m = re.search(r'=\s*(.+)$', line.strip())
            if m:
                self.print_time = m.group(1).strip()
                self.print_time_seconds = self._time_to_seconds(self.print_time)
        # Cura: ;TIME:7530
        if self.print_time_seconds is None:
            m = re.match(r';TIME:\s*([\d.]+)', line.strip(), re.IGNORECASE)
            if m:
                self.print_time_seconds = float(m.group(1))
                self.print_time = self._seconds_to_str(self.print_time_seconds)
        # Bambu/Orca: ; total estimated time: ...  or  ; model printing time: ...
        if self.print_time is None and ('total estimated time' in low or
                                        'model printing time' in low):
            m = re.search(r':\s*(.+)$', line.strip())
            if m:
                self.print_time = m.group(1).strip()
                self.print_time_seconds = self._time_to_seconds(self.print_time)

        # Layer height from config comment (must not match first_layer_height)
        if 'layer_height' in low and '=' in line:
            m = re.search(r'(?<!first_)layer_height\s*=\s*([\d.]+)', low)
            if m and not self.layer_height:
                try: self.layer_height = float(m.group(1))
                except ValueError: pass
        elif 'layer height' in low and ':' in line:
            m = re.search(r'layer height\s*:\s*([\d.]+)', low)
            if m and not self.layer_height:
                try: self.layer_height = float(m.group(1))
                except ValueError: pass

        # Filament used
        if self.filament_used is None:
            m = re.search(r'filament used \[mm\]\s*=\s*([\d.]+)', low)
            if m:
                self.filament_used = float(m.group(1))

    @staticmethod
    def _time_to_seconds(s):
        """Convert '2h 5m 30s' or '1d 2h 3m' to seconds."""
        total = 0
        for val, unit in re.findall(r'(\d+)\s*([dhms])', s.lower()):
            v = int(val)
            total += v * {'d': 86400, 'h': 3600, 'm': 60, 's': 1}[unit]
        return total if total > 0 else None

    @staticmethod
    def _seconds_to_str(sec):
        sec = int(sec)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

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
        for pat in [r'; thumbnail begin (\d+)x(\d+) \d+\r?\n(.*?); thumbnail end',
                    r'; thumbnail_QPix begin (\d+)x(\d+) \d+\r?\n(.*?); thumbnail_QPix end']:
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

        # App icon
        try:
            ico = resource_path('icon.ico')
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

        self.parser = GCodeParser()
        self.thumbnails = []
        self.current_filepath = None
        self.lang_var = tk.StringVar(value=self.lang)
        self.theme_var = tk.StringVar(value=self.theme_name)

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

        # Tools
        tlm = tk.Menu(menubar, tearoff=0, **mc)
        menubar.add_cascade(label=self.t('tools'), menu=tlm)
        tlm.add_command(label=self.t('edit_fan'), command=self._show_fan_editor)

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
                value=code,
                variable=self.lang_var
            )

        # Theme submenu
        theme_menu = tk.Menu(sm, tearoff=0, **mc)
        sm.add_cascade(label=self.t('theme'), menu=theme_menu)
        theme_menu.add_radiobutton(label=self.t('theme_dark'), value='dark',
                                   variable=self.theme_var,
                                   command=lambda: self._change_theme('dark'))
        theme_menu.add_radiobutton(label=self.t('theme_light'), value='light',
                                   variable=self.theme_var,
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

        # Print Info section (layer height, print time, fan)
        ttk.Label(lp, text=f"\u2139\ufe0f {self.t('print_info')}",
                  style='PanelTitle.TLabel').pack(anchor=tk.W)
        self.meta_label = ttk.Label(lp, text="—", style='PanelInfo.TLabel',
                                    wraplength=185)
        self.meta_label.pack(anchor=tk.W, pady=(2, 15))

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
        self.root.title(f"{APP_NAME} — {fn}")
        self.status_label.config(text=f"\u23f3 {self.t('loading')} {fn}...")
        self.root.update()
        self.thumbnails = ThumbnailExtractor.extract(filepath)
        self.status_label.config(text=f"\u23f3 {self.t('parsing')} {fn}...")
        self.root.update()
        if self.parser.parse(filepath):
            self._sync_ui_to_parser()
            self.status_label.config(
                text=f"\u2705 {fn} — {len(self.parser.layers)} layers, "
                     f"{len(self.parser.segments):,} segments")
        else:
            self.status_label.config(text=f"\u26a0\ufe0f {self.t('no_path')} {fn}")
            messagebox.showwarning(self.t('warning'), self.t('no_path_msg'))

    def _sync_ui_to_parser(self):
        """Point all widgets at the current parser state."""
        p = self.parser
        nl = len(p.layers)
        if self.current_filepath:
            fn = os.path.basename(self.current_filepath)
            fs = os.path.getsize(self.current_filepath) / (1024 * 1024)
            self.file_info.config(text=f"{fn}\n{fs:.1f} MB")
        self.layer_slider.config(from_=0, to=max(0, nl - 1))
        self.layer_var.set(max(0, nl - 1))
        self.layer_label.config(text=f"Layer: {nl} / {nl}")
        if p.layers:
            self.z_label.config(text=f"Z: {p.layers[-1]:.2f} mm")
        ec = sum(1 for s in p.segments if s[6] == 'extrude')
        tc = len(p.segments) - ec
        self.stats_label.config(
            text=f"{self.t('layers_lbl')}: {nl}\n"
                 f"{self.t('segments_lbl')}: {len(p.segments):,}\n"
                 f"{self.t('extrude_lbl')}: {ec:,}\n"
                 f"{self.t('travel_lbl')}: {tc:,}\n"
                 f"{self.t('thumb_lbl')}: {self.t('yes') if self.thumbnails else self.t('no')}")
        self._update_meta_panel()
        self.viewport.set_model(p)

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

    def _fan_summary(self):
        """Return human-readable fan speed summary as list of percentages."""
        speeds = sorted(self.parser.fan_speeds)
        if not speeds:
            return None
        pcts = []
        for s in speeds:
            if s <= 0:
                pcts.append(self.t('off'))
            else:
                pcts.append(f"{round(s / 255 * 100)}%")
        # Deduplicate preserving order
        seen = []
        for p in pcts:
            if p not in seen:
                seen.append(p)
        return seen

    def _update_meta_panel(self):
        """Fill the Print Info panel with parsed metadata."""
        p = self.parser
        lines = []
        # Layer height
        lh = f"{p.layer_height:.2f} mm" if p.layer_height else self.t('unknown')
        lines.append(f"{self.t('layer_height')}: {lh}")
        # First layer
        flh = f"{p.first_layer_height:.2f} mm" if p.first_layer_height else self.t('unknown')
        lines.append(f"{self.t('first_layer')}: {flh}")
        # Print time
        pt = p.print_time if p.print_time else self.t('unknown')
        lines.append(f"{self.t('print_time')}: {pt}")
        # Filament
        if p.filament_used:
            lines.append(f"{self.t('filament')}: {p.filament_used:,.0f} mm")
        # Fan speed
        fans = self._fan_summary()
        fan_str = ', '.join(fans) if fans else self.t('unknown')
        lines.append(f"{self.t('fan_speed')}: {fan_str}")
        # Slicer
        if p.slicer:
            lines.append(f"{self.t('slicer')}: {p.slicer}")
        self.meta_label.config(text='\n'.join(lines))

    def _show_fan_editor(self):
        if not self.current_filepath:
            messagebox.showinfo(self.t('info'), self.t('no_model'))
            return
        fans = self._fan_summary()
        if not fans:
            messagebox.showinfo(self.t('fan_editor'), self.t('no_fan'))
            return

        win = tk.Toplevel(self.root)
        win.title(self.t('fan_editor'))
        win.configure(bg=self.theme['bg'])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        th = self.theme

        tk.Label(win, text=f"\U0001f4a8 {self.t('fan_editor')}",
                 font=('Segoe UI', 13, 'bold'), bg=th['bg'],
                 fg=th['accent']).pack(pady=(15, 10), padx=20)

        tk.Label(win, text=self.t('detected_fan'), bg=th['bg'], fg=th['text_dim'],
                 font=('Segoe UI', 9)).pack(anchor=tk.W, padx=20)
        tk.Label(win, text='  ' + ', '.join(fans), bg=th['bg'], fg=th['text'],
                 font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, padx=20, pady=(0, 15))

        # New fan speed input
        frm = tk.Frame(win, bg=th['bg'])
        frm.pack(padx=20, pady=(0, 5), fill=tk.X)
        tk.Label(frm, text=self.t('new_fan'), bg=th['bg'], fg=th['text'],
                 font=('Segoe UI', 10)).pack(side=tk.LEFT)
        fan_pct = tk.IntVar(value=100)
        spin = tk.Spinbox(frm, from_=0, to=100, increment=5, width=6,
                          textvariable=fan_pct, font=('Segoe UI', 10))
        spin.pack(side=tk.LEFT, padx=8)

        # Slider for convenience
        slider = ttk.Scale(win, from_=0, to=100, orient=tk.HORIZONTAL,
                           command=lambda v: fan_pct.set(int(float(v))))
        slider.set(100)
        slider.pack(fill=tk.X, padx=20, pady=(5, 15))

        def apply_save():
            pct = max(0, min(100, fan_pct.get()))
            new_s = round(pct / 100 * 255)
            out = filedialog.asksaveasfilename(
                parent=win, title=self.t('apply_save'),
                defaultextension=".gcode",
                initialfile=os.path.splitext(os.path.basename(self.current_filepath))[0] + "_fan.gcode",
                filetypes=[("GCode", "*.gcode"), ("All", "*.*")])
            if not out:
                return
            count = self._rewrite_fan(self.current_filepath, out, new_s)
            messagebox.showinfo(self.t('success'),
                                self.t('fan_saved').format(out) + "\n\n" +
                                self.t('fan_replaced').format(count),
                                parent=win)
            win.destroy()

        btn = tk.Button(win, text=self.t('apply_save'), command=apply_save,
                        bg=th['success'], fg=th['bg'], relief=tk.FLAT,
                        font=('Segoe UI', 10, 'bold'), padx=15, pady=6,
                        cursor='hand2')
        btn.pack(pady=(0, 18))

    def _rewrite_fan(self, src, dst, new_s):
        """Rewrite all M106 S>0 commands with new_s value. Returns count."""
        count = 0
        with open(src, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        out_lines = []
        for line in lines:
            stripped = line.strip()
            # only touch active M106 commands (not in comments)
            if re.match(r'^M106\b', stripped, re.IGNORECASE):
                m = re.search(r'[Ss]([\d.]+)', stripped)
                if m and float(m.group(1)) > 0:
                    if new_s <= 0:
                        new_line = re.sub(r'^M106', 'M107', stripped, flags=re.IGNORECASE)
                        new_line = re.sub(r'\s*[Ss][\d.]+', '', new_line)
                    else:
                        new_line = re.sub(r'([Ss])[\d.]+', rf'\g<1>{new_s}', stripped)
                    # preserve line ending
                    ending = '\n' if line.endswith('\n') else ''
                    out_lines.append(new_line + ending)
                    count += 1
                    continue
            out_lines.append(line)
        with open(dst, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)
        return count

    def _change_language(self, code):
        self.lang = code
        self.config['language'] = code
        save_config(self.config)
        self._rebuild_ui()

    def _change_theme(self, name):
        self.theme_name = name
        self.theme = get_theme(name)
        self.config['theme'] = name
        save_config(self.config)
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Recreate menubar and widgets so theme/language applies fully.

        The windnd hook is NOT reinstalled: double hook = double file open.
        """
        self.root.config(menu='')
        for w in self.root.winfo_children():
            w.destroy()
        self._apply_theme()
        self._setup_menu()
        self._setup_ui()
        if self.parser.segments and self.current_filepath:
            fn = os.path.basename(self.current_filepath)
            self.root.title(f"{APP_NAME} — {fn}")
            self._sync_ui_to_parser()
            self.status_label.config(
                text=f"\u2705 {fn} — {len(self.parser.layers)} layers, "
                     f"{len(self.parser.segments):,} segments")

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
                "Metadata detection:\n"
                "PrusaSlicer, SuperSlicer, Cura, OrcaSlicer, Bambu Studio\n\n"
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
