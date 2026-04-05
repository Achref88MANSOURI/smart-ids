# 🔐 PHASE 0: REMÉDIATION IMMÉDIATE - RÉVOCATION CLÉS API
## Smart-IDS Security Emergency Response
**Date:** 29 Mars 2026  
**Durée:** 24 heures  
**Risque:** CRITICAL - Clés compromises en circulation  

---

## 📋 ÉTAPE 1: AUDIT DE L'UTILISATION ACTUELLE DES CLÉS

### Services affectés

```
┌─────────────────────────────────────────────────────────┐
│ CLÉS COMPROMISES IDENTIFIÉES (3)                        │
├─────────────────────────────────────────────────────────┤
│ 1. VT_API_KEY         → VirusTotal Reputation Check     │
│    Fichier: scripts/enrichment.py (line 27)             │
│    Utilisé par: ML enrichment service                   │
│                                                         │
│ 2. ABUSEIPDB_KEY      → IP Abuse/Reputation Database    │
│    Fichier: scripts/enrichment.py (line 28)             │
│    Utilisé par: ML enrichment service                   │
│                                                         │
│ 3. GEMINI_API_KEY     → Google LLM Analysis             │
│    Fichier: scripts/enrichment.py (line 30)             │
│    Fichier: dashboard/backend.py (line 17)              │
│    Utilisé par: Enrichment + Backend API                │
└─────────────────────────────────────────────────────────┘
```

### Services dépendant

```
SERVICE 1: enrichment.py (systemd: smart-ids-enrichment)
├─ État: RUNNING (PID 30265)
├─ Mémoire: 747MB
├─ Dépend de:
│  ├─ VT_API_KEY (IP reputation)
│  ├─ ABUSEIPDB_KEY (IP reputation)
│  └─ GEMINI_API_KEY (Sysmon event analysis)
└─ Fréquence: Polls every 15 seconds

SERVICE 2: backend.py (FastAPI: uvicorn)
├─ État: RUNNING (PID 30688, port 8080)
├─ Mémoire: 101MB
├─ Dépend de:
│  └─ GEMINI_API_KEY (LLM-assisted analysis via /api/analyze)
└─ Utilisateurs: SOC analysts

SERVICE 3: frontend (React on port 3000)
├─ État: RUNNING
├─ Dépend de: Backend (no direct API key usage)
└─ Utilisateurs: Web dashboard
```

---

## 🔴 ÉTAPE 2: CHRONOLOGIE DE COMPROMISSION

```
Risk Timeline Estimation:

T+0     Clés exposées dans .env (public repo)
T+24h   Attacker discovers via GitHub/source search
T+48h   Attacker begins exploitation:
        - VirusTotal: Pollute reputation database
        - AbuseIPDB: Exhaust quota (1000 req/day)
        - Gemini: Abuse quota ($$$)
        
T+72h   CRITICAL: Smart-IDS rendered ineffective
        - No IP reputation available
        - No LLM analysis possible
        - SOC blind to APT activity

STATUS: 🔴 WINDOW TO REVOKE: < 72 HOURS
```

---

## ✅ ÉTAPE 3: PLAN DE RÉVOCATION SÉCURISÉE (Sans Breaking Changes)

### 3.1 - PRÉ-REVOCATION (Avant de révoquer)

```bash
# ✓ Step 1: Préparer les NOUVELLES clés (avant révocation)
#   Location: Google Cloud Secret Manager

# ✓ Step 2: Mettre à jour .env avec les NOUVELLES clés
#   Important: Garder enrichment + backend running pendant la transition

# ✓ Step 3: Redémarrer les services avec les NOUVELLES clés
#   systemctl restart smart-ids-enrichment
#   systemctl restart smart-ids-backend (if exists)

# ✓ Step 4: ATTENDRE 5 minutes pour vérifier le bon fonctionnement

# ✓ Step 5: Vérifier les logs
#   journalctl -u smart-ids-enrichment -f
#   curl http://localhost:8080/api/health

# ✓ SEULEMENT ALORS: révoquer les clés anciennes
```

### 3.2 - MATRICE DE RÉVOCATION PAR SERVICE

