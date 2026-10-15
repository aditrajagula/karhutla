import sys
import joblib
import pandas as pd
import numpy as np

class OrdinalClassifier:
    pass

setattr(sys.modules['__main__'], 'OrdinalClassifier', OrdinalClassifier)

model = joblib.load('data/model_2019.joblib')
scaler = joblib.load('data/scaler_2019.joblib')
df = pd.read_parquet('data/era5_features.parquet')

# Features used in model
features = [
    'tp', 'tp_1', 'tp_2', 'tp_3', 'tp_4', 'tp_5',
    't2m', 'h2m', 'loss_last_prim', 'loss_last_sec',
    'frp_max', 'f_prim', 'peat', 'cs', 'ss', 'wk', 'sk', 'sp'
]

# Ensure column 'peat' exists
if 'peat' not in df.columns and 'peatd' in df.columns:
    df['peat'] = df['peatd']

# Let's take a sample from year 2019
sample_2019 = df[df['year'] == 2019].head(10)[features]
scaled_sample = scaler.transform(sample_2019)

# Predict using model.clfs
try:
    p_clf0 = model.clfs[0].predict_proba(scaled_sample)
    p_clf1 = model.clfs[1].predict_proba(scaled_sample)
    print("Testing Pre-trained Model on 2019 data:")
    print("Probability of Fire (>0 active fires):", np.round(p_clf0[:, 1], 4))
    print("Probability of High-Fire (>10 active fires):", np.round(p_clf1[:, 1], 4))
    print("SUCCESS! Pretrained model works perfectly on scikit-learn 1.6.1!")
except Exception as e:
    print("Error during predict:", e)
