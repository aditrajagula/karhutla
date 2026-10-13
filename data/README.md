# Direktori Data Spasial & Snapshot (JOINTS 2026)

Direktori ini digunakan untuk menyimpan:

1. `snapshots/`:
   - Berkas CSV atau GeoJSON 7 hari yang dibagikan oleh panitia Hackathon JOINTS 2026 sebagai benchmark nasional seragam.
   - Berfungsi sebagai mode fallback offline ketika API key atau layanan NASA FIRMS tidak tersedia.

2. `boundaries/`:
   - Batas administratif resmi Indonesia (Provinsi, Kabupaten/Kota) untuk memfilter bounding box FIRMS agar tidak menyertakan titik dari negara tetangga.
   - Layer spasial kawasan hutan dan lahan gambut (jika disediakan oleh panitia) sebagai konteks kedekatan spasial.
