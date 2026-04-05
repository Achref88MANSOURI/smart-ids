# ✅ PHASE 0: CHECKLIST DE RÉVOCATION SÉCURISÉE

**Date de démarrage:** 29 Mars 2026  
**Deadline:** 30 Mars 2026 (24h)  
**Criticité:** 🔴 URGENT  

---

## 📊 OVERVIEW PHASE 0

```
Objectif:  Révoquer les 3 clés API compromises sans breaking changes
Timeline:  120 minutes
Risque:    MEDIUM (si bien suivi) → LOW
Services:  Enrichment (ML) + Backend API + Frontend (aucun arrêt requis)
```

---

## ✅ CHECKLIST - AVANT DE COMMENCER

**Prérequis à vérifier:**

- [ ] Vous avez accès à Google Cloud Console (VMs sont sur GCP)
- [ ] Vous avez les credentials VirusTotal, AbuseIPDB, Gemini
- [ ] Vous pouvez SSH dans la machine avec sudo access
- [ ] Vous avez 2-3 heures libres (pour exécuter sans interruptions)
- [ ] Vous avez lu le document `PHASE0_REMEDIATION_API_KEYS.md`

**Services à vérifier:**

```bash
# Vérifier que les services tournent
sudo systemctl status smart-ids-enrichment
curl http://localhost:8080/api/health
curl -s http://10.0.1.7:9200/_cluster/health

# Si tous les 3 OK: ✅ Prêt à démarrer
```

---

## 🚀 EXÉCUTION PHASE 0

### Option 1: SCRIPT AUTOMATISÉ (RECOMMANDÉ - 120min)

```bash
cd /home/achrefmansouri600/smart-ids

# Lance le script interactif qui guide à travers tous les steps
sudo ./phase0_remediation.sh
```

**Le script:**
- ✅ Fait les backups
- ✅ Teste les services avant/après
- ✅ Redémarre les services de manière sûre
- ✅ Vérifie les logs
- ✅ Guide la révocation manuelle des clés
- ✅ Nettoie Git history
- ✅ Produit un rapport complet

### Option 2: MANUEL ÉTAPE PAR ÉTAPE (RECOMMANDÉ pour apprentissage - 120min)

Suivez le document détaillé: `PHASE0_REMEDIATION_API_KEYS.md`

**Étapes:**
1. **Audit** (10 min) - Comprendre l'utilisation
2. **Backup** (5 min) - Sauvegarder .env avant changement
3. **Générer nouvelles clés** (30 min) - Créer sur les plateformes
4. **Mettre à jour .env** (5 min) - Remplacer les clés
5. **Redémarrer services** (10 min) - Enrichment + Backend
6. **Tester** (15 min) - Vérifier logs et fonctionnalité
7. **Révoquer anciennes clés** (20 min) - Supprimer sur les plateformes
8. **Nettoyer Git** (15 min) - Supprimer de l'historique
9. **Finaliser** (10 min) - Vérification et audit trail

---

## 📋 CHECKLIST DÉTAILLÉE

### 🔵 PRÉ-REMÉDIATION (T+0 à T+30min)

- [ ] Créer nouvelle clé **VirusTotal**
  - [ ] Aller à: https://www.virustotal.com/gui/settings/apikey
  - [ ] Générer nouvelle clé
  - [ ] Tester avec curl (voir docs)
  - [ ] Copier la clé en SAFE PLACE

- [ ] Créer nouvelle clé **AbuseIPDB**
  - [ ] Aller à: https://www.abuseipdb.com/account
  - [ ] Générer nouvelle clé
  - [ ] Tester avec curl (voir docs)
  - [ ] Copier la clé en SAFE PLACE

- [ ] Créer nouvelle clé **Gemini**
  - [ ] Aller à: https://aistudio.google.com/app/apikeys
  - [ ] Générer nouvelle clé
  - [ ] Tester avec curl (voir docs)
  - [ ] Copier la clé en SAFE PLACE

### 🟡 EXÉCUTION (T+30 à T+90min)

- [ ] Backup du .env actuel
  ```bash
  cp .env .env.backup
  ```

- [ ] Audit de l'utilisation des clés
  ```bash
  grep -r "VT_API\|ABUSE\|GEMINI" . --include="*.py" | grep -v __pycache__
  ```

- [ ] Mettre à jour .env avec NOUVELLES clés
  ```bash
  cat > .env << 'EOF'
  VT_API_KEY=<NOUVELLE_CLÉ_VT>
  ABUSEIPDB_KEY=<NOUVELLE_CLÉ_ABUSE>
  GEMINI_API_KEY=<NOUVELLE_CLÉ_GEMINI>
  EOF
  ```

- [ ] Redémarrer enrichment service
  ```bash
  sudo systemctl restart smart-ids-enrichment
  sleep 5
  sudo systemctl status smart-ids-enrichment
  ```

