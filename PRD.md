# PRD — FireGuard
## Pantau Hotspot, Jaga Hutan dan Gambut
### Sistem Pemantauan Deteksi Aktivitas Termal + Pelaporan Masyarakat & Verifikasi Indikasi Perubahan Tutupan Hutan

| Atribut | Nilai |
|---|---|
| Subtema | Sustainability |
| Kompetisi | Hackathon JOINTS 2026 |
| Versi | **3.0** |
| Status | **Single Source of Truth (PRD)** |
| Menggantikan | `PRD_Joints_v2.md` (v2.0), `PRD-Hackathon-JOINTS-2026-Sustainability-Hotspot-WebAPI.md` (v1.0), selaras dengan `Joints-Bismillah Finalis.pdf` |
| Desain | Mengikuti `DSG.md` (FireGuard Design System v1.0) |
| Sumber data utama | **NASA FIRMS VIIRS API** (375 m; S-NPP, NOAA-20, NOAA-21) |
| Fallback | Snapshot nasional bersama (statis, berlabel) |
| Audiens | Panitia & peserta Hackathon JOINTS 2026; Operator Pemantauan; Tim Lapangan; Masyarakat/Relawan sekitar hutan & gambut |

---

## 1. Ringkasan Eksekutif

FireGuard adalah web map Indonesia yang mengambil **deteksi aktivitas termal (hotspot) NASA FIRMS VIIRS** melalui API, menyajikannya dengan filter waktu/wilayah, detail atribut sumber, status kebaruan dan provenance, serta **konteks spasial hutan dan gambut**.

**Baru di v3.0:** modul **Pelaporan Masyarakat & Verifikasi Indikasi Perubahan Tutupan Hutan**. Warga/relawan sekitar hutan dan gambut dapat melaporkan indikasi asap, kebakaran, pembukaan lahan, atau perubahan tutupan hutan di sekitar tempat tinggalnya, lengkap dengan lokasi (GPS atau titik di peta), waktu pengamatan, kategori, deskripsi, dan foto opsional. Laporan **tidak pernah** diperlakukan sebagai kejadian terkonfirmasi: ia masuk antrean verifikasi operator, divalidasi kelengkapan/duplikasi, diberi status berjejak audit, dan **ditampilkan secara visual berbeda** dari hotspot satelit serta dari data perubahan tutupan lahan.

Tujuan fitur: melengkapi pemantauan satelit dengan pengamatan langsung manusia, meningkatkan keterlacakan informasi, dan membantu menentukan **lokasi yang perlu ditinjau lebih lanjut** — tanpa mengabaikan keterbatasan data, tanpa klaim deforestasi otomatis, dan tanpa fungsi dispatch.

---

## 2. Latar Belakang & Masalah

Kebakaran hutan dan lahan berulang di Indonesia, khususnya pada lahan gambut dan vegetasi rentan terbakar, menghasilkan emisi gas/partikulat dan asap lintas wilayah. Deteksi satelit tersedia dari layanan publik, tetapi masyarakat sekitar hutan dan gambut kesulitan memantau titik api dan perubahan wilayahnya **sejak dini** dalam bentuk yang mudah dipakai, berkонтekst, berwaktu jelas, dan jelas asal datanya.

Celah yang ingin ditutup FireGuard:
1. Data satelit publik belum disajikan dengan konteks, waktu, dan provenance yang mudah dipahami warga.
2. Ada informasi lokal (asap, pembukaan lahan, bau terbakar) yang **belum** tercermin di citra satelit pada jam yang sama — dan sebaliknya, deteksi satelit bisa lolos dari perhatian warga.
3. Tidak ada mekanisme yang membuat informasi warga **terstruktur, terlacak, dan terverifikasi** alih-alih tersebar sebagai pesan tak terbuktikan.

---

## 3. Posisi Produk & Batas Klaim (KONTRAK KEJUJURAN)

