# GCode 3D Viewer

Interactive 3D preview application for `.gcode` files from 3D printing slicers.

<img width="522" height="398" alt="image" src="https://github.com/user-attachments/assets/089e2a5e-f618-404d-adf8-01a74c00776c" /><img width="522" height="398" alt="Video_2026_05_16-1_edit_0" src="https://github.com/user-attachments/assets/d58dcc7f-237d-4af7-ab3c-6132927c4773" />



## Features

- **Drag & Drop** — Drop .gcode files directly from Explorer
- **3D Interactive View** — Rotate, pan, zoom in real-time
- **Print Info** — Layer height, first layer height, print duration, fan speed, slicer detection
- **Fan Speed Editor** — Adjust fan speed (%) and save as a new gcode file
- **Multi-Language** — 12 languages: English, Indonesian, Chinese, Japanese, Korean, German, French, Spanish, Portuguese, Russian, Turkish, Italian
- **Light/Dark Theme** — Switch between dark and light mode, applied instantly
- **Layer Navigation** — Slider to view layer-by-layer
- **Color Gradient** — Height-based coloring (blue → green → yellow → red)
- **View Presets** — Top, Front, Side with one click
- **Embedded Thumbnail** — Extract and view thumbnails from slicers
- **Screenshot Export** — Save 3D view to PNG/JPG
- **Custom App Icon** — 3D-printing themed icon
- **Settings Persistence** — Language and theme saved automatically

## Print Info Detected

| Info | Source |
|------|--------|
| Layer Height | Computed from Z deltas + slicer config comment |
| First Layer Height | First positive Z value |
| Print Duration | Slicer estimate (PrusaSlicer/SuperSlicer/Cura/Orca/Bambu) |
| Fan Speed | Parsed from M106/M107 commands |
| Slicer | Auto-detected from header comments |

## Menu Bar

| Menu | Items |
|------|-------|
| File | Open, Save Screenshot, Save Thumbnail, Exit |
| View | Reset, Top/Front/Side, Zoom, Travel toggle |
| Thumbnail | View embedded, Save |
| Tools | Edit Fan Speed |
| Settings | Language (12), Theme (Dark/Light) |
| Help | Shortcuts, About |

## Mouse Controls

| Action | Function |
|--------|----------|
| Left drag | Rotate 3D |
| Right drag | Pan |
| Scroll wheel | Zoom |
| Drop file | Open directly |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+O | Open file |
| Ctrl+S | Save screenshot |
| R | Reset view |
| Numpad 7 | Top view |
| Numpad 1 | Front view |
| Numpad 3 | Side view |

## Usage

### Option 1: Run EXE (Recommended)

```
dist\GCodeViewer.exe
```

No installation needed. Just double-click.

### Option 2: Run from Python

```bash
pip install Pillow windnd
python gcode_viewer.py
```

## Supported Languages

English, Bahasa Indonesia, 中文, 日本語, 한국어, Deutsch, Français, Español, Português, Русский, Türkçe, Italiano

## Themes

- **Dark** (default) — Dark background, easy on the eyes
- **Light** — Bright background for well-lit environments

Language and theme switches apply immediately, no restart needed.

Settings are saved to `~/.gcode_viewer/settings.json`.

## Build EXE

```bash
pip install pyinstaller
python build_exe.py
```

## Supported Slicer Thumbnails

| Slicer | Format |
|--------|--------|
| PrusaSlicer / SuperSlicer / OrcaSlicer / Bambu Studio | `; thumbnail begin WxH` |
| Cura | `; thumbnail_QPix begin WxH` |

Both LF and CRLF line endings are handled.

## Credits

Developed by **BuildBox Studio**
[instagram.com/buildbox.studio](https://instagram.com/buildbox.studio)
