#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/achrefmansouri600/smart-ids')
from model_security import create_model_manifest, save_manifest, MODELS_DIR, MANIFEST_FILE
manifest = create_model_manifest(MODELS_DIR)
save_manifest(manifest, MANIFEST_FILE)
print("✅ Manifest régénéré")
