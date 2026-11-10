/**
 * Modul Geocoding & Resolusi Wilayah Kalimantan (Kabupaten / Kota & Lokasi Spesifik).
 * Mengidentifikasi nama Kabupaten/Kota, bagian wilayah spesifik, serta jarak ke pusat daerah
 * terdekat untuk setiap koordinat titik api (hotspot).
 */

export const KALIMANTAN_BOUNDS = {
  minLat: -5.2,
  maxLat: 4.8,
  minLon: 108.0,
  maxLon: 119.5,
};

export function isInsideKalimantan(lat?: number | null, lon?: number | null): boolean {
  if (typeof lat !== 'number' || typeof lon !== 'number') return false;
  if (Number.isNaN(lat) || Number.isNaN(lon)) return false;
  return (
    lat >= KALIMANTAN_BOUNDS.minLat &&
    lat <= KALIMANTAN_BOUNDS.maxLat &&
    lon >= KALIMANTAN_BOUNDS.minLon &&
    lon <= KALIMANTAN_BOUNDS.maxLon
  );
}

export interface LocationDetail {
  kabupaten: string; // e.g. "Kab. Kotawaringin Timur"
  kabupatenFull: string; // e.g. "Kabupaten Kotawaringin Timur"
  nearestCenter: string; // e.g. "Kota Sampit"
  distanceKm: number; // e.g. 28.4
  compassDirection: string; // e.g. "Barat Daya"
  subRegion: string; // e.g. "Kalimantan Tengah bagian Selatan"
  formattedShort: string; // e.g. "Kab. Kotawaringin Timur (±28 km dari Sampit)"
  formattedFull: string; // e.g. "Kab. Kotawaringin Timur • ±28 km arah Barat Daya dari Kota Sampit (Kalimantan Tengah bagian Selatan)"
}

interface CenterPoint {
  name: string;
  lat: number;
  lon: number;
  province: string;
  kabupaten: string;
  subRegion: string;
}

