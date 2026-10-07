"""Stateless, encrypted cookies for hosted sessions; secrets never reach JS."""
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

AUTH_TTL = 8 * 60 * 60
WORKSPACE_TTL = 180 * 24 * 60 * 60


def cipher():
    key = os.getenv("POCKET_FDE_SESSION_KEY")
    if os.getenv("VERCEL") and not key:
        raise RuntimeError("Hosted sessions require POCKET_FDE_SESSION_KEY")
    if not key:
        folder = Path(os.getenv("POCKET_FDE_DATA_DIR", str(Path.home() / ".local/share/pocket-fde")))
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / "session.key"
        try:
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                stream.write(Fernet.generate_key())
        except FileExistsError:
            pass
        key = path.read_bytes()
    return Fernet(key.encode() if isinstance(key, str) else key)


def seal(purpose, value):
    return cipher().encrypt(json.dumps({"purpose": purpose, "value": value}).encode()).decode()


def unseal(token, purpose, ttl):
    try:
        data = json.loads(cipher().decrypt((token or "").encode(), ttl=ttl))
        return data["value"] if data["purpose"] == purpose else None
    except (InvalidToken, ValueError, KeyError, TypeError):
        return None


def set_cookie(response, request, name, token, ttl):
    response.set_cookie(name, token, httponly=True, samesite="strict",
                        secure=bool(os.getenv("VERCEL")) or request.url.scheme == "https", max_age=ttl)


def authorized(request):
    code = os.getenv("POCKET_FDE_ACCESS_CODE")
    if os.getenv("VERCEL") and not code:
        return False  # Fail closed when hosting configuration is incomplete.
    return not code or unseal(request.cookies.get("pocketfde_access"), "access", AUTH_TTL) == code


def require_access(request):
    if not authorized(request):
        raise HTTPException(401, "Enter the demo access code to analyze and save work.")


def workspace_id(request, response=None):
    if getattr(request.state, "workspace_identity", None):
        return request.state.workspace_identity
    identity = unseal(request.cookies.get("pocketfde_workspace"), "workspace", WORKSPACE_TTL)
    if not isinstance(identity, str) or len(identity) != 32:
        identity = secrets.token_hex(16)
        if response is not None:
            set_cookie(response, request, "pocketfde_workspace", seal("workspace", identity), WORKSPACE_TTL)
    request.state.workspace_identity = identity
    return identity
