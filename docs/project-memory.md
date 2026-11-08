# Project Memory - GCode 3D Viewer

Memori teknis proyek: hasil audit, keputusan desain beserta alasannya, dan limitasi yang disadari. Dokumen ini jadi sumber kebenaran saat agent atau manusia baru masuk ke kode. Perbarui setiap kali ada keputusan atau temuan baru.

## Audit 2026-11-08 (versi 3.1.0, fixed di 3.2.0)

Scope: seluruh kode (parser, viewport, UI, fan editor, i18n, tema, build), README, dan pengalaman pemakaian. Total 8 temuan kritis/high diperbaiki, 14 masuk backlog.

### Diperbaiki di 3.2.0

| ID | Severity | Lokasi (3.2.0) | Temuan |
|----|----------|----------------|--------|
| C1 | Kritis | parser, cabang G92 | `G92` tidak dieksekusi. File Cura (absolute-E, `G92 E0` per layer) mengklasifikasi semua extrusion setelah reset pertama sebagai travel. Model dirender kosong karena travel tersembunyi. |
| C2 | Kritis | parser, `WORD_RE` (`gcode_viewer.py:37`) | Tokenisasi `line.split()` membuang baris tanpa spasi (`G1X10Y20E1`, flavor RepRap/Klipper) dan tidak menangani prefiks `N`. |
| H1 | High | parser, cabang G0/G1 | Setiap perubahan Z tercatat sebagai layer. Z-hop, nozzle lift awal, dan lift akhir menciptakan layer palsu; jumlah layer dan slider jadi salah. |
| H2 | High | `_compute_layer_height` (`gcode_viewer.py:185`), `_parse_comment` (`:206`) | Hasil hitung mode-of-diffs menimpa `layer_height` dari komentar slicer. Regex `layer_height` juga cocok di dalam `first_layer_height`, jadi nilai layer pertama bisa bocor jadi layer height. |
| H3 | High | `ThumbnailExtractor.extract` | Regex thumbnail butuh `\n` persis setelah byte count. File CRLF (Cura di Windows) gagal ekstrak total. Kini `\r?\n`. |
| H4 | High | `_rebuild_ui` (`gcode_viewer.py:1057`) | Ganti tema hanya mengubah bg root dan viewport; panel, menubar, dan label tetap tema lama sampai restart. Pesan restartnya pun salah (menyebut "language" untuk kasus tema). |
| H5 | High | `_setup_menu` | Radiobutton bahasa dan tema tanpa `variable` bersama: tidak ada tanda centang pada pilihan aktif. |
| H6 | High | `_update_meta_panel` (`gcode_viewer.py:927`) | `filament_used` diparse dan kunci i18n `filament` ada, tapi nilainya tidak pernah ditampilkan. |

### Backlog (disadari, belum diperbaiki)