// 56 Pusat Kabupaten/Kota & Titik Acuan Strategis di 5 Provinsi Kalimantan
const KALIMANTAN_CENTERS: CenterPoint[] = [
  // --- KALIMANTAN TENGAH ---
  { name: 'Palangka Raya', lat: -2.2078, lon: 113.9165, province: 'Kalimantan Tengah', kabupaten: 'Kota Palangka Raya', subRegion: 'Kalimantan Tengah bagian Tengah' },
  { name: 'Sampit', lat: -2.5333, lon: 112.9500, province: 'Kalimantan Tengah', kabupaten: 'Kab. Kotawaringin Timur', subRegion: 'Kalimantan Tengah bagian Selatan' },
  { name: 'Pangkalan Bun', lat: -2.6833, lon: 111.6167, province: 'Kalimantan Tengah', kabupaten: 'Kab. Kotawaringin Barat', subRegion: 'Kalimantan Tengah bagian Barat Daya' },
  { name: 'Kuala Kapuas', lat: -3.0094, lon: 114.3872, province: 'Kalimantan Tengah', kabupaten: 'Kab. Kapuas', subRegion: 'Kalimantan Tengah bagian Tenggara' },
  { name: 'Pulang Pisau', lat: -2.7500, lon: 114.2500, province: 'Kalimantan Tengah', kabupaten: 'Kab. Pulang Pisau', subRegion: 'Kalimantan Tengah bagian Selatan' },
  { name: 'Kasongan', lat: -1.9000, lon: 113.3833, province: 'Kalimantan Tengah', kabupaten: 'Kab. Katingan', subRegion: 'Kalimantan Tengah bagian Tengah-Selatan' },
  { name: 'Kuala Pembuang', lat: -3.3000, lon: 112.5500, province: 'Kalimantan Tengah', kabupaten: 'Kab. Seruyan', subRegion: 'Kalimantan Tengah bagian Pesisir Selatan' },
  { name: 'Muara Teweh', lat: -0.9500, lon: 114.8833, province: 'Kalimantan Tengah', kabupaten: 'Kab. Barito Utara', subRegion: 'Kalimantan Tengah bagian Timur Laut' },
  { name: 'Buntok', lat: -1.7167, lon: 114.8333, province: 'Kalimantan Tengah', kabupaten: 'Kab. Barito Selatan', subRegion: 'Kalimantan Tengah bagian Timur' },
  { name: 'Tamiang Layang', lat: -2.0333, lon: 115.1500, province: 'Kalimantan Tengah', kabupaten: 'Kab. Barito Timur', subRegion: 'Kalimantan Tengah bagian Timur' },
  { name: 'Puruk Cahu', lat: -0.6167, lon: 114.5833, province: 'Kalimantan Tengah', kabupaten: 'Kab. Murung Raya', subRegion: 'Kalimantan Tengah bagian Pedalaman Utara' },
  { name: 'Kuala Kurun', lat: -1.3167, lon: 113.8667, province: 'Kalimantan Tengah', kabupaten: 'Kab. Gunung Mas', subRegion: 'Kalimantan Tengah bagian Tengah-Utara' },
  { name: 'Nanga Bulik', lat: -2.1833, lon: 111.2833, province: 'Kalimantan Tengah', kabupaten: 'Kab. Lamandau', subRegion: 'Kalimantan Tengah bagian Barat' },
  { name: 'Sukamara', lat: -2.6333, lon: 111.2333, province: 'Kalimantan Tengah', kabupaten: 'Kab. Sukamara', subRegion: 'Kalimantan Tengah bagian Barat Daya' },

  // --- KALIMANTAN BARAT ---
  { name: 'Pontianak', lat: -0.0263, lon: 109.3425, province: 'Kalimantan Barat', kabupaten: 'Kota Pontianak', subRegion: 'Kalimantan Barat bagian Pesisir Barat' },
  { name: 'Singkawang', lat: 0.9083, lon: 108.9833, province: 'Kalimantan Barat', kabupaten: 'Kota Singkawang', subRegion: 'Kalimantan Barat bagian Barat Laut' },
  { name: 'Sambas', lat: 1.3500, lon: 109.3000, province: 'Kalimantan Barat', kabupaten: 'Kab. Sambas', subRegion: 'Kalimantan Barat bagian Paling Utara' },
  { name: 'Mempawah', lat: 0.3500, lon: 109.1667, province: 'Kalimantan Barat', kabupaten: 'Kab. Mempawah', subRegion: 'Kalimantan Barat bagian Pesisir Barat' },
  { name: 'Sungai Raya', lat: -0.1167, lon: 109.3833, province: 'Kalimantan Barat', kabupaten: 'Kab. Kubu Raya', subRegion: 'Kalimantan Barat bagian Barat Daya' },
  { name: 'Ketapang', lat: -1.8500, lon: 109.9667, province: 'Kalimantan Barat', kabupaten: 'Kab. Ketapang', subRegion: 'Kalimantan Barat bagian Selatan' },
  { name: 'Sukadana', lat: -1.2500, lon: 109.9500, province: 'Kalimantan Barat', kabupaten: 'Kab. Kayong Utara', subRegion: 'Kalimantan Barat bagian Pesisir Barat Daya' },
  { name: 'Sanggau', lat: 0.1167, lon: 110.5833, province: 'Kalimantan Barat', kabupaten: 'Kab. Sanggau', subRegion: 'Kalimantan Barat bagian Tengah' },
  { name: 'Sintang', lat: 0.0667, lon: 111.4833, province: 'Kalimantan Barat', kabupaten: 'Kab. Sintang', subRegion: 'Kalimantan Barat bagian Timur' },
  { name: 'Putussibau', lat: 0.8333, lon: 112.9167, province: 'Kalimantan Barat', kabupaten: 'Kab. Kapuas Hulu', subRegion: 'Kalimantan Barat bagian Pedalaman Timur' },
  { name: 'Bengkayang', lat: 0.8167, lon: 109.6667, province: 'Kalimantan Barat', kabupaten: 'Kab. Bengkayang', subRegion: 'Kalimantan Barat bagian Utara' },
  { name: 'Ngabang', lat: 0.3833, lon: 109.9500, province: 'Kalimantan Barat', kabupaten: 'Kab. Landak', subRegion: 'Kalimantan Barat bagian Tengah-Barat' },
  { name: 'Sekadau', lat: 0.0333, lon: 110.9500, province: 'Kalimantan Barat', kabupaten: 'Kab. Sekadau', subRegion: 'Kalimantan Barat bagian Tengah' },
  { name: 'Nanga Pinoh', lat: -0.3333, lon: 111.7000, province: 'Kalimantan Barat', kabupaten: 'Kab. Melawi', subRegion: 'Kalimantan Barat bagian Tenggara' },

  // --- KALIMANTAN SELATAN ---
  { name: 'Banjarmasin', lat: -3.3167, lon: 114.5833, province: 'Kalimantan Selatan', kabupaten: 'Kota Banjarmasin', subRegion: 'Kalimantan Selatan bagian Muara Barito' },
  { name: 'Banjarbaru', lat: -3.4500, lon: 114.8333, province: 'Kalimantan Selatan', kabupaten: 'Kota Banjarbaru', subRegion: 'Kalimantan Selatan bagian Lembah Meratus' },
  { name: 'Martapura', lat: -3.4167, lon: 114.8500, province: 'Kalimantan Selatan', kabupaten: 'Kab. Banjar', subRegion: 'Kalimantan Selatan bagian Tengah' },
  { name: 'Pelaihari', lat: -3.8000, lon: 114.7667, province: 'Kalimantan Selatan', kabupaten: 'Kab. Tanah Laut', subRegion: 'Kalimantan Selatan bagian Selatan' },
  { name: 'Batulicin', lat: -3.4500, lon: 115.9833, province: 'Kalimantan Selatan', kabupaten: 'Kab. Tanah Bumbu', subRegion: 'Kalimantan Selatan bagian Pesisir Tenggara' },
  { name: 'Kotabaru', lat: -3.2333, lon: 116.2167, province: 'Kalimantan Selatan', kabupaten: 'Kab. Kotabaru', subRegion: 'Kalimantan Selatan Pulau Laut' },
  { name: 'Marabahan', lat: -2.9833, lon: 114.7667, province: 'Kalimantan Selatan', kabupaten: 'Kab. Barito Kuala', subRegion: 'Kalimantan Selatan bagian Barat' },
  { name: 'Rantau', lat: -2.9333, lon: 115.1500, province: 'Kalimantan Selatan', kabupaten: 'Kab. Tapin', subRegion: 'Kalimantan Selatan bagian Tengah' },
  { name: 'Kandangan', lat: -2.7833, lon: 115.2667, province: 'Kalimantan Selatan', kabupaten: 'Kab. Hulu Sungai Selatan', subRegion: 'Kalimantan Selatan bagian Lembah Hulu' },
  { name: 'Barabai', lat: -2.5833, lon: 115.3833, province: 'Kalimantan Selatan', kabupaten: 'Kab. Hulu Sungai Tengah', subRegion: 'Kalimantan Selatan bagian Lembah Hulu' },
  { name: 'Amuntai', lat: -2.4167, lon: 115.2500, province: 'Kalimantan Selatan', kabupaten: 'Kab. Hulu Sungai Utara', subRegion: 'Kalimantan Selatan bagian Rawa Hulu' },
  { name: 'Paringin', lat: -2.3333, lon: 115.4667, province: 'Kalimantan Selatan', kabupaten: 'Kab. Balangan', subRegion: 'Kalimantan Selatan bagian Lereng Meratus' },
  { name: 'Tanjung', lat: -2.1833, lon: 115.4000, province: 'Kalimantan Selatan', kabupaten: 'Kab. Tabalong', subRegion: 'Kalimantan Selatan bagian Utara' },

  // --- KALIMANTAN TIMUR ---
  { name: 'Samarinda', lat: -0.5022, lon: 117.1536, province: 'Kalimantan Timur', kabupaten: 'Kota Samarinda', subRegion: 'Kalimantan Timur Muara Mahakam' },
  { name: 'Balikpapan', lat: -1.2654, lon: 116.8312, province: 'Kalimantan Timur', kabupaten: 'Kota Balikpapan', subRegion: 'Kalimantan Timur Pesisir Selat Makassar' },
  { name: 'Bontang', lat: 0.1333, lon: 117.5000, province: 'Kalimantan Timur', kabupaten: 'Kota Bontang', subRegion: 'Kalimantan Timur Pesisir Timur' },
  { name: 'Tenggarong', lat: -0.4167, lon: 116.9833, province: 'Kalimantan Timur', kabupaten: 'Kab. Kutai Kartanegara', subRegion: 'Kalimantan Timur Cekungan Mahakam' },
  { name: 'Sendawar', lat: -0.2333, lon: 115.7000, province: 'Kalimantan Timur', kabupaten: 'Kab. Kutai Barat', subRegion: 'Kalimantan Timur bagian Pedalaman Barat' },
  { name: 'Sangatta', lat: 0.5000, lon: 117.5500, province: 'Kalimantan Timur', kabupaten: 'Kab. Kutai Timur', subRegion: 'Kalimantan Timur bagian Timur' },
  { name: 'Tanjung Redeb', lat: 2.1500, lon: 117.4833, province: 'Kalimantan Timur', kabupaten: 'Kab. Berau', subRegion: 'Kalimantan Timur bagian Utara' },
  { name: 'Tanah Grogot', lat: -1.9000, lon: 116.2000, province: 'Kalimantan Timur', kabupaten: 'Kab. Paser', subRegion: 'Kalimantan Timur bagian Selatan' },
  { name: 'Penajam', lat: -1.3000, lon: 116.7500, province: 'Kalimantan Timur', kabupaten: 'Kab. Penajam Paser Utara', subRegion: 'Kalimantan Timur Teluk Balikpapan' },
  { name: 'Ujoh Bilang', lat: 0.4500, lon: 115.3000, province: 'Kalimantan Timur', kabupaten: 'Kab. Mahakam Ulu', subRegion: 'Kalimantan Timur bagian Jantung Pedalaman' },

  // --- KALIMANTAN UTARA ---
  { name: 'Tarakan', lat: 3.3000, lon: 117.6333, province: 'Kalimantan Utara', kabupaten: 'Kota Tarakan', subRegion: 'Kalimantan Utara Pulau Tarakan' },
  { name: 'Tanjung Selor', lat: 2.8500, lon: 117.3667, province: 'Kalimantan Utara', kabupaten: 'Kab. Bulungan', subRegion: 'Kalimantan Utara bagian Hilir Kayan' },
  { name: 'Malinau', lat: 3.5833, lon: 116.6333, province: 'Kalimantan Utara', kabupaten: 'Kab. Malinau', subRegion: 'Kalimantan Utara bagian Pegunungan Barat' },
  { name: 'Nunukan', lat: 4.1333, lon: 117.6667, province: 'Kalimantan Utara', kabupaten: 'Kab. Nunukan', subRegion: 'Kalimantan Utara bagian Perbatasan Utara' },
  { name: 'Tideng Pale', lat: 3.5500, lon: 117.1833, province: 'Kalimantan Utara', kabupaten: 'Kab. Tana Tidung', subRegion: 'Kalimantan Utara bagian Sungai Sesayap' },
];

function calcHaversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6371.0;
  const dLat = ((lat2 - lat1) * Math.PI) / 180.0;
  const dLon = ((lon2 - lon1) * Math.PI) / 180.0;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180.0) *
      Math.cos((lat2 * Math.PI) / 180.0) *
      Math.sin(dLon / 2) ** 2;
  return r * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function calcCompassDirection(lat1: number, lon1: number, lat2: number, lon2: number): string {
  const dLat = lat2 - lat1;
  const dLon = lon2 - lon1;
  const angle = (Math.atan2(dLon, dLat) * 180.0) / Math.PI;
  const normalized = (angle + 360) % 360;

  if (normalized >= 337.5 || normalized < 22.5) return 'Utara';
  if (normalized >= 22.5 && normalized < 67.5) return 'Timur Laut';
  if (normalized >= 67.5 && normalized < 112.5) return 'Timur';
  if (normalized >= 112.5 && normalized < 157.5) return 'Tenggara';
  if (normalized >= 157.5 && normalized < 202.5) return 'Selatan';
  if (normalized >= 202.5 && normalized < 247.5) return 'Barat Daya';
  if (normalized >= 247.5 && normalized < 292.5) return 'Barat';
  return 'Barat Laut';
}

/**
 * Mendapatkan detail lokasi akurat (Kabupaten, Kota Terdekat, Arah, dan Bagian Wilayah)
 * untuk setiap titik koordinat di Pulau Kalimantan.
 */
