from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
import jwt
from app.config import settings
import random
from .schemas import TokenPayload

password_hasher = PasswordHash.recommended()

def verify_password(plain_password, hashed_password) -> bool:
    """Check if the hashed_password is hashed from the plain_password."""
    return password_hasher.verify(plain_password, hashed_password)

def get_password_hash(password) -> str:
    return password_hasher.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Add the exp information to the data and return the encoded token of it."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> TokenPayload:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm]
    )
    return TokenPayload(**payload)

def generate_otp() -> str:
    """Return a 6-digits string number."""
    return f"{random.randint(100000, 999999)}"

def hash_otp(code: str) -> str:
    return password_hasher.hash(code)

def verify_otp(code: str, hashed_code: str) -> bool:
    """Check if the hashed_code is hashed from the code."""
    return password_hasher.verify(code, hashed_code)
