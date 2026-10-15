# PRD Hackathon JOINTS 2026

## Pantau Hotspot, Jaga Hutan dan Gambut

**Web pemantauan kebakaran dan perubahan lahan**  
**Subtema:** Sustainability  
**Versi:** 1.0  
**Tanggal:** 13 Oktober 2026  
**Audiens:** Panitia dan peserta Hackathon JOINTS 2026

> **Tantangan:** Bantu masyarakat sekitar hutan dan lahan gambut memantau deteksi hotspot dan konteks wilayahnya sejak dini melalui web yang mengambil data dari NASA FIRMS API.

**Fokus MVP:** web map Indonesia, FIRMS API, pencarian dan filter, konteks hutan/gambut, provenance data.  
**Data utama:** NASA FIRMS VIIRS API; snapshot nasional bersama menjadi fallback dan benchmark penilaian.

## 1. Ringkasan dan Masalah

Masyarakat sekitar hutan dan lahan gambut terdampak kebakaran serta deforestasi, tetapi sulit memantau titik api dan perubahan wilayah sejak dini. Deteksi satelit tersedia dari layanan publik, namun perlu disajikan dalam web yang mudah dipakai dan menunjukkan konteks, waktu, serta asal datanya.

### Tantangan Hackathon

Bagaimana kita membangun web yang mengambil deteksi hotspot Indonesia dari NASA FIRMS API dan membantu masyarakat/relawan sekitar hutan serta gambut menemukan titik yang perlu ditinjau sejak dini?

### Tujuan Produk

Menyajikan deteksi aktif FIRMS pada peta nasional melalui API, dengan pencarian, detail titik, metadata waktu, dan konteks spasial hutan/gambut bila tersedia. Sistem membantu pemantauan awal; sistem tidak mengonfirmasi kebakaran atau menyatakan deforestasi tanpa dataset perubahan tutupan lahan yang sesuai.

### Hasil yang Ingin Dicapai

- **Pantau:** masyarakat/relawan dapat melihat deteksi terbaru di sekitar wilayah hutan dan gambut yang dipilih.
- **Temukan:** pengguna dapat menyaring titik menurut lokasi dan waktu serta membuka detail deteksi.
- **Telusuri:** tiap titik memperlihatkan sumber, waktu observasi, status pembaruan API, dan konteks wilayah yang tersedia.
- **Gunakan dengan tepat:** antarmuka menjelaskan bahwa anomali termal bukan konfirmasi api; perubahan tutupan lahan memerlukan sumber tersendiri.

### Definisi Hotspot

Titik deteksi anomali termal aktif dari sensor satelit. Titik adalah indikasi untuk ditinjau, bukan bukti tunggal bahwa terjadi kebakaran.

## 2. Pengguna dan Ruang Lingkup

### Persona

- **Utama:** anggota masyarakat sekitar hutan/lahan gambut atau relawan pemantau lokal yang memerlukan web sederhana untuk menemukan dan meninjau deteksi di wilayahnya.
- **Pendukung:** operator organisasi lingkungan/instansi yang membandingkan wilayah dan periode.

### Kebutuhan Pengguna

- Melihat deteksi terbaru pada peta dan memusatkan pencarian pada kabupaten/wilayah sekitar hutan atau gambut.
- Menyaring berdasarkan rentang tanggal/waktu, satelit, dan wilayah; memahami bahwa hasil berasal dari lintasan satelit.
- Memilih titik untuk memeriksa koordinat, waktu akuisisi, satelit, confidence, FRP, dan atribut lain yang memang tersedia.
- Mengetahui status koneksi/pembaruan API dan waktu data terakhir berhasil diterima; tetap dapat melihat snapshot jika API bermasalah.

### Termasuk MVP

- Web map untuk Indonesia dengan navigasi dan zoom.
- Panggilan FIRMS API untuk deteksi aktif.
- Filter waktu dan wilayah, detail titik, status freshness, dan provenance.
- Konteks batas hutan/gambut bila panitia menyediakan layer resmi.
- Cache/snapshot agar aplikasi tetap dapat digunakan saat API gagal.
- Keadaan loading, kosong, dan error yang jelas.

### Di Luar Tantangan Inti

- Prediksi titik sebelum terdeteksi, konfirmasi kebakaran, penentuan sebab, atau estimasi luas kebakaran.
- Deteksi otomatis deforestasi tanpa data perubahan tutupan lahan yang sesuai.
- Rute pemadaman/evakuasi, dispatch, atau alert multi-kanal.
- Model ML atau klaim bahwa FIRMS sendiri mendeteksi perubahan tutupan lahan.

