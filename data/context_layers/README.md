# Dokumentasi Layer Konteks Kawasan Hutan dan Lahan Gambut

## 1. Status Ketersediaan Saat Ini

> **Status:** BELUM TERSEDIA (OPSIONAL).
> Panitia Hackathon JOINTS 2026 tidak menyediakan layer spasial tutupan hutan maupun peta hidrologis gambut.

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

* Antarmuka web dan API backend memperlakukan layer konteks ini sebagai komponen opsional yang dinonaktifkan secara anggun (*gracefully disabled*).
* Status API: `GET /api/v1/context-layers` mengembalikan status:
  ```json
  {
    "forest_layer_available": false,
    "peatland_layer_available": false,
    "status_message": "Layer konteks kawasan hutan dan gambut belum tersedia dari sumber resmi panitia/instansi."
  }
  ```
* Pipeline deteksi hotspot NASA FIRMS tetap beroperasi 100% tanpa hambatan.
* **Prinsip Penting:** Aplikasi **TIDAK MENGKLAIM** anomali termal sebagai bukti deforestasi atau kebakaran hutan tanpa dataset tutupan lahan resmi yang terverifikasi.
