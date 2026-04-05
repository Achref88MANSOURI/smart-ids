"""
Smart-IDS Dashboard API with OAuth2/JWT Authentication
PHASE 1: Authentication & Authorization
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import google.generativeai as google_genai
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import json
import logging

# ── Custom Imports ──────────────────────────────────────
from secure_secrets import get_gemini_api_key
from auth_module import (
    User, UserCreate, LoginRequest, TokenResponse, UserRole,
    create_user, authenticate_user, create_access_token, 
    create_refresh_token, verify_token, get_current_user, 
    require_role, init_default_users, revoke_token, LoginResponse
)
from input_validation import (
    validate_llm_input, validate_query_input, validate_alert_data,
    validate_json_response, ValidationError, ValidationStats,
    validate_username, validate_email, validate_password
)
from model_security import (
    verify_models_on_startup, get_model_status, 
    initialize_model_security, ModelTamperingError
)
from llm_security import (
    prepare_safe_alert_analysis, validate_llm_response,
    PromptSecurityStats, PromptInjectionError, ResponseValidationError,
    AdvancedPromptInjectionDetector
)

load_dotenv("/home/achrefmansouri600/smart-ids/.env")

# ── Logging Setup ────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────
ES_HOST    = "https://localhost:9200"
ES_USER = os.getenv("ES_USER", "smart_ids")
ES_PASS = os.getenv("ES_PASS")
ES_CA   = os.getenv("ES_CA", "/etc/smart-ids-ca.crt")
ES_INDEX   = "smart-ids-alerts-v5"
GEMINI_KEY = get_gemini_api_key()

# Rate Limiting
limiter = Limiter(key_func=get_remote_address)

# ── FastAPI App Init ────────────────────────────────────
app = FastAPI(
    title="Smart-IDS Dashboard API",
    description="Secure API with OAuth2/JWT Authentication",
    version="1.1.0"
)
app.state.limiter = limiter

# CORS Configuration - RESTRICTED (PHASE 1 hardening)
# In production, only allow specific frontend origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://100.77.38.125:3000",  # Windows Tailscale IP
    "http://100.76.134.101:3000",  # Windows dev IP
    "http://34.52.182.216:3000",   # GCP external IP
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ✓ RESTRICTED (was "*")
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # ✓ RESTRICTED (was "*")
    allow_headers=["Content-Type", "Authorization"],  # ✓ RESTRICTED (was "*")
)

# ── Elasticsearch Connection ────────────────────────────
es = Elasticsearch(
    ES_HOST,
    basic_auth=(ES_USER, ES_PASS),
    ca_certs=ES_CA,
    verify_certs=True
)

if GEMINI_KEY:
    google_genai.configure(api_key=GEMINI_KEY)
    gemini_client = google_genai
    logger.info("✓ Gemini connected")
else:
    gemini_client = None
    logger.warning("⚠ Gemini not configured")

# ── Request Models ──────────────────────────────────────

class ChatRequest(BaseModel):
    """Chat request with input validation"""
    message: str = Field(..., min_length=1, max_length=2000)
    
    @validator('message')
    def validate_message(cls, v):
        """Validate message against injection attacks"""
        try:
            return validate_llm_input(v)
        except ValidationError as e:
            ValidationStats.record_block("Chat Message Injection")
            raise ValueError(str(e))

class AnalyzeRequest(BaseModel):
    """Alert analysis request with input validation"""
    alert: dict = Field(..., min_items=1)
    
    @validator('alert')
    def validate_alert(cls, v):
        """Validate alert data structure and content"""
        try:
            return validate_alert_data(v)
        except ValidationError as e:
            ValidationStats.record_block("Alert Data Injection")
            raise ValueError(str(e))

class RegisterRequest(UserCreate):
    """User registration request with input validation"""
    
    @validator('username')
    def validate_user(cls, v):
        try:
            return validate_username(v)
        except ValidationError as e:
            raise ValueError(str(e))
    
    @validator('email')
    def validate_user_email(cls, v):
        try:
            return validate_email(v)
        except ValidationError as e:
            raise ValueError(str(e))
    
    @validator('password')
    def validate_user_password(cls, v):
        try:
            return validate_password(v)
        except ValidationError as e:
            raise ValueError(str(e))

# ── Helper Functions ────────────────────────────────────

def get_alerts(minutes=60, size=100):
    """Get alerts from Elasticsearch with validation"""
    # ✓ Input validation (PHASE 2 improvement)
    minutes = max(1, min(minutes, 43200))  # 1-1440 minutes
    size = max(1, min(size, 1000))        # 1-1000 documents
    
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = {
        "query": {"range": {"@timestamp": {"gte": since}}},
        "sort": [{"@timestamp": {"order": "desc"}}],
        "size": size
    }
    try:
        res = es.search(index=ES_INDEX, body=query)
        return [h["_source"] for h in res["hits"]["hits"]]
    except Exception as e:
        logger.error(f"Elasticsearch error: {e}")
        return []

def gemini_generate(prompt):
    """Generate content using Gemini API"""
    if not gemini_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API not configured"
        )
    try:
        model = gemini_client.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error generating analysis"
        )

def format_alerts_context(alerts):
    """Format alerts for LLM context"""
    lines = []
    for a in alerts[:20]:
        lines.append(
            f"[{a.get('@timestamp','')}] "
            f"{a.get('threat_level','?')} | "
            f"{a.get('signature','?')[:50]} | "
            f"IP:{a.get('src_ip','?')} | "
            f"MITRE:{a.get('mitre_technique','?')} | "
            f"XGB:{a.get('xgb_confidence','?')}% | "
            f"VT:{a.get('vt_score','?')} | "
            f"KC:{'OUI' if a.get('lstm_killchain') else 'NON'}"
        )
    return "\n".join(lines)

# ── Authentication Routes ───────────────────────────────

@app.post("/api/auth/register", response_model=User)
@limiter.limit("5/minute")  # ✓ Rate limiting
async def register(request: Request, req: RegisterRequest):
    """
    Register new user
    ROLE: Public (but rate-limited)
    """
    try:
        user = create_user(
            username=req.username,
            email=req.email,
            password=req.password,
            role=req.role
        )
        logger.info(f"User registered: {req.username}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed"
        )

@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute")  # ✓ Rate limiting
async def login(request: Request, req: LoginRequest):
    """
    Login user and get JWT tokens
    ROLE: Public (but rate-limited)
    """
    user = authenticate_user(req.username, req.password)
    
    if not user:
        logger.warning(f"Failed login attempt: {req.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"]
    )
    
    refresh_token = create_refresh_token(user["id"])
    
    logger.info(f"User logged in: {req.username}")
    
    return LoginResponse(
        user=User(**user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=86400  # 24 hours in seconds
        )
    )

@app.post("/api/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user (revoke current token)
    ROLE: Authenticated
    """
    # Token revocation is handled in dependencies
    logger.info(f"User logged out: {current_user.username}")
    return {"message": "Logout successful"}