FireGuard membantu **pemantauan awal**. FireGuard **tidak** mengonfirmasi kebakaran, **tidak** menentukan sebab, **tidak** memperkirakan luas kebakaran, dan **tidak** menyatakan deforestasi tanpa data perubahan tutupan lahan yang sesuai.

| Tiga kelas bukti | Nama tampilan | Arti yang diizinkan | Yang DILARANG |
|---|---|---|---|
| **A. Deteksi satelit** | "Deteksi aktivitas termal (FIRMS)" | Anomali termal 375 m pada waktu akuisisi; bisa berasal dari sumber panas lain | "Pasti terbakar", confidence = probabilitas terbakar |
| **B. Laporan masyarakat** | "Laporan warga (indikasi)" | Seseorang mengamati dan melaporkan; status verifikasi tercatat | "Terkonfirmasi kebakaran", bukti hukum, dasar dispatch |
| **C. Perubahan tutupan lahan** | "Indikasi perubahan tutupan (data spasial)" | Perubahan kelas/kanopi antar-periode dari raster yang sesuai | Luas pasti, atribusi sebab, verifikasi titik dari data agregat |

**Prinsip interaksi (wajib, dari PRD v1.0):**
- Warna/ukuran simbol **harus** punya legenda; confidence **tidak** disandikan sebagai kepastian kejadian.
- Clustering/aggregation hanya **bantuan visual**; selalu ada jalan melihat titik individual.
- Filter aktif, jumlah hasil, periode, dan metadata sumber **mudah ditemukan** tanpa membuka dokumentasi.
- Wilayah tanpa laporan = **"belum ada informasi pelaporan"**, bukan "aman".

---

## 4. Persona Pengguna

| Persona | Kebutuhan utama |
|---|---|
| **Operator Pemantauan** (pengguna utama) | Peta deteksi + waktu, atribut (confidence, FRP), fire danger bila tersedia, konteks geospasial, filter wilayah/waktu, detail titik/wilayah, **antrean verifikasi laporan** |
| **Tim Lapangan** | Lokasi & waktu deteksi/laporan, confidence dan atribut relevan, konteks wilayah, catatan bahwa verifikasi akhir tetap berdasarkan kondisi aktual |
| **Masyarakat / Relawan Pelapor** (baru) | Melaporkan dengan cepat dari ponsel, menentukan titik dengan GPS, mengunggah foto, melihat status laporannya, memahami bahwa laporannya **belum** terkonfirmasi |
| **Verifikator / Moderasi** (peran operator) | Kelengkapan, duplikasi, konsistensi dengan deteksi satelit, keputusan status + alasan, jejak audit |
| **Panitia / Reviewer** | Demo alur utama, kejujuran caveat, keamanan API key, ketahanan saat API gagal |

---

## 5. Tujuan & Non-Tujuan

### Tujuan
1. Menyajikan deteksi FIRMS pada peta nasional melalui **API**, dengan pencarian, detail titik, metadata waktu, provenance, dan konteks spasial hutan/gambut.
2. Membuka jalur **pelaporan masyarakat** yang terstruktur, tervalidasi, dan terverifikasi untuk lokasi yang perlu ditinjau lebih lanjut.
3. Menjaga **keterlacakan**: setiap titik dan laporan punya sumber, waktu, dan status yang terlihat.
4. Tetap berfungsi saat API gagal (snapshot statis berlabel).

### Non-Tujuan (Out of Scope — eksplisit)
- Prediksi titik sebelum terdeteksi; konfirmasi kebakaran; penentuan sebab; estimasi luas kebakaran.
- Deteksi otomatis deforestasi tanpa data perubahan tutupan lahan yang sesuai.
- Rute pemadaman/evakuasi, dispatch, alert multi-kanal (WhatsApp/SMS/push/sirene).
- Model ML untuk memfilter/membuka laporan pada MVP. **Peta risiko ML = Fase 2, eksperimental, tidak menjadi dasar keputusan verifikasi.**
- Menggunakan jumlah laporan sebagai ukuran tingkat/luas deforestasi.
- Menggunakan `IDN.xlsx` (agregat provinsi, tahunan, ambang >30% kanopi) sebagai verifikasi titik.

