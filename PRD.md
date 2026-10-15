# PRD Hackathon JOINTS 2026

## FireGuard Kalimantan
### Web Pemantauan Hotspot, Segmentasi Hutan/Gambut, Pelaporan Warga, Validasi Petugas, dan Alert Berbasis Lokasi Pengguna

**Subtema:** Sustainability  
**Versi:** 3.0  
**Tanggal:** 15 Oktober 2026  
**Status:** Single Source of Truth — Update dari PRD sebelumnya  
**Audiens:** Panitia, peserta Hackathon JOINTS 2026, tim engineering, QA, dan auditor

> **Fokus produk:**  
> Web map khusus Pulau Kalimantan yang menampilkan deteksi hotspot NASA FIRMS, segmentasi hutan dan gambut, pelaporan warga terkait deforestasi/alih fungsi lahan bekas karhutla, validasi oleh warga lain dan petugas, serta alert in-app berbasis laporan yang dekat dengan koordinat pengguna.

> **Batasan penting:**  
> Sistem **tidak real-time**, tidak menyediakan alert darurat berbasis satelit, dan tidak mengklaim kebakaran sebagai kejadian terkonfirmasi hanya dari satu piksel Hansen atau satu laporan warga.

---

## 1. Perubahan Utama pada Versi Ini

PRD ini diperbarui berdasarkan kekurangan berikut:

| Kekurangan yang dilaporkan | Keputusan/fitur pada PRD v3.0 |
|---|---|
| Data tidak real-time, tidak bisa alert | Sistem secara eksplisit menyatakan data **near-real-time/tertunda**, tidak ada alert darurat berbasis hotspot satelit. |
| Alert bisa berdasarkan laporan dekat koordinat pengguna | Alert hanya berbasis **laporan warga** yang berada di sekitar lokasi/GPS pengguna, ditampilkan sebagai notifikasi dalam aplikasi. |
| Perlu role petugas untuk verifikasi/validasi laporan | Ditambahkan role **Warga**, **Petugas**, dan opsional **Admin/Auditor**. |
| Perlu register dan login untuk warga dan petugas | Autentikasi wajib untuk membuat laporan, memvalidasi laporan, dan melakukan verifikasi petugas. |
| Laporan warga harus ditandai simbol titik biru | Laporan baru dari warga ditampilkan sebagai **titik biru**. |
| Jika warga lain memvalidasi laporan, laporan menjadi riwayat kebakaran dengan logo api | Laporan yang divalidasi oleh **warga lain** berubah menjadi status **Riwayat Kebakaran — Validasi Warga** dengan simbol **logo api**. |
| Segmentasi wilayah kurang presisi dan peta tidak sesuai Google Maps | Ditambahkan persyaratan CRS, georeferencing, alignment basemap, checkpoint QA, dan sumber batas wilayah yang lebih presisi. |
| Segmentasi lahan gambut dan hutan Kalimantan belum diterapkan | Segmentasi hutan/gambut Kalimantan menjadi **fitur wajib MVP**, menggunakan tile lokal dan metadata sumber yang jelas. |

---

## 2. Ringkasan Eksekutif

FireGuard Kalimantan adalah web pemantauan lingkungan untuk wilayah Pulau Kalimantan yang membantu masyarakat, relawan, dan petugas melihat konteks hotspot, hutan, gambut, serta laporan warga terkait deforestasi atau pengalihan lahan bekas karhutla.

Sistem ini tidak diposisikan sebagai sistem peringatan dini kebakaran real-time. Data satelit FIRMS bersifat near-real-time dan dapat mengalami keterlambatan beberapa jam. Oleh karena itu, fitur alert tidak dibangun berdasarkan hotspot satelit secara langsung, melainkan berdasarkan **laporan warga yang sudah masuk dan berada dekat dengan posisi pengguna**.

Pengguna dapat mendaftar dan login sebagai warga atau petugas. Warga dapat membuat laporan, melihat laporan di sekitar, serta memvalidasi laporan warga lain. Petugas dapat melakukan verifikasi lanjutan, menolak laporan, atau menandai laporan sebagai informasi yang perlu ditindaklanjuti.

---

## 3. Batasan Real-Time dan Alert

### 3.1 Data tidak real-time

Sistem wajib menampilkan pernyataan keterbatasan berikut pada area yang mudah dilihat:

> “Data hotspot satelit bersifat near-real-time dan dapat tertunda beberapa jam. Laporan warga adalah indikasi lapangan, bukan konfirmasi otomatis kebakaran. Sistem ini bukan sistem peringatan darurat.”

### 3.2 Alert tidak berbasis hotspot satelit

Karena data satelit tidak real-time dan tidak cukup untuk peringatan langsung, sistem **tidak menyediakan**:

- alert real-time berbasis hotspot FIRMS;
- alert otomatis berbasis satu piksel Hansen;
- notifikasi darurat kebakaran;
- SMS, WhatsApp, push notification eksternal, atau sirene;
- dispatch petugas secara otomatis.

