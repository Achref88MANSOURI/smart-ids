import time

from secure_secrets import get_vt_api_key
import json
import joblib
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from collections import deque
import os
import warnings
warnings.filterwarnings('ignore')

# --- NOUVEAU : Import de Gemini ---
import google.generativeai as genai

# TensorFlow (chargement silencieux)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
tf.get_logger().setLevel('ERROR')

# ── Configuration ──────────────────────────────────────
load_dotenv("/home/achrefmansouri600/smart-ids/.env")

ES_HOST   = "https://localhost:9200"
ES_USER = os.getenv("ES_USER", "smart_ids")
ES_PASS = os.getenv("ES_PASS")
ES_CA   = os.getenv("ES_CA", "/etc/smart-ids-ca.crt")
VT_KEY    = get_vt_api_key()
ABUSE_KEY = os.getenv("ABUSEIPDB_KEY")
# --- NOUVEAU : Configuration Gemini ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')

INDEX_IN_NET = "filebeat-*"
INDEX_IN_EP  = "winlogbeat-*" # NOUVEL INDEX ENDPOINT
INDEX_OUT    = "smart-ids-alerts-v5" # Passage en V5 !
POLL_SEC  = 15
SEQUENCE_LENGTH = 10  # LSTM window

# ... (VOS BLOCS FEATURES_XGB, FEATURES_LSTM, PORTS RESTENT IDENTIQUES) ...
FEATURES_XGB = ['src_port', 'dst_port', 'severity', 'bytes_toserver', 'bytes_toclient', 'pkts_toserver', 'pkts_toclient', 'bytes_ratio', 'pkts_ratio', 'bytes_per_pkt', 'total_bytes', 'total_pkts', 'pkt_size_avg', 'flow_asymmetry', 'is_admin_port', 'is_scan_port', 'port_diff', 'src_is_high', 'hour', 'is_night', 'sig_category']
FEATURES_LSTM = ['src_port', 'dst_port', 'bytes_toserver', 'bytes_toclient', 'pkts_toserver', 'pkts_toclient', 'severity', 'tcp_flags', 'flow_duration', 'min_pkt_len', 'max_pkt_len', 'bytes_per_sec', 'min_ttl', 'max_ttl', 'bytes_ratio', 'pkts_ratio', 'bytes_per_pkt', 'total_bytes', 'total_pkts', 'is_well_known_port', 'is_db_port', 'is_admin_port', 'port_diff', 'src_is_high_port', 'hour', 'is_night', 'is_business']
WELL_KNOWN_PORTS = set(range(0, 1024))
DB_PORTS         = {3306, 5432, 1433, 1521, 27017, 6379}
ADMIN_PORTS      = {22, 23, 3389, 5900, 8080, 8443}
SUSPICIOUS_PORTS = {4444, 1337, 31337, 9999, 6666}

# ... (VOS BLOCS DE CHARGEMENT DES MODELES RESTENT IDENTIQUES) ...
print("🔄 Chargement des modèles IA...")
xgb_model  = joblib.load("/home/achrefmansouri600/smart-ids/models/xgb_v3_master.pkl")
xgb_scaler = joblib.load("/home/achrefmansouri600/smart-ids/models/scaler_v3_master.pkl")
XGB_THRESHOLD = 0.75
print(f"  ✅ XGBoost V3       (98.71% accuracy, seuil={XGB_THRESHOLD})")

ae_model   = tf.keras.models.load_model("/home/achrefmansouri600/smart-ids/models/autoencoder_ids.keras", compile=False)
# ae_scaler incompatible — ancien modèle avec 33 features, on utilise 18
ae_scaler  = None  # Désactivé : Features 18->33 utilise normalization locale
with open("/home/achrefmansouri600/smart-ids/models/autoencoder_config.json") as f:
    ae_config = json.load(f)
AE_THRESHOLD = ae_config["threshold"]
print(f"  ✅ Autoencoder      (99.35% accuracy, seuil={AE_THRESHOLD:.4f})")

