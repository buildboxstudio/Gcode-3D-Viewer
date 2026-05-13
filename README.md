# GCode 3D Viewer

Interactive 3D preview application for `.gcode` files from 3D printing slicers.

## Features

- **Drag & Drop** — Drop .gcode files directly from Explorer
- **3D Interactive View** — Rotate, pan, zoom in real-time
- **Multi-Language** — 12 languages: English, Indonesian, Chinese, Japanese, Korean, German, French, Spanish, Portuguese, Russian, Turkish, Italian
- **Light/Dark Theme** — Switch between dark and light mode
- **Layer Navigation** — Slider to view layer-by-layer
- **Color Gradient** — Height-based coloring (blue → green → yellow → red)
- **View Presets** — Top, Front, Side with one click
- **Embedded Thumbnail** — Extract and view thumbnails from slicers
- **Screenshot Export** — Save 3D view to PNG/JPG
- **Settings Persistence** — Language and theme saved automatically

## Menu Bar

| Menu | Items |
|------|-------|
| File | Open, Save Screenshot, Save Thumbnail, Exit |
| View | Reset, Top/Front/Side, Zoom, Travel toggle |
| Thumbnail | View embedded, Save |
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

Settings are saved to `~/.gcode_viewer/settings.json`.

## Build EXE

```bash
pip install pyinstaller
python build_exe.py
```

## Supported Slicer Thumbnails

| Slicer | Format |
|--------|--------|
| PrusaSlicer / SuperSlicer | `; thumbnail begin WxH` |
| Cura | `; thumbnail_QPix begin WxH` |
| Elegoo | `;gimage:` / `;simage:` |

## Upload ke GitHub

Cara cepat upload project ini ke GitHub:

```bash
# 1. Buka terminal di folder project ini
cd "d:\Projek Aplikasi\Gcode Viewer"

# 2. Inisialisasi git
git init
git add .
git commit -m "Initial commit - GCode 3D Viewer v3.0"

# 3. Buat repository baru di github.com (klik New Repository)
#    Nama: gcode-3d-viewer
#    Jangan centang "Add README" (sudah ada)

# 4. Hubungkan dan push
git remote add origin https://github.com/USERNAME/gcode-3d-viewer.git
git branch -M main
git push -u origin main
```

Ganti `USERNAME` dengan username GitHub kamu.

Untuk release `.exe`:
1. Buka tab **Releases** di repository GitHub
2. Klik **Create a new release**
3. Tag: `v3.0.0`
4. Upload file `dist/GCodeViewer.exe` sebagai attachment
5. Publish

## Requirements (Python)

- Windows 10/11
- Python 3.10+
- Pillow
- windnd

## Credits

Developed by **BuildBox Studio**
[instagram.com/buildbox.studio](https://instagram.com/buildbox.studio)
