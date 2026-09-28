from functools import lru_cache
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import Settings

bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if credentials is not None:
        tokens = {
            "USER001": settings.auth_user001_token,
            "USER002": settings.auth_user002_token,
        }

        supplied_token = credentials.credentials.encode("utf-8")

        for user_id, token in tokens.items():
            expected_token = token.get_secret_value().encode("utf-8")

            if compare_digest(supplied_token, expected_token):
                return user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
