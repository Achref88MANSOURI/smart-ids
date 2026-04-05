import pandas as pd
import numpy as np
import joblib, json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, roc_auc_score
from imblearn.over_sampling import SMOTE
import xgboost as xgb

df = pd.read_csv("data/processed/dataset_real_gcp_v2.csv")
df = df[df['event_type'].isin(['flow', 'alert', 'ssh', 'tls'])].copy()
print(f"Dataset : {len(df)} | ATTACK={df.label.sum()} | NORMAL={len(df)-df.label.sum()}")

# Feature Engineering
df['hour'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce').dt.hour.fillna(12)
df['is_night']      = ((df['hour'] < 6) | (df['hour'] > 22)).astype(int)
df['bytes_ratio']   = df['bytes_toserver'] / (df['bytes_toclient'] + 1)
df['pkts_ratio']    = df['pkts_toserver']  / (df['pkts_toclient'] + 1)
df['bytes_per_pkt'] = df['bytes_toserver'] / (df['pkts_toserver'] + 1)
df['total_bytes']   = df['bytes_toserver'] + df['bytes_toclient']
df['total_pkts']    = df['pkts_toserver']  + df['pkts_toclient']
df['pkt_size_avg']  = df['total_bytes'] / (df['total_pkts'] + 1)
df['is_admin_port'] = df['dst_port'].isin([22,23,3389,5900,8080]).astype(int)
df['is_scan_port']  = (df['dst_port'] < 1024).astype(int)
df['port_diff']     = abs(df['src_port'] - df['dst_port'])
df['src_is_high']   = (df['src_port'] > 1024).astype(int)
df['is_alert']      = (df['event_type'] == 'alert').astype(int)
df['flow_asymmetry']= abs(df['bytes_toserver'] - df['bytes_toclient']) / (df['total_bytes'] + 1)
df['severity']      = df['severity'].fillna(0)

for col in ['signature', 'category', 'proto', 'event_type']:
    le = LabelEncoder()
    df[col+'_enc'] = le.fit_transform(df[col].fillna('unknown'))

FEATURES = [
    'src_port', 'dst_port', 'severity', 'is_alert',
    'bytes_toserver', 'bytes_toclient', 'pkts_toserver', 'pkts_toclient',
    'hour', 'is_night', 'bytes_ratio', 'pkts_ratio', 'bytes_per_pkt',
    'total_bytes', 'total_pkts', 'pkt_size_avg', 'flow_asymmetry',
    'is_admin_port', 'is_scan_port', 'port_diff', 'src_is_high',
    'signature_enc', 'category_enc', 'proto_enc', 'event_type_enc'
]

X = df[FEATURES].fillna(0)
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# SMOTE — augmenter les exemples d'attaque
print(f"Avant SMOTE : {dict(y_train.value_counts())}")
smote = SMOTE(sampling_strategy=0.5, random_state=42, k_neighbors=5)
X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)
print(f"Après SMOTE : {dict(pd.Series(y_train_sm).value_counts())}")

model = xgb.XGBClassifier(
    n_estimators=1000,   # plus d'arbres — pas encore convergé à 499
    max_depth=6,
    learning_rate=0.03,  # plus lent = meilleure précision
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=3,
    eval_metric='auc',
    early_stopping_rounds=50,
    random_state=42,
    verbosity=0
)
model.fit(X_train_sm, y_train_sm,
          eval_set=[(X_test, y_test)],
          verbose=100)

proba = model.predict_proba(X_test)[:,1]
auc = roc_auc_score(y_test, proba)
print(f"\nAUC-ROC : {auc:.4f}")

print("\n--- Trade-off Seuil ---")
best_t, best_rec = 0.5, 0
for t in np.arange(0.1, 0.95, 0.01):
    p = (proba >= t).astype(int)
    fp  = ((p==1)&(y_test==0)).sum() / max((y_test==0).sum(),1)
    rec = ((p==1)&(y_test==1)).sum() / max((y_test==1).sum(),1)
    if fp < 0.05 and rec > best_rec:
        best_rec, best_t = rec, t

for t in [0.3, 0.4, 0.5, 0.6, 0.7, round(best_t,2)]:
    p = (proba >= t).astype(int)
    fp  = ((p==1)&(y_test==0)).sum() / max((y_test==0).sum(),1)
    rec = ((p==1)&(y_test==1)).sum() / max((y_test==1).sum(),1)
    print(f"  Seuil {t:.2f} → FP={fp:.2%}  Recall={rec:.2%}")

print(f"\n✅ Meilleur seuil (FP<5%) : {best_t:.2f} | Recall={best_rec:.2%}")
pred = (proba >= best_t).astype(int)
print(classification_report(y_test, pred, target_names=['NORMAL','ATTACK']))

joblib.dump(model, "models/xgb_real_gcp_v4.pkl")
with open("models/xgb_real_gcp_v4_config.json","w") as f:
    json.dump({"threshold": round(best_t,2), "auc": round(auc,4),
               "features": FEATURES}, f, indent=2)
print("Sauvegardé : models/xgb_real_gcp_v4.pkl")