---

## 6. Ruang Lingkup

| Fase | Isi | Status |
|---|---|---|
| **MVP (demo penilaian)** | Peta Indonesia; FIRMS API + cache + fallback snapshot; filter waktu/wilayah/satelit; detail titik; freshness & provenance; layer konteks hutan/gambut; **modul lapor + validasi + dedupe + status verifikasi + audit + diferensiasi visual 3 kelas bukti** | **WAJIB** |
| **Fase 1.5** | FWI BMKG (opsional, bila sumber numerik tersedia); panel konteks tutupan pohon agregat dari `IDN.xlsx`; ekspor CSV/GeoJSON | Bila waktu cukup |
| **Fase 2** | Dashboard analitik (jumlah, distribusi wilayah, tren waktu); fitur "laporan terkait" lanjutan; citra Sentinel-2 before/after untuk verifikator | Pasca-hackathon |
| **Fase 3 (eksperimental)** | Peta risiko berbasis ML (RF/XGBoost) dengan ERA5-Land + burned area sebagai label — hanya dengan dataset, baseline, dan target yang ditetapkan lebih dulu | **Tidak** untuk demo |

---

## 7. Kebutuhan Fungsional

### 7.1 Inti pemantauan (dipertahankan dari v1.0)

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| **FR-01** | Peta Indonesia menampilkan deteksi FIRMS API atau snapshot yang lolos filter | Posisi mengikuti koordinat sumber; tampilan dapat dinavigasi; tidak menyamarkan makna titik |
| **FR-02** | Filter periode observasi (rentang tanggal/waktu) | Hasil hanya berisi rekaman dalam rentang terpilih; **zona waktu dijelaskan** (UTC + WIB/WITA/WIT) |
| **FR-03** | Filter/navigasi wilayah bila batas administratif disediakan | Wilayah terpilih jelas; batas wilayah ditandai **sebagai konteks, bukan data hotspot** |
| **FR-04** | Memilih titik membuka detail atribut sumber | Koordinat, waktu akuisisi, satelit/sensor, confidence/FRP bila tersedia, sumber terlihat |
| **FR-05** | Status dataset & kebaruan selalu terlihat | Snapshot: label **"statis"** + waktu pengambilan. Mode API: waktu observasi, waktu diterima, status terakhir |
| **FR-06** | Keadaan kosong, error, loading | Penjelasan yang dapat ditindaklanjuti; data **tidak** dianggap valid saat gagal diproses |
| **FR-07** | Layer konteks hutan/gambut opsional dari panitia | Legenda & sumber jelas; jarak/kedekatan dihitung terhadap geometri sumber; **tanpa klaim deforestasi** |
| **FR-08** | Ambil deteksi FIRMS melalui API web | **API key hanya di backend**; tampilkan status & waktu pembaruan; **cache** hasil; **fallback snapshot** saat gagal |
| **FR-09** | Layer FWI opsional | FWI dijelaskan sebagai **indikator intensitas api bila kebakaran terjadi**; tampilkan tanggal prakiraan & **atribusi BMKG**; bila hanya peta visual → nyatakan keterbatasan |

### 7.2 Modul Pelaporan Masyarakat & Verifikasi (BARU)