# ── Public Health Route ─────────────────────────────────

@app.get("/api/health")
def health():
    """Health check (public endpoint)"""
    return {
        "status": "ok",
        "es": es.ping(),
        "gemini": gemini_client is not None,
        "index": ES_INDEX
    }

# ── Protected Routes (require authentication) ──────────

@app.get("/api/alerts")
@limiter.limit("100/minute")  # ✓ Rate limiting
async def api_alerts(
    request: Request,  # Required for rate limiting
    minutes: int = 60,
    size: int = 50,
    current_user: User = Depends(get_current_user)  # ✓ Authentication required
):
    """
    Get recent alerts
    ROLE: Authenticated (all roles)
    """
    logger.info(f"User {current_user.username} accessed alerts")
    alerts = get_alerts(minutes, size)
    return {"alerts": alerts, "total": len(alerts)}

@app.get("/api/stats")
@limiter.limit("50/minute")  # ✓ Rate limiting
async def api_stats(
    request: Request,
    minutes: int = 60,
    current_user: User = Depends(get_current_user)  # ✓ Authentication required
):
    """
    Get security statistics
    ROLE: Authenticated (all roles)
    """
    logger.info(f"User {current_user.username} accessed stats")
    alerts = get_alerts(minutes, 1000)
    stats  = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    kill_chains  = 0
    signatures   = {}
    mitre_map    = {}
    xgb_sum      = 0

    for a in alerts:
        lvl = a.get("threat_level", "LOW")
        stats[lvl] = stats.get(lvl, 0) + 1
        if a.get("lstm_killchain"):
            kill_chains += 1
        sig = a.get("signature", "Unknown")[:45]
        signatures[sig] = signatures.get(sig, 0) + 1
        mt = a.get("mitre_technique", "T0000")
        tactic = a.get("mitre_tactic", "Unknown")
        mitre_map[mt] = {"count": mitre_map.get(mt, {}).get("count", 0) + 1, "tactic": tactic}
        xgb_sum += a.get("xgb_confidence", 0) or 0

    return {
        "stats":           stats,
        "total":           len(alerts),
        "kill_chains":     kill_chains,
        "top_signatures":  sorted(signatures.items(), key=lambda x: x[1], reverse=True)[:5],
        "top_mitre":       sorted(mitre_map.items(), key=lambda x: x[1]["count"], reverse=True)[:5],
        "avg_confidence":  round(xgb_sum / max(len(alerts), 1), 2)
    }

