# Sumber dan Verifikasi Geometri Batas Indonesia

Dokumen ini mencatat asal-usul, spesifikasi, dan metode verifikasi data batas wilayah Indonesia yang digunakan pada modul geospasial pipeline.

## 1. Sumber Data Saat Ini

* **File:** `data/boundaries/indonesia_provinces.geojson`
* **Sumber Penyedia:** Dataset batas 34 Provinsi Indonesia (repositori publik `superpikar/indonesia-geojson`, turunan dari GADM / CartoDB).
* **Format:** GeoJSON (RFC 7946).
* **Sistem Koordinat (CRS):** WGS84 (EPSG:4326), urutan sumbu `[longitude, latitude]`.
* **Tipe Geometri:** 34 fitur `MultiPolygon` yang mencakup pulau-pulau di 34 provinsi Indonesia.
* **Ukuran File:** ~343 KB (teroptimasi dan tergeneralisasi untuk komputasi cepat in-memory).

## 2. Cara Verifikasi Geometri

Geometri diverifikasi menggunakan library `shapely` dengan langkah:
1. Memuat seluruh fitur poligon GeoJSON.
2. Memeriksa validitas topologi (`geom.is_valid`).
3. Menerapkan `shapely.validation.make_valid()` bila ditemukan verteks batas yang menyentuh diri sendiri (*self-intersection*).
4. Membangun indeks spasial `STRtree` untuk mempercepat operasi *Point-in-Polygon* (PiP).

## 3. Sumber Alternatif Resmi Nasional (Rujukan Instansi Pemerintah)

Untuk integrasi level produksi dengan sertifikasi nasional:
1. **Badan Informasi Geospasial (BIG) / Ina-Geoportal:**
   * URL: [https://tanahair.indonesia.go.id](https://tanahair.indonesia.go.id)
   * Lapisan: Peta Rupa Bumi Indonesia (RBI) Batas Wilayah Administrasi.
2. **Badan Pusat Statistik (BPS):**
   * Peta Wilayah Kerja Statistik (Wilkerstat).
3. **Natural Earth Data:**
   * URL: [https://www.naturalearthdata.com](https://www.naturalearthdata.com)
   * Lapisan: 1:10m Admin 0 Countries (`IDN` / Indonesia).

## 4. Batasan & Caveat

Data poligon batas ini digunakan murni untuk memfilter titik anomali satelit agar tidak mencakup laut lepas dan negara tetangga yang terbawa oleh *bounding box* kueri NASA FIRMS. Data ini **bukan penentu sengketa perbatasan teritorial negara**.