| ID | Severity | Lokasi | Temuan |
|----|----------|--------|--------|
| B1 | Medium | `_render_scene` (`gcode_viewer.py:449`) | Skala proyeksi `s = dist/(dist+fy)`. Saat zoom di atas sekitar 4x, `dist` mengecil sampai penyebut bisa negatif untuk titik dekat kamera; hasilnya garis termirror acak. Perlu near-plane clamp. |
| B2 | Medium | `GCodeViewerApp._load_gcode` | Parse dan render sinkron di mainloop. File besar (>100 MB) membekukan UI belasan detik. Butuh thread worker + antre render. |
| B3 | Medium | `_render_scene` (`gcode_viewer.py:469-473`) | Decimentasi `step = len(segs)//100000` melompati segmen, bukan menipiskan visual. File >100k segmen tampil bergaris bolong. |
| B4 | Medium | `gcode_viewer.py:666` | Binding `r`/`R` level root aktif juga saat mengetik di Spinbox fan editor. Perlu cek fokus widget. |
| B5 | Medium | `_sync_ui_to_parser` | Label `Layer: x / y` dan `Z: x mm` hardcode bahasa Inggris, tidak lewat `self.t()`. |
| B6 | Medium | `gcode_viewer.py:668` | Preset view hanya numpad (KP_7/1/3) tapi akselerator menu menulis "7/1/3". Laptop tanpa numpad tidak bisa pakai pintasan. Tambah binding top-row dan `+`/`-` untuk zoom. |
| B7 | Medium | `_show_fan_editor` (`gcode_viewer.py:952`) | Input Spinbox non-angka membuat `IntVar.get()` melempar TclError, dialog diam. Perlu try/except. |
| B8 | Medium | `_rewrite_fan` (`gcode_viewer.py:1017`) | Baris M106 ditulis ulang tanpa `\r`, file CRLF hasil campur LF. `re.sub` S juga menyentuh angka S di dalam komentar baris yang sama. |
| B9 | Low | `GCodeParser.parse` | `G2`/`G3` (arc) diabaikan; file hasil arc-optimizer Klipper bolong melengkung. `G91`/`G90` (relative XYZ) juga diabaikan. |
| B10 | Low | `draw_placeholder` (`gcode_viewer.py:375`) | Dipanggil sebelum window ter-map, `winfo_width()` = 1, teks muncul sesaat di pojok kiri atas sebelum Configure memperbaiki. |
| B11 | Low | `GCodeParser.parse` (`gcode_viewer.py:175`) | Error parse lewat `print()`, tidak terlihat di exe windowed. |
| B12 | Low | `__init__` | Tidak ada `SetProcessDpiAwareness`. Di layar scaling 150% seluruh app tampak blur. |
| B13 | Low | `_setup_ui` | Emoji sebagai header section panel berisiko tampil sebagai kotak di sebagian font, dan terindikasi pola generik. Kandidat diganti teks polos. |
| B14 | Low | `ThumbnailExtractor` | `f.read()` memuat seluruh file ke memori untuk regex DOTALL. File ratusan MB boros. |

## Keputusan desain

1. **Layer = Z gerakan extrude.** Aturan paling sederhana yang benar untuk z-hop dan lift. Alternatif yang pernah dipertimbangkan: deteksi dari komentar `;LAYER:` Cura (tidak universal) dan "Z naik setelah extrusi" (gagal untuk z-hop). Konsekuensi: file aneh yang benar-benar extrude di ketinggian lift tetap tercatat sebagai layer, itu perilaku yang jujur.
2. **Komentar slicer menang atas hitungan.** Komentar `layer_height` adalah konfigurasi asli slicer; mode-of-diffs hanya fallback. Hitungan tetap dipertahankan karena tidak semua slicer menulis komentar.
3. **Rebuild UI untuk tema/bahasa.** Menambal widget satu per satu rapuh (ada 30+ titik warna dan string). Destroy semua widget lalu bangun ulang lebih pendek dan selalu konsisten. State file aktif dipulihkan lewat `_sync_ui_to_parser`.
4. **Hook windnd hanya sekali.** `windnd.hook_drop_files` tidak idempoten; hook ganda membuka file dua kali per drop. Karena itu `_setup_dnd` tidak ikut dalam rebuild.
5. **Tanpa framework test.** Enam test regresi cukup dengan assert + loop. Fixture gcode kecil lebih berharga daripada mock Tkinter.
6. **Radiobutton menu pakai `StringVar` bersama** (`lang_var`, `theme_var`) agar penanda aktif selalu akurat tanpa logika manual.

## Limitasi yang disadari

- **Vase mode / spiral.** Z berubah di setiap gerakan sehingga setiap segmen jadi "layer" tersendiri; slider memuat ribuan layer. Belum ada solusi; kalau dikerjakan, mulai dari kuantisasi Z atau deteksi `;TYPE:Spiral`.
- **Software rendering.** Frame = gambar ulang seluruh segmen via PIL. Model besar berat saat drag. Solusi jangka panjang: naik ke OpenGL (mis. moderngl) atau cache bitmap per layer.
- **`first_layer_height` dari komentar tidak diparse**, hanya dari Z extrude pertama. Cukup akurat, tapi komentar `; first_layer_height =` diabaikan nilainya.
- **Windows-only** (windnd, iconbitmap). Port ke luar Windows butuh pengganti drag-drop dan ikon.

## Catatan repo

- `build/`, `dist/`, `__pycache__/` adalah artefak build, jangan commit. `.gitignore` sudah benar.
- `dist/GCodeViewer.exe` yang ada saat ini masih build 3.1.0. Build ulang setelah rilis 3.2.0.
- Versi single source of truth: `APP_VERSION`. Docstring module sengaja tidak bawa versi lagi (dulu tidak sinkron).