| ID | Kebutuhan | Penerimaan minimum |
|---|---|---|
| **FR-10** | Form pelaporan masyarakat | Kategori tetap: `indikasi_asap`, `indikasi_kebakaran`, `pembukaan_lahan`, `perubahan_tutupan`, `lainnya`. Field: lokasi, waktu pengamatan, deskripsi, foto opsional (maks. 2, kompresi sisi klien). Submisi menghasilkan status awal **`menunggu_verifikasi`** |
| **FR-11** | Penentuan lokasi | GPS perangkat **atau** pilih titik di peta. Disimpan: koordinat, **metode**, **akurasi/radius ketidakpastian**. Radius ketidakpastian **ditampilkan** di peta & detail |
| **FR-12** | Validasi & deduplikasi | Validasi kelengkapan, koordinat dalam wilayah Indonesia, waktu pengamatan tidak di masa depan, selisih waktu-lapor masuk akal. Kandidat duplikat = kesamaan **lokasi (radius) + jendela waktu + kategori** → ditandai sebagai **terkait**, **tidak dihapus** |
| **FR-13** | Antrean & siklus status verifikasi | Status: `menunggu_verifikasi` → `perlu_pemeriksaan` → `terverifikasi` \| `ditolak` (alasan wajib). Setiap perubahan tercatat: siapa, kapan, alasan |
| **FR-14** | Laporan terkait | Laporan yang diduga merujuk kejadian sama dapat **dihubungkan**; tampilan "kejadian terkait" menampilkan seluruh anggota tanpa menghapus yang asli |
| **FR-15** | Diferensiasi visual 3 kelas bukti | Kelas A (satelit), B (laporan warga), C (perubahan tutupan) berbeda **warna + bentuk + label + entri legenda**; tidak pernah digabung menjadi satu simbol "kepastian"; toggle independen |
| **FR-16** | Provenance laporan | Detail menampilkan: waktu **mengamati** vs waktu **melapor**, metode lokasi + akurasi, sumber/atribusi foto, status, **riwayat status (audit trail)**, dan pernyataan "belum terkonfirmasi" selama status bukan `terverifikasi` |
| **FR-17** | Cakupan pelaporan | Wilayah tanpa laporan ditandai **"belum ada informasi pelaporan"** (netral), **bukan** "aman/bebas api". Indikator cakupan per wilayah tersedia |
| **FR-18** | Perbandingan dengan data lain di detail laporan | Menampilkan: deteksi FIRMS terdekat dalam radius & jendela waktu (sebagai **konsisten/tidak konsisten**, bukan konfirmasi), konteks hutan/gambut, dan **konteks agregat tutupan pohon** bila tersedia dengan label "agregat, bukan pengukuran di titik ini" |
| **FR-19** | Keamanan & privasi pelapor | **EXIF/GPS foto di-strip**, kompresi, opsi **anonim**, tanpa data kontak di tampilan publik, pseudonym ID, rate limit per perangkat/sesi, moderasi konten, disclaimer keselamatan ("laporkan dari jarak aman; jangan mendekati asap/api") |
| **FR-20** | Ekspor & audit | Ekspor CSV/GeoJSON laporan + metadata; log audit perubahan status tidak dapat diedit diam-diam |
| **FR-21** | Ringkasan kualitas data (ringkas) | Jumlah laporan, distribusi status, median waktu verifikasi, cakupan wilayah. **Tidak** menampilkan skor/luas deforestasi |

---

## 8. User Stories & Acceptance Criteria

