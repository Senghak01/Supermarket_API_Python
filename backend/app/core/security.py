import datetime
import hashlib
import secrets
from typing import Any, Dict, Optional
import bcrypt
import jwt
from fastapi.security import HTTPBearer
from app.core.config import settings
from app.core.errors import AppError

# A pre-hashed dummy string so timing attacks cannot determine if an email exists
# bcrypt hash of "dummy_password_for_timing_safety"
DUMMY_BCRYPT_HASH = b"$2b$12$e86gY7P7Z8j7QWq6L1M7..2Z8FqVqYx3aR9c4kKj5p3s8y2rKzFmG"

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt. Validates 72-byte max limit."""
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise AppError.bad_request("Password cannot exceed 72 bytes.")
    if len(pw_bytes) < 8:
        raise AppError.bad_request("Password must be at least 8 characters.")

    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def verify_dummy_password(plain_password: str) -> None:
    """Run a real bcrypt check against a dummy hash to keep execution timing constant."""
    try:
        bcrypt.checkpw(plain_password.encode("utf-8")[:72], DUMMY_BCRYPT_HASH)
    except Exception:
        pass


def hash_token(token: str) -> str:
    """Hash a refresh token using SHA-256 for safe DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_random_token() -> str:
    """Generate a cryptographically secure random token string."""
    return secrets.token_urlsafe(48)


# --- Customer Token Methods ---

def create_access_token(customer_id: int, email: str) -> str:
    """Create a signed JWT for Customer mobile app."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload: Dict[str, Any] = {
        "sub": str(customer_id),
        "email": email,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate Customer JWT claims (iss, aud, exp)."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["exp", "iss", "aud", "sub"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppError(status_code=401, message="Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise AppError(status_code=401, message="Invalid authentication token.")


# --- Employee / Admin Token Methods ---

def create_admin_access_token(employee_id: int, email: str, role: str) -> str:
    """Create a short-lived (15-min) signed JWT for Employee/Admin Web App."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(minutes=settings.JWT_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(employee_id),
        "email": email,
        "role": role,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_ADMIN_AUDIENCE,  # Customer tokens have aud=SupermarketApp and will be rejected
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_admin_token(token: str) -> Dict[str, Any]:
    """Decode and validate Admin/Employee JWT claims (iss, aud, exp, role)."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_ADMIN_AUDIENCE,
            options={"require": ["exp", "iss", "aud", "sub"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppError(status_code=401, message="Admin session has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise AppError(status_code=401, message="Invalid administrator credentials.")
