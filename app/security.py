from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
import jwt
from app.config import settings

password_hasher = PasswordHash.recommended()

def verify_password(plain_password, hashed_password):
    return password_hasher.verify(plain_password, hashed_password)

def get_password_hash(password):
    return password_hasher.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def decode_access_token(token: str):
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
