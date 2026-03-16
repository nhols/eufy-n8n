import os
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

UI_BASIC_AUTH_USER_ENV_VAR = "UI_BASIC_AUTH_USER"
UI_BASIC_AUTH_PASSWORD_ENV_VAR = "UI_BASIC_AUTH_PASSWORD"
VID_ANALYSER_API_KEY_ENV_VAR = "VID_ANALYSER_API_KEY"

_basic_security = HTTPBasic()


def require_ui_basic_auth(credentials: HTTPBasicCredentials = Depends(_basic_security)) -> None:
    expected_user = os.getenv(UI_BASIC_AUTH_USER_ENV_VAR)
    expected_password = os.getenv(UI_BASIC_AUTH_PASSWORD_ENV_VAR)
    if not expected_user or not expected_password:
        raise HTTPException(status_code=503, detail="UI auth is not configured")

    valid_user = secrets.compare_digest(credentials.username, expected_user)
    valid_password = secrets.compare_digest(credentials.password, expected_password)
    if valid_user and valid_password:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid UI credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_vid_analyser_api_key(
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected_api_key = os.getenv(VID_ANALYSER_API_KEY_ENV_VAR)
    if not expected_api_key:
        raise HTTPException(status_code=503, detail="API key is not configured")
    if api_key and secrets.compare_digest(api_key, expected_api_key):
        return
    raise HTTPException(status_code=401, detail="Invalid API key")
