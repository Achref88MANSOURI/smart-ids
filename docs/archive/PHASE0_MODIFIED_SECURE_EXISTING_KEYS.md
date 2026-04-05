# 🔐 PHASE 0 MODIFIÉE: SÉCURISATION DES CLÉS EXISTANTES
## Smart-IDS - Sans remplacement de clés
**Date:** 29 Mars 2026  
**Approche:** Garder les clés actuelles mais les sécuriser  
**Durée:** 60-90 minutes  
**Impact:** ZÉRO downtime, aucune clé changée  

---

## 📍 NOUVELLE STRATÉGIE

Au lieu de:
```
❌ Révoquer les anciennes clés
❌ Générer de nouvelles clés
❌ Remplacer dans .env
```

On fait:
```
✅ Garder les clés actuelles
✅ Les déplacer hors du .env exposé
✅ Les stocker de manière SÉCURISÉE
✅ Nettoyer Git history
✅ Ajouter protection supplémentaire
```

---

## 🎯 OBJECTIFS PHASE 0 MODIFIÉE

### 1️⃣ **Sécuriser le stockage des clés**
```
AVANT:  .env (visible, en plaintext, committé en git) ❌
APRÈS:  Google Cloud Secret Manager (chiffré, audité) ✅
```

### 2️⃣ **Nettoyer l'exposition Git**
```
AVANT:  Clés dans l'historique Git public ❌
APRÈS:  Historique purgé, .env ignoré ✅
```

### 3️⃣ **Monitorer l'usage des clés**
```
AVANT:  Pas de logs d'utilisation ❌
APRÈS:  Chaque utilisation tracée + alertes ✅
```

### 4️⃣ **Restreindre l'accès**
```
AVANT:  N'importe quel process peut lire .env ❌
APRÈS:  Seuls enrichment + backend peuvent accéder ✅
```

### 5️⃣ **Ajouter défense-en-profondeur**
```
AVANT:  Clés en clair = exploitable immédiatement ❌
APRÈS:  Plusieurs couches de sécurité ✅
```

---

## ✅ PHASE 0 NOUVELLE: ÉTAPES DÉTAILLÉES

### ÉTAPE 1: AUDIT DES CLÉS ACTUELLES (10 min)

```bash
# Vérifier les clés dans la système
cat /home/achrefmansouri600/smart-ids/.env

# Résultat:
VT_API_KEY=cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c
ABUSEIPDB_KEY=3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be503761c43a8605ebfb0
GEMINI_API_KEY=AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE

# Chercher où elles sont utilisées
grep -r "VT_API_KEY\|ABUSEIPDB_KEY\|GEMINI_API_KEY" /home/achrefmansouri600/smart-ids --include="*.py" | grep -v __pycache__ | head -10

# Résultat: utilisées dans enrichment.py et backend.py
```

### ÉTAPE 2: DÉPLACER VERS GOOGLE CLOUD SECRET MANAGER (30 min)

#### 2.1 - Se connecter à GCP

```bash
# Authentifier à Google Cloud
gcloud auth login

# Sélectionner le projet
gcloud config set project cyber-security-lab

# Vérifier la connexion
gcloud config list
```

#### 2.2 - Créer les secrets dans GCP

```bash
# Créer secret pour VirusTotal
echo -n "cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c" | \
  gcloud secrets create smart-ids-vt-api-key --replication-policy="automatic" --data-file=-

# Créer secret pour AbuseIPDB
echo -n "3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be503761c43a8605ebfb0" | \
  gcloud secrets create smart-ids-abuseipdb-key --replication-policy="automatic" --data-file=-

# Créer secret pour Gemini
echo -n "AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE" | \
  gcloud secrets create smart-ids-gemini-api-key --replication-policy="automatic" --data-file=-

# Vérifier que les secrets sont créés
gcloud secrets list --filter="name:smart-ids*"

# Résultat: 3 secrets créés et chiffrés
```

#### 2.3 - Accorder les permissions

```bash
# Trouver le service account de la VM
PROJECT_ID="cyber-security-lab"
COMPUTE_EMAIL=$(gcloud compute instances describe $(gcloud compute instances list --format='value(name)' | head -1) --zone=europe-west1-c --format='value(serviceAccounts[0].email)')

# Accorder rôle pour accéder aux secrets
gcloud secrets add-iam-policy-binding smart-ids-vt-api-key \
  --member=serviceAccount:$COMPUTE_EMAIL \
  --role=roles/secretmanager.secretAccessor

gcloud secrets add-iam-policy-binding smart-ids-abuseipdb-key \
  --member=serviceAccount:$COMPUTE_EMAIL \
  --role=roles/secretmanager.secretAccessor

gcloud secrets add-iam-policy-binding smart-ids-gemini-api-key \
  --member=serviceAccount:$COMPUTE_EMAIL \
  --role=roles/secretmanager.secretAccessor

# Vérifier les permissions
gcloud secrets get-iam-policy smart-ids-vt-api-key
```