FWI BMKG atau data tutupan lahan historis dapat menjadi layer konteks opsional bila sumber, akses, dan atribusinya disediakan.

> Gunakan istilah **deteksi hotspot/anomali termal**. Jangan menyajikan confidence sebagai probabilitas bahwa lokasi pasti terbakar.

## 3. Data dan Sumber Kebenaran

### Sumber Utama: NASA FIRMS Area API

NASA FIRMS Area API mengembalikan deteksi aktif sebagai CSV berdasarkan sumber/sensor, area, dan periode. Penggunaan API memerlukan free `MAP_KEY`; kueri area dibatasi 1–5 hari per permintaan dan layanan menerapkan batas transaksi. API key harus berada di server/backend, tidak dikirim ke browser atau disimpan dalam repositori.

Untuk cakupan nasional, tim harus menghindari kueri berulang berlebihan, menyimpan hasil sementara, dan memfilter hasil terhadap batas geografis Indonesia agar titik dari bounding box negara tetangga tidak ikut ditampilkan. Untuk rentang tujuh hari, pecah permintaan menjadi beberapa jendela maksimal lima hari.

### Mode Data MVP dan Penilaian

- **Web utama:** aplikasi memanggil FIRMS API melalui backend/proxy dan memperbarui data sesuai aksi pengguna atau interval yang wajar. Tampilkan status dan waktu pembaruan.
- **Snapshot bersama:** panitia menyediakan CSV/GeoJSON tujuh hari untuk mode fallback dan benchmark nasional yang seragam. Snapshot membantu penilaian ketika API key, jaringan, atau layanan gagal.
- **Manifest:** catat sumber, produk/sensor, waktu pengambilan UTC, rentang observasi, batas geografis/kueri, versi/atribusi, jumlah rekaman, dan checksum.
- **Dokumentasi kolom:** jelaskan definisi, nullable/opsional, koordinat, zona waktu, serta pemetaan kolom sumber ke tampilan.

### Atribut Minimum

| Atribut | Pemakaian | Ketentuan |
|---|---|---|
| Latitude, longitude | Lokasi titik pada peta | Jangan menggeser atau mengagregasi titik tanpa menjelaskan transformasinya. |
| Tanggal dan waktu akuisisi | Filter waktu, detail, urutan | Simpan zona waktu sumber; normalisasi untuk filter/tampilan secara konsisten. |
| Satelit/platform dan sensor bila tersedia | Detail dan provenance | Tampilkan nilai sumber; tandai atribut yang tidak tersedia. |
| Confidence dan FRP bila tersedia | Detail dan filter opsional | Jangan mengarang nilai atau mengubah kategori confidence menjadi probabilitas kebakaran. |
| Waktu pengambilan dan identitas snapshot | Kartu status data | Wajib tampil sebagai metadata terpisah dari waktu observasi. |

### Kelayakan dan Batas Dataset

FIRMS API memadai untuk menemukan deteksi aktif yang sudah diamati, bukan memprediksi kebakaran atau mendeteksi alih fungsi lahan. Bounding box nasional mencakup area di luar Indonesia sehingga hasil perlu difilter memakai geometri batas resmi. NASA mengumumkan penghentian pengiriman data Suomi-NPP mulai 1 November 2026; prototipe tidak boleh bergantung pada S-NPP saja. Gunakan NOAA-20/NOAA-21 dan periksa ketersediaan data saat demo. Layer hutan/gambut memberi konteks kedekatan, bukan bukti perubahan lahan.

## 4. Alur Pengguna dan Kebutuhan Fungsional

