import pandas as pd
from datetime import datetime, timezone

df = pd.read_csv("data/raw/packetbeat_raw.csv")
attacks = pd.read_csv("data/raw/attack_log.csv")

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
attacks["timestamp"] = pd.to_datetime(attacks["timestamp"], utc=True)

# Construire les intervalles d'attaque
intervals = []
starts = attacks[attacks["status"] == "START"].reset_index(drop=True)
ends = attacks[attacks["status"] == "END"].reset_index(drop=True)
for i in range(len(starts)):
    intervals.append({
        "start": starts.loc[i, "timestamp"],
        "end": ends.loc[i, "timestamp"],
        "technique_id": starts.loc[i, "technique_id"],
        "technique_name": starts.loc[i, "technique_name"],
        "target": starts.loc[i, "target"]
    })

def label_row(ts):
    for iv in intervals:
        if iv["start"] <= ts <= iv["end"]:
            return "ATTACK", iv["technique_id"]
    return "NORMAL", "NONE"

print("Labellisation en cours...")
labels = df["timestamp"].apply(label_row)
df["label"] = [l[0] for l in labels]
df["mitre_technique"] = [l[1] for l in labels]

print(df["label"].value_counts())
print(df["mitre_technique"].value_counts())

df.to_csv("data/processed/dataset_labeled.csv", index=False)
print(f"\nDataset sauvegardé : {len(df)} lignes")
print("data/processed/dataset_labeled.csv")
