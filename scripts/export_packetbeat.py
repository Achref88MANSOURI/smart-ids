from elasticsearch import Elasticsearch
import pandas as pd
import json

es = Elasticsearch("http://localhost:9200")

# Période de capture : trafic normal + attaques
query = {
    "query": {
        "range": {
            "@timestamp": {
                "gte": "2026-03-30T04:00:00Z",
                "lte": "2026-03-30T07:00:00Z"
            }
        }
    },
    "size": 10000,
    "_source": [
        "@timestamp", "type", "network.protocol",
        "source.ip", "source.port",
        "destination.ip", "destination.port",
        "network.bytes", "network.packets",
        "event.duration"
    ]
}

resp = es.search(index="packetbeat-windows-*", body=query, scroll="2m")
scroll_id = resp["_scroll_id"]
rows = []

while True:
    hits = resp["hits"]["hits"]
    if not hits:
        break
    for hit in hits:
        s = hit["_source"]
        rows.append({
            "timestamp": s.get("@timestamp", ""),
            "type": s.get("type", ""),
            "protocol": s.get("network", {}).get("protocol", ""),
            "src_ip": s.get("source", {}).get("ip", ""),
            "src_port": s.get("source", {}).get("port", 0),
            "dst_ip": s.get("destination", {}).get("ip", ""),
            "dst_port": s.get("destination", {}).get("port", 0),
            "bytes": s.get("network", {}).get("bytes", 0),
            "packets": s.get("network", {}).get("packets", 0),
            "duration": s.get("event", {}).get("duration", 0),
        })
    resp = es.scroll(scroll_id=scroll_id, scroll="2m")

df = pd.DataFrame(rows)
print(f"Total lignes exportées : {len(df)}")
print(df.dtypes)
print(df.head(3))

df.to_csv("/home/achrefmansouri600/smart-ids/data/raw/packetbeat_raw.csv", index=False)
print("Sauvegardé : data/raw/packetbeat_raw.csv")