**Alur utama:** buka peta → pilih periode atau wilayah → jelajahi sebaran → pilih titik → baca detail dan provenance → bagikan/ekspor informasi bila solusi peserta mendukungnya.

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| FR-01 | Peta Indonesia menampilkan deteksi FIRMS API atau snapshot yang lolos filter. | Posisi mengikuti koordinat sumber; tampilan dapat dinavigasi dan tidak menyamarkan makna titik. |
| FR-02 | Filter periode observasi dengan rentang tanggal/waktu. | Hasil hanya berisi rekaman dalam rentang terpilih; zona waktu dijelaskan. |
| FR-03 | Filter atau navigasi wilayah bila batas administratif disediakan. | Wilayah yang dipilih jelas; batas wilayah ditandai sebagai konteks, bukan data hotspot. |
| FR-04 | Memilih titik membuka detail atribut sumber. | Koordinat, waktu akuisisi, satelit/sensor, confidence/FRP bila tersedia, dan sumber terlihat. |
| FR-05 | Status dataset dan kebaruan data selalu terlihat. | Snapshot menunjukkan “statis” dan waktu pengambilan; mode API menunjukkan waktu observasi, waktu diterima, serta status terakhir. |
| FR-06 | Antarmuka memiliki keadaan kosong, error, dan loading. | Pengguna diberi penjelasan yang dapat ditindaklanjuti; data tidak dianggap valid saat gagal diproses. |
| FR-07 | Layer konteks hutan/gambut opsional dari panitia. | Legenda dan sumber jelas; jarak/kedekatan dihitung terhadap geometri sumber tanpa klaim deforestasi. |
| FR-08 | Ambil deteksi FIRMS melalui API web. | API key hanya di backend; tunjukkan status dan waktu pembaruan; cache hasil dan fallback ke snapshot saat gagal. |
| FR-09 | Layer FWI opsional bila diintegrasikan. | Jelaskan FWI sebagai indikator intensitas api jika kebakaran terjadi; tampilkan tanggal prakiraan dan atribusi BMKG. |

### Prinsip Interaksi

- Warna/ukuran simbol harus memiliki legenda; hindari menyandikan confidence sebagai kepastian kejadian.
- Untuk titik berdekatan, gunakan clustering/aggregation hanya sebagai bantuan visual dan sediakan jalan untuk melihat titik individual.
- Filter aktif, jumlah hasil, periode, dan metadata sumber harus mudah ditemukan tanpa membuka dokumentasi terpisah.

## 5. Freshness, Kualitas, dan Batasan

### Definisi Waktu

| Waktu | Arti | Perilaku UI |
|---|---|---|
| Waktu observasi/akuisisi | Kapan sensor merekam deteksi. | Tampil pada detail dan digunakan untuk filter waktu. |
| Waktu snapshot/pengambilan | Kapan file bersama diambil dari sumber. | Tampil pada label dataset statis; bukan waktu kejadian. |
| Waktu diterima/diproses | Kapan layanan peserta menerima dan mengolah data, bila live. | Tampil terpisah dari observasi; kegagalan pembaruan mempertahankan status dan waktu sukses terakhir. |

### Perlakuan Freshness

- Dataset snapshot wajib diberi label “data statis” dengan waktu pengambilan UTC dan rentang waktu observasi yang tercakup.
- Mode API wajib menampilkan waktu sukses pembaruan terakhir dan menyatakan bila sumber tidak tersedia atau data melewati ambang freshness yang ditetapkan tim.
- Jangan menjanjikan “real-time”. FIRMS global NRT umumnya menyediakan data beberapa jam setelah pengamatan; jadwal lintasan satelit berarti observasi tidak berlangsung terus-menerus. Cantumkan batas ini pada penjelasan sumber.
- Jika salah satu layer gagal, layer dan fungsi lain tetap dapat digunakan; error harus terlihat dan tidak menampilkan data usang seolah-olah baru.

### Kualitas Data dan Tanggung Jawab

- Validasi koordinat masuk akal, waktu terurai, kolom penting tersedia, serta duplikasi/rekaman tidak valid ditangani dengan aturan yang didokumentasikan.
- Simpan provenance: sumber, produk, versi jika ada, parameter unduhan, waktu ingestion, dan transformasi yang dilakukan.
- Cantumkan NASA FIRMS sebagai sumber sesuai ketentuan produk/API yang dipakai; cantumkan BMKG jika memakai citra atau data FWI.
- Sistem adalah alat bantu pemantauan. Verifikasi kondisi lapangan dan keputusan respons tetap dilakukan pihak berwenang.

> Pernyataan keterbatasan yang disarankan: “Titik pada peta menunjukkan anomali termal yang dideteksi sensor satelit pada waktu tertentu. Deteksi dapat terlewat atau berasal dari sumber panas lain; verifikasi lapangan tetap diperlukan.”

## 6. Persyaratan Kualitas dan Penerimaan

MVP dinilai berhasil bila pengguna dapat menyelesaikan tugas pencarian dasar melalui FIRMS API dan mengulanginya pada snapshot benchmark nasional yang sama, tanpa mengartikan deteksi sebagai konfirmasi kebakaran.

### Persyaratan Non-Fungsional

