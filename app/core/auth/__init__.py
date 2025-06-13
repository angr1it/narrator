from fastapi import Header, HTTPException, status

from config import app_settings


def get_token_header(authorization: str | None = Header(default=None)) -> str:
    """Проверяет Bearer‑токен из заголовка Authorization."""
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    token = authorization.replace("Bearer ", "")
    if token != app_settings.AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return token