### 3.3 Alert berbasis laporan dekat lokasi pengguna

Fitur alert yang diperbolehkan adalah:

- alert dalam aplikasi;
- berbasis laporan warga yang sudah tersimpan di server;
- dihitung berdasarkan jarak laporan terhadap koordinat/GPS pengguna;
- hanya muncul jika pengguna memberikan izin lokasi;
- dapat diatur radiusnya, misalnya 1 km, 3 km, 5 km, atau 10 km;
- tidak diklaim sebagai peringatan resmi atau darurat.

Contoh microcopy:

> “Ada 3 laporan warga dalam radius 2 km dari lokasi Anda. Laporan ini merupakan indikasi dari warga, bukan konfirmasi kejadian.”

---

## 4. Persona dan Role

### 4.1 Warga

Warga adalah masyarakat umum, relawan, atau pengguna lokal.

Hak akses:

- register dan login;
- membuat laporan;
- melihat laporan publik dengan koordinat yang disamarkan;
- memvalidasi laporan warga lain;
- menerima alert berbasis lokasi;
- melihat riwayat laporan sendiri.

Batasan:

- tidak dapat memvalidasi laporan milik sendiri;
- tidak dapat mengakses koordinat presisi laporan milik orang lain kecuali diberikan oleh sistem sesuai aturan;
- tidak dapat mengubah status laporan menjadi terverifikasi petugas.

### 4.2 Petugas

Petugas adalah pihak yang memiliki kewenangan atau ditunjuk untuk memeriksa laporan.

Hak akses:

- semua hak warga;
- melihat koordinat presisi laporan sesuai kebijakan privasi;
- memverifikasi laporan;
- menolak laporan dengan alasan;
- mengubah status laporan menjadi terverifikasi petugas atau ditolak;
- melihat audit trail laporan.

Batasan:

- akun petugas harus melalui proses approval atau kode instansi;
- akses petugas dicatat dalam audit log;
- petugas tidak boleh ditampilkan sebagai sumber konfirmasi hukum bila belum ada verifikasi lapangan resmi.

### 4.3 Admin/Auditor

Role ini opsional untuk kebutuhan hackathon, tetapi disarankan.

Hak akses:

- approve akun petugas;
- melihat audit log;
- memeriksa hasil QA peta dan segmentasi;
- membaca log status laporan tanpa mengubah data operasional.

---

## 5. Ruang Lingkup Wilayah

### 5.1 Fokus Pulau Kalimantan

Sistem hanya menampilkan wilayah Pulau Kalimantan, mencakup:

- Kalimantan Barat;
- Kalimantan Tengah;
- Kalimantan Selatan;
- Kalimantan Timur;
- Kalimantan Utara.

### 5.2 Aturan batas wilayah

- Peta wajib dikunci pada bounding box Kalimantan.
- Titik FIRMS di luar geometri Kalimantan tidak ditampilkan.
- Laporan warga di luar Kalimantan ditolak atau ditandai sebagai di luar cakupan.
- Batas administratif digunakan sebagai konteks, bukan sebagai sumber kebenaran kejadian.

---

## 6. Kebutuhan Fungsional

## 6.1 Peta, Basemap, dan Presisi Wilayah

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-01 | Peta utama menampilkan wilayah Kalimantan saja. | maxBounds Kalimantan aktif; pengguna tidak dapat tersesat jauh ke luar wilayah. |
| FR-02 | Basemap dapat dipilih atau diganti. | Minimal tersedia basemap jalan dan citra/satelit jika sumber memungkinkan. |
| FR-03 | Peta harus menggunakan sistem koordinat yang benar. | Data sumber WGS84 EPSG:4326; tampilan Web Mercator EPSG:3857; tidak ada offset yang tidak dijelaskan. |
| FR-04 | Peta harus selaras secara visual dengan basemap umum seperti Google Maps/OSM/Esri. | Dilakukan uji checkpoint visual; offset tidak melebihi toleransi yang ditentukan. |
| FR-05 | Segmentasi wilayah administratif harus presisi. | Menggunakan sumber batas resmi atau sumber terpercaya dengan tahun dan sumber jelas. |
| FR-06 | Sistem tidak boleh menggeser koordinat laporan/hotspot tanpa penjelasan. | Jika ada snapping/generalisasi, metode dan radiusnya harus ditampilkan. |

### Aturan presisi peta

Untuk mengatasi masalah “peta tidak sesuai Google Maps” dan segmentasi kurang presisi:

1. Semua koordinat sumber disimpan dalam WGS84 lat/lon.
2. Rendering menggunakan Web Mercator yang sama dengan sebagian besar basemap web.
3. Tile raster/vector harus menggunakan tile grid XYZ yang benar.
4. Tidak boleh ada transformasi manual yang menggeser posisi tanpa dokumentasi.
5. Jika memakai Google Maps sebagai pembanding visual, Google Maps hanya digunakan sebagai referensi visual, bukan sumber kebenaran koordinat.
6. QA wajib melakukan uji checkpoint pada minimal 10 titik di 5 provinsi Kalimantan.

### Toleransi alignment

- Offset visual layer terhadap basemap maksimal 2 pixel pada zoom 12–15 untuk kebutuhan demo.
- Jika offset lebih besar, layer wajib diperbaiki atau diberi catatan “sedang dikalibrasi”.
- Perbedaan karena sumber citra/tahun citra harus dijelaskan, bukan disembunyikan.

---

## 6.2 Segmentasi Hutan dan Gambut Kalimantan

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-07 | Sistem menampilkan layer segmentasi hutan untuk Kalimantan. | Layer aktif/nonaktif, legenda, sumber, tahun data, dan threshold ditampilkan. |
| FR-08 | Sistem menampilkan layer segmentasi gambut untuk Kalimantan. | Layer gambut tampil dengan sumber dan metadata; jika sumber resmi belum tersedia, sistem menampilkan status “sumber belum final”. |
| FR-09 | Segmentasi hutan dan gambut dapat digabungkan. | Kelas “Hutan Gambut” dan “Non-Hutan Gambut” dapat ditampilkan. |
| FR-10 | Segmentasi harus menggunakan tile lokal/cache. | Tidak bergantung penuh pada remote raster global saat demo. |
| FR-11 | Segmentasi tidak boleh diklaim sebagai kondisi terkini jika berbasis baseline 2000. | Label “baseline tahun 2000” atau tahun data lain wajib tampil. |

### Kelas segmentasi minimum

| Kelas | Definisi | Catatan tampilan |
|---|---|---|
| Hutan | Tutupan pohon ≥ threshold, misalnya 30% pada baseline. | Warna hijau transparan. |
| Non-Hutan | Tutupan pohon < threshold dan data valid. | Abu-abu/transparan. |
| Gambut | Area masuk poligon/raster gambut. | Warna coklat/ungu dengan pola arsir. |
| Hutan Gambut | Irisan hutan dan gambut. | Hijau-coklat atau pola arsir khusus. |
| Non-Hutan Gambut | Area gambut tetapi tidak memenuhi threshold hutan. | Coklat muda/arsir. |
| No Data | Tidak ada data valid. | Abu-abu dengan legenda “tidak ada data”. |

### Sumber data segmentasi

Sumber minimum yang dapat digunakan:

- Hansen/GFC `treecover2000` untuk baseline tutupan pohon.
- Hansen/GFC `datamask` untuk membedakan data valid dan no-data.
- Peta gambut dari sumber resmi atau sumber global yang dicantumkan dengan jelas.
- Batas Kalimantan dari sumber administratif resmi/terpercaya.

Jika peta gambut resmi Indonesia belum tersedia, sistem boleh menampilkan layer alternatif dengan label:

> “Layer gambut menggunakan sumber alternatif. Sumber resmi dan tahun data perlu divalidasi.”

---

## 6.3 Hotspot FIRMS

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-12 | Menampilkan deteksi hotspot FIRMS untuk Kalimantan. | Data difilter ke wilayah Kalimantan. |
| FR-13 | Menampilkan atribut hotspot. | Koordinat, waktu akuisisi, satelit, confidence, FRP bila tersedia. |
| FR-14 | Menampilkan status freshness. | Waktu observasi, waktu diterima, dan label near-real-time. |
| FR-15 | Tidak menyebut hotspot sebagai kebakaran pasti. | Detail menampilkan kalimat “anomali termal, bukan konfirmasi kebakaran”. |
| FR-16 | Fallback saat API gagal. | Snapshot/cache lokal Kalimantan dapat ditampilkan dengan label “data statis”. |

---

## 6.4 Autentikasi dan Manajemen Akun

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-17 | Sistem menyediakan register untuk warga. | Warga dapat membuat akun dengan email/username dan password. |
| FR-18 | Sistem menyediakan login untuk warga dan petugas. | Login membedakan role berdasarkan data akun. |
| FR-19 | Register petugas memerlukan approval atau kode khusus. | Akun petugas tidak aktif sebelum disetujui admin atau kode instansi valid. |
| FR-20 | Password disimpan secara aman. | Hashing dengan bcrypt/argon2; tidak disimpan plaintext. |
| FR-21 | Sesi pengguna memiliki batas waktu dan logout. | Token/session expiring; logout menghapus sesi aktif. |
| FR-22 | Sistem mencatat aktivitas penting. | Login, buat laporan, validasi, verifikasi, dan penolakan dicatat dalam audit log. |

### Data akun minimum

- user id;
- username atau email;
- password hash;
- role: warga/petugas/admin;
- status akun;
- waktu pembuatan akun.