| ID | User Story | AC |
|---|---|---|
| **US-01** | Sebagai **masyarakat/relawan**, saya ingin melaporkan indikasi asap/kebakaran/pembukaan lahan di sekitar saya, agar lokasi itu dapat ditinjau lebih lanjut | **AC-01** Form dapat dibuka dari peta; titik dapat diambil dari GPS atau dipilih manual; kategori & waktu pengamatan wajib; foto opsional. **AC-02** Setelah kirim, laporan tampil sebagai simbol **kelas B** dengan status `menunggu_verifikasi` dan teks "belum terkonfirmasi". **AC-03** Tidak ada klaim otomatis apa pun yang muncul |
| **US-02** | Sebagai **Operator Pemantauan**, saya ingin memverifikasi laporan, agar kualitas data terjaga | **AC-04** Antrean verifikasi menampilkan kelengkapan, duplikat kandidat, dan deteksi FIRMS terdekat dalam radius/jendela waktu. **AC-05** Operator dapat mengubah status ke `perlu_pemeriksaan`/`terverifikasi`/`ditolak` dengan **alasan wajib** untuk penolakan. **AC-06** Seluruh perubahan tercatat (waktu, aktor, alasan) |
| **US-03** | Sebagai **Operator**, saya ingin membandingkan laporan warga dengan deteksi satelit tanpa mencampurkannya | **AC-07** Tiga layer dapat diaktifkan/nonaktifkan independen dengan legenda terpisah. **AC-08** Sistem menyatakan "konsisten"/"tidak konsisten" beserta radius & jendela waktu yang dipakai, **bukan** "terkonfirmasi" |
| **US-04** | Sebagai **Relawan**, saya ingin menyaring wilayah dan periode, agar fokus pada kabupaten sekitar saya | **AC-09** Filter wilayah/waktu/satelit bekerja; jumlah hasil, periode, zona waktu, dan metadata sumber terlihat tanpa dokumentasi terpisah |
| **US-05** | Sebagai **Operator**, saya ingin membuka satu titik FIRMS dan membaca atributnya | **AC-10** Detail menampilkan koordinat, waktu akuisisi, satelit/sensor, confidence/FRP bila tersedia, sumber, dan waktu pengambilan dataset |
| **US-06** | Sebagai **Operator**, saya ingin layer FWI bila tersedia | **AC-11** FWI tampil dengan kategori, tanggal prakiraan, atribusi BMKG, dan deskripsi "indikator intensitas api bila kebakaran terjadi". Bila tidak tersedia secara numerik → keadaan **"tidak tersedia"** yang jujur |
| **US-07** | Sebagai **Operator**, saya ingin konteks tutupan pohon wilayah | **AC-12** Panel agregat (provinsi/tahun, ambang >30% kanopi, sumber & atribusi) tampil dengan label eksplisit bahwa ia **bukan** pengukuran di titik laporan |
| **US-08** | Sebagai **pengguna**, saya ingin aplikasi tetap berguna saat API gagal | **AC-13** Fallback snapshot tampil berlabel **"statis"** + waktu pengambilan + status kegagalan API |
| **US-09** | Sebagai **panitia/auditor**, saya ingin menelusuri asal setiap informasi | **AC-14** Ekspor laporan + audit trail dapat diunduh dan dibaca tanpa konteks tersembunyi |

---

## 9. Alur Pengguna

### 9.1 Melaporkan (masyarakat)
Buka peta → zonoom ke sekitar → tombol **Lapor** → ambil titik (GPS/manual) + radius akurasi → pilih kategori → isi waktu pengamatan & deskripsi → unggah foto (opsional, EXIF di-strip) → centang persetujuan & baca disclaimer keselamatan → kirim → **status `menunggu_verifikasi`** → pengguna dapat memantau status laporannya.

### 9.2 Memverifikasi (operator)
Antrean → buka laporan → periksa kelengkapan & duplikat kandidat → lihat deteksi FIRMS terdekat (radius/jendela waktu) + konteks hutan/gambut → keputusan: `perlu_pemeriksaan` / `terverifikasi` / `ditolak (alasan)` → audit trail tercatat → tampilan publik diperbarui (simbol kelas B berubah state, **tetap** kelas B).

### 9.3 Perbandingan bukti
Operator mengaktifkan layer A, B, C secara terpisah → membaca legenda masing-masing → menarik kesimpulan "perlu tinjauan lapangan", **bukan** "terbukti".

---

## 10. Model Data (ringkas)

**`HotspotObservation`** — `id`, `lat`, `lon`, `acq_date`, `acq_time`, `confidence`, `frp`, `satellite`, `sensor`, `source`, `ingested_at`, `dataset_mode` (`api`\|`snapshot`), `snapshot_taken_at`.

**`Report`** — `id` (pseudonym), `lat`, `lon`, `location_method` (`gps`\|`map_pick`), `accuracy_m`, `observed_at`, `reported_at`, `category`, `description`, `status`, `dedupe_key`, `linked_report_ids[]`, `consent_granted`, `anonymous`, `created_by_ref`, `safety_ack`.

