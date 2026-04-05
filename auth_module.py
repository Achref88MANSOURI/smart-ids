"""
Authentication & Authorization Module
Implements JWT-based OAuth2 security for Smart-IDS
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from enum import Enum
import jwt
import secrets
import hashlib
from functools import lru_cache
from pydantic import BaseModel, Field, validator
from fastapi import Depends, HTTPException, status, Request
import os

# ── Configuration ────────────────────────────────────────

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "7"))

# In production, use persistent database (PostgreSQL, MongoDB, etc.)
# For now, using in-memory storage with backup to file
USERS_DB = {}
TOKENS_BLACKLIST = set()
REFRESH_TOKENS_DB = {}

# ── Models ───────────────────────────────────────────────

class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    SOC_ANALYST = "soc_analyst"
    VIEWER = "viewer"

class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(...)
    role: UserRole = UserRole.VIEWER

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()

class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8, max_length=100)

class User(UserBase):
    """User response model"""
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True

class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class TokenPayload(BaseModel):
    """JWT token payload"""
    user_id: str
    username: str
    email: str
    role: UserRole
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for revocation tracking

class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str

class LoginResponse(BaseModel):
    """Login response"""
    user: User
    tokens: TokenResponse

# ── Password Management ──────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password with salt using PBKDF2"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # iterations
    )
    return f"{salt}${pwd_hash.hex()}"

def verify_password(password: str, hash_: str) -> bool:
    """Verify password against hash"""
    try:
        salt, pwd_hash = hash_.split('$')
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return computed_hash.hex() == pwd_hash
    except Exception:
        return False

# ── JWT Token Management ─────────────────────────────────

def create_access_token(user_id: str, username: str, email: str, role: UserRole) -> str:
    """Create JWT access token"""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRY_HOURS)
    jti = secrets.token_urlsafe(16)
    
    payload = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "role": role,
        "exp": exp.timestamp(),
        "iat": now.timestamp(),
        "jti": jti
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def create_refresh_token(user_id: str) -> str:
    """Create JWT refresh token"""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
    jti = secrets.token_urlsafe(16)
    
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "exp": exp.timestamp(),
        "iat": now.timestamp(),
        "jti": jti
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    REFRESH_TOKENS_DB[jti] = {"user_id": user_id, "exp": exp}
    return token

def verify_token(token: str) -> TokenPayload:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Check if token is blacklisted
        if payload.get("jti") in TOKENS_BLACKLIST:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
        
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def revoke_token(token: str):
    """Revoke a token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        TOKENS_BLACKLIST.add(payload.get("jti"))
    except Exception:
        pass

# ── User Management ────────────────────────────────────

def create_user(username: str, email: str, password: str, role: UserRole = UserRole.VIEWER) -> User:
    """Create new user"""
    if username in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    user_id = secrets.token_urlsafe(16)
    user = {
        "id": user_id,
        "username": username,
        "email": email.lower(),
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
        "is_active": True
    }
    
    USERS_DB[username] = user
    return User(**user)

def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username"""
    return USERS_DB.get(username)

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user credentials"""
    user = get_user_by_username(username)
    
    if not user or not user.get("is_active"):
        return None
    
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Update last login
    user["last_login"] = datetime.now(timezone.utc)
    
    return user

def get_user_id_from_username(username: str) -> Optional[str]:
    """Get user ID from username"""
    user = get_user_by_username(username)
    return user["id"] if user else None

# ── Dependency Injection ─────────────────────────────────

async def get_current_user(request: Request) -> User:
    """
    Dependency to get current authenticated user from Authorization header.
    Use as: @app.get("/path")
            async def endpoint(current_user: User = Depends(get_current_user))
    
    Expects Bearer token in Authorization header:
    Authorization: Bearer <jwt_token>
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )
    
    # Parse "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'"
        )
    
    token = parts[1]
    
    # verify_token may raise HTTPException
    try:
        payload = verify_token(token)
    except HTTPException:
        raise
    
    user = get_user_by_username(payload.username)
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return User(**user)

def require_role(*allowed_roles):
    """
    Dependency to require specific user role(s).
    Use as: @app.get("/path", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            role_names = ', '.join(str(r.value if isinstance(r, UserRole) else r) for r in allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This operation requires one of these roles: {role_names}"
            )
        return current_user
    return role_checker

# ── Initialization ───────────────────────────────────────

def init_default_users():
    """Initialize default admin user"""
    # Create default admin user if not exists
    if "admin" not in USERS_DB:
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123456")
        create_user(
            username="admin",
            email="admin@smart-ids.local",
            password=admin_password,
            role=UserRole.ADMIN
        )
        print(f"✓ Default admin user created (password: {admin_password[:3]}***)")
    
    # Create default SOC analyst user if not exists
    if "analyst" not in USERS_DB:
        analyst_password = os.getenv("ANALYST_PASSWORD", "analyst123456")
        create_user(
            username="analyst",
            email="analyst@smart-ids.local",
            password=analyst_password,
            role=UserRole.SOC_ANALYST
        )
        print(f"✓ Default analyst user created")

    # Create default viewer user if not exists
    if "viewer" not in USERS_DB:
        viewer_password = os.getenv("VIEWER_PASSWORD", "viewer123456")
        create_user(
            username="viewer",
            email="viewer@smart-ids.local",
            password=viewer_password,
            role=UserRole.VIEWER
        )
        print(f"✓ Default viewer user created")
