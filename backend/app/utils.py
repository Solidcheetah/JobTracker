from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.config import security_settings
import jwt


def generate_access_token(
    data: dict,
    expiry: timedelta | None = None,
) -> str:
    if expiry is None:
        expiry = timedelta(minutes=security_settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    return jwt.encode(
        payload={
            **data,
            "jti": str(uuid4()),
            "exp": datetime.now(timezone.utc) + expiry,
        },
        algorithm=security_settings.JWT_ALGORITHM,
        key=security_settings.JWT_SECRET,
    )


def decode_access_token(token: str) -> dict | None:

    try:
        return jwt.decode(
            jwt=token,
            key=security_settings.JWT_SECRET,
            algorithms=[security_settings.JWT_ALGORITHM],
        )

    except jwt.PyJWTError:
        return None
