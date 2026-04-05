"""
Model Integrity Verification Module - PHASE 2
HMAC-SHA256 signatures for ML model tampering detection
"""

import os
import json
import hashlib
import hmac
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
MODELS_DIR = PROJECT_ROOT / "models"
MANIFEST_FILE = MODELS_DIR / ".model_manifest.json"

# Models to protect (critical models only to start)
CRITICAL_MODELS = [
    "lstm_ae_attention.keras",
    "lstm_encoder.keras",
    "lstm_v3_real.keras",
    "autoencoder_ids.keras",
    "modele_ids.pkl",
    "isolation_forest.pkl",
    "xgb_v3_master.pkl",
]

# ────────────────────────────────────────────────────────
# HMAC SIGNATURE GENERATION
# ────────────────────────────────────────────────────────

def generate_model_signature(model_path: Path, secret_key: Optional[str] = None) -> str:
    """
    Generate HMAC-SHA256 signature for a model file
    
    Args:
        model_path: Path to model file (string or Path object)
        secret_key: Secret key for HMAC (uses system hostname if not provided)
    
    Returns:
        HMAC signature as hex string
    
    Raises:
        FileNotFoundError: If model file doesn't exist
        IOError: If unable to read model file
    """
    # Convert string to Path if needed
    if isinstance(model_path, str):
        model_path = Path(model_path)
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Use system identifier as secret (tied to this machine)
    if secret_key is None:
        try:
            import socket
            secret_key = socket.gethostname()
        except:
            secret_key = "smart-ids-default-key"
    
    # Generate signature by reading file in chunks (memory efficient)
    hmac_obj = hmac.new(secret_key.encode(), digestmod=hashlib.sha256)
    
    try:
        with open(model_path, 'rb') as f:
            # Read in 64KB chunks for memory efficiency
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                hmac_obj.update(chunk)
    except IOError as e:
        raise IOError(f"Failed to read model file {model_path}: {e}")
    
    return hmac_obj.hexdigest()


def create_model_manifest(models_dir: Path = MODELS_DIR, 
                         critical_only: bool = True) -> Dict[str, Dict]:
    """
    Create manifest file with signatures for all models
    
    Args:
        models_dir: Directory containing models
        critical_only: Only sign critical models (set False to sign all)
    
    Returns:
        Manifest dictionary
    """
    manifest = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "critical_only": critical_only,
        "models": {}
    }
    
    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory not found: {models_dir}")
    
    model_files = [
        f for f in models_dir.glob("*")
        if f.is_file() and f.suffix in ['.keras', '.pkl', '.h5', '.pt', '.pth']
    ]
    
    if critical_only:
        model_files = [f for f in model_files if f.name in CRITICAL_MODELS]
    
    for model_path in model_files:
        try:
            signature = generate_model_signature(model_path)
            file_size = model_path.stat().st_size
            mod_time = datetime.fromtimestamp(model_path.stat().st_mtime).isoformat() + "Z"
            
            manifest["models"][model_path.name] = {
                "signature": signature,
                "size": file_size,
                "modified": mod_time,
                "algorithm": "hmac-sha256",
                "status": "verified"
            }
            logger.info(f"✓ Signed model: {model_path.name} ({file_size} bytes)")
        
        except Exception as e:
            logger.error(f"✗ Failed to sign model {model_path.name}: {e}")
            manifest["models"][model_path.name] = {
                "signature": None,
                "error": str(e),
                "status": "error"
            }
    
    return manifest


def save_manifest(manifest: Dict, manifest_path: Path = MANIFEST_FILE) -> None:
    """
    Save manifest to JSON file (with restricted permissions)
    
    Args:
        manifest: Manifest dictionary
        manifest_path: Path to save manifest
    """
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Restrict permissions to owner only (600)
        os.chmod(manifest_path, 0o600)
        logger.info(f"✓ Manifest saved to {manifest_path} [permissions: 600]")
    
    except Exception as e:
        raise IOError(f"Failed to save manifest: {e}")


def load_manifest(manifest_path: Path = MANIFEST_FILE) -> Dict:
    """
    Load manifest from JSON file
    
    Args:
        manifest_path: Path to manifest file
    
    Returns:
        Manifest dictionary
    
    Raises:
        FileNotFoundError: If manifest doesn't exist
        json.JSONDecodeError: If manifest is corrupted
    """
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Model manifest not found: {manifest_path}\n"
            f"Run generate_model_manifest() to create it"
        )
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        return manifest
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Manifest corrupted or invalid JSON: {e}",
            e.doc,
            e.pos
        )


# ────────────────────────────────────────────────────────
# MODEL VERIFICATION
# ────────────────────────────────────────────────────────

class ModelTamperingError(Exception):
    """Raised when model tampering is detected"""
    pass