| Area | Persyaratan |
|---|---|
| Kinerja | Peta dan filter tetap responsif untuk ukuran snapshot yang dibagikan. Tim menjelaskan batas perangkat/jaringan bila memengaruhi penggunaan. |
| Keandalan | Kegagalan API/layer tidak mematikan seluruh web; snapshot/cache lokal ditampilkan dengan label data statis, dan kesalahan tidak disamarkan. |
| Keamanan | Credential API live tidak ditanam di kode sisi-klien atau repositori publik; snapshot bersama tidak membutuhkan secret peserta. |
| Aksesibilitas | Informasi penting tidak dibedakan hanya dengan warna; legenda, label, dan kontrol inti dapat dibaca. |
| Reproducibility | Mode live diuji dengan API; mode snapshot lokal memungkinkan benchmark tanpa ketergantungan pada jaringan/API. |

### Uji Penerimaan Panitia

- **AC-01:** Bandingkan sejumlah koordinat dan waktu terpilih pada peta/detail dengan rekaman sumber; nilai harus cocok setelah transformasi proyeksi yang benar.
- **AC-02:** Pilih rentang waktu yang diketahui; pastikan seluruh hasil berada di rentang tersebut dan tidak ada rekaman relevan yang hilang dari hasil filter.
- **AC-03:** Pilih wilayah (jika batas wilayah diberikan); cek beberapa rekaman di dalam dan di luar batas terhadap aturan spasial yang dijelaskan.
- **AC-04:** Pilih titik dan pastikan atribut opsional yang kosong ditandai tidak tersedia, bukan diisi nilai tebakan.
- **AC-05:** Periksa label snapshot: timestamp pengambilan dan periode observasi berbeda serta status statis terlihat.
- **AC-06:** Simulasikan API tidak tersedia atau kena batas kueri; antarmuka menandai kegagalan dan memuat snapshot/cache dengan timestamp yang benar.
- **AC-07:** Pastikan API key tidak tampak di bundle browser, URL publik, log, atau repositori; hasil nasional sudah difilter dengan batas Indonesia.
- **AC-08:** Tanyakan kepada pengguna uji apakah titik berarti deteksi/anomali termal dan apakah layer hutan/gambut membuktikan deforestasi; salah tafsir berarti kriteria gagal.

Gunakan kelulusan AC-01 sampai AC-08 dan keberhasilan menyelesaikan tugas pencarian benchmark. Catat waktu respons dan usability sebagai hasil pengujian, bukan target angka tanpa baseline.

## 7. Brief Peserta dan Penilaian

### Prompt Tantangan

> Rancang dan bangun web yang mengambil deteksi anomali termal satelit Indonesia melalui NASA FIRMS API, agar masyarakat/relawan sekitar hutan dan gambut dapat menemukan titik yang relevan, melihat detail serta konteks wilayah, dan memahami waktu, sumber, serta batas data. Sediakan snapshot bersama sebagai fallback ketika layanan/API tidak tersedia dan sebagai benchmark penilaian yang seragam.

### Keluaran Tim

- Prototipe web yang dapat dijalankan: integrasi FIRMS API melalui backend, dengan mode snapshot/cache untuk benchmark dan kegagalan koneksi.
- GitHub repository asli tim dengan README.md berisi alur, setup, konfigurasi API key lewat environment, dan cara menjalankan.
- Demo alur masyarakat/relawan: pilih wilayah hutan/gambut → temukan deteksi baru → buka detail → lihat waktu, sumber, status API, serta konteks lokasi.
- Pitch deck dan video proposal sesuai ketentuan JOINTS; nyatakan seluruh penggunaan AI beserta tools dan perannya.
- Ringkas batasan: deteksi satelit bukan konfirmasi kebakaran; layer konteks bukan deteksi deforestasi.

### Rubrik Penilaian Hackathon JOINTS

| Aspek | Bobot | Bukti yang dicari pada solusi ini |
|---|---:|---|
| Inovasi Solusi | 25% | Pendekatan baru dan relevan untuk pemantauan titik api oleh komunitas sekitar hutan/gambut. |
| Implementasi Teknis | 30% | Integrasi FIRMS API benar, backend/key aman, geospasial dan cache/fallback berfungsi. |
| Fungsionalitas & Desain | 20% | Web map, pencarian, detail, status data dan konteks lokasi mudah digunakan. |
| Dampak & Kelayakan Implementasi | 15% | Manfaat bagi pemantau lokal jelas; batas data dan langkah penerapan realistis. |
| Presentasi & Demonstrasi | 10% | Demo alur utama meyakinkan dan menjelaskan caveat secara jujur. |

