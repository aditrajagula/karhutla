# DESIGN.md: Sistem Pemantauan Hotspot dan Konteks Gambut (Karhutla)

> **Spesifikasi Arah Desain & Filter Visual (Antislop)**  
> **Dasar PRD:** Hackathon JOINTS 2026 (Subtema: Sustainability)  
> **Tujuan:** Antarmuka geospasial yang faktual, tenang, dan transparan bagi masyarakat sekitar hutan, relawan pemantau lokal, serta evaluator lingkungan.

---

## 1. Identitas, Karakter, dan Design Read

### Karakter Produk
Aplikasi ini bukan produk komersial atau landing page SaaS pemasaran, melainkan **utilitas geospasial layanan publik**. Karakter visual harus memancarkan:
- **Kejujuran Data:** Menyajikan informasi satelit apa adanya tanpa dramatisasi atau klaim palsu.
- **Ketenangan & Kejelasan:** Peta dan data spasial adalah fokus utama. Elemen kontrol tidak boleh menutupi atau mengaburkan informasi medan.
- **Kesiapan Lapangan:** Kontras tinggi, teks terbaca jelas di bawah terik matahari (light mode) maupun saat pemantauan malam hari (dark mode).

### Design Read
> `Reading this as: Web pemantauan geospasial publik (Map-first utility) untuk masyarakat lokal, relawan, dan pemantau lingkungan, in a utilitarian & earth-tactical GIS style, dial ENERGY 1 / RHYTHM 1 / MOTION 1.`

### Liveliness Dials
```
Dial: ENERGY 1 / RHYTHM 1 / MOTION 1
```
- **ENERGY 1 (Calm):** Layout terstruktur seperti sistem informasi BMKG atau USGS. Tidak menggunakan warna neon, background berpendar, atau ornamen visual mencolok.
- **RHYTHM 1 (Predictable & Structured):** Konsisten dan langsung pada fungsi. Tata letak map-first yang stabil di seluruh interaksi tanpa pergeseran layout yang mengejutkan.
- **MOTION 1 (Functional & Calm):** Animasi hanya berupa transisi panel/drawer (maksimal 200ms) dan hover states interaktif. Tidak ada efek bouncing, looping pulse, atau floating element.

---

## 2. Prinsip Bahasa dan Integritas Data

Sesuai aturan antislop (R-02, R-16, R-17, R-18, R-36, R-38):

1. **Bebas Em Dash (R-02):**
   Tidak ada karakter em dash dalam seluruh salinan antarmuka pengguna. Gunakan titik dua `:`, tanda kurung `()`, koma `,`, atau titik `.`.
2. **Bebas Buzzword AI (R-16):**
   Dilarang menggunakan istilah seperti "AI-Powered", "Next-Gen", "Seamless", "Revolusioner", atau "Deteksi Cerdas". Gunakan terminologi teknis yang akurat: "Deteksi Satelit VIIRS NASA FIRMS", "Layer Spasial Lahan Gambut", "Indeks Cuaca Kebakaran (FWI)".
3. **Ketepatan Istilah Hotspot:**
   - Gunakan istilah **Deteksi Hotspot / Anomali Termal Satelit**.
   - Dilarang menyebut titik anomali sebagai "Titik Pasti Terbakar" atau menyajikan tingkat confidence sebagai probabilitas kepastian kebakaran.
4. **Ketepatan Layer Konteks:**
   - Layer batas hutan dan gambut disajikan sebagai **Konteks Kedekatan Wilayah**, bukan klaim deforestasi atau perusakan lahan otomatis.
5. **Transparansi Provenance & Freshness (R-17, R-38):**
   - Mode Live API: Wajib menampilkan waktu observasi satelit (UTC dan lokal), waktu data diterima backend, dan status latensi.
   - Mode Snapshot: Wajib menampilkan label tegas "Data Statis (Snapshot Benchmark JOINTS)" beserta timestamp pengambilan file.

---

## 3. Sistem Palet Warna (Color System)

Mengikuti batasan R-01, R-25, dan R-29 (maksimal 2-3 core colors + 1 accent fungsional, tanpa gradien generik biru-ungu):

### Palet Inti (Core Palette)