def verify_model(model_name: str, manifest: Dict, 
                models_dir: Path = MODELS_DIR) -> Tuple[bool, str]:
    """
    Verify a single model against manifest
    
    Args:
        model_name: Name of model file
        manifest: Manifest dictionary
        models_dir: Directory containing models
    
    Returns:
        Tuple of (is_valid, message)
    
    Raises:
        ModelTamperingError: If tampering detected
    """
    model_path = models_dir / model_name
    
    # Check if model exists
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Check if model in manifest
    if model_name not in manifest["models"]:
        raise ValueError(f"Model not in manifest: {model_name}")
    
    manifest_entry = manifest["models"][model_name]
    
    # Check for errors in manifest
    if manifest_entry.get("status") == "error":
        raise ValueError(f"Model has error in manifest: {manifest_entry.get('error')}")
    
    # Verify signature
    try:
        current_signature = generate_model_signature(model_path)
        original_signature = manifest_entry["signature"]
        
        if current_signature == original_signature:
            current_size = model_path.stat().st_size
            original_size = manifest_entry["size"]
            
            if current_size != original_size:
                raise ModelTamperingError(
                    f"❌ MODEL TAMPERING DETECTED: {model_name}\n"
                    f"   File size changed: {original_size} → {current_size} bytes\n"
                    f"   The model may have been modified or corrupted!"
                )
            
            return True, f"✓ Model verified: {model_name}"
        
        else:
            raise ModelTamperingError(
                f"❌ MODEL TAMPERING DETECTED: {model_name}\n"
                f"   Signature mismatch!\n"
                f"   Expected: {original_signature[:16]}...\n"
                f"   Got:      {current_signature[:16]}...\n"
                f"   The model has been modified or corrupted!"
            )
    
    except ModelTamperingError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error verifying model {model_name}: {e}")


def verify_all_models(manifest: Dict = None, 
                     models_dir: Path = MODELS_DIR,
                     manifest_path: Path = MANIFEST_FILE) -> Dict[str, bool]:
    """
    Verify all models in manifest
    
    Args:
        manifest: Manifest dictionary (loads from file if None)
        models_dir: Directory containing models
        manifest_path: Path to manifest file
    
    Returns:
        Dictionary of model_name -> is_valid
    
    Raises:
        ModelTamperingError: If any model tampering detected
    """
    if manifest is None:
        manifest = load_manifest(manifest_path)
    
    results = {}
    tampering_detected = []
    
    logger.info(f"🔍 Verifying {len(manifest['models'])} models...")
    
    for model_name in manifest["models"]:
        try:
            is_valid, message = verify_model(model_name, manifest, models_dir)
            results[model_name] = is_valid
            logger.info(message)
        
        except ModelTamperingError as e:
            results[model_name] = False
            tampering_detected.append(str(e))
            logger.error(str(e))
        
        except Exception as e:
            results[model_name] = False
            logger.warning(f"⚠ Warning verifying {model_name}: {e}")
    
    # Raise if tampering detected
    if tampering_detected:
        error_msg = "\n\n".join(tampering_detected)
        raise ModelTamperingError(
            f"\n🚨 SECURITY ALERT: Model tampering detected!\n\n{error_msg}"
        )
    
    return results


# ────────────────────────────────────────────────────────
# BOOTSTRAP FUNCTIONS
# ────────────────────────────────────────────────────────

def initialize_model_security(models_dir: Path = MODELS_DIR,
                            manifest_path: Path = MANIFEST_FILE,
                            critical_only: bool = True) -> bool:
    """
    Initialize model security on first run
    Creates manifest if it doesn't exist
    
    Args:
        models_dir: Directory containing models
        manifest_path: Path to manifest file
        critical_only: Only protect critical models
    
    Returns:
        True if successful
    """
    # Skip if manifest already exists
    if manifest_path.exists():
        logger.info("✓ Model manifest already exists")
        return True
    
    logger.info("📝 Initializing model security...")
    
    try:
        # Generate manifest
        manifest = create_model_manifest(models_dir, critical_only)
        
        # Save manifest
        save_manifest(manifest, manifest_path)
        
        logger.info(f"✓ Model security initialized with {len(manifest['models'])} models")
        return True
    
    except Exception as e:
        logger.error(f"✗ Failed to initialize model security: {e}")
        return False


def verify_models_on_startup(models_dir: Path = MODELS_DIR,
                            manifest_path: Path = MANIFEST_FILE) -> bool:
    """
    Verify all models on application startup
    
    Args:
        models_dir: Directory containing models
        manifest_path: Path to manifest file
    
    Returns:
        True if all models verified successfully
    
    Raises:
        ModelTamperingError: If tampering detected
    """
    logger.info("🔐 PHASE 2: Model Integrity Verification")
    logger.info("=" * 50)
    
    try:
        # Load manifest
        manifest = load_manifest(manifest_path)
        logger.info(f"Manifest created: {manifest['created_at']}")
        logger.info("")
        
        # Verify all models
        results = verify_all_models(manifest, models_dir, manifest_path)
        
        valid_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        logger.info("")
        logger.info("=" * 50)
        logger.info(f"✓ Model verification complete: {valid_count}/{total_count} OK")
        
        return True
    
    except ModelTamperingError as e:
        logger.critical(str(e))
        raise
    except Exception as e:
        logger.error(f"✗ Model verification failed: {e}")
        raise


# ────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ────────────────────────────────────────────────────────

def get_model_status(manifest_path: Path = MANIFEST_FILE) -> Dict[str, Dict]:
    """
    Get status of all models in manifest
    
    Args:
        manifest_path: Path to manifest file
    
    Returns:
        Dictionary of model status info
    """
    try:
        manifest = load_manifest(manifest_path)
        
        status = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "manifest_created": manifest["created_at"],
            "models": {},
            "summary": {
                "total": len(manifest["models"]),
                "verified": 0,
                "unverified": 0,
                "errors": 0
            }
        }
        
        for model_name, model_info in manifest["models"].items():
            model_status = model_info.get("status", "unknown")
            status["models"][model_name] = {
                "status": model_status,
                "size": model_info.get("size", "unknown"),
                "modified": model_info.get("modified", "unknown"),
                "signature": model_info.get("signature", "")[:16] + "..." if model_info.get("signature") else "None"
            }
            
            if model_status == "verified":
                status["summary"]["verified"] += 1
            elif model_status == "error":
                status["summary"]["errors"] += 1
            else:
                status["summary"]["unverified"] += 1
        
        return status
    
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