Semua tim menggunakan versi snapshot dan tugas benchmark yang sama. Nilai setiap aspek berdasarkan bukti dari demo/prototipe. Penggunaan AI diperbolehkan; tim wajib mencantumkan tools AI dan perannya dalam pitch deck. Fitur lanjutan dinilai melalui inovasi, implementasi, fungsionalitas, dampak, dan demonstrasi sesuai rubrik JOINTS.

### Tugas Benchmark yang Disarankan

“Tampilkan deteksi pada periode yang ditentukan, fokuskan peta ke wilayah yang dipilih, lalu buka satu titik dan laporkan koordinat, waktu observasi, satelit, confidence/FRP bila tersedia, serta waktu pengambilan dataset.”

## 8. Tahapan, Kelanjutan, dan Rujukan

### Urutan Kerja yang Disarankan

| Tahap | Hasil yang dibangun |
|---|---|
| 1. Pahami data | Baca manifest dan skema, validasi koordinat/waktu, identifikasi nilai hilang. |
| 2. Bangun pencarian | Tampilkan peta nasional dan filter waktu/wilayah; pastikan hitungan hasil benar. |
| 3. Tambahkan konteks | Detail titik, legenda, provenance, timestamp snapshot, serta empty/error states. |
| 4. Uji dan demo | Jalankan acceptance checks dan peragakan tugas benchmark dengan bahasa yang tepat. |

### Kemungkinan Pengembangan Setelah Hackathon

Integrasi sumber FWI BMKG yang dapat diakses secara konsisten; validasi kegunaan dengan operator; sumber data batas wilayah resmi; peningkatan pembaruan langsung; dan analisis prediktif terpisah. Pengembangan prediksi memerlukan definisi target/horizon, label independen yang sesuai, pemisahan data berbasis waktu/ruang untuk evaluasi, serta evaluasi false negative/false positive. Fitur tersebut tidak menjadi komitmen MVP.

### Keselarasan Submission JOINTS

- **Pitch deck:** kertas A4, maksimal 10 halaman di luar cover dan references.
- **Video proposal Hackathon:** maksimal 2 menit.
- **Source code:** GitHub repository orisinal dengan README.md berisi cara menjalankan.
- **Prototype:** wajib ditunjukkan; solusi ini menetapkan web app sebagai bentuk implementasi.
- **Penggunaan AI:** wajib mencantumkan tools yang digunakan dan perannya dalam pitch deck.
- **Jadwal pada deck:** pengumpulan 15–16 Oktober 2026; Grand Final Hackathon 1 November 2026; pitching 10–12 menit dan tanya jawab 5–8 menit sesuai jadwal panitia.

### Catatan Panitia

Siapkan snapshot FIRMS tujuh hari dan manifest untuk mode benchmark; uji endpoint/API serta akses MAP_KEY sebelum acara. Berikan layer batas Indonesia dan, bila tersedia, batas hutan/gambut dengan sumber resmi.

### Referensi

- NASA FIRMS — [API Area](https://firms.modaps.eosdis.nasa.gov/api/area/): parameter area/sensor/periode, free MAP_KEY, rentang kueri, dan batas transaksi.
- NASA FIRMS — [API usage tutorial](https://firms.modaps.eosdis.nasa.gov/content/academy/data_api/firms_api_use.html): contoh kolom hasil serta anjuran mengendalikan jumlah kueri.
- NASA FIRMS — [API dan pengumuman sensor](https://firms.modaps.eosdis.nasa.gov/api/): pengumuman penghentian layanan Suomi-NPP mulai 1 November 2026.
- NASA FIRMS — [Archive Download](https://firms.modaps.eosdis.nasa.gov/download/): format dan rentang ketersediaan arsip VIIRS.
- BMKG — [Fire Weather Index Indonesia](https://www.bmkg.go.id/cuaca/karhutla/fwi): konteks FWI nasional dan prakiraan; atribusi BMKG wajib untuk penggunaan citra sesuai ketentuan yang dipublikasikan.
- JOINTS 2026 — *Technical Meeting Hackathon & Ideathon*, 12 Oktober 2026: subtema Sustainability, format submission, penggunaan AI, dan rubrik Hackathon.
- PRD sumber: *Joints-Bismillah Finalis*, terutama latar karhutla, batas interpretasi hotspot/FWI, dan kandidat sumber data historis.
