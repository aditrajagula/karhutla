# Dokumentasi Layer Konteks Kawasan Hutan dan Lahan Gambut

## 1. Status Ketersediaan Saat Ini

> **Status:** Layer gambut tersedia; layer kawasan hutan resmi menyeluruh belum tersedia.
> GeoJSON lokal `backend/app/peat_kalimantan_big_official.geojson` mencakup 100 poligon gambut Kalimantan. Metadata tahun, sumber, lisensi, dan provenance layer tersebut belum tercatat pada manifest proyek dan harus dilengkapi berdasarkan sumber aslinya.
> Raster Hansen GFC lokal hanya tersedia untuk demonstrasi pada tile kecil sekitar Palangka Raya; cakupannya tidak memadai untuk segmentasi hutan seluruh Kalimantan.

## 2. Rujukan Sumber Resmi Nasional

Jika di masa mendatang tim ingin mengintegrasikan layer ini secara mandiri, gunakan hanya data resmi yang dapat diverifikasi:

1. **Peta Kawasan Hutan & Penutupan Lahan:**
   * **Instansi:** Kementerian Lingkungan Hidup dan Kehutanan (KLHK).
   * **Sumber Portal:** Geoportal MenLHK ([https://geoportal.menlhk.go.id](https://geoportal.menlhk.go.id)).
   * **Lapisan:** Kawasan Hutan Indonesia, Peta Penutupan Lahan (Land Cover) tahunan.
2. **Peta Kesatuan Hidrologis Gambut (KHG):**
   * **Instansi:** Badan Restorasi Gambut dan Mangrove (BRGM) & KLHK.
   * **Sumber Portal:** Geoportal PRIMS Gambut BRGM ([https://prims.brgm.go.id](https://prims.brgm.go.id)).
   * **Lapisan:** Peta Fungsi Ekosistem Gambut (Fungsi Lindung dan Fungsi Budidaya).

## 3. Integrasi Layer Gambut ke Peta

* Frontend memuat layer saat pengguna menyalakan kontrol `Poligon gambut`. Backend menyajikan `GET /api/v1/map-data/peatland`; geometri disederhanakan dengan toleransi 0.0001 derajat hanya untuk mempercepat render. File sumber tidak diubah dan bentuk yang disederhanakan tidak digunakan untuk klasifikasi titik.
* `GET /api/v1/map-data/classified-hotspots` menyajikan snapshot FIRMS dengan atribut klasifikasi `in_peat`, `peat_class`, dan `fire_risk_priority`. `GET /api/v1/map-data/firms-manifest` menyediakan metadata waktu dan cakupan snapshot.
* Kontrol peta memungkinkan menampilkan seluruh titik snapshot atau menyaringnya ke titik yang telah diklasifikasikan `in_peat=true`. Hasil klasifikasi tersebut berasal dari dataset snapshot yang disediakan, bukan dihitung ulang oleh frontend.
* `GET /api/v1/context-layers` mengembalikan cakupan dan status aktual layer hutan serta gambut:
  ```json
  {
    "forest_layer": {
      "available": false,
      "source": "Hansen GFC 2025 v1.13 (tile lokal demonstrasi) dan rujukan KLHK",
      "status_message": "Raster Hansen lokal hanya mencakup area kecil di sekitar Palangka Raya."
    },
    "peatland_layer": {
      "available": true,
      "source": "GeoJSON lokal peat_kalimantan_big_official.geojson",
      "status_message": "Layer poligon tersedia; tahun, lisensi, dan provenance belum tercatat."
    },
    "boundary_layer": {
      "available": true,
      "source": "Batas 5 provinsi Kalimantan (WGS84 EPSG:4326)",
      "status_message": "Geometri 5 provinsi Kalimantan aktif untuk filter spasial.",
      "feature_count": 5
    }
  }
  ```
* **Batas interpretasi:** Poligon gambut menunjukkan lokasi gambut, bukan area terbakar. Hotspot FIRMS menunjukkan anomali termal, bukan konfirmasi kebakaran. Pemetaan batas area terbakar memerlukan produk atau analisis burned-area tersendiri.
* Layer hutan dan gambut adalah klasifikasi berbeda. Jangan menyamakan tutupan pohon, kawasan hutan yang ditetapkan secara hukum, dan lahan gambut.
