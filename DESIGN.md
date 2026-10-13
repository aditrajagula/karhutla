# DSG — FireGuard Design System
### Versi 2.0 · Pendamping `PRD.md` · Subtema Sustainability · Hackathon JOINTS 2026
### Antislop UI Mode: DURING (Human-Crafted GIS Dashboard)

---

## 0. Prinsip Desain & Identitas

1. **Kejujuran Data Spasial:** Setiap simbol dan kartu membawa metadata sumber, waktu observasi, dan sensor. Desain tidak pernah menyamarkan ketidakpastian deteksi anomali termal.
2. **Skala Suhu Termal Tiga Tingkat (Kuning, Oranye, Merah):** Anomali termal satelit diklasifikasikan berdasarkan intensitas suhu terang (*Brightness Temperature*) dan daya radiasi api (*Fire Radiative Power* / FRP).
3. **Warna Hijau Tetap Ada, Namun Memiliki Makna Presisi:**
   * **Hijau DIGUNAKAN UNTUK:** Identitas merek (*brand*), status sinkronisasi sistem (*API Live OK / sync*), verifikasi laporan lapangan konsisten, aksen rute/interaksi, dan layer poligon konteks tutupan kanopi hutan tropis.
   * **Hijau TIDAK PERNAH DIGUNAKAN UNTUK:** Menandai wilayah titik peta sebagai "aman / bebas api". Ketiadaan deteksi bukan bukti ketiadaan kebakaran. Wilayah tanpa laporan disajikan dengan abu-abu netral.
4. **Antarmuka Dark GIS Berkontras Tinggi (Inspirasi Dashboard Modern):** Mengadopsi tata letak kanvas gelap (*charcoal slate*) yang tenang dan tajam, kartu mengambang (*floating detail card*) bersudut membulat halus (*16px*), pin peta dengan tag indikator nilai, serta filter *pill* yang rapi dan mudah dioperasikan di lapangan.
5. **Ketenangan Visual (Anti-Alarmisme):** Menghindari animasi api berkedip berlebihan atau gradien neon artifisial. Visualisasi mengajak pengguna meneliti data secara objektif.

---

## 1. Token Warna

### 1.1 Netral & Permukaan (Dark-First GIS Theme)
Terinspirasi dari layout dasbor spasial berkontras tinggi dengan keterbacaan prima:

| Token | Light Mode | Dark Mode (Default Dasbor) | Kegunaan & Rasio Kontras |
|---|---|---|---|
| `--fg` | `#111827` | `#FAFAFA` | Teks utama, judul (kontras 15:1 di Dark) |
| `--fg-muted` | `#64748B` | `#A1A1AA` | Teks sekunder, label metadata, satuan |
| `--surface-0` | `#F8FAFC` | `#121214` | Kanvas dasar peta & latar aplikasi |
| `--surface-1` | `#FFFFFF` | `#18181B` | Sidebar kontrol, floating detail card |
| `--surface-2` | `#F1F5F9` | `#27272A` | Search input bar, chip pill, dropdown filter |
| `--border` | `#E2E8F0` | `#3F3F46` | Garis batas tipis 1px penegas struktur |
| `--border-subtle` | `#CBD5E1` | `#27272A` | Batas sekunder antar elemen chip |

---

### 1.2 Skala Hotspot Termal (Suhu & FRP Satelit VIIRS/MODIS)
Skala tiga warna intuitif untuk anomali termal satelit. Setiap tingkat memiliki warna inti, warna halo transparan, dan label baku:

| Kategori Suhu | Token Inti | Token Halo / Glow Ring | Nilai Hex | Ambang Ukur Teknis | Penyajian Visual pada Peta |
|---|---|---|---|---|---|
| **Hotspot Suhu Rendah** | `--ev-hotspot-low` | `--ev-hotspot-low-halo` | `#EAB308` (Kuning Amber) | FRP $< 15\text{ MW}$ atau Brightness $< 325\text{ K}$ | Lingkaran 8 px kuning + halo tipis 14 px (20% opasitas) |
| **Hotspot Suhu Sedang** | `--ev-hotspot-mid` | `--ev-hotspot-mid-halo` | `#F97316` (Oranye Termal) | FRP $15 - 50\text{ MW}$ atau Brightness $325 - 350\text{ K}$ | Lingkaran 10 px oranye + halo 18 px (24% opasitas) |
| **Hotspot Suhu Tinggi** | `--ev-hotspot-high` | `--ev-hotspot-high-halo` | `#EF4444` (Merah Intens) | FRP $> 50\text{ MW}$ atau Brightness $> 350\text{ K}$ | Lingkaran 12 px merah + halo 22 px (30% opasitas) + ring seleksi |