# LSTM V4 PRO — Autoencoder + Attention (non-supervisé)
lstm_autoencoder = tf.keras.models.load_model(
    "/home/achrefmansouri600/smart-ids/models/lstm_ae_attention.keras", compile=False)
with open("/home/achrefmansouri600/smart-ids/models/lstm_v4_config.json") as _f:
    _lstm_cfg = json.load(_f)
LSTM_AE_PERCENTILE = _lstm_cfg.get("threshold_percentile", 99)
LSTM_AE_WINDOW     = deque(maxlen=_lstm_cfg.get("window_size", 200))
LSTM_AE_INIT_DONE  = False
print(f"  ✅ LSTM V4 AE+Attention (non-supervisé, P{LSTM_AE_PERCENTILE:.0f} adaptatif)")

if GEMINI_KEY: print(f"  ✅ IA Gemini        (Analyse sémantique Endpoint activée)")

# lstm_buffer remplacé par LSTM_AE_WINDOW (seuil adaptatif V4)
ip_cache = {}

# ... (VOS FONCTIONS get_ip_reputation, get_mitre_tag, build_features, predict_xgb, predict_autoencoder, predict_lstm, compute_threat_level RESTENT IDENTIQUES) ...
def get_ip_reputation(ip):
    if not ip or ip.startswith(("10.", "192.168.", "172.", "127.", "169.")): return {"vt_score": 0, "abuse_score": 0, "cached": True}
    if ip in ip_cache:
        if time.time() - ip_cache[ip]["timestamp"] < 3600:
            ip_cache[ip]["cached"] = True
            return ip_cache[ip]
    result = {"vt_score": 0, "abuse_score": 0, "cached": False}
    try:
        vt_resp = requests.get(f"https://www.virustotal.com/api/v3/ip_addresses/{ip}", headers={"x-apikey": VT_KEY}, timeout=5)
        if vt_resp.status_code == 200:
            stats = vt_resp.json()["data"]["attributes"]["last_analysis_stats"]
            result["vt_score"] = stats.get("malicious", 0) + stats.get("suspicious", 0)
    except: pass
    try:
        ab_resp = requests.get("https://api.abuseipdb.com/api/v2/check", headers={"Key": ABUSE_KEY, "Accept": "application/json"}, params={"ipAddress": ip, "maxAgeInDays": 90}, timeout=5)
        if ab_resp.status_code == 200:
            result["abuse_score"] = ab_resp.json()["data"]["abuseConfidenceScore"]
    except: pass
    result["timestamp"] = time.time()
    ip_cache[ip] = result
    time.sleep(0.3)
    return result

def get_geo_for_ip(ip):
    """Récupère les données geo depuis filebeat pour une IP donnée"""
    try:
        result = es.search(index="filebeat-*", body={
            "size": 1,
            "query": {"term": {"source.ip": ip}},
            "_source": ["source.geo"]
        })
        hits = result.get("hits", {}).get("hits", [])
        if hits:
            geo = hits[0]["_source"].get("source", {}).get("geo", {})
            if geo:
                return {
                    "country_name": geo.get("country_name", ""),
                    "country_iso_code": geo.get("country_iso_code", ""),
                    "continent_name": geo.get("continent_name", ""),
                    "location": geo.get("location", {})
                }
    except: pass
    return {}

