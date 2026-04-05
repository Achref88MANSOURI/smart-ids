# 🛡️ Smart-IDS Framework V5

> Système de Détection d'Intrusion Hybride — Triple IA + Gemini + GCP

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![XGBoost](https://img.shields.io/badge/XGBoost-AUC_0.9898-green)](https://xgboost.readthedocs.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)](https://fastapi.tiangolo.com)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.x-yellow)](https://elastic.co)
[![License](https://img.shields.io/badge/License-MIT-red)](LICENSE)

---

## 📋 Description

Smart-IDS est une plateforme SOC (Security Operations Center) complète déployée sur Google Cloud Platform. Elle capture le trafic réseau en temps réel, l'analyse avec une triple intelligence artificielle, et génère des rapports automatiques via Gemini 2.5 Flash.

---

## 🏗️ Architecture

```
Attacker VM (Kali) ──→ Victim VM (Ubuntu)
         │                     │
         └──── Packet Mirroring GCP ────→ IDS Sensor (Suricata + Filebeat)
                                                    │
                                          Elasticsearch 8.x (HTTPS)
                                                    │
                                          Enrichment Pipeline (ML)
                                         ┌──────────┼──────────┐
                                      XGBoost   Autoencoder   LSTM V4
                                         └──────────┼──────────┘
                                                    │
                                    ┌───────────────┴───────────────┐
                                 Kibana                      React Dashboard
                              (MITRE ATT&CK)              (FastAPI + JWT)
```

---

## ⚡ Stack Technique

| Composant | Technologie | Version |
|---|---|---|
| IDS | Suricata | 7.0+ |
| Transport | Filebeat | 8.12 |
| Base de données | Elasticsearch | 8.x |
| ML Supervisé | XGBoost V4 Clean | AUC 0.9898 |
| ML Non-supervisé | Autoencoder | 99.35% |
| ML Séquentiel | LSTM V4 PRO + Attention | AUC 0.982 |
| LLM | Gemini 2.5 Flash | API |
| Backend | FastAPI + JWT | 0.110 |
| Frontend | React | 18 |
| Visualisation | Kibana | 8.x |
| Cloud | Google Cloud Platform | - |

---

## 🎯 Performances ML

| Modèle | AUC-ROC | Recall | FP Rate | F1 |
|---|---|---|---|---|
| XGBoost V4 Clean | **0.9898** | 93.5% | 4.6% | 0.909 |
| Autoencoder | - | 99.35% | - | - |
| LSTM V4 PRO | **0.982** | - | 1.1% | 0.850 |

Dataset d'entraînement : 7 733 attaques réelles GCP + 20 187 flux normaux — **zéro bruit STREAM labelisé ATTACK**.

---

## 🔐 Sécurité — 6 Couches

- **Fernet 256-bit** — secrets chiffrés au repos
- **OAuth2/JWT** — authentification + RBAC 3 rôles (admin, analyst, viewer)
- **Input Validation** — 25+ patterns de sanitisation
- **HMAC-SHA256** — intégrité des modèles ML
- **Prompt Injection Defense** — protection LLM
- **Elasticsearch HTTPS** — TLS + Basic Auth

---

## 🌐 Infrastructure GCP

| Machine | IP Interne | Rôle |
|---|---|---|
| attacker-vm | 10.0.2.2 | Kali Linux — simulation d'attaques |
| victim-vm | 10.0.1.2 | Cible vulnérable Ubuntu |
| ids-sensor | 10.0.1.3 | Suricata 7.0 + Filebeat |
| soc-manager-c | 10.0.1.7 | ELK Stack + IA + Dashboard |

---

## 🚀 Démarrage Rapide

### Prérequis

- Google Cloud Platform (4 VMs)
- Python 3.12
- Node.js 18+
- Elasticsearch 8.x

### Installation

```bash
git clone https://github.com/Achref88MANSOURI/smart-ids.git
cd smart-ids

# Environnement Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Remplir : GEMINI_API_KEY, VT_API_KEY, ABUSEIPDB_KEY, ES_PASS

# Build React
cd dashboard/frontend
npm install && npm run build
cd ../..
```

### Démarrage

```bash
# Sur soc-manager-c
sudo systemctl start elasticsearch
sleep 15
sudo systemctl start kibana smart-ids-enrichment smart-ids-backend

# Mettre à jour l'IP externe (après reboot GCP)
~/smart-ids/scripts/update_ip.sh
```

### Accès

| Service | URL | Credentials |
|---|---|---|
| Dashboard React | `http://<IP>:8080` | admin/admin123456 |
| Kibana | `http://<IP>:5601` | elastic/\<password\> |
| API FastAPI | `http://<IP>:8080/docs` | JWT Token |

---

## 📊 Règles IDS MITRE ATT&CK

| Règle | Technique | Description |
|---|---|---|
| SMARTIDS T1046 Nmap SYN Scan | T1046 | Network Service Discovery |
| SMARTIDS T1110 SSH Brute Force | T1110 | Credential Access |
| SMARTIDS T1499 SYN Flood | T1499 | Endpoint DoS |
| SMARTIDS T1190 SQL Injection | T1190 | Initial Access |
| SMARTIDS T1082 SMB Enumeration | T1082 | System Information Discovery |

48 102 règles Emerging Threats Open (2026) + 11 règles custom SMARTIDS.

---

## 📁 Structure du Projet

```
smart-ids/
├── scripts/
│   ├── enrichment.py          # Pipeline ML temps réel (700+ lignes)
│   ├── train_hybrid_final.py  # Entraînement XGBoost
│   ├── train_lstm_v4_pro.py   # Entraînement LSTM
│   └── update_ip.sh           # Mise à jour IP GCP
├── dashboard/
│   ├── backend.py             # FastAPI (1500+ lignes)
│   └── frontend/              # React App
├── models/                    # Modèles ML (3.6 MB)
├── data/processed/            # Datasets entraînement
├── auth_module.py             # JWT/OAuth2
├── model_security.py          # HMAC intégrité
├── llm_security.py            # Prompt injection defense
└── .env.example               # Template configuration
```

---

## 🔑 Variables d'Environnement

```bash
# .env.example
GEMINI_API_KEY=your_gemini_key
VT_API_KEY=your_virustotal_key
ABUSEIPDB_KEY=your_abuseipdb_key
ES_USER=smart_ids
ES_PASS=your_elasticsearch_password
ES_CA=/etc/smart-ids-ca.crt
```

---

## 📈 Métriques Production

```
Alertes enrichies     : 65 000+
Kill Chains détectées : 40 000+
IPs malveillantes VT  : 4 745
Top MITRE             : T1110 (Brute Force SSH) — 90%+
Latence pipeline      : < 30 secondes
```

---

## 🤝 Contribution

1. Fork le projet
2. Crée une branche (`git checkout -b feature/amelioration`)
3. Commit (`git commit -m 'Ajout feature'`)
4. Push (`git push origin feature/amelioration`)
5. Ouvre une Pull Request

---

## 📄 Licence

MIT License — voir [LICENSE](LICENSE)