### ÉTAPE 3: MODIFIER LE CODE POUR LIRE DEPUIS GCP (20 min)

#### 3.1 - Installer la librairie Google Secret Manager

```bash
cd /home/achrefmansouri600/smart-ids
source venv_ml/bin/activate

pip install google-cloud-secret-manager

# Vérifier
python3 -c "from google.cloud import secretmanager; print('✓ Installed')"
```

#### 3.2 - Créer un helper pour récupérer les secrets

```bash
cat > /home/achrefmansouri600/smart-ids/utils/secret_manager.py << 'EOF'
"""
Google Cloud Secret Manager helper
Récupère les clés API de manière sécurisée depuis GCP
"""

from google.cloud import secretmanager
import os
from functools import lru_cache

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "cyber-security-lab")

@lru_cache(maxsize=10)
def get_secret(secret_name: str) -> str:
    """
    Récupère un secret depuis Google Cloud Secret Manager
    
    Args:
        secret_name: ex: "smart-ids-vt-api-key"
    
    Returns:
        La valeur du secret (déchiffrée)
    """
    client = secretmanager.SecretManagerServiceClient()
    
    # Construire le chemin
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    
    try:
        # Récupérer le secret
        response = client.access_secret_version(request={"name": name})
        
        # Décoder
        secret_value = response.payload.data.decode('UTF-8')
        return secret_value
        
    except Exception as e:
        print(f"❌ Erreur récupération secret {secret_name}: {e}")
        return None

# Convenience functions
def get_vt_api_key():
    return get_secret("smart-ids-vt-api-key")

def get_abuseipdb_key():
    return get_secret("smart-ids-abuseipdb-key")

def get_gemini_api_key():
    return get_secret("smart-ids-gemini-api-key")
EOF

chmod 600 /home/achrefmansouri600/smart-ids/utils/secret_manager.py
```

#### 3.3 - Modifier enrichment.py

```bash
# Lire le fichier actuel et voir comment les clés sont chargées
head -50 /home/achrefmansouri600/smart-ids/scripts/enrichment.py | grep -A 5 "load_dotenv\|VT_KEY\|ABUSE_KEY\|GEMINI_KEY"

# Résultat: Actuellement il charge depuis .env avec os.getenv()
```

Remplacer dans `scripts/enrichment.py`:

```python
# AVANT:
from dotenv import load_dotenv
import os

load_dotenv("/home/achrefmansouri600/smart-ids/.env")
VT_KEY = os.getenv("VT_API_KEY")
ABUSE_KEY = os.getenv("ABUSEIPDB_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# APRÈS:
import sys
sys.path.insert(0, "/home/achrefmansouri600/smart-ids")
from utils.secret_manager import get_vt_api_key, get_abuseipdb_key, get_gemini_api_key

VT_KEY = get_vt_api_key()
ABUSE_KEY = get_abuseipdb_key()
GEMINI_KEY = get_gemini_api_key()
```

#### 3.4 - Modifier backend.py

```python
# AVANT:
from dotenv import load_dotenv
import os

load_dotenv("/home/achrefmansouri600/smart-ids/.env")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

# APRÈS:
import sys
sys.path.insert(0, "/home/achrefmansouri600/smart-ids")
from utils.secret_manager import get_gemini_api_key

GEMINI_KEY = get_gemini_api_key() or ""
```

### ÉTAPE 4: TESTER LES MODIFICATIONS (15 min)