def get_mitre_tag(signature, category):
    sig = str(signature).upper()
    if any(k in sig for k in ["SCAN", "NMAP", "RECON", "RECONNAISSANCE"]): return {"tactic": "Reconnaissance",      "technique": "T1046", "name": "Network Service Discovery"}
    elif any(k in sig for k in ["BRUTE", "PASSWORD", "CREDENTIAL"]): return {"tactic": "Credential Access",   "technique": "T1110", "name": "Brute Force"}
    elif any(k in sig for k in ["ICMP", "PING", "DDOS", "DOS", "FLOOD"]): return {"tactic": "Impact",              "technique": "T1499", "name": "Endpoint Denial of Service"}
    elif any(k in sig for k in ["XSS", "INJECTION", "SQL", "WEB", "HTTP"]): return {"tactic": "Initial Access",      "technique": "T1190", "name": "Exploit Public-Facing Application"}
    elif any(k in sig for k in ["COMPROMISED", "DROP", "CINS", "BOTNET", "BOT"]): return {"tactic": "Command and Control", "technique": "T1071", "name": "Application Layer Protocol"}
    elif any(k in sig for k in ["BACKDOOR", "SHELLCODE", "EXPLOIT"]): return {"tactic": "Execution",           "technique": "T1059", "name": "Command and Scripting Interpreter"}
    elif any(k in sig for k in ["MITM", "THEFT", "INFILTR"]): return {"tactic": "Collection",          "technique": "T1557", "name": "Adversary-in-the-Middle"}
    elif any(k in sig for k in ["RANSOMWARE", "WORM", "FUZZER"]): return {"tactic": "Impact",              "technique": "T1486", "name": "Data Encrypted for Impact"}
    elif any(k in sig for k in ["USER-AGENT", "GO-HTTP", "GO HTTP", "USERAGENT"]): return {"tactic": "Discovery", "technique": "T1590", "name": "Gather Victim Network Info"}
    elif any(k in sig for k in ["DNS", "DOMAIN", "LOOKUP"]): return {"tactic": "Reconnaissance", "technique": "T1596", "name": "DNS Passive Recon"}
    elif any(k in sig for k in ["SSH", "TELNET", "RDP"]): return {"tactic": "Lateral Movement", "technique": "T1021", "name": "Remote Services"}
    elif any(k in sig for k in ["STREAM", "INVALID", "SHUTDOWN", "GENERIC PROTOCOL", "ET INFO"]): return None
    else: return {"tactic": "Unknown", "technique": "T0000", "name": "Unclassified"}

def build_features(alert_raw, timestamp_str):
    src_port  = alert_raw.get("src_port", 0) or 0
    dst_port  = alert_raw.get("dst_port", 0) or 0
    bytes_tos = alert_raw.get("bytes_toserver", 0) or 0
    bytes_toc = alert_raw.get("bytes_toclient", 0) or 0
    pkts_tos  = alert_raw.get("pkts_toserver", 0) or 0
    pkts_toc  = alert_raw.get("pkts_toclient", 0) or 0
    severity  = alert_raw.get("severity", 0) or 0
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        hour, minute = ts.hour, ts.minute
    except: hour, minute = 12, 0
    is_night    = 1 if (hour < 6 or hour > 22) else 0
    is_business = 1 if (8 <= hour <= 18) else 0
    is_weekend  = 0
    bytes_ratio   = bytes_tos / (bytes_toc + 1)
    pkts_ratio    = pkts_tos  / (pkts_toc + 1)
    bytes_per_pkt = bytes_tos / (pkts_tos + 1)
    total_bytes   = bytes_tos + bytes_toc
    total_pkts    = pkts_tos  + pkts_toc
    is_unidir     = 1 if bytes_toc == 0 else 0
    pkt_size_avg  = total_bytes / (total_pkts + 1)
    flow_asymmetry= abs(bytes_tos - bytes_toc) / (total_bytes + 1)
    is_scan_port  = 1 if dst_port < 1024 else 0
    src_is_high   = 1 if src_port > 1024 else 0
    # sig_category pour le nouveau modèle V4
    sig = str(alert_raw.get("signature", "")).upper()
    if   'SCAN'        in sig: sig_category = 1
    elif 'COMPROMISED' in sig: sig_category = 2
    elif 'DROP'        in sig: sig_category = 3
    elif 'CINS'        in sig: sig_category = 4
    elif 'EXPLOIT'     in sig: sig_category = 5
    elif 'BRUTE'       in sig: sig_category = 6
    else:                      sig_category = 7
    return {
        'src_port': src_port, 'dst_port': dst_port, 'bytes_toserver': bytes_tos, 'bytes_toclient': bytes_toc, 'pkts_toserver': pkts_tos, 'pkts_toclient': pkts_toc, 'severity': severity,
        'tcp_flags': 0, 'flow_duration': 0, 'min_pkt_len': 0, 'max_pkt_len': 0, 'bytes_per_sec': 0, 'min_ttl': 0, 'max_ttl': 0, 'longest_pkt': 0, 'shortest_pkt': 0, 'protocol_num': 0,
        'bytes_ratio': bytes_ratio, 'pkts_ratio': pkts_ratio, 'bytes_per_pkt': bytes_per_pkt, 'total_bytes': total_bytes, 'total_pkts': total_pkts, 'is_unidirectional': is_unidir,
        'is_well_known_port': 1 if dst_port in WELL_KNOWN_PORTS else 0, 'is_db_port':         1 if dst_port in DB_PORTS else 0, 'is_admin_port':      1 if dst_port in ADMIN_PORTS else 0,
        'is_suspicious_port': 1 if dst_port in SUSPICIOUS_PORTS else 0, 'port_diff': abs(src_port - dst_port), 'src_is_high_port': 1 if src_port > 1024 else 0, 'pkt_size_avg': pkt_size_avg, 'flow_asymmetry': flow_asymmetry, 'is_scan_port': is_scan_port, 'src_is_high': src_is_high,
        'hour': hour, 'minute': minute, 'is_night': is_night, 'is_business': is_business, 'is_weekend': is_weekend, 'sig_category': sig_category,
    }