```
┌─────────────────────────────────────────────────────────┐
│ SERVICE/API        │ REVOKE URL              │ NOTES      │
├─────────────────────────────────────────────────────────┤
│ VirusTotal         │ virustotal.com/settings │ Delete old │
│                    │ /apikey                 │ key first  │
├─────────────────────────────────────────────────────────┤
│ AbuseIPDB          │ abuseipdb.com/account   │ Revoke +   │
│                    │ /api/keys               │ Create new │
├─────────────────────────────────────────────────────────┤
│ Google Generative  │ aistudio.google.com/    │ Delete old │
│ AI (Gemini)        │ app/apikeys             │ key        │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 ÉTAPE 4: PROCÉDURE ÉTAPE PAR ÉTAPE

### PHASE 0.1: GÉNÉRER NOUVELLES CLÉS (30 min)

#### 4.1a - Créer nouvelle clé VirusTotal
```bash
# 1. Aller à: https://www.virustotal.com/gui/settings/apikey
# 2. Cliquer "+ Generate new API key"
# 3. Copier la clé générée
# 4. Sauvegarder dans un endroit sécurisé (ex: 1Password)

# Nouvelle clé format: 64 caractères hexadécimals
# Example: a1b2c3d4e5f6... (à remplacer par la vraie)
```

#### 4.1b - Créer nouvelle clé AbuseIPDB
```bash
# 1. Aller à: https://www.abuseipdb.com/register (si besoin de nouveau compte)
# 2. Login à: https://www.abuseipdb.com/account
# 3. Section "API" → Générer nouvelle clé
# 4. Copier la clé
# 5. Tester la connexion avec: 
curl -G "https://api.abuseipdb.com/api/v2/check" \
  -d "ipAddress=8.8.8.8" \
  -d "maxAgeInDays=90" \
  -H "Key: <NEW_KEY>" \
  -H "Accept: application/json"
# Output should show: 200 OK
```

#### 4.1c - Créer nouvelle clé Gemini
```bash
# 1. Aller à: https://aistudio.google.com/app/apikeys
# 2. Cliquer "Create new API key"
# 3. Sélectionner: "Create API key in new project" OU "Existing project"
# 4. Copier la clé
# 5. Tester:
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent" \
  -H "x-goog-api-key: <NEW_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{"text": "Say hello"}]
    }]
  }'
# Output should show: 200 OK avec texte
```

### PHASE 0.2: METTRE À JOUR LE PROJET (30 min)

#### 4.2a - Mettre à jour .env avec NOUVELLES clés
```bash
# ✅ SÉCURITÉ: Faire une sauvegarde d'abord
cp /home/achrefmansouri600/smart-ids/.env /home/achrefmansouri600/smart-ids/.env.backup

# Mettre à jour le fichier:
cat > /home/achrefmansouri600/smart-ids/.env << 'EOF'
VT_API_KEY=<NEW_VIRUSTOTAL_KEY>
ABUSEIPDB_KEY=<NEW_ABUSEIPDB_KEY>
GEMINI_API_KEY=<NEW_GEMINI_KEY>
EOF

# Vérifier que les clés ne contiennent pas les anciennes valeurs:
cat /home/achrefmansouri600/smart-ids/.env
```

#### 4.2b - Redémarrer les services
```bash
# Redémarrer enrichment service
sudo systemctl restart smart-ids-enrichment

# Attendre 5 secondes
sleep 5

# Vérifier que le service est UP
sudo systemctl status smart-ids-enrichment
# Output: ✓ active (running)

# Vérifier les logs pour erreurs
sudo journalctl -u smart-ids-enrichment -n 20 --no-pager
# Chercher: "[SUCCESS]" ou "[ERROR]"
```

#### 4.2c - Redémarrer backend API
```bash
# Si backend est lancé via systemd:
sudo systemctl restart smart-ids-backend

# Ou si lancé manuellement (uvicorn):
# 1. Kill le processus uvicorn
pkill -f "uvicorn backend:app"

# 2. Relancer
cd /home/achrefmansouri600/smart-ids/dashboard
nohup uvicorn backend:app --host 0.0.0.0 --port 8080 > backend.log 2>&1 &

# 3. Attendre 5 secondes et vérifier
sleep 5
curl http://localhost:8080/api/health
# Output: {"status": "ok", ...}
```

### PHASE 0.3: VÉRIFIER LE BON FONCTIONNEMENT (15 min)

#### 4.3a - Test enrichment service
```bash
# Vérifier que le service fetche les alertes Elasticsearch
sudo journalctl -u smart-ids-enrichment -n 50 --no-pager | tail -20

# Chercher les logs:
# ✅ "Successfully fetched X alerts from Elasticsearch"
# ✅ "IP reputation lookup succeeded"
# ✅ "Gemini analysis completed"
# ❌ "API error" ou "Connection timeout" ou "Invalid key"
```

#### 4.3b - Test backend API
```bash
# Test endpoint health
curl http://localhost:8080/api/health
# Output: {"status": "ok", "es": true, "gemini": true}

# Test alerts retrieval
curl "http://localhost:8080/api/alerts?minutes=60&size=10"
# Output: {"alerts": [...], "total": X}

