# AGENTS.md - GCode 3D Viewer

Panduan untuk agent (AI atau manusia) yang bekerja di repo ini. Bacakan dulu sebelum mengubah apa pun.

## Apa aplikasi ini

Viewer .gcode untuk Windows. Desktop app Python + Tkinter, 3D preview lewat software rendering (Pillow), tanpa OpenGL. Satu file utama, dua modul pendukung. Lihat `docs/project-memory.md` untuk keputusan desain dan daftar bug, `docs/workflow.md` untuk cara kerja harian.

## Peta file

| File | Isi |
|------|-----|
| `gcode_viewer.py` | Semua logika: `GCodeParser`, `ThumbnailExtractor`, `Viewport3D`, `GCodeViewerApp` |
| `languages.py` | Kamus `LANGUAGES` (12 bahasa), fallback ke English via `get_text` |
| `themes.py` | Kamus `THEMES` (dark/light) via `get_theme`, fallback dark |
| `tests/` | Regresi parser, fixture gcode. Jalankan: `python tests/test_parser.py` |
| `build_exe.py` | Bungkus PyInstaller jadi `dist/GCodeViewer.exe` |
| `docs/` | project-memory (audit, keputusan) dan workflow |

## Aturan parser (jangan dilanggar)

1. **Layer dideteksi dari Z gerakan extrude saja** (`gcode_viewer.py`, cabang G0/G1). Perubahan Z saat travel adalah z-hop atau lift, bukan layer. Kalau aturan ini berubah, test `test_zhop_not_layers` dan semua file PrusaSlicer dengan z-hop rusak.
2. **`G92` harus dieksekusi** sebagai reset posisi (terutama E). Tanpa ini, file Cura (absolute-E, `G92 E0` per layer) mengklasifikasi extrusion jadi travel dan model hilang.
3. **Tokenisasi memakai `WORD_RE`**, bukan `split()`. Gcode bisa tanpa spasi (`G1X10Y20E1`) dan berprefiks `N` (nomor baris).
4. **Komentar slicer menang atas hitungan.** `layer_height` dari komentar tidak boleh ditimpa `_compute_layer_height`. Regex komentar harus pakai `(?<!first_)layer_height` agar tidak cocok di dalam `first_layer_height`.
5. **Toleran CRLF dan LF.** Regex yang menyentuh akhir baris harus `\r?\n`.
6. Klasifikasi segmen: `extrude` jika ada E dan `ne > ce`, selain itu `travel`. Retraction (E turun) memang travel, itu disengaja.

## Aturan UI

1. **Ganti tema/bahasa lewat `_rebuild_ui()`**, bukan dengan menambal widget satu per satu. Rebuild menghancurkan semua widget lalu memanggil `_setup_menu` + `_setup_ui` + `_sync_ui_to_parser`.
2. **Jangan panggil `_setup_dnd()` dua kali.** Hook windnd ganda berarti setiap file drop terbuka dua kali. Hook hanya dipasang di `__init__`.
3. Teks bahasa lewat `self.t(kunci)`. String bahasa Inggris hardcode di UI adalah bug i18n. Kunci baru wajib masuk `_BASE` di `languages.py` (locale lain otomatis fallback).
4. Warna lewat `themes.py`. Jangan hardcode warna di `gcode_viewer.py`, kecuali gradien tinggi-Z di `_render_scene` yang memang spesifik viewport.

## Konvensi kode

- Komentar seperlunya, jelaskan *kenapa* bukan *apa*. Kode sekitar jarang berkomentar, ikuti.
- Tanpa emoji di header panel atau label. Tanpa banner dekoratif.
- Tidak ada dependensi baru kecuali sangat perlu. Sekarang cuma Pillow dan windnd.
- Versi aplikasi hanya di `APP_VERSION`. Sinkron dengan entri CHANGELOG saat rilis.

## Build dan test

```bash
pip install Pillow windnd          # runtime
python tests/test_parser.py        # regresi parser, wajib hijau
python gcode_viewer.py             # jalankan app
python build_exe.py                # build exe (butuh pyinstaller)
```

Test parser tidak butuh framework. Tambahkan fixture gcode baru di `tests/` kalau menambah jalur parser.

## Jebakan yang sudah pernah terjadi

- Regex `layer_height` cocok di dalam `first_layer_height` (fixed 3.2.0, lihat kunci nomor 4 di atas).
- Thumbnail Cura Windows gagal karena CRLF (fixed 3.2.0).
- `print()` tidak terlihat di exe windowed. Kalau butuh laporan error saat production, pakai `messagebox` atau tulis ke file, jangan print.
- Folder `build/`, `dist/`, `__pycache__/` adalah artefak. Jangan commit (sudah ada di `.gitignore`).