### Larangan akun

- Jangan menampilkan password.
- Jangan menyimpan kontak pelapor secara publik.
- Jangan menampilkan daftar pengguna ke pengguna lain.
- Jangan menampilkan data pribadi di endpoint publik.

---

## 6.5 Pelaporan Warga

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-23 | Warga login untuk membuat laporan. | Tidak ada laporan publik tanpa akun. |
| FR-24 | Warga dapat membuat laporan dengan lokasi. | Lokasi dari GPS perangkat atau pilih titik di peta. |
| FR-25 | Laporan memiliki kategori. | Minimal: kebakaran/asap, deforestasi, alih fungsi lahan bekas karhutla, lain-lain. |
| FR-26 | Laporan memiliki deskripsi dan waktu kejadian. | Deskripsi opsional tetapi waktu pengamatan wajib. |
| FR-27 | Laporan dapat menyertakan foto. | Foto opsional; EXIF/GPS foto di-strip sebelum disimpan. |
| FR-28 | Laporan baru ditampilkan sebagai titik biru. | Simbol default laporan warga adalah titik biru. |
| FR-29 | Laporan di luar Kalimantan ditolak. | Validasi spasial aktif. |
| FR-30 | Laporan memiliki status awal. | Status awal: `menunggu_validasi`. |

### Kategori laporan

| Kategori | Makna |
|---|---|
| `asap_kebakaran` | Warga melihat asap atau indikasi kebakaran. |
| `deforestasi` | Warga melihat pembukaan hutan/perubahan tutupan. |
| `alih_fungsi_bekas_karhutla` | Warga melihat penggunaan lahan baru di area bekas terbakar. |
| `lainnya` | Observasi lain yang relevan. |

### Simbol laporan warga baru

- Bentuk: lingkaran/titik.
- Warna: biru.
- Warna yang disarankan: `#2563EB`.
- Label: “Laporan Warga”.
- Status: `menunggu_validasi`.

---

## 6.6 Validasi Warga dan Riwayat Kebakaran

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-31 | Warga lain dapat memvalidasi laporan. | Validasi hanya bisa dilakukan oleh akun warga yang login. |
| FR-32 | Warga tidak dapat memvalidasi laporan sendiri. | Sistem menolak aksi validasi jika `validator_id = reporter_id`. |
| FR-33 | Validasi warga mengubah status laporan. | Setelah divalidasi oleh warga lain, laporan berubah menjadi `riwayat_kebakaran_validasi_warga`. |
| FR-34 | Laporan yang menjadi riwayat kebakaran ditampilkan dengan logo api. | Simbol berubah dari titik biru menjadi ikon api. |
| FR-35 | Validasi warga dicatat. | Audit log mencatat siapa, kapan, dan jenis validasi. |
| FR-36 | Status riwayat kebakaran bukan konfirmasi otoritas. | Detail wajib menampilkan label “validasi warga, bukan konfirmasi resmi”. |

### Aturan validasi warga

- Satu validasi dari warga lain sudah cukup untuk mengubah simbol menjadi riwayat kebakaran pada MVP.
- Validasi tidak boleh dilakukan oleh pemilik laporan.
- Sistem dapat menampilkan jumlah validasi warga.
- Petugas dapat meninjau ulang laporan yang sudah menjadi riwayat kebakaran.
- Jika petugas menolak laporan, status dapat berubah menjadi `ditolak`.

### Simbol riwayat kebakaran

- Bentuk: logo api.
- Warna utama: merah/oranye.
- Warna yang disarankan: `#DC2626` atau `#EA580C`.
- Label: “Riwayat Kebakaran — Validasi Warga”.
- Catatan wajib: “Ditandai berdasarkan validasi warga lain, bukan konfirmasi resmi.”

---

## 6.7 Verifikasi Petugas

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-37 | Petugas dapat melihat antrean laporan. | Daftar laporan dapat difilter berdasarkan status, kategori, wilayah, dan waktu. |
| FR-38 | Petugas dapat memverifikasi laporan. | Petugas dapat mengubah status menjadi `terverifikasi_petugas`. |
| FR-39 | Petugas dapat menolak laporan. | Penolakan wajib disertai alasan minimum. |
| FR-40 | Petugas dapat melihat koordinat lebih presisi. | Akses koordinat presisi dicatat dalam audit log. |
| FR-41 | Verifikasi petugas tidak boleh otomatis berarti kebakaran pasti. | Label: “terverifikasi petugas sebagai indikasi lanjutan, bukan bukti hukum”. |
| FR-42 | Semua aksi petugas dicatat. | Audit trail menampilkan aktor, waktu, aksi, dan alasan. |

### Status laporan setelah petugas

