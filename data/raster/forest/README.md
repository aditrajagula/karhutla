# Panduan dan Spesifikasi Dataset GLAD Forest Extent 2020

## 1. Identitas dan Sumber Resmi Dataset
- **Nama Dataset**: GLAD Global Land Cover and Land Use Change 2000–2020 (GLCLUC2020)
- **Layer**: Forest Extent 2020 (`Forest_extent_2020`)
- **Institusi/Penyedia**: Global Land Analysis and Discovery (GLAD) Lab, Department of Geographical Sciences, University of Maryland (UMD).
- **Halaman Resmi**: [https://glad.umd.edu/dataset/GLCLUC2020](https://glad.umd.edu/dataset/GLCLUC2020)
- **Direktori Berkas Resmi**: [https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/](https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/)
- **Publikasi Rujukan**:
  - Potapov, P., Hansen, M. C., Pickens, A., Hernandez-Serna, A., Tyukavina, A., Turubanova, S., Zalles, V., Li, X., Khan, A., Stolle, F., Harris, N., Song, X.-P., Baggett, A., Kommareddy, I., & Kommareddy, A. (2022). *The global 2000-2020 land cover and land use change dataset derived from the Landsat archive: first results*. Frontiers in Remote Sensing, 3, 856903. [DOI: 10.3389/frsen.2022.856903](https://doi.org/10.3389/frsen.2022.856903).
  - Potapov, P., et al. (2020). *Mapping and monitoring global forest canopy height through integration of GEDI and Landsat data*. Remote Sensing of Environment, 253, 112165.

## 2. Karakteristik Teknis Dataset
- **Format Berkas**: Cloud-Optimized GeoTIFF (.tif)
- **Sistem Koordinat (CRS)**: Geografis WGS84 (`EPSG:4326`)
- **Resolusi Spasial**: 30 meter per piksel (~0.00025° atau 0.9 arc-second pada khatulistiwa)
- **Dimensi Grid**: Tile global 10° × 10° (40.000 × 40.000 piksel per tile)
- **Tipe Data**: Byte (UInt8)
- **Definisi Nilai Piksel**:
  - `1`: **FOREST** (Tutupan pohon dengan tinggi kanopi ≥ 5 meter pada tahun 2020, selaras dengan baseline FAO FRA; mencakup agroforestri dan kebun pohon; mengecualikan area hutan yang belum berstok).
  - `0`: **NON_FOREST** (Bukan tutupan hutan berkanopi ≥ 5 meter).
  - `255` / `NoData`: **UNKNOWN** (Badan air, laut, atau di luar cakupan pemrosesan).

> [!IMPORTANT]
> **Keterbatasan Ilmiah & Status Waktu**:
> Dataset ini merepresentasikan kondisi biofisik tutupan kanopi pohon pada tahun **2020**, bukan kondisi real-time terkini.
> Klasifikasi `FOREST` atau `NON_FOREST` tidak menyimpulkan status legalitas lahan dan bukan jaminan bahwa suatu area aman dari kebakaran.

## 3. Tile yang Dibutuhkan untuk Wilayah Kalimantan
Wilayah daratan 5 provinsi Kalimantan (Indonesia) berada pada rentang koordinat geografis lintang 5°LU hingga 5°LS dan bujur 108°BT hingga 120°BT.
Berdasarkan sistem grid 10° × 10° GLAD (menggunakan koordinat sudut barat laut / top-left corner):

| ID Tile | Cakupan Geografis (WGS84) | Area di Kalimantan | Tautan Unduh Resmi Langsung |
| :--- | :--- | :--- | :--- |
| `00N_100E.tif` | Lintang: -10° s.d. 0°, Bujur: 100° s.d. 110° | Kalimantan Barat bagian Selatan | `https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/00N_100E.tif` |
| `00N_110E.tif` | Lintang: -10° s.d. 0°, Bujur: 110° s.d. 120° | Kalimantan Tengah, Kalimantan Selatan, Kalimantan Timur bagian Selatan | `https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/00N_110E.tif` |
| `10N_100E.tif` | Lintang: 0° s.d. 10°, Bujur: 100° s.d. 110° | Kalimantan Barat bagian Utara | `https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/10N_100E.tif` |
| `10N_110E.tif` | Lintang: 0° s.d. 10°, Bujur: 110° s.d. 120° | Kalimantan Utara, Kalimantan Timur bagian Utara | `https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/10N_110E.tif` |

## 4. Langkah Pengunduhan Manual
1. Buat direktori penyimpanan: `data/raster/forest/`
2. Unduh 4 berkas GeoTIFF di atas langsung dari repositori resmi University of Maryland:
   ```bash
   # Contoh perintah unduh menggunakan curl di folder data/raster/forest/:
   curl -O https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/00N_100E.tif
   curl -O https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/00N_110E.tif
   curl -O https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/10N_100E.tif
   curl -O https://glad.umd.edu/users/Potapov/GLCLUC2020/Forest_extent_2020/10N_110E.tif
   ```
3. Pastikan berkas GeoTIFF diletakkan di direktori ini (`data/raster/forest/`).
4. Setelah berkas terunduh, endpoint `/api/v1/context-layers` dan modul pembaca `glad_forest_reader` akan otomatis mendeteksi ketersediaan raster dan melayani lookup koordinat secara instan.
