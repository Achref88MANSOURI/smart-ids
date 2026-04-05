#!/bin/bash
NEW_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")
OLD_IP=$(grep -oP '(?<=API = "http://)\d+\.\d+\.\d+\.\d+' /home/achrefmansouri600/smart-ids/dashboard/frontend/src/App.js)

if [ "$NEW_IP" != "$OLD_IP" ]; then
    echo "IP changée : $OLD_IP → $NEW_IP"
    sed -i "s|$OLD_IP|$NEW_IP|g" \
      /home/achrefmansouri600/smart-ids/dashboard/frontend/src/App.js \
      /home/achrefmansouri600/smart-ids/dashboard/frontend/src/Login.js \
      /home/achrefmansouri600/smart-ids/dashboard/backend.py
    cd /home/achrefmansouri600/smart-ids/dashboard/frontend
    npm run build 2>/dev/null
    echo "✅ IP mise à jour et React rebuild"
else
    echo "✅ IP inchangée : $NEW_IP"
fi
