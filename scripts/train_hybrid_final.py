import pandas as pd
import numpy as np
import joblib, json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb

# --- Charger les deux datasets
gcp = pd.read_csv("data/processed/dataset_real_gcp_v2.csv")
master = pd.read_csv("data/processed/dataset_master.csv")

print(f"GCP réel   : {len(gcp)} lignes | ATTACK={gcp.label.sum()}")
print(f"Master NF  : {len(master)} lignes | ATTACK={master.label.sum()}")

# --- Aligner les colonnes communes
# GCP → features réseau
gcp_clean = gcp[gcp['event_type'].isin(['flow','alert','ssh','tls'])].copy()
gcp_clean['source'] = 'gcp_real'

# Renommer colonnes master pour aligner avec GCP
master_clean = master.copy()
master_clean['source'] = 'nf_uq'

# Colonnes communes minimales
COMMON = ['src_port', 'dst_port', 'severity',
          'bytes_toserver', 'bytes_toclient',
          'pkts_toserver', 'pkts_toclient', 'label']

gcp_sub   = gcp_clean[COMMON].fillna(0)
master_sub = master_clean[COMMON].fillna(0)

# Échantillonner master pour équilibrer
master_sample = pd.concat([
    master_sub[master_sub.label==0].sample(min(8000, len(master_sub[master_sub.label==0])), random_state=42),
    master_sub[master_sub.label==1].sample(min(8000, len(master_sub[master_sub.label==1])), random_state=42)
])

df = pd.concat([gcp_sub, master_sample], ignore_index=True)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print(f"\nDataset hybride : {len(df)} | ATTACK={df.label.sum()} | NORMAL={len(df)-df.label.sum()}")

# --- Feature Engineering
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
df['flow_asymmetry']= abs(df['bytes_toserver'] - df['bytes_toclient']) / (df['total_bytes'] + 1)

FEATURES = [
    'src_port', 'dst_port', 'severity',
    'bytes_toserver', 'bytes_toclient', 'pkts_toserver', 'pkts_toclient',
    'bytes_ratio', 'pkts_ratio', 'bytes_per_pkt',
    'total_bytes', 'total_pkts', 'pkt_size_avg', 'flow_asymmetry',
    'is_admin_port', 'is_scan_port', 'port_diff', 'src_is_high'
]

X = df[FEATURES].fillna(0)
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = xgb.XGBClassifier(
    n_estimators=1200, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
    eval_metric='auc', early_stopping_rounds=50,
    random_state=42, verbosity=0
)
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=100)

proba = model.predict_proba(X_test)[:,1]
auc = roc_auc_score(y_test, proba)
print(f"\nAUC-ROC : {auc:.4f}")

best_t, best_rec = 0.5, 0
for t in np.arange(0.1, 0.95, 0.01):
    p = (proba >= t).astype(int)
    fp  = ((p==1)&(y_test==0)).sum() / max((y_test==0).sum(),1)
    rec = ((p==1)&(y_test==1)).sum() / max((y_test==1).sum(),1)
    if fp < 0.05 and rec > best_rec:
        best_rec, best_t = rec, t

for t in [0.3, 0.4, 0.5, round(best_t,2)]:
    p = (proba >= t).astype(int)
    fp  = ((p==1)&(y_test==0)).sum() / max((y_test==0).sum(),1)
    rec = ((p==1)&(y_test==1)).sum() / max((y_test==1).sum(),1)
    print(f"  Seuil {t:.2f} → FP={fp:.2%}  Recall={rec:.2%}")

print(f"\n✅ Meilleur seuil : {best_t:.2f} | Recall={best_rec:.2%}")
pred = (proba >= best_t).astype(int)
print(classification_report(y_test, pred, target_names=['NORMAL','ATTACK']))

joblib.dump(model, "models/xgb_hybrid_final.pkl")
with open("models/xgb_hybrid_final_config.json","w") as f:
    json.dump({"threshold": round(best_t,2), "auc": round(auc,4),
               "features": FEATURES}, f, indent=2)
print("Sauvegardé : models/xgb_hybrid_final.pkl")
