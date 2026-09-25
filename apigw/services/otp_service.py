from sqlmodel import Session

import security
from database import OTP


def create_otp(
    session: Session,
    email: str,
) -> str:
    code = security.generate_otp()
    db_otp = OTP(email=email, hashed_code=security.hash_code(code))
    session.add(db_otp)
    session.commit()
    return code
