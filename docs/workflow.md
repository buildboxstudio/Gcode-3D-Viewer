# Workflow - GCode 3D Viewer

Cara kerja harian, urutan pengujian sebelum rilis, dan prosedur untuk perubahan yang sering diminta.

## Setup

```bash
pip install -r requirements.txt   # Pillow, windnd
python gcode_viewer.py
```

Windows saja. Drag and drop butuh `windnd`; tanpa itu app jalan tapi status bar menulis "Drag & Drop: N/A".

## Loop harian

1. Ubah kode.
2. `python tests/test_parser.py` wajib hijau. Ini regresi parser: G92, baris tanpa spasi, z-hop, prioritas layer height, thumbnail CRLF.
3. Jalankan app, uji manual sesuai bagian "Checklist manual" kalau sentuhannya masuk area itu.
4. Perbarui `docs/project-memory.md` kalau ada keputusan atau temuan baru, dan `CHANGELOG.md` kalau ada perubahan perilaku.

## Checklist manual

Jalankan `python gcode_viewer.py` lalu:

**Parser**
- [ ] Buka `test_sample.gcode`: 12 segmen, 8 extrude, thumbnail 32x32 dan 16x16 tampil.
- [ ] Buka `tests/cura_g92.gcode`: model terlihat penuh (dulu dirender kosong).
- [ ] Buka `tests/zhop.gcode`: jumlah layer 2 (0.3 dan 0.55), bukan 5.
- [ ] Drag-drop file dari Explorer jalan, dan file non-gcode ditolak dengan peringatan.

**Viewport**
- [ ] Drag kiri rotasi, drag kanan pan, scroll zoom, R reset.
- [ ] Slider layer: turunkan ke 1, hanya layer bawah yang tampil, label Z ikut.
- [ ] Centang Show Travel, garis travel keluar.

**Tema dan bahasa**
- [ ] Ganti ke Light: seluruh UI (panel, menu, viewport, status bar) ikut terang saat itu juga, tanpa restart, tanpa dialog.
- [ ] Ganti ke Bahasa Indonesia: semua label ikut berganti, file yang sedang dibuka tetap tampil dengan statnya.
- [ ] Tutup dan buka lagi: pilihan tersimpan di `~/.gcode_viewer/settings.json`.

**Fan editor**
- [ ] Buka file dengan M106, Tools > Edit Fan Speed, Apply & Save As, file hasil berisi nilai S baru.

## Rilis

1. Pastikan `python tests/test_parser.py` hijau dan checklist manual lolos.
2. Naikkan `APP_VERSION` di `gcode_viewer.py`. Patch untuk bugfix, minor untuk fitur.
3. Tambah entri di `CHANGELOG.md` di bawah versi baru, tulis tanggal.
4. `python build_exe.py`, lalu uji `dist/GCodeViewer.exe` sebentar (buka file, ganti tema).
5. Commit dengan pesan `release: x.y.z`.

## Prosedur yang sering diminta

**Tambah bahasa**
1. Tambah locale baru di `languages.py`: `{**_BASE, 'name': ..., ...}` terjemahan yang sudah stabil saja, sisanya fallback ke English.
2. Perbarui hitungan bahasa di README dan About (`GCodeViewerApp._show_about`).
3. Uji: ganti bahasa live, restart, pastikan tersimpan.

**Tambah tema**
1. Tambah dict di `themes.py`, lengkapi semua kunci yang dipakai dark/light (lihat pasangan lama sebagai cetak biru).
2. Tambah radiobutton di submenu Theme (`_setup_menu`) dengan `value` dan `variable=self.theme_var`.
3. Uji: ganti ke tema baru, seluruh area ikut, screenshot masih benar warna backgroundnya.

**Ubah parser**
1. Tulis fixture `.gcode` kecil di `tests/` yang menunjukkan perilaku baru, tambah fungsi `test_*` di `tests/test_parser.py`.
2. Baru ubah parser. Test lama tidak boleh merah.
3. Ingat aturan di `AGENTS.md`: layer dari extrude-Z, `G92` dieksekusi, komentar slicer menang, CRLF toleran.

**Menambah dependensi**
Pikirkan ulang. App ini sengaja hanya Pillow + windnd supaya exe kecil dan build cepat. Kalau terpaksa: tambah ke `requirements.txt`, tambah `--hidden-import` dan cek ukuran exe di `build_exe.py`, catat alasan di project-memory.
