from enum import Enum

from fastapi import HTTPException


# app business meaning
# things only BE knows
class ErrorCode(str, Enum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    AUTH_FAILED = "AUTH_FAILED"
    INCORRECT_PASSWORD = "INCORRECT_PASSWORD"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    ACCOUNT_HAS_NO_EMAIL = "ACCOUNT_HAS_NO_EMAIL"
    OTP_NOT_FOUND = "OTP_NOT_FOUND"
    OTP_EXPIRED = "OTP_EXPIRED"
    INVALID_OTP = "INVALID_OTP"

    RESERVED_COLLECTION_NAME = "RESERVED_COLLECTION_NAME"
    COLLECTION_ALREADY_EXISTS = "COLLECTION_ALREADY_EXISTS"

    BRICK_ALREADY_EXISTS = "BRICK_ALREADY_EXISTS"
    BRICK_EDIT_FORBIDDEN = "BRICK_EDIT_FORBIDDEN"
    BRICK_OVERRIDE_ALREADY_EXISTS = "BRICK_OVERRIDE_ALREADY_EXISTS"

    INVALID_EXPLANATION_RESPONSE = "INVALID_EXPLANATION_RESPONSE"


class RequestException(HTTPException):
    def __init__(
        self,
        status_code: int,
        debug_message: str,
        error_code: ErrorCode | None = None,  # code for learner-facing message
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "debug_message": debug_message,
                "error_code": error_code.value if error_code else None,
            },
            headers=headers,
        )
