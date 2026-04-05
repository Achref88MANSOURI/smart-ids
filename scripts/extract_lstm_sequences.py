import json
import numpy as np
import pandas as pd
from elasticsearch import Elasticsearch
from datetime import datetime, timezone
from collections import defaultdict

es = Elasticsearch("http://localhost:9200")

print("📥 Extraction des alertes depuis smart-ids-alerts-v5...")

# Récupérer toutes les alertes réseau triées par timestamp
query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"event_type": "network_alert"}},
                {"exists": {"field": "src_ip"}},
                {"exists": {"field": "mitre_technique"}}
            ],
            "must_not": [
                {"term": {"mitre_technique": "T0000"}}
            ]
        }
    },
    "sort": [{"@timestamp": "asc"}],
    "_source": ["@timestamp", "src_ip", "dst_ip", "mitre_technique",
                "threat_level", "signature", "xgb_confidence",
                "ae_score", "vt_score", "abuse_score"],
    "size": 2000
}

resp = es.search(index="smart-ids-alerts-v5", body=query)
hits = resp["hits"]["hits"]
print(f"  → {len(hits)} alertes récupérées")

# Construire un DataFrame
rows = []
for h in hits:
    s = h["_source"]
    rows.append({
        "timestamp": s.get("@timestamp", ""),
        "src_ip":    s.get("src_ip", ""),
        "dst_ip":    s.get("dst_ip", ""),
        "mitre":     s.get("mitre_technique", "T0000"),
        "threat":    s.get("threat_level", "LOW"),
        "xgb_conf":  s.get("xgb_confidence", 0),
        "ae_score":  s.get("ae_score", 0),
        "vt_score":  s.get("vt_score", 0),
        "abuse":     s.get("abuse_score", 0),
    })

df = pd.DataFrame(rows)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values("timestamp").reset_index(drop=True)

print(f"\n📊 Distribution par src_ip (top 10) :")
print(df["src_ip"].value_counts().head(10))

print(f"\n📊 Distribution MITRE :")
print(df["mitre"].value_counts())

print(f"\n📊 Distribution Threat Level :")
print(df["threat"].value_counts())

# Grouper par src_ip et construire des séquences temporelles
WINDOW_MINUTES = 30
MIN_SEQ_LEN = 3

print(f"\n🔗 Construction des séquences (fenêtre {WINDOW_MINUTES} min, min {MIN_SEQ_LEN} alertes)...")

# Encodage MITRE
mitre_codes = {"T1046": 1, "T1110": 2, "T1499": 3, "T1190": 4,
               "T1071": 5, "T1059": 6, "T1557": 7, "T1486": 8,
               "T1590": 9, "T1596": 10, "T1021": 11}

threat_codes = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# Définir si une séquence est une kill chain réelle
# Kill chain = progression sur au moins 2 techniques MITRE différentes
def is_kill_chain(seq_mitres):
    unique = set(seq_mitres)
    # Progression typique : Reconnaissance → Exploitation → C2
    recon = any(m in unique for m in ["T1046", "T1590", "T1596"])
    exploit = any(m in unique for m in ["T1190", "T1059", "T1110"])
    c2 = any(m in unique for m in ["T1071", "T1557", "T1021"])
    lateral = any(m in unique for m in ["T1499", "T1486"])
    stages = sum([recon, exploit, c2, lateral])
    return 1 if (stages >= 2 or len(unique) >= 2) else 0

sequences = []
labels = []
seq_info = []

for src_ip, group in df.groupby("src_ip"):
    group = group.sort_values("timestamp").reset_index(drop=True)
    if len(group) < MIN_SEQ_LEN:
        continue

    # Fenêtre glissante temporelle
    for i in range(len(group)):
        t_start = group.loc[i, "timestamp"]
        t_end = t_start + pd.Timedelta(minutes=WINDOW_MINUTES)
        window = group[(group["timestamp"] >= t_start) &
                       (group["timestamp"] <= t_end)]

        if len(window) < MIN_SEQ_LEN:
            continue

        # Construire le vecteur de features pour chaque alerte
        seq_vectors = []
        for _, row in window.iterrows():
            vec = [
                mitre_codes.get(row["mitre"], 0) / 11.0,
                threat_codes.get(row["threat"], 0) / 3.0,
                min(row["xgb_conf"], 100) / 100.0,
                min(row["ae_score"], 100) / 100.0,
                min(row["vt_score"], 50) / 50.0,
                min(row["abuse"], 100) / 100.0,
            ]
            seq_vectors.append(vec)

        # Padder/tronquer à 10 alertes
        if len(seq_vectors) >= 10:
            seq_vectors = seq_vectors[:10]
        else:
            pad = [[0.0] * 6] * (10 - len(seq_vectors))
            seq_vectors = pad + seq_vectors

        label = is_kill_chain(window["mitre"].tolist())
        sequences.append(seq_vectors)
        labels.append(label)
        seq_info.append({
            "src_ip": src_ip,
            "start": str(t_start),
            "n_alerts": len(window),
            "mitres": list(window["mitre"].unique()),
            "label": label
        })

sequences = np.array(sequences, dtype=np.float32)
labels = np.array(labels, dtype=np.float32)

print(f"\n✅ {len(sequences)} séquences construites")
print(f"   Kill chains réelles : {labels.sum():.0f} ({labels.mean()*100:.1f}%)")
print(f"   Non kill chains    : {(1-labels).sum():.0f} ({(1-labels.mean())*100:.1f}%)")
print(f"   Shape séquences   : {sequences.shape}")

# Sauvegarder
np.save("/home/achrefmansouri600/smart-ids/data/processed/lstm_sequences_real.npy", sequences)
np.save("/home/achrefmansouri600/smart-ids/data/processed/lstm_labels_real.npy", labels)

with open("/home/achrefmansouri600/smart-ids/data/processed/lstm_seq_info.json", "w") as f:
    json.dump(seq_info[:20], f, indent=2, default=str)

print("\n💾 Données sauvegardées :")
print("   data/processed/lstm_sequences_real.npy")
print("   data/processed/lstm_labels_real.npy")
print("   data/processed/lstm_seq_info.json (20 exemples)")
print("\n🚀 Prêt pour l'entraînement LSTM V3 !")
