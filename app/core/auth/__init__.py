from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import app_settings

security = HTTPBearer(auto_error=False)


def get_token_header(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    token = credentials.credentials if credentials else None
    if token != app_settings.AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return token
