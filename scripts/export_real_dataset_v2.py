import json
import pandas as pd
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")
INDEX = ".ds-filebeat-8.12.2-2026.03.19-000001"

# IPs attaquantes connues
ATTACKER_IPS = {"10.0.2.2", "100.76.134.101"}

WINDOWS = [
    ("2026-03-30T23:00:00Z", "2026-03-30T23:10:00Z"),
    ("2026-03-31T20:47:00Z", "2026-03-31T20:55:00Z"),
    ("2026-04-01T17:37:00Z", "2026-04-01T17:45:00Z"),
    ("2026-04-01T18:05:00Z", "2026-04-01T18:10:00Z"),
    ("2026-04-01T18:24:00Z", "2026-04-01T18:26:00Z"),
    # Trafic normal — nuit calme
    ("2026-03-30T20:00:00Z", "2026-03-30T22:30:00Z"),
]

def parse_doc(hit):
    src = hit["_source"]
    raw = src.get("event", {}).get("original", "{}")
    try:
        eve = json.loads(raw)
    except:
        return None

    # Ignorer les events sans IP
    src_ip = eve.get("src_ip")
    dst_ip = eve.get("dest_ip")
    if not src_ip:
        return None

    alert = eve.get("alert", {})
    flow  = eve.get("flow", {})

    return {
        "timestamp": eve.get("timestamp"),
        "src_ip":    src_ip,
        "dst_ip":    dst_ip,
        "src_port":  eve.get("src_port", 0),
        "dst_port":  eve.get("dest_port", 0),
        "proto":     eve.get("proto", ""),
        "event_type": eve.get("event_type", ""),
        "signature": alert.get("signature", ""),
        "category":  alert.get("category", ""),
        "severity":  alert.get("severity", 0),
        "bytes_toserver":  flow.get("bytes_toserver", 0),
        "bytes_toclient":  flow.get("bytes_toclient", 0),
        "pkts_toserver":   flow.get("pkts_toserver", 0),
        "pkts_toclient":   flow.get("pkts_toclient", 0),
        "label": 1 if src_ip in ATTACKER_IPS else 0
    }

all_rows = []

for start, end in WINDOWS:
    query = {
        "query": {"range": {"@timestamp": {"gte": start, "lte": end}}},
        "size": 8000,
        "_source": ["event.original"]
    }
    resp = es.search(index=INDEX, body=query)
    rows = [r for h in resp["hits"]["hits"] if (r := parse_doc(h))]
    attack = sum(1 for r in rows if r["label"] == 1)
    print(f"  {start[5:16]} → {len(rows)} docs | ATTACK={attack}")
    all_rows.extend(rows)

df = pd.DataFrame(all_rows)
print(f"\nTotal : {len(df)} | ATTACK={df.label.sum()} | NORMAL={len(df)-df.label.sum()}")
print("IPs attaquantes trouvées :", df[df.label==1]["src_ip"].unique())
print("Event types :", df["event_type"].value_counts().head(8).to_dict())

df.to_csv("data/processed/dataset_real_gcp_v2.csv", index=False)
print("Sauvegardé : data/processed/dataset_real_gcp_v2.csv")