**`ReportMedia`** — `id`, `report_id`, `storage_key`, `exif_stripped: true`, `width`, `height`, `bytes`, `uploaded_at`.

**`VerificationEvent`** — `id`, `report_id`, `from_status`, `to_status`, `reason`, `actor_role`, `created_at` *(append-only)*.

**`CoverageStat`** — `admin_id`, `period`, `report_count`, `verified_count`, `status: "belum_ada_informasi_pelaporan" | "ada"`.

**`ContextAggregate`** (dari `IDN.xlsx`) — `admin_level1`, `year`, `tree_cover_loss`, `dominant_driver`, `canopy_threshold: ">30%"`, `source`, `attribution`, `granularity_note: "agregat, bukan per-piksel"`.

**Enum status laporan:** `menunggu_verifikasi`, `perlu_pemeriksaan`, `terverifikasi`, `ditolak`.
**Enum kelas bukti:** `A_satelit`, `B_laporan_warga`, `C_perubahan_tutupan`.

---

## 11. Sumber Data & Provenance

| Sumber | Penggunaan | Status | Aturan penyajian |
|---|---|---|---|
| **NASA FIRMS VIIRS (375 m)** | Deteksi aktivitas termal NRT | **Utama (API)** | Selalu dengan waktu akuisisi, satelit/sensor, confidence/FRP bila ada, + waktu pengambilan dataset |
| **Snapshot nasional bersama** | Fallback & benchmark | Wajib ada | Label **"statis"** + waktu pengambilan |
| **Layer konteks hutan/gambut (panitia)** | Konteks spasial | Opsional | Legenda + sumber; batas = konteks, bukan data hotspot |
| **`IDN.xlsx` (GFW: tree cover & loss by driver, nasional–provinsi)** | **Konteks agregat** tutupan pohon & pendorong | Opsional (Fase 1.5) | Wajib label: **agregat tahunan, ambang >30% kanopi, bukan pengukuran di titik ini**; **tidak** dipakai untuk verifikasi |
| **BMKG FWI** | Indikator fire danger, hingga H+7 | **Opsional**, ketersediaan API belum pasti | Atribusi BMKG + tanggal prakiraan + definisi "intensitas api bila kebakaran terjadi" |
| **ESA WorldCover / peta gambut resmi / DEM / batas admin** | Fitur & agregasi kontekstual | Perlu verifikasi sumber resmi, tahun, resolusi | Bila sumber resmi belum ditemukan → **jangan** ditampilkan |
| **Hansen GFC / GLAD / RADD / Sentinel-2 / MCD64A1** | **Prasyarat** klaim "indikasi perubahan tutupan" per titik | Fase 2 | Tanpa ini, kelas C **tidak** boleh diklaim |

---

## 12. Kebutuhan Non-Fungsional

| Kategori | requirement |
|---|---|
| **Keamanan** | API key **hanya di backend**; proxy dengan allowlist domain; foto melalui URL bertanda & kedaluwarsa; sanitasi deskripsi; rate limit per sesi/perangkat |
| **Privasi** | Strip EXIF/GPS; opsi anonim; tanpa nomor/kontak di publik; minimalisasi data; retensi default 24 bulan; hak hapus atas permintaan |
| **Keselamatan** | Disclaimer wajib sebelum kirim: laporkan dari jarak aman, jangan mendekati asap/api; **tidak** ada fitur dispatch/rute |
| **Keandalan** | Cache respons API; fallback snapshot; antrian ulang saat gagal; **data tidak dianggap valid saat pipeline gagal** |
| **Performa** | Peta interaktif首 < 2 s pada koneksi sedang; clustering sebagai bantuan visual; kompresi foto sisi klien |
| **Aksesibilitas** | WCAG 2.1 AA; kontras ≥ 4.5:1; target sentuh ≥ 44 px; peta punya **alternatif daftar** yang dapat dinavigasi papan ketik; `aria-live` untuk status kebaruan |
| **Konektivitas rendah** | Mode hemat data; **draft laporan tersimpan lokal** saat offline, kirim saat terhubung |
| **i18n** | Indonesia (default) & Inggris untuk label teknis |
| **Auditabilitas** | Audit trail append-only; ekspor CSV/GeoJSON |

