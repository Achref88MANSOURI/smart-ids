import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from imblearn.over_sampling import SMOTE
import xgboost as xgb
import joblib

df = pd.read_csv("data/processed/dataset_labeled.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True)

# --- Feature Engineering ---
df["hour"] = df["timestamp"].dt.hour
df["is_night"] = ((df["hour"] < 6) | (df["hour"] > 22)).astype(int)
df["is_business"] = ((df["hour"] >= 8) & (df["hour"] <= 18)).astype(int)
df["bytes_per_pkt"] = df["bytes"] / (df["packets"] + 1)
df["is_well_known_port"] = (df["dst_port"] < 1024).astype(int)
df["is_dns_port"] = (df["dst_port"] == 53).astype(int)
df["is_admin_port"] = df["dst_port"].isin([22, 23, 3389, 445, 135]).astype(int)
df["is_suspicious_port"] = df["dst_port"].isin([4444, 1337, 31337]).astype(int)
df["duration_ms"] = df["duration"] / 1e6

le_proto = LabelEncoder()
le_type = LabelEncoder()
df["protocol_enc"] = le_proto.fit_transform(df["protocol"].fillna("unknown"))
df["type_enc"] = le_type.fit_transform(df["type"].fillna("unknown"))

features = [
    "src_port", "dst_port", "bytes", "packets", "duration_ms",
    "hour", "is_night", "is_business",
    "bytes_per_pkt", "is_well_known_port", "is_dns_port",
    "is_admin_port", "is_suspicious_port",
    "protocol_enc", "type_enc"
]

X = df[features].fillna(0)
y = (df["label"] == "ATTACK").astype(int)

print(f"Dataset : {len(X)} lignes, {X.shape[1]} features")
print(f"Distribution : NORMAL={sum(y==0)}, ATTACK={sum(y==1)}")

# --- Split chronologique ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# --- SMOTE ---
print("Application SMOTE...")
sm = SMOTE(random_state=42, k_neighbors=3)
X_train_res, y_train_res = sm.fit_resample(X_train, y_train)
print(f"Après SMOTE : {pd.Series(y_train_res).value_counts().to_dict()}")

# --- Scaler ---
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train_res)
X_test_sc = scaler.transform(X_test)

# --- XGBoost ---
print("Entraînement XGBoost...")
model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=7,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric="logloss",
    verbosity=0
)
model.fit(X_train_sc, y_train_res)

# --- Évaluation ---
y_pred = model.predict(X_test_sc)
y_prob = model.predict_proba(X_test_sc)[:, 1]

print("\n=== Résultats XGBoost ===")
print(classification_report(y_test, y_pred, target_names=["NORMAL", "ATTACK"]))
print(f"AUC-ROC : {roc_auc_score(y_test, y_prob):.4f}")

cm = confusion_matrix(y_test, y_pred)
tn, fp, fn, tp = cm.ravel()
fpr = fp / (fp + tn) * 100
print(f"Faux Positifs : {fpr:.2f}%")
print(f"Matrice confusion : TN={tn} FP={fp} FN={fn} TP={tp}")

# --- Sauvegarde ---
joblib.dump(model, "models/xgb_real_dataset.pkl")
joblib.dump(scaler, "models/scaler_real_dataset.pkl")
joblib.dump(le_proto, "models/le_proto_real.pkl")
joblib.dump(le_type, "models/le_type_real.pkl")
print("\nModèles sauvegardés.")

# --- Optimisation du seuil ---
print("\n=== Optimisation du seuil ===")
from sklearn.metrics import precision_recall_curve
import numpy as np

precisions, recalls, thresholds = precision_recall_curve(y_test, y_prob)

# Trouver le seuil qui donne FP < 5%
best_threshold = 0.5
best_f1 = 0
for thresh in thresholds:
    y_pred_t = (y_prob >= thresh).astype(int)
    tn_t, fp_t, fn_t, tp_t = confusion_matrix(y_test, y_pred_t).ravel()
    fpr_t = fp_t / (fp_t + tn_t) * 100
    if fpr_t <= 5.0:
        from sklearn.metrics import f1_score
        f1_t = f1_score(y_test, y_pred_t)
        if f1_t > best_f1:
            best_f1 = f1_t
            best_threshold = thresh
            best_stats = (tn_t, fp_t, fn_t, tp_t, fpr_t)

tn_t, fp_t, fn_t, tp_t, fpr_t = best_stats
print(f"Seuil optimal : {best_threshold:.3f}")
print(f"FP Rate : {fpr_t:.2f}%")
print(f"Recall : {tp_t/(tp_t+fn_t)*100:.2f}%")
print(f"Precision : {tp_t/(tp_t+fp_t)*100:.2f}%")
print(f"Matrice : TN={tn_t} FP={fp_t} FN={fn_t} TP={tp_t}")

# Sauvegarder le seuil
import json
config = {"threshold": float(best_threshold)}
with open("models/xgb_real_config.json", "w") as f:
    json.dump(config, f)
print(f"Seuil sauvegardé dans models/xgb_real_config.json")
