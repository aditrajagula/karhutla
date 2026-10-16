import requests

url = "https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/SUMBER_DAYA_ALAM_DAN_LINGKUNGAN/MapServer/6/query"
params = {
    "where": "landform LIKE '%Gambut%' OR landform LIKE '%Kubah%'",
    "returnCountOnly": "true",
    "f": "json"
}
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

resp = requests.get(url, params=params, headers=headers, timeout=30).json()
print(f"Total feature ASLI di server BIG: {resp.get('count', 'Gagal cek')}")