| Status | Makna | Simbol |
|---|---|---|
| `terverifikasi_petugas` | Laporan sudah diperiksa petugas dan dianggap layak ditindaklanjuti. | Logo api dengan badge/check. |
| `ditolak` | Laporan tidak valid, duplikat, spam, atau tidak cukup bukti. | Abu-abu/sembunyikan dari peta publik default. |
| `perlu_tinjauan_lapangan` | Perlu pemeriksaan lapangan lebih lanjut. | Logo api atau segitiga peringatan dengan label khusus. |

---

## 6.8 Alert Berbasis Lokasi Pengguna

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-43 | Pengguna dapat mengaktifkan alert berbasis lokasi. | Meminta izin GPS/lokasi secara eksplisit. |
| FR-44 | Alert dihitung dari laporan warga dekat lokasi pengguna. | Sistem menghitung jarak laporan ke koordinat pengguna. |
| FR-45 | Radius alert dapat dipilih. | Minimal opsi: 1 km, 3 km, 5 km, 10 km. |
| FR-46 | Alert ditampilkan dalam aplikasi. | Berupa badge, banner, atau daftar “laporan terdekat”. |
| FR-47 | Alert tidak berbasis hotspot satelit. | Tidak ada klaim alert real-time dari FIRMS. |
| FR-48 | Alert tidak menampilkan data pribadi pelapor. | Hanya menampilkan kategori, waktu, status, dan jarak. |
| FR-49 | Pengguna dapat mematikan alert. | Toggle off tersedia. |
| FR-50 | Lokasi pengguna tidak dipublikasikan. | GPS pengguna hanya dipakai untuk perhitungan alert sisi klien/server yang aman. |

### Mekanisme alert MVP

1. Pengguna login.
2. Pengguna mengaktifkan “Alert laporan terdekat”.
3. Browser/perangkat meminta izin lokasi.
4. Sistem mengambil koordinat pengguna secara aman.
5. Sistem mencari laporan dalam radius yang dipilih.
6. Sistem menampilkan daftar laporan terdekat.
7. Alert diperbarui saat pengguna membuka aplikasi atau menekan tombol refresh.

### Batasan alert

- Tidak ada klaim real-time.
- Tidak ada notifikasi darurat.
- Tidak ada SMS/WhatsApp/push eksternal pada MVP.
- Jika push notification implementasi platform memungkinkan, ia tetap bersifat opsional dan harus diberi label “tidak real-time”.

---

## 6.9 Privasi dan Keamanan Laporan

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-51 | Endpoint publik tidak membocorkan koordinat presisi laporan warga. | Koordinat publik disamarkan dengan grid/jitter, misalnya 100–500 m. |
| FR-52 | Kontak pelapor tidak ditampilkan publik. | Email, nomor telepon, dan identitas tidak muncul di peta atau API publik. |
| FR-53 | Foto laporan di-strip EXIF/GPS. | Metadata GPS dan perangkat dihapus sebelum disimpan. |
| FR-54 | Warga dapat melihat laporan publik dalam bentuk umum. | Detail menampilkan lokasi aproksimasi. |
| FR-55 | Petugas dapat melihat lokasi presisi dengan audit. | Akses presisi dicatat. |
| FR-56 | Lokasi pengguna untuk alert tidak dibagikan ke pengguna lain. | Tidak ada fitur menampilkan posisi pengguna lain. |

---

## 7. Status Laporan dan Simbol Peta

| Status | Dibuat oleh | Validasi | Simbol | Keterangan publik |
|---|---|---|---|---|
| `menunggu_validasi` | Warga | Belum ada validasi warga lain | Titik biru | Laporan baru. |
| `riwayat_kebakaran_validasi_warga` | Warga | Divalidasi warga lain | Logo api | Validasi warga, bukan konfirmasi resmi. |
| `terverifikasi_petugas` | Warga | Diverifikasi petugas | Logo api + badge/check | Indikasi lanjutan, bukan bukti hukum. |
| `perlu_tinjauan_lapangan` | Warga/Petugas | Perlu cek lapangan | Logo api atau segitiga | Belum final. |
| `ditolak` | Warga | Ditolak petugas | Abu-abu/sembunyi | Tidak ditampilkan default. |

### Layer lain

| Layer | Simbol | Catatan |
|---|---|---|
| Hotspot FIRMS | Lingkaran oranye | Anomali termal, bukan konfirmasi kebakaran. |
| Hutan | Poligon hijau transparan | Baseline sesuai tahun data. |
| Gambut | Poligon coklat/arsir | Konteks lahan gambut. |
| Hutan gambut | Hijau-coklat/arsir khusus | Irisan hutan dan gambut. |
| No data | Abu-abu | Bukan berarti aman. |

---

## 8. Alur Pengguna Utama

### 8.1 Warga membuat laporan

1. Warga membuka aplikasi.
2. Warga register/login.
3. Warga memilih “Buat Laporan”.
4. Sistem meminta izin lokasi atau pengguna memilih titik di peta.
5. Warga memilih kategori.
6. Warga mengisi waktu pengamatan dan deskripsi.
7. Warga mengunggah foto jika ada.
8. Sistem menghapus EXIF/GPS foto.
9. Laporan tersimpan dengan status `menunggu_validasi`.
10. Laporan tampil sebagai titik biru.