*Catatan Legenda Wajib:* "Warna mengindikasikan intensitas daya pancar termal sensor satelit (FRP), bukan konfirmasi luas kobaran api riil di lapangan."

---

### 1.3 Peran & Penerapan Warna Hijau (Presisi & Tanpa Salah Paham)

| Peran Token | Token | Nilai Hex | Makna & Penggunaan |
|---|---|---|---|
| **Brand & Aksen Utama** | `--brand` / `--accent-mint` | `#10B981` (Mint Emerald) | Tombol aksi primer, highlight aktif, garis rute pemantauan |
| **Status API Live OK** | `--status-live` | `#10B981` (Teks) / `#064E3B` (Bg) | Indikator "Live FIRMS API Aktif & Terhubung" (mirip chip `Open 'til 6pm`) |
| **Laporan Terverifikasi** | `--st-verified` | `#059669` | Diamond laporan warga yang telah dicocokkan konsisten dengan lapangan |
| **Konteks Kanopi Hutan** | `--ctx-forest` | `rgba(16, 185, 129, 0.12)` | Poligon kawasan hutan lindung/konservasi (lapisan latar belakang) |

---

### 1.4 Kelas Bukti Multi-Modal (Bentuk + Pola + Warna)
Sesuai kaidah aksesibilitas, warna tidak pernah menjadi satu-satunya pembeda:

| Kelas Bukti | Geometri Simbol | Pola & Gaya Garis | Skema Warna |
|---|---|---|---|
| **A. Deteksi Satelit FIRMS** | **Lingkaran (Circle)** + Halo | Cincin luar solid/dashed sesuai confidence | Kuning / Oranye / Merah (sesuai intensitas §1.2) |
| **B. Laporan Lapangan Warga** | **Belah Ketupat (Diamond)** | Outline putus-putus (menunggu) / Solid (terverifikasi) | Ungu Indigo (`#818CF8`) / Hijau (`#059669`) |
| **C. Poligon Perubahan Tutupan** | **Poligon Spasial** | **Arsir diagonal 45°** | Cyan Teal (`#06B6D4` @ 20%) |

---

### 1.5 Konteks Spasial & Tanpa Data
| Token | Nilai | Penjelasan |
|---|---|---|
| `--ctx-peat` | `rgba(180, 83, 9, 0.14)` + garis putus-putus | Batas kesatuan hidrologis gambut (KHG) |
| `--ctx-admin` | `#52525B` @ 1px | Garis batas kabupaten/provinsi Indonesia |
| `--nodata` | `rgba(161, 161, 170, 0.35)` | Abu-abu netral untuk area belum terjamah pelaporan |

---

## 2. Tipografi

* **Font Utama UI:** `Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif.
* **Font Angka & Metrik:** `Inter` dengan properti `font-variant-numeric: tabular-nums` (mencegah teks bergetar saat angka berganti).
* **Font Data Koordinat:** `JetBrains Mono`, `ui-monospace`, `Menlo`, monospace.

### Skala Hierarki Tipografi:
* **H1 / Judul Panel Utama:** 16px / Semi-Bold (600) / Tracking -0.2px / `--fg`
* **Headline Kartu Detail:** 15px / Semi-Bold (600) / `--fg`
* **Label Field & Filter Pill:** 12.5px / Medium (500) / `--fg`
* **Body / Keterangan Fakta:** 13px / Regular (400) / Leading 1.5 / `--fg-muted`
* **Metadata & Badge Angka:** 11px / Semi-Bold (600) / Mono / `--fg-muted`

---

## 3. Spacing, Radius, Elevasi, dan Struktur Kartu

### 3.1 Radius Terkalibrasi (Sesuai Referensi Dasbor):
* **Pill Radius (`--r-pill: 999px`):** Chip filter kategori (`Kuning`, `Oranye`, `Merah`, `Semua`), dropdown filter (`Live API`, `Rentang 2 Hari`).
* **Tag Marker Map (`--r-tag: 6px`):** Kotak label angka FRP/suhu kecil di bawah pin peta (seperti tag `100`, `80` pada gambar referensi).
* **Input & Tombol (`--r-md: 10px`):** Search input bar, tombol aksi sekunder outline.
* **Container & Floating Card (`--r-lg: 16px`):** Kartu detail hotspot melayang di atas peta dan container sidebar kiri.

### 3.2 Elevasi & Shadow (Dose Cap Antislop):
* **Matte Flat (`0px`):** Seluruh elemen input, chip, dan daftar baris di sidebar.
* **Elevasi Kartu Melayang (`--e-floating`):** `0 12px 32px -4px rgba(0, 0, 0, 0.45), 0 4px 12px -2px rgba(0, 0, 0, 0.30)` khusus untuk Floating Detail Card di atas peta.
* **Border Penegas:** 1px solid `--border` (`#3F3F46`) di sekeliling kartu agar kontras terhadap basemap.