---

## 13. Analisis Dataset `IDN.xlsx` (Keputusan)

**Putusan: dipakai sebagai KONTEKS AGREGAT, bukan sebagai alat verifikasi atau pengukur luas.**

| Bisa | Tidak bisa |
|---|---|
| Menunjukkan kehilangan tutupan pohon & **dominant driver** per provinsi per tahun sebagai latar wilayah | Menentukan apa pun di koordinat laporan tertentu |
| Membantu prioritisasi wilayah tinjauan | Menghitung luas deforestasi dari jumlah laporan |
| Menjelaskan secara jujur mengapa suatu provinsi rawan | Mendeteksi perubahan pada **gambut terbuka/semak** (ambang >30% kanopi) |
| Menjadi pembanding tren tahunan | Mencocokkan laporan near-real-time dengan resolusi tahunan |

**Validasi yang wajib dilakukan sebelum integrasi:** konfirmasi kolom, tingkat administrasi, rentang tahun, satuan, kelengkapan atribusi *driver*, lisensi & teks atribusi GFW/Hansen.
**Yang dibutuhkan agar klaim kelas C sah:** raster perubahan tutupan 10–30 m (Hansen GFC / GLAD / RADD), ESA WorldCover untuk kelas lahan, Sentinel-2 untuk tinjauan visual before/after, MCD64A1 sebagai pembanding kebakaran.

---

## 14. KPI & Indikator Keberhasilan

| Indikator | Cara ukur | Target |
|---|---|---|
| Hotspot ingestion | Data FIRMS diterima & diproses | Berfungsi sesuai periode pengujian |
| Akurasi spasial hotspot | Koordinat sumber diplot sesuai | Lulus seluruh test case |
| **Data freshness** | Waktu observasi → waktu diterima | **Dicatat & dilaporkan**, tidak dipaksakan < 15 menit |
| Integrasi fire danger | Indeks tampil pada wilayah/periode sesuai | Seluruh fungsi MVP berjalan |
| Integrasi spasial | Hotspot + konteks dalam satu peta | Lulus test case MVP |
| **Kelengkapan laporan** | % laporan dengan lokasi + waktu + kategori + deskripsi | ≥ 90% lolos validasi awal |
| **Dedupe** | % kandidat duplikat terdeteksi & tertaut (bukan terhapus) | Tertaut, 0 laporan hilang |
| **Waktu verifikasi** | Median `reported_at` → keputusan pertama | Terukur & dilaporkan |
| **Integritas status** | % perubahan status beralasan & ber-audit | 100% |
| **Kejujuran cakupan** | Wilayah tanpa laporan tampil sebagai "belum ada informasi" | 100% |
| Kinerja ML* | Precision/Recall/F1 | **Fase 2** — setelah dataset, baseline, dan target ditetapkan |

---

## 15. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Laporan palsu/spam mengotori peta | Validasi, rate limit, antrean verifikasi, status eksplisit, simbol berbeda dari satelit |
| Publik menafsirkan laporan = kebakaran terkonfirmasi | Label "indikasi", status terlihat, mikrocopy dilarang memakai "terkonfirmasi" kecuali status `terverifikasi` + caveat |
| Kesalahpahaman confidence satelit | Confidence sebagai atribut + kelas tampilan dengan legenda, bukan ukuran kepastian |
| Klaim deforestasi tanpa data yang sesuai | Kelas C dibatasi; `IDN.xlsx` diberi label agregat; tanpa raster sesuai → fitur C nonaktif |
| Bahaya bagi pelapor | Disclaimer keselamatan, tanpa dispatch/rute, tanpa identitas publik |
| Kebocoran PII lewat foto | Strip EXIF/GPS, kompresi, opsi anonim, retensi & hak hapus |
| API FIRMS gagal | Cache + snapshot statis berlabel + status error yang dapat ditindaklanjuti |
| Scope membengkak (rubrik implementasi 30%) | MVP dipangkas; dashboard & ML ke Fase 2; tiap FR punya penerimaan minimum |
| Layer konteks tanpa sumber resmi | Jangan tampilkan bila sumber/tahun/resolusi tidak terverifikasi |