### 8.2 Warga lain memvalidasi laporan

1. Warga lain login.
2. Warga lain membuka detail laporan.
3. Warga lain memilih “Validasi laporan”.
4. Sistem memeriksa bahwa validator bukan pemilik laporan.
5. Sistem mencatat validasi.
6. Laporan berubah menjadi `riwayat_kebakaran_validasi_warga`.
7. Simbol berubah menjadi logo api.

### 8.3 Petugas memverifikasi laporan

1. Petugas login.
2. Petugas membuka antrean laporan.
3. Petugas melihat detail, foto, koordinat presisi, dan riwayat validasi.
4. Petugas memilih:
   - verifikasi sebagai indikasi lanjutan;
   - perlu tinjauan lapangan;
   - tolak dengan alasan.
5. Sistem mencatat aksi petugas.
6. Tampilan publik diperbarui sesuai status.

### 8.4 Pengguna menerima alert laporan terdekat

1. Pengguna login.
2. Pengguna mengaktifkan alert lokasi.
3. Pengguna memberi izin GPS.
4. Pengguna memilih radius.
5. Sistem menampilkan jumlah laporan dalam radius.
6. Pengguna dapat membuka daftar laporan terdekat.
7. Alert tidak diklaim sebagai peringatan resmi.

---

## 9. Spesifikasi Teknis Peta dan Segmentasi

### 9.1 Sistem koordinat

- Sumber koordinat: WGS84 lat/lon, EPSG:4326.
- Tampilan peta web: Web Mercator, EPSG:3857.
- Tile raster: XYZ/MBTiles.
- Vector layer: GeoJSON/Vector Tiles jika digunakan.
- Semua transformasi harus mengikuti geotransform metadata GeoTIFF.

### 9.2 Perbaikan presisi segmentasi

Untuk memperbaiki segmentasi yang kurang presisi:

1. Gunakan batas Kalimantan resmi/terpercaya.
2. Clip raster segmentasi ke batas Kalimantan.
3. Reprojection ke EPSG:3857 untuk tile web.
4. Pastikan tidak ada pergeseran origin tile.
5. Gunakan resampling yang sesuai, misalnya nearest untuk data kelas.
6. Lakukan uji visual pada beberapa zoom.
7. Simpan metadata versi layer.

### 9.3 Pipeline segmentasi Kalimantan

Tahapan minimum:

1. Ambil raster tutupan pohon dan gambut.
2. Clip ke batas Kalimantan.
3. Buat kelas segmentasi.
4. Validasi nilai no-data.
5. Generate tile lokal.
6. Uji checkpoint koordinat.
7. Upload/deploy tile lokal.
8. Tampilkan legenda dan metadata.

### 9.4 Checkpoint QA peta

Minimal 10 checkpoint:

- 2 titik di Kalimantan Barat;
- 2 titik di Kalimantan Tengah;
- 2 titik di Kalimantan Selatan;
- 2 titik di Kalimantan Timur;
- 2 titik di Kalimantan Utara.

Setiap checkpoint mencatat:

- koordinat referensi;
- posisi pada aplikasi;
- posisi pada basemap pembanding;
- offset pixel/meter;
- status lulus/gagal;
- catatan penyebab jika gagal.

---

## 10. Model Data Minimum

### 10.1 User

| Field | Keterangan |
|---|---|
| id | ID unik pengguna. |
| username | Username publik/pseudonym. |
| email | Email opsional, tidak dipublikasikan. |
| password_hash | Hash password. |
| role | warga, petugas, admin. |
| status | aktif, pending, nonaktif. |
| created_at | Waktu akun dibuat. |

### 10.2 Report

| Field | Keterangan |
|---|---|
| id | ID laporan. |
| reporter_id | ID warga pembuat laporan. |
| category | Kategori laporan. |
| description | Deskripsi. |
| observed_at | Waktu pengamatan. |
| private_lat | Koordinat asli untuk petugas. |
| private_lon | Koordinat asli untuk petugas. |
| public_lat | Koordinat publik yang disamarkan. |
| public_lon | Koordinat publik yang disamarkan. |
| location_method | GPS atau pilih peta. |
| accuracy_m | Akurasi GPS jika tersedia. |
| status | Status laporan. |
| created_at | Waktu laporan dibuat. |

### 10.3 ReportValidation

| Field | Keterangan |
|---|---|
| id | ID validasi. |
| report_id | ID laporan. |
| validator_id | ID validator. |
| validator_role | warga atau petugas. |
| action | validasi_warga, verifikasi_petugas, tolak. |
| reason | Alasan, wajib untuk penolakan. |
| created_at | Waktu aksi. |