# Test LLM endpoint
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Bonjour"}'
# Output: {"response": "..."}
```

#### 4.3c - Vérifier les logs pour erreurs
```bash
# Frontend logs (si applicable)
curl http://localhost:3000
# Output: HTML page (status 200)

# Backend error logs
tail -20 /tmp/backend.log
# Chercher: "ERROR" ou "CRITICAL"

# Enrichment error logs
sudo journalctl -u smart-ids-enrichment -p err --no-pager
# Devrait être vide
```

### PHASE 0.4: RÉVOQUER LES CLÉS ANCIENNES (20 min)

#### 🔴 **ATTENTION: À NE FAIRE QUE APRÈS VÉRIFICATION COMPLÈTE**

```bash
# ✳️ VÉRIFICATION PRÉ-REVOCATION CHECKLIST:
# ☐ Enrichment service running + logs OK
# ☐ Backend API responding correctly
# ☐ No "Invalid API key" errors in logs
# ☐ Dashboard responding
# ☐ New keys tested manually

# SEULEMENT ALORS:
```

#### 4.4a - Révoquer VirusTotal
```
1. Aller à: https://www.virustotal.com/gui/settings/apikey
2. Chercher: "API keys" section
3. Trouver l'ANCIENNE clé: cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c
4. Cliquer "Delete" ou "Revoke"
5. Confirmer la suppression
6. Vérifier que seule la NOUVELLE clé existe
```

#### 4.4b - Révoquer AbuseIPDB
```
1. Aller à: https://www.abuseipdb.com/account
2. Section "API" → "Keys"
3. Trouver l'ANCIENNE clé: 3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be503761c43a8605ebfb0
4. Cliquer "Revoke"
5. Confirmer
6. Vérifier que seule la NOUVELLE clé existe
```

#### 4.4c - Révoquer Gemini
```
1. Aller à: https://aistudio.google.com/app/apikeys
2. Chercher l'ANCIENNE clé: AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE
3. Cliquer "Delete"
4. Confirmer la suppression
5. Vérifier que seule la NOUVELLE clé existe
```

### PHASE 0.5: AUDIT & NETTOYAGE GIT (20 min)

#### 4.5a - Vérifier qu'aucune clé n'est commise dans Git
```bash
# Chercher toutes les occurrences des ANCIENNES clés
git log --all -S "cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c" --source

git log --all -S "3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be5" --source

git log --all -S "AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE" --source

# Résultat: Devrait montrer les commits qui les contiennent
```

#### 4.5b - Si clés trouvées: Nettoyer l'historique Git
```bash
# ⚠️ CETTE COMMANDE EST DESTRUCTIVE - À NE FAIRE QU'UNE SEULE FOIS

# Installation git-filter-repo (plus moderne que git-filter-branch):
sudo apt-get install git-filter-repo

# Nettoyer la clé VT_API_KEY:
git filter-repo --replace-text <(echo 'cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c==>REDACTED')

# Nettoyer la clé ABUSEIPDB:
git filter-repo --replace-text <(echo '3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be503761c43a8605ebfb0==>REDACTED')

# Nettoyer la clé GEMINI:
git filter-repo --replace-text <(echo 'AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE==>REDACTED')

# Push en force:
git push -f origin main
# ⚠️ Cela affectera tous les collaborateurs!
```

#### 4.5c - Ajouter .env à .gitignore (prévention future)
```bash
# Ajouter .env au gitignore si pas déjà présent
echo ".env" >> /home/achrefmansouri600/smart-ids/.gitignore
echo ".env.local" >> /home/achrefmansouri600/smart-ids/.gitignore
echo ".env.backup" >> /home/achrefmansouri600/smart-ids/.gitignore

# Commit et push
git add .gitignore
git commit -m "security: Add .env to gitignore - prevent API key exposure"
git push origin main
```

---

## 📊 ÉTAPE 5: VÉRIFICATION POST-REMÉDIATION

### Checklist de vérification (15 min)

```
✅ PRÉ-REVOCATION:
   ☐ Nouvelles clés VirusTotal générées et testées
   ☐ Nouvelles clés AbuseIPDB générées et testées
   ☐ Nouvelles clés Gemini générées et testées
   ☐ .env mis à jour avec NOUVELLES clés
   ☐ Enrichment service redémarré et logs OK
   ☐ Backend API redémarré et responding
   ☐ Dashboard accessible
   ☐ Pas d'erreurs "Invalid API key"

✅ RÉVOCATION:
   ☐ Anciennes clés révoquées VirusTotal
   ☐ Anciennes clés révoquées AbuseIPDB
   ☐ Anciennes clés révoquées Gemini
   ☐ Vérification que seules les NOUVELLES clés existent

