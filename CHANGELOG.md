# Changelog

Format [Keep a Changelog](https://keepachangelog.com/). Versi mengikuti `APP_VERSION` di `gcode_viewer.py`.

## [3.2.0] - 2026-11-08

Hasil audit menyeluruh terhadap parser, UI, dan UX. Dua bug kritis membuat file tertentu dirender salah sejak versi sebelumnya.

### Fixed

- **File Cura dirender kosong.** Parser mengabaikan `G92`, jadi file dengan absolute-E dan reset `G92 E0` per layer mengklasifikasi semua extrusion setelah reset pertama sebagai travel. Travel tersembunyi secara default, model tidak terlihat.
- **Baris tanpa spasi terbuang.** Tokenisasi memakai `line.split()`, sehingga `G1X10Y20E1` (flavor RepRap/Klipper) tidak dikenali. Kini memakai `WORD_RE` dan mengabaikan prefiks nomor baris `N`.
- **Layer palsu dari z-hop dan nozzle lift.** Setiap perubahan Z tercatat sebagai layer. Kini layer dideteksi dari Z gerakan extrude saja, jadi z-hop, lift awal, dan lift akhir tidak menggelembungkan jumlah layer.
- **Layer height salah timpa.** Hasil hitung mode-of-diffs menimpa nilai `layer_height` dari komentar slicer. Kini komentar slicer menang, hitungan jadi fallback. Regex juga tidak lagi salah cocok di dalam `first_layer_height`.
- **Thumbnail hilang di file CRLF.** Regex `…\d+\n` gagal pada file ber-ending `\r\n` (Cura di Windows). Kini `\r?\n`.
- **Ganti tema atau bahasa setengah jadi.** Panel dan menubar tetap memakai tema lama sampai restart, dan pesannya menyebut "language" untuk kedua kasus. Kini UI di-rebuild penuh saat itu juga, tanpa restart.
- **Menu Settings tanpa penanda aktif.** Radiobutton bahasa dan tema tidak memakai `variable` bersama, jadi tidak ada tanda centang. Kini ada.
- **Filament diparse tapi tidak tampil.** `filament used [mm]` kini muncul di panel Print Info.

### Changed

- Dialog About: daftar slicer dikoreksi menjadi PrusaSlicer, SuperSlicer, Cura, OrcaSlicer, Bambu Studio. Klaim lama "Elegoo" tidak punya implementasi.
- README: hapus klaim thumbnail Elegoo `;gimage:`/`;simage:`, catat dukungan LF dan CRLF.
- Kunci terjemahan tak terpakai (`restart_msg`, `thumb_error`) dihapus dari 12 bahasa.

### Added

- `tests/test_parser.py` + 5 fixture gcode: regresi untuk G92, baris tanpa spasi, z-hop, prioritas layer height, dan thumbnail CRLF.

## Sebelum 3.2.0

Riwayat tidak terlacak. Rekonstruksi dari kode, bukan dari catatan rilis:

- **3.1.0** - Fan speed editor, panel Print Info (layer height, durasi, fan, slicer), 12 bahasa, tema gelap/terang, thumbnail embedded.
- **3.0.0** - Basis aplikasi: parser gcode, viewport 3D software-rendered (Pillow), layer slider, screenshot export.