- [ ] Vérifier les logs (pas d'erreurs API key)
  ```bash
  sudo journalctl -u smart-ids-enrichment -n 20 --no-pager
  ```

- [ ] Redémarrer backend API
  ```bash
  # Si utilisant systemd
  sudo systemctl restart smart-ids-backend
  
  # Si utilisant uvicorn manuel
  pkill -f "uvicorn backend:app"
  cd dashboard
  nohup uvicorn backend:app --host 0.0.0.0 --port 8080 > ../backend.log 2>&1 &
  ```

- [ ] Tester les endpoints
  ```bash
  curl http://localhost:8080/api/health
  curl "http://localhost:8080/api/alerts?minutes=60&size=5"
  curl http://localhost:3000  # Frontend
  ```

- [ ] Vérifier pas d'erreurs "Invalid API key"
  ```bash
  sudo journalctl -u smart-ids-enrichment -p err --no-pager
  grep -i "invalid\|error\|fail" /tmp/backend.log 2>/dev/null | head -5
  ```

### 🔴 RÉVOCATION (T+90 à T+110min)

⚠️ **NE FAIRE QUE SI TOUS LES TESTS PRÉCÉDENTS PASSENT**

- [ ] Révoquer **VirusTotal** OLD KEY
  - [ ] URL: https://www.virustotal.com/gui/settings/apikey
  - [ ] Trouver et supprimer: `cc1b6e61eb90a2a02ea77f806e63cc57fd274c74e8fb3a444a455efe61cfc61c`
  - [ ] Confirmer sans la nouvelle clé seulement

- [ ] Révoquer **AbuseIPDB** OLD KEY
  - [ ] URL: https://www.abuseipdb.com/account
  - [ ] Trouver et révoquer: `3ba3642b819971f29b0a6ced3445fad74586d9ed8a9ac339bdfb064f7a8be503761c43a8605ebfb0`
  - [ ] Confirmer

- [ ] Révoquer **Gemini** OLD KEY
  - [ ] URL: https://aistudio.google.com/app/apikeys
  - [ ] Trouver et supprimer: `AIzaSyAIesdtFopSUEU6TSraYDCqc2ksiPHo2KE`
  - [ ] Confirmer

### 🟢 POST-REMÉDIATION (T+110 à T+120min)

- [ ] Nettoyer Git history
  ```bash
  sudo apt-get install git-filter-repo
  git filter-repo --replace-text <(echo 'OLD_KEY==>REDACTED')
  git push -f origin main
  ```

- [ ] Ajouter .env au gitignore
  ```bash
  echo ".env" >> .gitignore
  echo ".env.backup" >> .gitignore
  git add .gitignore
  git commit -m "security: Add .env to gitignore"
  git push
  ```

- [ ] Vérification finale
  ```bash
  # Services status
  sudo systemctl status smart-ids-enrichment
  curl http://localhost:8080/api/health
  
  # Log summary
  echo "=== DERNIÈRES HEURES ===" 
  sudo journalctl -u smart-ids-enrichment -n 100 --no-pager | grep -E "ERROR|SUCCESS|KEY" | tail -10
  
  # Git status
  git log --oneline | head -3
  cat .gitignore | grep -E ".env|backup"
  ```

---

## 🆘 EN CAS DE PROBLÈME

### Problème: Service ne restart pas après mise à jour .env

```bash
# 1. Check logs d'erreur
sudo journalctl -u smart-ids-enrichment -p err -n 50

# 2. Restaurer ancien .env
cp .env.backup .env

# 3. Restart service
sudo systemctl restart smart-ids-enrichment

# 4. Chercher la cause (clés mal copiées?)
grep "VT_API\|ABUSE\|GEMINI" .env
```

### Problème: Backend ne répond plus

```bash
# 1. Kill tous les processus Python associés
pkill -f uvicorn
pkill -f enrichment

# 2. Attendre 5 secondes
sleep 5

# 3. Redémarrer manuellement
cd /home/achrefmansouri600/smart-ids/dashboard
python3 -c "from backend import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8080)" &

# 4. Tester
curl http://localhost:8080/api/health
```

### Problème: Anciennes clés ne peuvent pas être révoquées

```bash
# Si les plateformes ne veulent pas révoquer:
# 1. Chercher toutes les clés associées
# 2. Contacter le support de la plateforme
# 3. Vérifier 2FA si requis
```

---

## 📈 RÉSULTATS ATTENDUS

Après PHASE 0:

```
✅ Service Enrichment: RUNNING
✅ Backend API: RESPONDING
✅ Frontend: ACCESSIBLE
✅ Logs: NO API KEY ERRORS
✅ Anciennes clés: RÉVOQUÉES
✅ Git history: CLEANED
✅ Nouvelles clés: ACTIVES
✅ Aucun downtime: ✓ (services tournent en continu)
```

**Temps total**: 120 minutes ≈ 2 heures  
**Expertise requise**: MEDIUM (follow docs, tests requis)  
**Risque de breakage**: LOW (si checklist suivi)  

---

## 📞 SUPPORT PHASE 0

Si problème:

1. **Vérifier** les logs: `sudo journalctl -u smart-ids-enrichment -n 50`
2. **Restaurer** l'ancien .env: `cp .env.backup .env`
3. **Redémarrer** les services: `sudo systemctl restart smart-ids-enrichment`
4. **Chercher** dans le document: `PHASE0_REMEDIATION_API_KEYS.md`

---

## ⏰ TIMELINE RECOMMENDATION

**Jour 1 (Aujourd'hui 29 Mars):**
- Matin: Générer nouvelles clés (30 min)
- Après-midi: Exécuter le script phase0_remediation.sh (90 min)
- Soir: Révocation manuelle des clés (20 min)
- Total: ~3h30

**Jour 2 (30 Mars):**
- Matin: Vérifications finales + audit Git (30 min)
- Après-midi: Commencer PHASE 1 (Auth/JWT)

---

**Créé:** 29 Mars 2026  
**Status:** 🔴 À COMMENCER IMMÉDIATEMENT  
**Auteur:** Security Team  

---
