from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json


def _base64url_encode(value: bytes) -> str:
    """Encode bytes using URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    """Decode a URL-safe base64 string, restoring stripped padding first."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_invite_token(secret: str, room_id: str, version: int) -> str:
    """Create a signed 24-hour invite token bound to a room and version."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "room_id": room_id,
        "version": version,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
    }

    encoded_header = _base64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    encoded_signature = _base64url_encode(signature)
    return f"{signing_input}.{encoded_signature}"


def decode_invite_token(secret: str, token: str) -> dict:
    """Verify token signature and expiry, then return the decoded payload."""
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise ValueError("invalid") from exc

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = _base64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise ValueError("invalid")

    try:
        header = json.loads(_base64url_decode(encoded_header).decode("utf-8"))
        payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid") from exc

    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise ValueError("invalid")

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("invalid")
    if exp < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("expired")

    if not isinstance(payload.get("room_id"), str):
        raise ValueError("invalid")
    if not isinstance(payload.get("version"), int):
        raise ValueError("invalid")

    return payload