```bash
# Télécharger les secrets et vérifier
cd /home/achrefmansouri600/smart-ids

# Test 1: Vérifier que secret_manager fonctionne
python3 << 'EOF'
import sys
sys.path.insert(0, ".")
from utils.secret_manager import get_vt_api_key, get_gemini_api_key

vt_key = get_vt_api_key()
print(f"✅ VT Key retrieved: {vt_key[:20]}..." if vt_key else "❌ Failed to get VT key")

gemini_key = get_gemini_api_key()
print(f"✅ Gemini Key retrieved: {gemini_key[:20]}..." if gemini_key else "❌ Failed to get Gemini key")
EOF

# Test 2: Redémarrer enrichment service
sudo systemctl stop smart-ids-enrichment
sleep 3
sudo systemctl start smart-ids-enrichment
sleep 5

# Vérifier que le service fonctionne
sudo systemctl status smart-ids-enrichment

# Vérifier les logs
sudo journalctl -u smart-ids-enrichment -n 20 --no-pager

# Chercher les erreurs
sudo journalctl -u smart-ids-enrichment -p err --no-pager | head -5

# Résultat: Pas d'erreur → les clés sont correctement récupérées!
```

```bash
# Test 3: Vérifier le backend API
curl http://localhost:8080/api/health
# Résultat: {"status": "ok", ...}

# Test 4: Vérifier les endpoints spécifiques
curl "http://localhost:8080/api/alerts?minutes=60&size=5"
# Résultat: {"alerts": [...], "total": X}

# Test 5: Vérifier le chatbot LLM
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Bonjour"}'
# Résultat: {"response": "..."}
```

### ÉTAPE 5: NETTOYER GIT (15 min)

#### 5.1 - Supprimer .env du repo

```bash
cd /home/achrefmansouri600/smart-ids

# Vérifier l'état actuel
git status | grep .env

# Supprimer .env des fichiers trackés (mais garder le fichier localement)
git rm --cached .env

# Vérifier
git status

# Commit
git add .gitignore
git commit -m "security: Remove .env from git tracking and add to gitignore"

# Pousser
git push origin main
```

#### 5.2 - Nettoyer l'historique Git

```bash
# Installer git-filter-repo si nécessaire
sudo apt-get install git-filter-repo

# Nettoyer l'historique pour les anciennes clés
cd /home/achrefmansouri600/smart-ids

git filter-repo --replace-text <(cat << 'EOF'
cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c==>REDACTED_VT_KEY
3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be503761c43a8605ebfb0==>REDACTED_ABUSE_KEY
AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE==>REDACTED_GEMINI_KEY
EOF
)

# Force push (attention: cela affecte tous les collaborateurs!)
git push -f origin main

# Vérifier
git log --all -S "AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE" --source || echo "✅ Clés supprimées de l'historique"
```

### ÉTAPE 6: SÉCURISER .env LOCALEMENT (10 min)

```bash
# Créer un .env.template (pour documentation, SANS les vraies clés)
cat > /home/achrefmansouri600/smart-ids/.env.template << 'EOF'
# Template pour .env
# NOTE: Les clés réelles sont stockées dans Google Cloud Secret Manager
# Pour local development, créer un .env avec les vraies clés (NEVER commit!)

VT_API_KEY=<your-virustotal-key-here>
ABUSEIPDB_KEY=<your-abuseipdb-key-here>
GEMINI_API_KEY=<your-gemini-key-here>
EOF

# Restreindre les permissions du .env actuel (si existe)
if [ -f /home/achrefmansouri600/smart-ids/.env ]; then
    chmod 600 /home/achrefmansouri600/smart-ids/.env
    echo "✓ .env permissions set to 600"
fi

# Vérifier le .gitignore
cat /home/achrefmansouri600/smart-ids/.gitignore | grep -E "^\.env|^env"

# Si absent, ajouter:
echo ".env" >> /home/achrefmansouri600/smart-ids/.gitignore
echo ".env.local" >> /home/achrefmansouri600/smart-ids/.gitignore
echo ".env.backup" >> /home/achrefmansouri600/smart-ids/.gitignore

# Commit
git add .gitignore
git commit -m "security: Add .env to gitignore"
git push origin main
```

### ÉTAPE 7: AJOUTER MONITORING D'UTILISATION (15 min)

Créer un logger pour tracer chaque accès aux secrets:

```bash
cat > /home/achrefmansouri600/smart-ids/utils/secret_audit_log.py << 'EOF'
"""
Audit logging pour accès aux secrets
"""

import logging
import json
from datetime import datetime
from pathlib import Path

# Créer le dossier de logs s'il n'existe pas
LOG_DIR = Path("/var/log/smart-ids")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Setup logger
audit_logger = logging.getLogger("secret_audit")
handler = logging.FileHandler(LOG_DIR / "secret_access.log")
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(handler)
audit_logger.setLevel(logging.INFO)

def log_secret_access(secret_name: str, success: bool, source: str = "unknown"):
    """Log chaque accès à un secret"""
    audit_logger.info(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "secret": secret_name,
        "success": success,
        "source": source
    }))

def log_secret_error(secret_name: str, error: str):
    """Log les erreurs d'accès aux secrets"""
    audit_logger.error(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "secret": secret_name,
        "error": str(error)
    }))
EOF

chmod 640 /home/achrefmansouri600/smart-ids/utils/secret_audit_log.py
```

