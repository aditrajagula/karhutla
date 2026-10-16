import pandas as pd

print("1. Memuat Hotspot FIRMS...")
df = pd.read_csv("firms_kalimantan.csv") # Sesuaikan nama file lu
print(f"   Total awal: {len(df)}")

print("2. Melakukan HARD FILTER Kalimantan...")
# Bujur (Longitude): 108.5 sampai 119.0 (Sulawesi mulai ~118.5, kita amankan di 119.0)
# Lintang (Latitude): -4.5 sampai 4.5
df_kal = df[
    (df['longitude'] >= 108.5) & (df['longitude'] <= 119.0) &
    (df['latitude'] >= -4.5) & (df['latitude'] <= 4.5)
]

print(f"   Total setelah filter: {len(df_kal)}")
print(f"   {len(df) - len(df_kal)} hotspot di luar Kalimantan (Sulawesi/dll) dibuang!")

# Simpan file baru
df_kal.to_csv("firms_kalimantan_STRICT.csv", index=False)
print("\n✅ SELESAI! Gunakan file firms_kalimantan_STRICT.csv untuk spatial join.")