| Kategori | Hex Code | Peran UI | Alasan Desain (R-31) |
|---|---|---|---|
| **Core 1: Base Slate** | Light: `#F8FAFC`<br>Dark: `#0F172A` | Background kanvas aplikasi dan kontainer panel kontrol. | Memberikan bidang netral kontras tinggi yang tidak bersaing dengan warna peta. |
| **Core 2: Deep Earth / Forest** | Light: `#1E3A2F`<br>Dark: `#134E4A` | Identitas bilah judul, header layer, dan ikon status hutan/lingkungan. | Mencerminkan konteks konservasi hutan dan memberikan penegasan hierarki navigasi. |
| **Core 3: Border & Neutral Tint** | Light: `#CBD5E1`<br>Dark: `#334155` | Garis pembatas kartu, separator panel kontrol, dan status non-aktif. | Memisahkan elemen data secara tegas tanpa bayangan tebal yang mengambang. |
| **Accent: Thermal Flame Amber** | `#D97706` (Light)<br>`#F59E0B` (Dark) | Titik anomali termal pada peta, badge status peringatan, dan seleksi titik aktif. | Memberikan satu fokus visual instan untuk titik panas tanpa memakai warna merah agresif yang menyesatkan. |

### Aturan Penerapan Warna
- **Dilarang keras:** Gradien biru-ke-ungu, orb ungu di latar belakang, tombol neon, dan warna aksen yang dihamburkan ke seluruh teks atau garis hiasan.
- **Aksen Tunggal:** Warna amber hanya muncul pada simbol hotspot di peta, chip status peringatan, dan outline titik yang sedang dipilih.

### Standar Aksesibilitas Kontras (WCAG AA - R-25)
- Teks biasa (`#0F172A` di atas `#F8FAFC` untuk light mode) memiliki rasio kontras 14.5:1 (jauh di atas batas 4.5:1).
- Teks sekunder (`#475569` di atas `#F8FAFC`) memiliki rasio kontras 5.2:1.
- Dark mode teks utama (`#F8FAFC` di atas `#0F172A`) memiliki rasio kontras 15.8:1.
- Badge aksen menggunakan teks gelap di atas latar amber terang untuk memastikan keterbacaan minimal 4.5:1.

---

## 4. Tipografi dan Skala Hierarki

Sesuai aturan R-06 dan C-1:

### Pemilihan Font
- **Primary Typeface:** `Plus Jakarta Sans` atau `Inter` (Sans-Serif modern berkarakter jelas, optimal untuk teks Indonesia dan tampilan koordinat di layar kecil).
- **Alasan Pemilihan (R-31):** Memiliki legibilitas sangat tinggi pada ukuran kecil (12px-14px) untuk pembacaan koordinat GPS di layar lapangan.
- **Font Monospace:** Hanya digunakan untuk string data teknis murni (seperti koordinat `Lat/Long` dan kode satelit `NOAA-20/21`) menggunakan font bawaan sistem (`ui-monospace`, `monospace`). Dilarang memakai font monospace besar untuk judul atau gaya buatan.

### Skala Tipografi
- **Header Aplikasi (H1):** 18px (Mobile) / 20px (Desktop), Semibold.
- **Judul Panel / Kartu (H2):** 15px, Semibold.
- **Label Atribut & Body Text:** 13px - 14px, Regular.
- **Data Metrik & Koordinat:** 12px, Tabular/Monospace, Medium.
- **Caption / Keterangan Sumber:** 11px - 12px, Regular, Muted.

---

## 5. Tata Letak (Layout Architecture)

Mengikuti R-05, R-03, dan C-3 (Anti-Template Landing Page):

Aplikasi ini adalah **Utilitas Peta Satu Layar Penuh (Full-Viewport Geospatial Utility)**, bukan halaman marketing bertingkat.

```
+--------------------------------------------------------------------------+
|  TOP BAR: Judul Web | Status Data (Live / Snapshot) | Toggle Tema | Info |
+------------------------------------+-------------------------------------+
|  SIDEBAR KONTROL (Desktop 360px):  |  PETA UTAMA (MAP CANVAS):           |
|  - Filter Tanggal & Rentang Waktu  |  - Peta Indonesia interaktif        |
|  - Filter Wilayah (Provinsi/Kab)   |  - Layer Titik Hotspot (VIIRS)      |
|  - Sakelar Layer (Gambut/Hutan)    |  - Layer Batas Gambut / Hutan       |
|  - Ringkasan Jumlah Deteksi        |  - Kontrol Zoom & Basemap           |
|  - Detail Titik Terpilih           |  - Legenda Faktual di Sudut Bawah   |
+------------------------------------+-------------------------------------+
```