---

## 4. Symbologi Peta & Marker Tagging

Mengadaptasi gaya penandaan peta dari referensi desain:

1. **Struktur Pin Marker Komposit:**
   * **Bagian Atas (Icon Pin Circle):** Lingkaran 24×24px dengan latar warna gelap/putih solid, di dalamnya terdapat titik warna sesuai suhu (Kuning/Oranye/Merah).
   * **Bagian Bawah (Value Tag Pill):** Pill badge kecil menempel tepat di bawah pin bertuliskan nilai FRP (contoh: `🔥 42 MW` atau `335 K`), berlatar belakang `#18181B` dengan border halus `#3F3F46`.
2. **State Interaksi Marker:**
   * **Default:** Opasitas 0.9, ukuran proporsional.
   * **Hover:** Kursor pointer, ring halo luar membesar halus (+4px).
   * **Selected:** Ring luar putih kontras 2px + Floating Detail Card otomatis terbuka mengarah ke titik tersebut.

---

## 5. Komponen Utama

### 5.1 Sidebar Kontrol (Kiri)
* **Header Brand:** Logo minimalis + Judul "FireGuard" + Badge Live Status warna hijau mint (`● Live API`).
* **Search Input:** Input pencarian kabupaten/provinsi berlatar `#27272A` dengan ikon kaca pembesar di sisi kiri.
* **Horizontal Filter Bar (Pill Group):**
  * Pill dropdown: `Status Suhu` (Kuning, Oranye, Merah).
  * Pill dropdown: `Sensor VIIRS` (NOAA-20, Suomi NPP).
  * Pill tombol: `Rentang Waktu`.
* **Hotspot Item Cards (Daftar Titik):**
  * Avatar sirkular dengan warna tingkat suhu (Kuning / Oranye / Merah).
  * Baris 1: Nama Kabupaten/Provinsi & Nilai FRP.
  * Baris 2: Waktu observasi UTC & Tingkat Keyakinan (*Confidence*).
  * Sisi kanan: Tag status ringkas.

### 5.2 Floating Detail Card (Mengambang di Atas Peta)
Komponen kartu terinspirasi langsung dari modal detail "Adidas" pada gambar referensi pengguna:
* **Container:** Berada di atas peta (`z-index: 50`), posisi responsif, `background: #18181B`, `border-radius: 16px`, `border: 1px solid #3F3F46`.
* **Header Kartu:**
  * Avatar lingkaran satelit + Judul Titik Anomali Termal.
  * Baris koordinat dan status waktu akuisisi beraksen hijau mint.
* **Baris Chip Metrik:**
  * Chip 1: `🔥 FRP: [Nilai] MW`
  * Chip 2: `🌡️ Suhu: [Nilai] K`
  * Chip 3: `🛰️ [Satelit / Sensor]`
* **Blok Provenance & Deskripsi Faktual:**
  * Judul: "Deteksi Sensor Satelit VIIRS"
  * Poin 1: Sumber dataset NASA FIRMS Area API.
  * Poin 2: Waktu observasi dibandingkan waktu data diterima server.
  * Poin 3: Konteks tumpang susun (di dalam kawasan gambut / non-gambut).
* **Tombol Aksi Bawah:**
  * Tombol penuh bergaris tepi: `Salin Koordinat & Metadata Lengkap`.

---

## 6. Pola Mikrocopy Faktual (Bahasa Indonesia)

