import sys
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score

print("="*60)
print("  PENGUJIAN DATASET & MODEL PREDIKSI KEBAKARAN (KARHUTLA)")
print("="*60)

# 1. Load Dataset
print("\n[1/3] Membaca dataset 'data/era5_features.parquet'...")
df = pd.read_parquet('data/era5_features.parquet')
print(f"      Total baris data : {len(df):,} baris")
print(f"      Rentang tahun    : {df['year'].min()} s/d {df['year'].max()}")

# 2. Definisikan Fitur untuk Model Regresi
# Menggunakan fitur iklim ERA5 + deforestasi Hansen + gambut + elevasi
features = [
    'tp', 'tp_1', 'tp_2', 'tp_3', 'tp_4', 'tp_5',  # Curah hujan bulanan & 5 bulan sblmnya
    't2m', 'h2m', 'w10',                          # Suhu 2m, kelembaban, kecepatan angin
    'loss_last_prim', 'loss_last_sec',            # Deforestasi tahun sebelumnya (Hansen GFC)
    'f_prim', 'peatd', 'dem'                       # Tutupan hutan primer, kedalaman gambut, elevasi
]

# Siapkan label target biner (1 = Terjadi Kebakaran / Hotspot > 0, 0 = Aman)
df['target'] = (df['frp'] > 0).astype(int)

# Split Train (2002-2018) & Test (2019 - Tahun El Nino Ekstrem)
train_df = df[df['year'] < 2019]
test_df = df[df['year'] == 2019]

X_train, y_train = train_df[features], train_df['target']
X_test, y_test = test_df[features], test_df['target']

# 3. Training Model Regresi Logistik
print("\n[2/3] Melatih Model Regresi Logistik Biner...")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

log_model = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
log_model.fit(X_train_scaled, y_train)

# Evaluasi pada data uji tahun 2019
y_prob = log_model.predict_proba(X_test_scaled)[:, 1]
y_pred = (y_prob >= 0.5).astype(int)
auc = roc_auc_score(y_test, y_prob)

print(f"      Status Training : Sukses!")
print(f"      Evaluasi Uji Tahun 2019:")
print(f"      - ROC-AUC Score : {auc:.4f}")

# Simpan Model Regresi Logistik yang baru ditrain
joblib.dump(log_model, 'data/model_regresi_logistik.joblib')
joblib.dump(scaler, 'data/scaler_regresi_logistik.joblib')
print("      Model tersimpan di : data/model_regresi_logistik.joblib")

# 4. Koefisien & Odds Ratio
coef_df = pd.DataFrame({
    'Fitur': features,
    'Koefisien (Beta)': log_model.coef_[0],
    'Odds Ratio (e^Beta)': np.exp(log_model.coef_[0])
}).sort_values(by='Koefisien (Beta)', ascending=False)

print("\n[3/3] Interpretasi Parameter Model Regresi (Top Pemicu Kebakaran):")
print("-" * 55)
for idx, row in coef_df.head(5).iterrows():
    print(f"  + {row['Fitur']:<15} | Beta: {row['Koefisien (Beta)']:>7.4f} | Odds Ratio: {row['Odds Ratio (e^Beta)']:>6.2f}x")
print("  ... (faktor pencegah)")
for idx, row in coef_df.tail(3).iterrows():
    print(f"  - {row['Fitur']:<15} | Beta: {row['Koefisien (Beta)']:>7.4f} | Odds Ratio: {row['Odds Ratio (e^Beta)']:>6.2f}x")
print("-" * 55)

print("\n>> SELURUH PENGUJIAN SELESAI DENGAN SUKSES! <<")