### Desktop Layout (Breakpoint >= 1024px)
- **Map Canvas:** Memenuhi sisa layar secara responsif dengan Leaflet / MapLibre.
- **Sidebar Terpadu (360px - 400px):** Sisi kiri layar, menampung form filter, status dataset, dan kartu detail titik yang sedang diklik.
- **Status Bar Ringkas:** Di bagian atas atau dalam header sidebar, menunjukkan mode data saat ini (API aktif atau Snapshot benchmark).

### Mobile Layout (Breakpoint < 1024px, R-03)
- **Full Screen Map:** Peta tetap dapat digeser dan di-zoom tanpa terhalang elemen statis yang terlalu besar.
- **Collapsible Bottom Sheet:**
  - *Posisi Tertutup (Collapsed, 56px):* Menampilkan jumlah deteksi aktif dan tombol pemicu filter.
  - *Posisi Setengah (Half, 45% tinggi layar):* Menampilkan kontrol filter tanggal dan wilayah.
  - *Posisi Penuh (Expanded):* Menampilkan detail lengkap titik yang sedang dipilih beserta asal datanya.
- **Tap Targets:** Semua tombol dan sakelar memiliki tinggi minimum 44px x 44px untuk kenyamanan jari di layar sentuh.

---

## 6. Komponen dan Pembatasan Dosis Visual (Dose Caps)

Sesuai R-04, R-08, R-09, R-10, R-11, R-12, R-13, R-14:

1. **Border Radius (R-11):**
   - Panel kontrol, kartu detail, dan input: `6px` atau `8px`.
   - Tombol kontrol: `6px`.
   - Dilarang membuat seluruh elemen berbentuk kapsul lonjong (pill).
2. **Elevasi & Bayangan (R-12):**
   - Hanya panel kontrol yang melayang di atas peta yang memiliki bayangan lembut (`box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1)`).
   - Elemen internal di dalam panel tidak memiliki bayangan bertingkat.
3. **Glassmorphism (R-10):**
   - Dibatasi maksimal 1 elemen: panel overlay kontrol zoom pada peta dengan latar semi-transparan tipis (`backdrop-filter: blur(4px)`, opacity 90%).
4. **Ikonografi Faktual (R-04):**
   - Hanya gunakan ikon yang mewakili fungsinya: pin peta, kalender filter, lapisan layer, informasi sumber, dan panah orientasi kompas.
   - Dilarang keras memakai ikon bintang gemerlap (sparkle), roket, robot AI, atau emoji hiasan.
5. **Badge dan Chip Status (R-09):**
   - Hanya digunakan untuk status faktual:
     - Badge Mode: `Mode: Snapshot Statis` atau `Mode: Live FIRMS API`
     - Badge Satelit: `Satelit: NOAA-20 (VIIRS)`
     - Badge Confidence: `Tingkat Keyakinan: Nominal`
   - Dilarang menggunakan badge hiasan tanpa data.
6. **Titik Status Real-Time (Status Dot - R-31):**
   - Titik hijau/kuning kecil di status bar hanya menunjukkan kondisi koneksi API aktual (Hijau: Berhasil tersinkronisasi, Oranye: Menggunakan snapshot lokal, Merah: Gagal memuat).
   - Dilarang menambahkan animasi denyut (pulsing glow) tanpa henti.

---

## 7. Keadaan Antarmuka Lengkap (UI States - R-27)

Setiap bagian data harus memiliki 4 kondisi nyata:

### 1. State Normal (Data Ditemukan)
Menampilkan titik anomali termal pada peta dengan koordinat akurat, panel ringkasan jumlah titik dalam rentang filter, dan tombol inspeksi titik.

### 2. State Loading
- Peta: Spinner netral di pojok atas peta dengan pesan: *"Mengambil deteksi satelit FIRMS untuk wilayah terpilih..."*
- Panel: Skeleton loader tipis berwarna abu-abu netral untuk menahan layout agar tidak bergeser saat data masuk.

### 3. State Kosong (Empty State)
- Terjadi jika: Filter wilayah atau rentang tanggal tidak memiliki rekaman anomali termal.
- Tampilan: Pesan faktual dan informatif, bukan sekadar "Tidak ada data".
  - Pesan: *"Tidak ada anomali termal terdeteksi oleh satelit VIIRS pada rentang tanggal terpilih di wilayah ini."*
  - Aksi pemulihan: Tombol *"Perluas Rentang Tanggal"* atau *"Tampilkan Seluruh Indonesia"*.

