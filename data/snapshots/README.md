# Penyimpanan Snapshot Lokal Tim

## 1. Status Dataset Panitia

> **Pemberitahuan:** Panitia Hackathon JOINTS 2026 **tidak menyediakan dataset apa pun**, termasuk snapshot benchmark nasional 7 hari.

## 2. Kebijakan Snapshot Lokal Tim

Sesuai arahan desain terbaru:
1. **Bukan Benchmark Resmi Panitia:** Seluruh snapshot yang tersimpan di direktori ini dilabeli secara eksplisit sebagai:
   `"snapshot_type": "TEAM_LOCAL_CAPTURE"`
   (Bukan data benchmark panitia).
2. **Kapan Snapshot Dibuat:** Snapshot dibuat otomatis oleh backend **hanya ketika** panggilan ke NASA FIRMS Area API berhasil mendapatkan data riil.
3. **Format Penyimpanan:**
   * File data mentah: `snapshot_team_<YYYYMMDD_HHMMSS>.csv`
   * File manifest verifikasi: `manifest_<YYYYMMDD_HHMMSS>.json`
4. **Metadata Manifest yang Wajib Disimpan:**
   * `source`: Sumber data (misal `NASA_FIRMS_VIIRS`)
   * `sensor_product`: Sensor satelit (misal `VJ114IMGTDL_NRT` / NOAA-20)
   * `fetched_at_utc`: Waktu penarikan data dari server NASA dalam format ISO-8601 UTC
   * `observation_date_range`: Rentang tanggal observasi `min` dan `max`
   * `query_parameters`: Parameter kueri yang dikirimkan (area bounding box, rentang hari)
   * `record_count`: Jumlah baris/rekaman yang diterima
   * `checksum_sha256`: Hash integritas SHA-256 dari file CSV mentah
   * `label`: `"Snapshot Hasil Pengambilan Mandiri Tim (Bukan Benchmark Panitia)"`

## 3. Perilaku Saat Offline / API Gagal

* Jika `FIRMS_MAP_KEY` belum dikonfigurasi atau API FIRMS tidak merespons:
  * Sistem memeriksa apakah terdapat snapshot tim lokal yang valid di direktori ini.
  * **Jika ada snapshot:** Sistem beralih ke snapshot terbaru, menetapkan status data menjadi `"FALLBACK_LOCAL_SNAPSHOT"`, dan menampilkan timestamp pengambilan secara transparan.
  * **Jika belum ada snapshot sama sekali:** Sistem mengembalikan status `"NO_DATA_AVAILABLE"` disertai pesan instruksi: *"Koneksi API gagal dan belum ada snapshot lokal tim yang tersimpan. Harap konfigurasikan FIRMS_MAP_KEY di .env atau lakukan sinkronisasi awal saat online."*