def predict_xgb(features):
    df = pd.DataFrame([features])[FEATURES_XGB]
    proba  = xgb_model.predict_proba(df)[0][1]
    pred   = 1 if proba >= XGB_THRESHOLD else 0
    return pred, round(proba * 100, 2)

def predict_autoencoder(features):
    """Autoencoder sans scaler — utilise normalization locale des 18 features"""
    try:
        # Récupérer les 18 features disponibles
        vals = np.array([[features[f] for f in FEATURES_XGB]])
        
        # Normalization locale simple (z-score)
        vals_norm = (vals - np.mean(vals)) / (np.std(vals) + 1e-8)
        
        # Prédiction autoencoder
        recon = ae_model.predict(vals_norm, verbose=0)
        error = float(np.mean(np.power(vals_norm - recon, 2)))
        is_anomaly = 1 if error > AE_THRESHOLD else 0
        ae_score = min(100, round(error / (AE_THRESHOLD * 2) * 100, 1))
        return is_anomaly, ae_score, round(error, 6)
    except Exception as e:
        # Si anomalie — retourner scores neutres
        return 0, 0.0, 0.0

def predict_lstm(features):
    """LSTM V4 PRO — Autoencoder + Attention + Seuil adaptatif"""
    global LSTM_AE_INIT_DONE

    # Construire vecteur 6 features normalisées
    mitre_codes = {"T1046":1,"T1110":2,"T1499":3,"T1190":4,"T1071":5,
                   "T1059":6,"T1557":7,"T1486":8,"T1590":9,"T1596":10,"T1021":11}
    threat_codes = {"LOW":0,"MEDIUM":1,"HIGH":2,"CRITICAL":3}
    vec_6 = [
        mitre_codes.get(features.get("mitre",""), 0) / 11.0,
        threat_codes.get(features.get("threat_level","LOW"), 0) / 3.0,
        min(features.get("xgb_conf", 0), 100) / 100.0,
        min(features.get("ae_score", 0), 100) / 100.0,
        min(features.get("vt_score", 0), 50)  / 50.0,
        min(features.get("abuse_score", 0), 100) / 100.0,
    ]

    # Buffer circulaire de 10 alertes
    if not hasattr(predict_lstm, "_seq_buf"):
        predict_lstm._seq_buf = deque(maxlen=SEQUENCE_LENGTH)
    predict_lstm._seq_buf.append(vec_6)

    if len(predict_lstm._seq_buf) < SEQUENCE_LENGTH:
        return 0, 0.0, f"buffer {len(predict_lstm._seq_buf)}/{SEQUENCE_LENGTH}"

    # Séquence shape (1, 10, 6)
    seq = np.array(list(predict_lstm._seq_buf), dtype=np.float32).reshape(1, 10, 6)

    # Score d'anomalie
    rec = lstm_autoencoder.predict(seq, verbose=0)
    mse = float(np.mean(np.power(seq - rec, 2)))
    mx  = float(np.max(np.mean(np.power(seq - rec, 2), axis=2)))
    anomaly = 0.7 * mse + 0.3 * mx

    # Seuil adaptatif P99 fenêtre glissante
    if len(LSTM_AE_WINDOW) < 10:
        # Pas assez de données — seuil par défaut conservateur
        threshold = 0.12272
    else:
        threshold = float(np.percentile(list(LSTM_AE_WINDOW), LSTM_AE_PERCENTILE))

    pred = 1 if anomaly >= threshold else 0

    # Mettre à jour la fenêtre uniquement si normal
    if pred == 0:
        LSTM_AE_WINDOW.append(anomaly)

    confidence = min(anomaly / max(threshold, 1e-8) * 50, 100)
    status = f"ae={anomaly:.5f} thresh={threshold:.5f}"
    return pred, round(confidence, 2), status