✅ NETTOYAGE:
   ☐ Git history audité (0 anciennes clés trouvées)
   ☐ .env ajouté à .gitignore
   ☐ Commit "security: " done
```

### Test de Fonctionnalité Post-Remédiation

```bash
# Vérifier que le projet fonctionne toujours:

LOG_FILE="/tmp/smart_ids_phase0_test.log"

echo "=== SMART-IDS PHASE 0 POST-REMEDIATION TEST ===" | tee $LOG_FILE
echo "" | tee -a $LOG_FILE

# 1. Check enrichment service
echo "1️⃣ Enrichment Service Status:" | tee -a $LOG_FILE
sudo systemctl status smart-ids-enrichment | grep "active" | tee -a $LOG_FILE

# 2. Check backend
echo "" | tee -a $LOG_FILE
echo "2️⃣ Backend Health:" | tee -a $LOG_FILE
curl -s http://localhost:8080/api/health | python3 -m json.tool | tee -a $LOG_FILE

# 3. Check Elasticsearch
echo "" | tee -a $LOG_FILE
echo "3️⃣ Elasticsearch Status:" | tee -a $LOG_FILE
curl -s http://10.0.1.7:9200/_cluster/health | python3 -m json.tool | head -5 | tee -a $LOG_FILE

# 4. Check recent enrichment logs
echo "" | tee -a $LOG_FILE
echo "4️⃣ Recent Enrichment Logs (last 10 lines):" | tee -a $LOG_FILE
sudo journalctl -u smart-ids-enrichment -n 10 --no-pager | tee -a $LOG_FILE

# 5. Check for API key errors
echo "" | tee -a $LOG_FILE
echo "5️⃣ Checking for API Key Errors:" | tee -a $LOG_FILE
sudo journalctl -u smart-ids-enrichment --since "10 minutes ago" | grep -i "key\|error\|api" | head -5 | tee -a $LOG_FILE
if [ $? -ne 0 ]; then
  echo "✅ No API key errors found!" | tee -a $LOG_FILE
fi

echo "" | tee -a $LOG_FILE
echo "=== TEST COMPLETE ===" | tee -a $LOG_FILE
cat $LOG_FILE
```

---

## 🚨 ÉTAPE 6: MESURES D'URGENCE SI PROBLÈME

Si services ne restart pas correctement:

```bash
### Option 1: Revenir à l'ancienne clé (temporaire)
# cp /home/achrefmansouri600/smart-ids/.env.backup /home/achrefmansouri600/smart-ids/.env
# sudo systemctl restart smart-ids-enrichment
# (Ne faire que pour diagnostic - l'ancienne clé est toujours compromise)

### Option 2: Désactiver les services affectés
sudo systemctl stop smart-ids-enrichment
# Garder backend mais sans enrichment

### Option 3: Logs détaillés
sudo journalctl -u smart-ids-enrichment -p err -n 100
# Pour diagnostiquer le problème exact
```

---

## 📅 TIMELINE COMPLÈTE PHASE 0

```
├─ T+0min     : Générer nouvelles clés (30 min)
├─ T+30min    : Mettre à jour .env + redémarrer services (30 min)
├─ T+60min    : Vérifier fonctionnement (15 min)
├─ T+75min    : Révoquer anciennes clés (20 min)
├─ T+95min    : Nettoyer Git + audit (15 min)
├─ T+110min   : Test post-remédiation (10 min)
└─ T+120min   : COMPLETE ✅

GATE: Ne révoquer que si tous les tests passent
```

---

## 🔒 APRÈS PHASE 0: RECOMMANDATIONS IMMÉDIATE (Jour 1-2)

```
☐ Stocker les NOUVELLES clés de manière sécurisée:
  ├─ Google Cloud Secret Manager
  ├─ HashiCorp Vault
  └─ 1Password/LastPass (NOT .env!)

☐ Mettre en place rotation programmée:
  ├─ VirusTotal: rotation mensuelle
  ├─ AbuseIPDB: rotation mensuelle
  └─ Gemini: rotation tous les 3 mois

☐ Implémenter monitoring d'abuse:
  ├─ Alert si quota AbuseIPDB > 800/1000
  ├─ Alert si Gemini costs > seuil
  └─ Alert si VirusTotal rate limit hit

☐ Notification à la team:
  ├─ Que les clés ont été compromises et révoquées
  ├─ Timeline de la remédiation
  └─ Prochaines étapes (Phase 1: Auth)
```

---

**Créé:** 29 Mars 2026  
**Auteur:** Security Team  
**Status:** 🔴 À EXÉCUTER IMMÉDIATEMENT  
**Durée estimée:** 120 minutes  
**Complexité:** MEDIUM (Pas de code change, juste configuration)  

---