export function getKalimantanLocationDetail(lat: number, lon: number, hintProvince?: string): LocationDetail {
  // Filter pusat acuan yang sesuai dengan hint provinsi jika ada
  let pool = KALIMANTAN_CENTERS;
  if (hintProvince) {
    const cleanHint = hintProvince.toLowerCase();
    const matched = KALIMANTAN_CENTERS.filter((c) =>
      c.province.toLowerCase().includes(cleanHint) || cleanHint.includes(c.province.toLowerCase())
    );
    if (matched.length > 0) {
      pool = matched;
    }
  }

  // Cari pusat terdekat menggunakan jarak geodetik
  let closest = pool[0];
  let minDistance = calcHaversineKm(lat, lon, closest.lat, closest.lon);

  for (let i = 1; i < pool.length; i++) {
    const d = calcHaversineKm(lat, lon, pool[i].lat, pool[i].lon);
    if (d < minDistance) {
      minDistance = d;
      closest = pool[i];
    }
  }

  const roundedKm = Math.round(minDistance * 10) / 10;
  // Arah mata angin dari pusat kota menuju ke titik hotspot
  const dir = calcCompassDirection(closest.lat, closest.lon, lat, lon);

  const kabupatenShort = closest.kabupaten.startsWith('Kota')
    ? closest.kabupaten
    : closest.kabupaten.replace('Kabupaten', 'Kab.');
  const kabupatenFull = closest.kabupaten.startsWith('Kota')
    ? closest.kabupaten
    : closest.kabupaten.replace('Kab.', 'Kabupaten');

  return {
    kabupaten: kabupatenShort,
    kabupatenFull,
    nearestCenter: closest.name,
    distanceKm: roundedKm,
    compassDirection: dir,
    subRegion: closest.subRegion,
    formattedShort: `${kabupatenShort} (±${Math.round(roundedKm)} km dari ${closest.name})`,
    formattedFull: `${kabupatenFull} • ±${roundedKm} km arah ${dir} dari ${closest.name} (${closest.subRegion})`,
  };
}