### 10.4 AlertSetting

| Field | Keterangan |
|---|---|
| user_id | ID pengguna. |
| enabled | Status alert aktif. |
| radius_m | Radius alert. |
| last_lat | Lokasi terakhir pengguna, jika disimpan. |
| last_lon | Lokasi terakhir pengguna, jika disimpan. |
| updated_at | Waktu pengaturan diperbarui. |

### 10.5 MapCheckpoint

| Field | Keterangan |
|---|---|
| id | ID checkpoint. |
| lat | Koordinat referensi. |
| lon | Koordinat referensi. |
| app_offset_px | Offset pada aplikasi. |
| reference_offset_px | Offset pada pembanding. |
| status | Lulus/gagal. |
| checked_at | Waktu pemeriksaan. |

---

## 11. Persyaratan Non-Fungsional

### 11.1 Keamanan

- API key FIRMS hanya di backend.
- Password tidak disimpan plaintext.
- Endpoint publik tidak menampilkan email, nomor, atau koordinat presisi.
- Akses petugas ke koordinat presisi dicatat.
- Rate limit untuk register, login, buat laporan, dan validasi.
- EXIF foto dihapus.

### 11.2 Privasi

- Lokasi pengguna untuk alert tidak dipublikasikan.
- Warga hanya melihat koordinat aproksimasi laporan warga lain.
- Petugas melihat koordinat presisi hanya jika diperlukan.
- Audit log tidak mencatat password.
- Data pribadi tidak dipakai untuk scoring publik.

### 11.3 Keandalan

- Jika FIRMS API gagal, gunakan snapshot/cache Kalimantan.
- Jika layer segmentasi gagal, peta tetap tampil dengan layer lain.
- Jika GPS tidak tersedia, alert lokasi dinonaktifkan dengan pesan jelas.
- Jika validasi gagal, status laporan tidak berubah.

### 11.4 Performa

- Segmentasi menggunakan tile lokal/cache.
- Peta tidak boleh menunggu remote raster global tanpa timeout.
- Remote access raster dibatasi timeout maksimal 3 detik pada mode demo.
- Alert lokasi dihitung cepat untuk radius yang dipilih.

### 11.5 Kejujuran data

- Tidak menyebut real-time absolut.
- Tidak menyebut kebakaran pasti.
- Tidak menyebut deforestasi pasti dari satu piksel.
- Tidak menyebut riwayat kebakaran validasi warga sebagai bukti hukum.

---

## 12. Acceptance Criteria

| ID | Kriteria |
|---|---|
| AC-01 | Peta terkunci pada wilayah Kalimantan. |
| AC-02 | Titik FIRMS di luar Kalimantan tidak ditampilkan. |
| AC-03 | Layer segmentasi hutan dan gambut Kalimantan tampil dengan legenda. |
| AC-04 | Segmentasi tidak diklaim sebagai data real-time atau bukti deforestasi. |
| AC-05 | Register warga berhasil dan pengguna dapat login. |
| AC-06 | Register petugas memerlukan approval/kode khusus. |
| AC-07 | Warga login dapat membuat laporan. |
| AC-08 | Laporan baru tampil sebagai titik biru. |
| AC-09 | Warga tidak dapat memvalidasi laporan sendiri. |
| AC-10 | Warga lain dapat memvalidasi laporan. |
| AC-11 | Setelah validasi warga lain, laporan berubah menjadi riwayat kebakaran dengan logo api. |
| AC-12 | Status riwayat kebakaran validasi warga menampilkan disclaimer. |
| AC-13 | Petugas dapat memverifikasi laporan. |
| AC-14 | Petugas dapat menolak laporan dengan alasan wajib. |
| AC-15 | Alert hanya muncul berdasarkan laporan dekat GPS pengguna, bukan hotspot. |
| AC-16 | Alert tidak menampilkan kontak pelapor. |
| AC-17 | Endpoint publik tidak membocorkan koordinat presisi dan kontak. |
| AC-18 | Peta memiliki alignment yang wajar terhadap basemap umum. |
| AC-19 | Checkpoint QA peta dicatat dan dapat ditunjukkan saat demo. |
| AC-20 | Sistem menampilkan pernyataan bahwa data tidak real-time. |

---

## 13. Gerbang Rilis

Sebelum demo atau produksi terbatas, sistem wajib melewati gerbang berikut.

### GR-1 Tes backend penuh

- Jalankan seluruh suite backend, bukan hanya tes fitur terbaru.
- Jangan menyamakan sebagian tes dengan keamanan seluruh sistem.

### GR-2 Keamanan autentikasi

- Uji register, login, logout, session expiry.
- Uji warga tidak bisa mengakses endpoint petugas.
- Uji warga tidak bisa validasi laporan sendiri.
- Uji password tidak bocor di log/response.

### GR-3 Privasi laporan