* **Deteksi Satelit:** "Anomali Termal Satelit" (Bukan "Titik Kebakaran Pasti").
* **Confidence Satelit:** "Tingkat Keyakinan Sensor: Nominal / Tinggi" (Bukan "Probabilitas Kebakaran 80%").
* **Status Hijau:** "Koneksi NASA FIRMS Aktif" (Bukan "Wilayah Dinyatakan Aman").
* **Wilayah Tanpa Deteksi:** "Tidak ada anomali termal terdeteksi pada filter ini. Hal ini bukan jaminan ketiadaan api di lapangan."

---

## 7. Aksesibilitas & Uji Kontras

1. **Rasio Kontras Minimum:**
   * Teks putih `#FAFAFA` di atas permukaan `#18181B` = **15.2 : 1** (Lolos WCAG AAA).
   * Teks sekunder `#A1A1AA` di atas `#18181B` = **6.8 : 1** (Lolos WCAG AA).
   * Titik Kuning `#EAB308` di atas peta gelap `#121214` = **8.4 : 1** (Sangat kontras).
   * Titik Oranye `#F97316` di atas peta gelap `#121214` = **6.2 : 1** (Sangat kontras).
   * Titik Merah `#EF4444` di atas peta gelap `#121214` = **5.1 : 1** (Lolos WCAG AA).
2. **Kemandirian Warna:** Setiap kartu dan tooltip selalu memuat label teks tertulis (`Suhu Rendah`, `Suhu Sedang`, `Suhu Tinggi`), sehingga pengguna buta warna tetap dapat membaca data secara akurat.
3. **Keyboard & Focus:** Outline focus ring 2px warna hijau mint (`#10B981`) dengan offset 2px pada semua elemen interaktif.

---

## 8. Snippet Token CSS (Siap Digunakan)

```css
:root {
  /* Netral & Permukaan (Dark GIS Modern) */
  --fg: #FAFAFA;
  --fg-muted: #A1A1AA;
  --surface-0: #121214;
  --surface-1: #18181B;
  --surface-2: #27272A;
  --border: #3F3F46;
  --border-subtle: #27272A;

  /* Skala Hotspot Termal Tiga Tingkat */
  --ev-hotspot-low: #EAB308;        /* Kuning: Suhu/FRP Rendah (<15 MW) */
  --ev-hotspot-low-halo: rgba(234, 179, 8, 0.22);
  --ev-hotspot-mid: #F97316;        /* Oranye: Suhu/FRP Sedang (15-50 MW) */
  --ev-hotspot-mid-halo: rgba(249, 115, 22, 0.26);
  --ev-hotspot-high: #EF4444;       /* Merah: Suhu/FRP Tinggi (>50 MW) */
  --ev-hotspot-high-halo: rgba(239, 68, 68, 0.32);

  /* Aksen Hijau (Brand, Status API Live, Tutupan Hutan) */
  --brand: #10B981;
  --accent-mint: #10B981;
  --status-live: #10B981;
  --ctx-forest: rgba(16, 185, 129, 0.12);
  --st-verified: #059669;

  /* Kelas Bukti Tambahan */
  --ev-report: #818CF8;             /* Diamond Laporan Warga */
  --ev-coverchange: #06B6D4;        /* Poligon Perubahan Tutupan */
  --ctx-peat: rgba(180, 83, 9, 0.14);
  --nodata: rgba(161, 161, 170, 0.35);

  /* Radius Elemen Berdasarkan Hierarki */
  --r-tag: 6px;
  --r-md: 10px;
  --r-lg: 16px;
  --r-pill: 999px;

  /* Elevasi Khusus Floating Elements */
  --e-floating: 0 12px 32px -4px rgba(0, 0, 0, 0.45), 0 4px 12px -2px rgba(0, 0, 0, 0.30);

  /* Tipografi */
  --font-ui: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
}

/* Light Theme Companion (Bila Diperlukan) */
.theme-light {
  --fg: #111827;
  --fg-muted: #64748B;
  --surface-0: #F8FAFC;
  --surface-1: #FFFFFF;
  --surface-2: #F1F5F9;
  --border: #E2E8F0;
  --border-subtle: #CBD5E1;
  --e-floating: 0 12px 32px -4px rgba(0, 0, 0, 0.12), 0 4px 12px -2px rgba(0, 0, 0, 0.06);
}
```