def compute_threat_level(xgb_pred, xgb_conf, ae_anomaly, ae_score, lstm_pred, vt_score, abuse_score):
    score = 0
    if xgb_pred == 1:   score += xgb_conf / 100 * 40
    if ae_anomaly == 1:  score += min(ae_score / 100 * 20, 20)
    if lstm_pred == 1:   score += 20
    if vt_score > 0:     score += min(vt_score * 3, 15)
    if abuse_score > 0:  score += min(abuse_score / 20, 5)
    if score >= 70:   return "CRITICAL"
    elif score >= 40: return "HIGH"
    elif score >= 20: return "MEDIUM"
    else:             return "LOW"

# --- NOUVELLE FONCTION : Analyse sémantique Gemini pour Sysmon ---
def analyze_sysmon_with_gemini(process_name, command_line):
    """Demande à Gemini d'analyser la dangerosité d'une ligne de commande."""
    if not GEMINI_KEY:
        return "LOW", "Gemini non configuré."
    
    # Filtrer les bruits normaux (pour économiser le quota API)
    safe_processes = ["svchost.exe", "SearchIndexer.exe", "chrome.exe", "msedge.exe", "conhost.exe"]
    if process_name in safe_processes and ("powershell" not in str(command_line).lower() and "cmd.exe" not in str(command_line).lower()):
        return "LOW", "Processus légitime standard."

    prompt = f"""Tu es un analyste SOC expert en cybersécurité. Analyse cette exécution de processus Sysmon (Event ID 1).
Processus : {process_name}
Ligne de commande : {command_line}

Réponds STRICTEMENT au format JSON suivant, sans aucun autre texte autour :
{{
  "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "reason": "Une phrase courte expliquant pourquoi",
  "mitre_technique": "Txxxx (si applicable, sinon null)"
}}"""
    
    try:
        response = gemini_model.generate_content(prompt)
        # Nettoyage de la réponse si Gemini a ajouté des balises markdown
        clean_json = response.text.strip().replace("```json", "").replace("```", "")
        analysis = json.loads(clean_json)
        return analysis.get("threat_level", "UNKNOWN"), analysis.get("reason", "Erreur parsing API"), analysis.get("mitre_technique")
    except Exception as e:
        return "UNKNOWN", f"Erreur IA: {str(e)[:50]}", None