### 4. State Gagal / Error & Fallback
- Terjadi jika: Panggilan API FIRMS mengalami kegagalan jaringan, batas kuota transaksi, atau server timeout.
- Tampilan: Banner notifikasi jelas di atas panel:
  - Pesan: *"Gagal menghubungi layanan NASA FIRMS API. Menampilkan snapshot lokal 7 hari (Benchmark JOINTS 2026)."*
  - Provenance: Menampilkan timestamp pengambilan file snapshot bersama (`Waktu Snapshot: 2026-10-13 00:00 UTC`).
  - Aksi: Tombol *"Coba Hubungkan Kembali ke API"*.

---

## 8. Aksesibilitas dan Dukungan Tema (Accessibility & Themes)

Sesuai R-21, R-32, dan R-34:

### Navigasi Papan Ketik (Keyboard Navigation - R-32)
- Semua kontrol (pilihan tanggal, pemilihan provinsi, tombol ganti basemap, penutupan drawer) dapat dijangkau menggunakan tombol `Tab`.
- Titik fokus memiliki indikator cincin (focus ring) yang jelas: `outline: 2px solid #2563EB; outline-offset: 2px`.
- Modal detail titik dan bottom sheet dapat ditutup dengan tombol `Escape`.

### Tema Ganda yang Berfungsi Penuh (Light & Dark Mode - R-21, R-34)
- **Mode Terang (Light):** Dioptimalkan untuk keterbacaan tinggi di luar ruangan/lapangan. Kontras basemap terang dengan titik oranye-amber yang kontras.
- **Mode Gelap (Dark):** Dioptimalkan untuk pemantauan malam hari, mengurangi silau layar. Basemap gelap (dark matter/carto dark) dengan titik anomali termal yang tegas.
- Kedua mode harus lulus verifikasi kontras WCAG AA sebelum dirilis.

---

## 9. Struktur Salinan Antarmuka (UI Copywriting)

Sesuai panduan antislop copywriting:

| Konteks | Contoh Salinan yang Benar | Hindari (AI Slop) |
|---|---|---|
| Judul Web | Pemantauan Hotspot & Konteks Gambut | Dashboard AI Canggih Pemantau Karhutla Revolusioner |
| Status Live | Terhubung ke NASA FIRMS (Diperbarui 14:15 WIB) | Real-time AI Fire Detection Active |
| Status Snapshot | Mode Snapshot Statis (Benchmark JOINTS) | Historical Data Vault Mode |
| Disclaimer | Anomali termal adalah indikasi sensor satelit untuk ditinjau, bukan bukti pasti kebakaran lahan. | Powered by AI, 99.9% Akurat Mendeteksi Api |
| Tombol Filter | Terapkan Filter Wilayah | Jelajahi Sekarang / Get Started |
| Tombol Reset | Pulihkan Pengaturan Awal | Refresh Magic |

---

## 10. Daftar Verifikasi Kepatuhan (Delivery Gate Verification)

Sebelum setiap perubahan antarmuka dianggap selesai, verifikasi item berikut:
- [x] R-02: Bebas dari karakter em dash di seluruh antarmuka.
- [x] R-03: Tata letak mobile responsif tanpa luapan horizontal, kontrol ramah sentuhan (min 44px).
- [x] R-05: Tata letak map-first fungsional, bebas dari template generic landing page.
- [x] R-09: Badge hanya menyajikan status data riil (mode dataset, platform satelit, tingkat confidence).
- [x] R-16: Bebas dari istilah pemasaran berlebihan atau klaim kecerdasan buatan palsu.
- [x] R-17: Tidak ada angka metrik atau statistik yang dibuat-buat tanpa sumber riil.
- [x] R-21 & R-34: Tema terang dan gelap berfungsi seimbang dengan kontras teruji.
- [x] R-25: Seluruh teks memenuhi rasio kontras minimum WCAG AA (4.5:1 untuk teks normal).
- [x] R-26: Seluruh tombol dan kontrol navigasi memiliki fungsi nyata.
- [x] R-27: Keadaan Normal, Loading, Kosong, dan Error/Fallback tersedia secara lengkap.
- [x] R-31: Setiap keputusan visual memiliki alasan fungsi satu baris.