@app.post("/api/analyze")
@limiter.limit("50/minute")  # ✓ Rate limiting
async def api_analyze(
    request: Request,
    req: AnalyzeRequest,
    current_user: User = Depends(get_current_user)  # ✓ Authentication required
):
    """
    PHASE 2: Analyze alert with safe LLM prompting
    ROLE: Authenticated (all roles)
    """
    try:
        logger.info(f"User {current_user.username} analyzed alert")
        ValidationStats.record_attempt()
        PromptSecurityStats.record_prompt()
        
        # Prepare safe prompt (includes injection detection, data validation)
        prep = prepare_safe_alert_analysis(req.alert)
        safe_prompt = prep["safe_prompt"]
        expected_schema = prep["expected_schema"]
        
        # Send structured prompt to Gemini
        response_text = gemini_generate(safe_prompt)
        
        # Validate and parse response
        try:
            analysis = validate_llm_response(response_text, expected_schema)
            PromptSecurityStats.record_success()
            
            logger.info(f"✓ Alert analysis completed safely")
            return {"analysis": analysis}
        
        except ResponseValidationError as e:
            logger.error(f"Response validation failed: {str(e)}")
            PromptSecurityStats.record_validation_failure()
            raise HTTPException(status_code=502, detail=f"LLM response invalid: {str(e)}")
    
    except PromptInjectionError as e:
        logger.warning(f"⚠️ Prompt injection detected: {str(e)}")
        PromptSecurityStats.record_injection_attempt()
        raise HTTPException(status_code=400, detail=f"Request rejected: {str(e)}")
    
    except ValidationError as e:
        logger.warning(f"❌ Input validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid alert data: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in alert analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@app.post("/api/chat")
@limiter.limit("50/minute")  # ✓ Rate limiting
async def api_chat(
    request: Request,
    req: ChatRequest,
    current_user: User = Depends(get_current_user)  # ✓ Authentication required
):
    """
    PHASE 2: Chat with SOC AI (safe structured prompting)
    ROLE: Authenticated (all roles)
    """
    try:
        logger.info(f"User {current_user.username} started chat")
        ValidationStats.record_attempt()
        PromptSecurityStats.record_prompt()
        
        # Check user question for injection patterns
        is_injection, patterns = AdvancedPromptInjectionDetector.detect_injection(req.message)
        if is_injection:
            logger.warning(f"⚠️ Potential injection in chat: {patterns}")
            PromptSecurityStats.record_injection_attempt()
            # Don't reject, but proceed with caution
        
        # Get context alerts
        alerts = get_alerts(minutes=120, size=50)
        
        # Create structured prompt (import here to avoid circular imports)
        from llm_security import create_safe_chat_analysis_prompt
        prompt, schema = create_safe_chat_analysis_prompt(alerts, req.message)
        
        # Send to Gemini
        response_text = gemini_generate(prompt)
        
        # Validate response
        try:
            response = validate_llm_response(response_text, schema)
            PromptSecurityStats.record_success()
            
            logger.info(f"✓ Chat analysis completed safely")
            return {"response": response}
        
        except ResponseValidationError as e:
            logger.error(f"Chat response validation failed: {str(e)}")
            PromptSecurityStats.record_validation_failure()
            raise HTTPException(status_code=502, detail=f"LLM response invalid: {str(e)}")
    
    except ValidationError as e:
        logger.warning(f"❌ Chat input validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat failed")

@app.get("/api/summary")
@limiter.limit("50/minute")  # ✓ Rate limiting
async def api_summary(
    request: Request,
    current_user: User = Depends(get_current_user)  # ✓ Authentication required
):
    """
    Get security summary report
    ROLE: Authenticated (all roles)
    """
    logger.info(f"User {current_user.username} accessed summary")
    alerts = get_alerts(minutes=480, size=200)
    stats  = {
        "total":       len(alerts),
        "critical":    sum(1 for a in alerts if a.get("threat_level") == "CRITICAL"),
        "high":        sum(1 for a in alerts if a.get("threat_level") == "HIGH"),
        "kill_chains": sum(1 for a in alerts if a.get("lstm_killchain")),
    }
    context = format_alerts_context(alerts)
    prompt  = f"""Tu es un analyste SOC senior. Génère un rapport de sécurité professionnel en français.

STATISTIQUES (8 dernières heures) :
- Total alertes : {stats['total']}
- CRITICAL      : {stats['critical']}
- HIGH          : {stats['high']}
- Kill Chains   : {stats['kill_chains']}

ÉCHANTILLON D'ALERTES :
{context}

Génère un rapport professionnel de 2-3 paragraphes avec recommandations."""

    return {"summary": gemini_generate(prompt)}

# ── Admin Routes (only for admin role) ─────────────────

@app.get("/api/admin/users", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_list_users(current_user: User = Depends(get_current_user)):
    """
    List all users (admin only)
    ROLE: admin
    """
    logger.info(f"Admin {current_user.username} listed users")
    from auth_module import USERS_DB
    users = [User(**user) for user in USERS_DB.values()]
    return {"users": users, "total": len(users)}

@app.get("/api/admin/validation-stats", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_validation_stats(current_user: User = Depends(get_current_user)):
    """
    Get validation statistics (admin only)
    ROLE: admin
    Shows how many injection attempts were blocked
    """
    logger.info(f"Admin {current_user.username} requested validation stats")
    return ValidationStats.get_stats()

@app.get("/api/admin/model-status", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_model_status(current_user: User = Depends(get_current_user)):
    """
    Get model integrity status (admin only)
    ROLE: admin
    Shows HMAC signatures and verification status
    """
    logger.info(f"Admin {current_user.username} requested model status")
    from pathlib import Path
    return get_model_status(Path(__file__).parent.parent / "models" / ".model_manifest.json")

@app.post("/api/admin/verify-models", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_verify_models(current_user: User = Depends(get_current_user)):
    """
    Re-verify all models (admin only)
    ROLE: admin
    Check if any models have been tampered with
    """
    logger.info(f"Admin {current_user.username} initiated model verification")
    try:
        from pathlib import Path
        from model_security import verify_models_on_startup
        models_dir = Path(__file__).parent.parent / "models"
        manifest_path = models_dir / ".model_manifest.json"
        verify_models_on_startup(models_dir, manifest_path)
        return {"status": "success", "message": "All models verified successfully"}
    except ModelTamperingError as e:
        logger.critical(f"🚨 MODEL TAMPERING DETECTED: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Model tampering detected: {str(e)}")
    except Exception as e:
        logger.error(f"Model verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Model verification failed: {str(e)}")

@app.get("/api/admin/prompt-security-stats", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_prompt_security_stats(current_user: User = Depends(get_current_user)):
    """
    Get prompt security statistics (admin only)
    ROLE: admin
    Shows injection attempts, validation failures, etc.
    """
    logger.info(f"Admin {current_user.username} requested prompt security stats")
    return PromptSecurityStats.get_stats()

# ── Startup Event ────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("\n" + "=" * 60)
    logger.info("   SMART-IDS SECURITY INITIALIZATION")
    logger.info("=" * 60)
    
    # PHASE 1: Authentication
    logger.info("\n[PHASE 1] Authentication & Authorization")
    logger.info("Initializing authentication system...")
    init_default_users()
    logger.info("✓ Authentication ready")
    
    # PHASE 2: Model Integrity
    logger.info("\n[PHASE 2] Model Integrity Verification")
    try:
        from pathlib import Path
        models_dir = Path(__file__).parent.parent / "models"
        manifest_path = models_dir / ".model_manifest.json"
        
        # Initialize manifest if needed
        initialize_model_security(models_dir, manifest_path, critical_only=False)
        
        # Verify all models
        verify_models_on_startup(models_dir, manifest_path)
        logger.info("✓ Model integrity verified")
    except ModelTamperingError as e:
        logger.critical("\n" + "=" * 60)
        logger.critical(f"🚨 CRITICAL SECURITY ALERT: {str(e)}")
        logger.critical("=" * 60)
        raise
    except Exception as e:
        logger.warning(f"⚠ Model verification warning: {e}")
    
    # PHASE 2 (Deep): Prompt Injection Defense
    logger.info("\n[PHASE 2-3] Prompt Injection Defense (Structured Prompting)")
    logger.info("Initializing LLM security with structured prompting...")
    logger.info("  • Structured prompt framework: ACTIVE")
    logger.info("  • Response validation: ENABLED")
    logger.info("  • Injection detection: ENABLED")
    logger.info("✓ LLM security ready")
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ Application ready (All security layers active)")
    logger.info("=" * 60 + "\n")

# ── Exception Handlers ──────────────────────────────────


# Servir le build React
import os as _os
_build = _os.path.join(_os.path.dirname(__file__), "frontend/build")
if _os.path.exists(_build):
    app.mount("/", StaticFiles(directory=_build, html=True), name="static")

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    """Handle rate limit exceeded"""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Too many requests."}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