- Uji endpoint publik tidak menampilkan koordinat presisi.
- Uji kontak pelapor tidak bocor.
- Uji foto tidak mengandung EXIF/GPS.
- Uji lokasi pengguna alert tidak dipublikasikan.

### GR-4 QA peta dan segmentasi

- Uji checkpoint koordinat.
- Uji alignment layer dengan basemap.
- Uji segmentasi hutan/gambut Kalimantan tampil benar.
- Uji kelas no-data tidak disamakan dengan non-hutan.

### GR-5 Validasi laporan

- Uji laporan baru menjadi titik biru.
- Uji validasi warga lain mengubah simbol menjadi logo api.
- Uji petugas dapat verifikasi dan tolak.
- Uji audit trail tercatat.

### GR-6 Alert lokasi

- Uji alert muncul jika ada laporan dalam radius.
- Uji alert tidak muncul jika tidak ada laporan.
- Uji alert tidak berbasis hotspot.
- Uji alert tidak menampilkan data pribadi.

---

## 14. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Validasi warga palsu | Laporan tidak benar menjadi riwayat kebakaran | Audit log, akun login, petugas dapat menolak, disclaimer validasi warga. |
| Spam laporan | Peta penuh titik tidak relevan | Rate limit, moderasi, penolakan petugas, deduplikasi sederhana. |
| Kebocoran lokasi pelapor | Privasi terganggu | Koordinat publik disamarkan, endpoint publik dibatasi. |
| GPS pengguna disalahgunakan | Pelacakan pengguna | Lokasi pengguna tidak dipublikasikan, hanya untuk alert. |
| Peta tidak presisi | Salah interpretasi lokasi | Checkpoint QA, CRS benar, kalibrasi tile. |
| Segmentasi gambut tidak resmi | Klaim konteks salah | Tampilkan sumber, tahun, dan status sumber. |
| Data FIRMS tertunda | Pengguna mengira real-time | Label near-real-time dan disclaimer. |
| Alert dianggap peringatan darurat | Respons salah | Microcopy tegas bahwa alert bukan peringatan resmi. |

---

## 15. Skrip Demo

1. Buka peta Kalimantan.
2. Tampilkan disclaimer bahwa data tidak real-time.
3. Tampilkan layer hotspot FIRMS dengan label anomali termal.
4. Aktifkan segmentasi hutan dan gambut Kalimantan.
5. Tunjukkan legenda dan metadata segmentasi.
6. Register/login sebagai warga.
7. Buat laporan baru.
8. Tunjukkan laporan tampil sebagai titik biru.
9. Login sebagai warga lain.
10. Validasi laporan warga pertama.
11. Tunjukkan laporan berubah menjadi logo api sebagai riwayat kebakaran validasi warga.
12. Login sebagai petugas.
13. Verifikasi laporan atau tolak dengan alasan.
14. Tunjukkan audit trail.
15. Aktifkan alert berbasis lokasi.
16. Tunjukkan daftar laporan dekat GPS pengguna.
17. Tunjukkan bahwa alert tidak berbasis hotspot dan tidak diklaim darurat.
18. Tunjukkan endpoint publik tidak membocorkan koordinat presisi dan kontak.

---

## 16. Larangan Bahasa dan Klaim

Jangan gunakan klaim berikut pada UI, demo, atau pitch:

- “real-time absolut”;
- “kebakaran terkonfirmasi”;
- “sistem membuktikan deforestasi”;
- “satu piksel Hansen membuktikan kebakaran”;
- “alert darurat resmi”;
- “dispatch otomatis petugas”;
- “riwayat kebakaran validasi warga adalah bukti hukum”;
- “wilayah tanpa laporan berarti aman”.

Gunakan bahasa yang disarankan:

- “deteksi anomali termal”;
- “indikasi lapangan”;
- “laporan warga”;
- “validasi warga”;
- “verifikasi petugas”;
- “perlu tinjauan lanjutan”;
- “data near-real-time”;
- “alert berbasis laporan terdekat”.

---

## 17. Kesimpulan

PRD versi ini menegaskan bahwa FireGuard Kalimantan adalah sistem pemantauan dan pelaporan berbasis indikasi, bukan sistem peringatan kebakaran real-time. Alert hanya dibangun dari laporan warga yang dekat dengan lokasi pengguna. Fitur autentikasi, role warga/petugas, validasi warga, simbol titik biru, riwayat kebakaran berlogo api, perbaikan presisi peta, dan implementasi segmentasi hutan/gambut Kalimantan menjadi bagian wajib dari MVP.

Status yang tepat untuk disampaikan adalah:

> “Integrasi peta, laporan warga, validasi, dan segmentasi telah dirancang untuk meningkatkan kewaspadaan kontekstual. Namun sistem ini tidak membuktikan kebakaran, deforestasi, atau aktivitas ilegal secara otomatis. Semua laporan tetap memerlukan verifikasi lanjutan oleh pihak berwenang.”