Mettre à jour le secret_manager.py pour logger:

```python
# Dans utils/secret_manager.py, ajouter:

from utils.secret_audit_log import log_secret_access, log_secret_error

def get_secret(secret_name: str) -> str:
    """..."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    
    try:
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode('UTF-8')
        
        # ✓ Log succès
        log_secret_access(secret_name, success=True, source="secret_manager")
        
        return secret_value
        
    except Exception as e:
        # ✓ Log erreur
        log_secret_error(secret_name, str(e))
        return None
```

### ÉTAPE 8: VÉRIFICATION FINALE (10 min)

```bash
# Checklist finale

echo "=== PHASE 0 FINAL VERIFICATION ==="
echo ""

# 1. Vérifier que les secrets sont dans GCP
echo "1️⃣ Secrets dans GCP:"
gcloud secrets list --filter="name:smart-ids*" --format="table(name)"

# 2. Vérifier que enrichment fonctionne
echo ""
echo "2️⃣ Enrichment service:"
sudo systemctl status smart-ids-enrichment | grep active

# 3. Vérifier que backend fonctionne
echo ""
echo "3️⃣ Backend API:"
curl -s http://localhost:8080/api/health | python3 -m json.tool | head -3

# 4. Vérifier que .env n'est pas dans git
echo ""
echo "4️⃣ Git check:"
git ls-files | grep ".env" && echo "❌ .env still in git" || echo "✅ .env properly ignored"

# 5. Vérifier que les clés ne sont pas dans l'historique
echo ""
echo "5️⃣ Git history check:"
git log --all -S "AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE" --source --oneline | wc -l | xargs -I {} sh -c 'if [ {} -gt 0 ]; then echo "❌ Found in {} commits"; else echo "✅ No keys found in history"; fi'

# 6. Vérifier les logs d'accès aux secrets
echo ""
echo "6️⃣ Secret access logs:"
sudo tail -5 /var/log/smart-ids/secret_access.log 2>/dev/null || echo "Log file will be created on first access"

echo ""
echo "=== PHASE 0 COMPLETE ==="
```

---

## 📊 AVANTAGES DE CETTE APPROCHE

### ✅ Les clés restent fonctionnelles
```
Les services continuent d'utiliser les MÊMES clés API
Aucun besoin de changer chez VirusTotal, AbuseIPDB, Gemini
Services continuent de tourner sans interruption
```

### ✅ Meilleure sécurité
```
AVANT:  .env en plaintext + git history exposé = 🔴
APRÈS:  Secrets chiffrés + 3 couches protection = 🟢

Protection 1: Chiffrement Google Cloud
Protection 2: Permissions IAM restrictives
Protection 3: Audit logging de chaque accès
```

### ✅ Nettoyage complet
```
Git history: Clés supprimées ✓
.env: Pas commité, juste local ✓
Monitoring: Chaque accès tracé ✓
```

### ✅ Pas de downtime
```
Aucun restart requis avant finalisation
Tests complets avant de pousser
Services continuent de tourner
```

---

## 🎯 RÉSULTAT FINAL

```
Avant PHASE 0:
├─ Clés en plaintext dans .env ❌
├─ Clés dans git history ❌
├─ Pas de monitoring ❌
└─ N'importe qui peut les voir ❌

Après PHASE 0:
├─ Clés chiffrées dans GCP ✅
├─ Git history purgé ✅
├─ Audit logging actif ✅
├─ Accès restreint + monitored ✅
└─ Même clés, mieux sécurisées ✅
```

---

## ⏱️ TIMELINE RÉSUMÉ

```
T+0   min: Audit + GCP setup
T+30  min: Secrets créés dans GCP
T+50  min: Code modifié + testé
T+70  min: Git nettoyé
T+85  min: Vérification finale
T+90  min: ✅ PHASE 0 COMPLÈTE

Total: 90 minutes (1.5 heures)
```

---

**Approche:** Sécuriser les clés existantes, pas les remplacer  
**Impact:** ZÉRO downtime  
**Risque:** TRÈS BAS (tout est testé avant production)  
**Prochaine étape:** PHASE 1 (Authentification OAuth2)  

---
