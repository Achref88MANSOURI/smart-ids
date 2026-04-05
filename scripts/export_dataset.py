from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import pandas as pd
import json
import os

load_dotenv("/home/achrefmansouri600/smart-ids/.env")

# Connexion Elasticsearch
es = Elasticsearch("http://10.0.1.7:9200")
print("Connexion ES :", es.ping())

# Filtre KQL anti-bruit (identique au Dashboard Kibana)
query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"suricata.eve.event_type": "alert"}}
            ],
            "must_not": [
                {"term": {"suricata.eve.alert.signature": "SURICATA STREAM Packet with invalid ack"}},
                {"term": {"suricata.eve.alert.signature": "SURICATA STREAM SHUTDOWN RST invalid ack"}}
            ]
        }
    },
    "_source": [
        "@timestamp",
        "source.ip",
        "source.port",
        "destination.ip",
        "destination.port",
        "network.protocol",
        "suricata.eve.alert.signature",
        "suricata.eve.alert.category",
        "suricata.eve.alert.severity",
        "suricata.eve.flow.bytes_toserver",
        "suricata.eve.flow.bytes_toclient",
        "suricata.eve.flow.pkts_toserver",
        "suricata.eve.flow.pkts_toclient"
    ]
}

# Scroll API pour récupérer TOUS les documents (pas limité à 10 000)
print("Début de l'export...")
records = []
page = es.search(index="filebeat-*", body=query, scroll="2m", size=1000)
scroll_id = page["_scroll_id"]
hits = page["hits"]["hits"]

while hits:
    for hit in hits:
        src = hit["_source"]
        records.append({
            "timestamp":        src.get("@timestamp", ""),
            "src_ip":           src.get("source", {}).get("ip", ""),
            "src_port":         src.get("source", {}).get("port", 0),
            "dst_ip":           src.get("destination", {}).get("ip", ""),
            "dst_port":         src.get("destination", {}).get("port", 0),
            "protocol":         src.get("network", {}).get("protocol", ""),
            "signature":        src.get("suricata", {}).get("eve", {}).get("alert", {}).get("signature", ""),
            "category":         src.get("suricata", {}).get("eve", {}).get("alert", {}).get("category", ""),
            "severity":         src.get("suricata", {}).get("eve", {}).get("alert", {}).get("severity", 0),
            "bytes_toserver":   src.get("suricata", {}).get("eve", {}).get("flow", {}).get("bytes_toserver", 0),
            "bytes_toclient":   src.get("suricata", {}).get("eve", {}).get("flow", {}).get("bytes_toclient", 0),
            "pkts_toserver":    src.get("suricata", {}).get("eve", {}).get("flow", {}).get("pkts_toserver", 0),
            "pkts_toclient":    src.get("suricata", {}).get("eve", {}).get("flow", {}).get("pkts_toclient", 0),
        })
    print(f"  {len(records)} documents récupérés...", end="\r")
    page = es.scroll(scroll_id=scroll_id, scroll="2m")
    scroll_id = page["_scroll_id"]
    hits = page["hits"]["hits"]

es.clear_scroll(scroll_id=scroll_id)

# Sauvegarde CSV
df = pd.DataFrame(records)
output_path = "/home/achrefmansouri600/smart-ids/data/raw/alerts_export.csv"
df.to_csv(output_path, index=False)

print(f"\n✅ Export terminé !")
print(f"   Lignes exportées : {len(df)}")
print(f"   Fichier : {output_path}")
print(f"\nAperçu des données :")
print(df.head())
print(f"\nColonnes : {list(df.columns)}")
print(f"Types :\n{df.dtypes}")