# ── Connexion Elasticsearch ─────────────────────────────
es = Elasticsearch(
    ES_HOST,
    basic_auth=(ES_USER, ES_PASS),
    ca_certs=ES_CA,
    verify_certs=True
)
print(f"\n✅ Elasticsearch : {es.ping()}", flush=True)

print(f"\n{'='*65}", flush=True)
print(f"🚀 Smart-IDS Enrichment V5 — Réseau (ML) + Endpoint (Gemini)", flush=True)
print(f"  Index OUT     : {INDEX_OUT}", flush=True)
print(f"  Polling       : {POLL_SEC}s", flush=True)
print(f"{'='*65}\n", flush=True)

# Initialiser 25 min en arrière pour couvrir le backlog Filebeat
from datetime import timedelta as _td
last_check = (datetime.now(timezone.utc) - _td(minutes=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
processed_net = 0
processed_ep  = 0

while True:
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # =====================================================================
        # PARTIE 1 : ANALYSE RESEAU (SURICATA / ML)
        # =====================================================================
        query_net = {
            "query": {
                "bool": {
                    "must": [
                        {"term":  {"suricata.eve.event_type": "alert"}},
                        {"range": {"event.ingested": {"gte": last_check, "lt": now}}}
                    ],
                    "must_not": [
                        {"term": {"suricata.eve.alert.signature": "SURICATA STREAM Packet with invalid ack"}},
                        {"term": {"suricata.eve.alert.signature": "SURICATA STREAM SHUTDOWN RST invalid ack"}}
                    ]
                }
            },
            "_source": [ "@timestamp", "source.ip", "source.port", "destination.ip", "destination.port", "network.protocol", "suricata.eve.alert.signature", "suricata.eve.alert.category", "suricata.eve.alert.severity", "suricata.eve.flow.bytes_toserver", "suricata.eve.flow.bytes_toclient", "suricata.eve.flow.pkts_toserver", "suricata.eve.flow.pkts_toclient" ],
            "size": 100
        }

        hits_net = es.search(index=INDEX_IN_NET, body=query_net).get("hits", {}).get("hits", [])
        
        if hits_net:
            print(f"[{now}] 🌐 {len(hits_net)} alertes Réseau (Suricata)", flush=True)
            for hit in hits_net:
                src = hit["_source"]
                eve = src.get("suricata", {}).get("eve", {})
                alert_data = eve.get("alert", {})
                timestamp  = src.get("@timestamp", now)
                
                # Récupération des données réseau brutes
                alert_raw = {
                    "src_port": src.get("source", {}).get("port", 0) or 0,
                    "dst_port": src.get("destination", {}).get("port", 0) or 0,
                    "bytes_toserver": eve.get("flow", {}).get("bytes_toserver", 0) or 0,
                    "bytes_toclient": eve.get("flow", {}).get("bytes_toclient", 0) or 0,
                    "pkts_toserver": eve.get("flow", {}).get("pkts_toserver", 0) or 0,
                    "pkts_toclient": eve.get("flow", {}).get("pkts_toclient", 0) or 0,
                    "severity": alert_data.get("severity", 0) or 0,
                }
                
                # ML Pipeline
                features = build_features(alert_raw, timestamp)
                xgb_pred, xgb_conf = predict_xgb(features)
                ae_anomaly, ae_score, ae_error = predict_autoencoder(features)
                lstm_pred, lstm_conf, lstm_status = predict_lstm(features)
                reputation = get_ip_reputation(src.get("source", {}).get("ip", ""))
                mitre = get_mitre_tag(alert_data.get("signature", ""), alert_data.get("category", ""))
                if mitre is None: continue  # Filtrer bruit réseau
                threat_level = compute_threat_level(xgb_pred, xgb_conf, ae_anomaly, ae_score, lstm_pred, reputation["vt_score"], reputation["abuse_score"])

                super_alert = {
                    "@timestamp": now, "processed_at": now, "model_version": "V5-Network",
                    "event_type": "network_alert", "threat_level": threat_level,
                    "src_ip": src.get("source", {}).get("ip", ""), "dst_ip": src.get("destination", {}).get("ip", ""),
                    "signature": alert_data.get("signature", ""),
                    "xgb_confidence": xgb_conf, "ae_score": ae_score, "lstm_killchain": lstm_pred,
                    "vt_score": reputation["vt_score"], "abuse_score": reputation["abuse_score"], "mitre_technique": mitre["technique"],
                    "src_geo": get_geo_for_ip(src.get("source", {}).get("ip", "")),
                    "ml_confidence": xgb_conf # Rétrocompatibilité
                }
                es.index(index=INDEX_OUT, document=super_alert)
                processed_net += 1

        # =====================================================================
        # PARTIE 2 : ANALYSE ENDPOINT (SYSMON / GEMINI) - NOUVEAU !!
        # =====================================================================
        query_ep = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"winlog.channel": "Microsoft-Windows-Sysmon/Operational"}},
                        {"term": {"event.code": 1}}, # Se concentrer sur ProcessCreate (ID 1)
                        {"range": {"event.ingested": {"gte": last_check, "lt": now}}}
                    ]
                }
            },
            "_source": ["@timestamp", "host.name", "winlog.event_data.Image", "winlog.event_data.CommandLine", "winlog.event_data.User"],
            "size": 50 # Limite pour ne pas spammer l'API Gemini
        }

        try:
            hits_ep = es.search(index=INDEX_IN_EP, body=query_ep).get("hits", {}).get("hits", [])
            if hits_ep:
                print(f"[{now}] 💻 {len(hits_ep)} logs Endpoint (Sysmon Event ID 1)", flush=True)
                for hit in hits_ep:
                    src = hit["_source"]
                    event_data = src.get("winlog", {}).get("event_data", {})
                    
                    # Extraire le nom de l'exécutable du chemin complet
                    image_path = event_data.get("Image", "")
                    process_name = image_path.split("\\")[-1] if image_path else "unknown.exe"
                    cmd_line = event_data.get("CommandLine", "")
                    
                    # Interroger Gemini (Seulement si la commande existe)
                    if cmd_line:
                        gemini_threat, gemini_reason, gemini_mitre = analyze_sysmon_with_gemini(process_name, cmd_line)
                        
                        # Création de l'alerte Endpoint V5
                        super_alert_ep = {
                            "@timestamp": now,
                            "processed_at": now,
                            "model_version": "V5-Endpoint-LLM",
                            "event_type": "endpoint_process",
                            "threat_level": gemini_threat,
                            "host_name": src.get("host", {}).get("name", ""),
                            "user": event_data.get("User", ""),
                            "process_name": process_name,
                            "command_line": cmd_line,
                            "gemini_analysis": gemini_reason,
                            "mitre_technique": gemini_mitre or "T0000"
                        }
                        
                        # On indexe SEULEMENT si c'est suspect (pour ne pas polluer l'index)
                        if gemini_threat in ["MEDIUM", "HIGH", "CRITICAL"]:
                            es.index(index=INDEX_OUT, document=super_alert_ep)
                            print(f"  🚨 Sysmon [{gemini_threat}] {process_name} : {gemini_reason[:60]}...", flush=True)
                    
                    processed_ep += 1
        except Exception as e:
            # Silencieux si l'index Sysmon n'existe pas encore parfaitement
            pass

        if not hits_net and not hits_ep:
            print(f"[{now}] 💤 Aucune alerte (Net:{processed_net} | EP:{processed_ep})", flush=True)

        last_check = now
        time.sleep(POLL_SEC)

    except KeyboardInterrupt:
        print(f"\n🛑 Script V5 arrêté. Alertes traitées -> Net:{processed_net} | EP:{processed_ep}")
        break
    except Exception as e:
        print(f"❌ Erreur boucle : {e}")
        time.sleep(5)