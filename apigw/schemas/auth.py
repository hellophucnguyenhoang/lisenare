from schemas.base import Schema


class Token(Schema):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(Schema):
    sub: str  # learner_id, store as string for required
    username: str
    exp: int


class PasswordRecoveryResponse(Schema):
    message: str
    # Masked email for security
    # Only use email preview in a verified session flow
    # That means user is already authenticated
    email_preview: str | None = None