---

## 16. Keselarasan Rubrik & Skrip Demo

| Bobot | Bukti yang ditunjukkan |
|---|---|
| **Inovasi 25%** | Jalur **pelaporan masyarakat + verifikasi berjenjang** yang melengkapi (bukan menggantikan) satelit, dengan pemisahan tiga kelas bukti |
| **Implementasi Teknis 30%** | Integrasi FIRMS API benar, **API key di backend**, cache + fallback snapshot, geospasial & dedupe berfungsi, audit trail |
| **Fungsionalitas & Desain 20%** | Web map, pencarian, filter, detail titik, status kebaruan, konteks, form lapor yang mudah dipakai di ponsel |
| **Dampak & Kelayakan 15%** | Manfaat bagi pemantau lokal jelas; batas data & langkah penerapan realistis; privasi & keselamatan ditangani |
| **Presentasi 10%** | Demo singkat, caveat diucapkan secara terbuka |

**Skrip demo (≤ 5 menit):**
1. *"Tampilkan deteksi pada periode yang ditentukan, fokuskan peta ke wilayah yang dipilih, lalu buka satu titik dan laporkan koordinat, waktu observasi, satelit, confidence/FRP bila tersedia, serta waktu pengambilan dataset."*
2. Matikan jaringan API → tunjukkan **snapshot statis berlabel** + status error yang jujur.
3. Buat **laporan warga** (GPS + kategori + foto) → tunjukkan strip EXIF, status `menunggu_verifikasi`, simbol **kelas B** yang berbeda dari titik satelit.
4. Sebagai operator: lihat **deteksi terdekat** (radius & jendela waktu) → nyatakan "konsisten/tidak konsisten", **bukan** terkonfirmasi → ubah status → tunjukkan **audit trail**.
5. Tunjukkan wilayah **tanpa laporan** sebagai "belum ada informasi pelaporan".
6. Tutup dengan batas produk: tidak mengonfirmasi kebakaran, tidak menghitung deforestasi, tidak melakukan dispatch.

---

## 17. Asumsi & Pertanyaan Terbuka

- Ketersediaan **API numerik FWI BMKG** belum dipastikan → bila hanya peta visual, fitur ditampilkan sebagai konteks terbatas atau dinonaktifkan.
- **Peta gambut resmi** (sumber, tahun, resolusi) belum ditetapkan → tanpa sumber resmi, layer tidak ditampilkan.
- Batas administratif (provinsi/kabupaten) diperlukan untuk FR-03 & FR-17.
- Layer konteks hutan/gambut diasumsikan disediakan panitia; bila tidak, FR-07 dinyatakan "tidak tersedia".
- Skema `IDN.xlsx` perlu diverifikasi (kolom, tahun, tingkat admin, atribusi).

---

## 18. Glosarium & Larangan Istilah

**Gunakan:** deteksi aktivitas termal (hotspot) · anomali termal · indikasi · perlu tinjauan · konsisten/tidak konsisten · belum ada informasi pelaporan · agregat.
**Dilarang:** "kebakaran terkonfirmasi" (kecuali status `terverifikasi` + caveat) · "pasti terbakar" · confidence = probabilitas terbakar · "deforestasi terdeteksi" dari data agregat · "wilayah aman" untuk wilayah tanpa data · janji alert WhatsApp/SMS/push/sirene.