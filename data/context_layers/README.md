# Dokumentasi Layer Konteks Kawasan Hutan dan Lahan Gambut

## 1. Status Ketersediaan Saat Ini

> **Status:** TERBATAS.
> Terdapat raster Hansen GFC lokal untuk demonstrasi pada tile kecil sekitar Palangka Raya. Cakupan tersebut tidak memadai untuk segmentasi tutupan hutan seluruh Kalimantan. Dataset resmi kawasan hutan dan layer hidrologis gambut belum tersedia.

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

## 3. Perilaku Aplikasi Saat Layer Belum Tersedia

* Antarmuka web dan API backend tidak mengklaim bahwa tile lokal mencakup seluruh Kalimantan. Statistik Hansen agregat juga ditandai sebagai data demonstrasi dan belum terverifikasi.
* `GET /api/v1/context-layers` mengembalikan cakupan dan status aktual layer hutan serta gambut:
  ```json
  {
    "forest_layer": {
      "available": false,
      "source": "Hansen GFC 2025 v1.13 (tile lokal demonstrasi) dan rujukan KLHK",
      "status_message": "Raster Hansen lokal hanya mencakup area kecil di sekitar Palangka Raya."
    },
    "peatland_layer": {
      "available": false,
      "source": "Badan Restorasi Gambut dan Mangrove (BRGM)",
      "status_message": "Dataset resmi kesatuan hidrologis gambut belum tersedia dari panitia/instansi."
    },
    "boundary_layer": {
      "available": true,
      "source": "Batas 5 provinsi Kalimantan (WGS84 EPSG:4326)",
      "status_message": "Geometri 5 provinsi Kalimantan aktif untuk filter spasial.",
      "feature_count": 5
    }
  }
  ```
* Pipeline FIRMS tidak bergantung pada layer konteks tersebut.
* **Prinsip Penting:** Aplikasi **TIDAK MENGKLAIM** anomali termal sebagai bukti deforestasi atau kebakaran hutan tanpa dataset tutupan lahan resmi yang terverifikasi.
