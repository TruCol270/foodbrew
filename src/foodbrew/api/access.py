"""The access gate for the hosted single instance (M6 decisions #1, #2, #3).

This is HTTP Basic auth and nothing more. It is not an identity system: there
is one password for one person, so there is no user table, no session, and no
username check. It exists because the hosted instance has no custom domain and
therefore nothing in front of it to hold a policy — see the plan's decision #1
for why that reverses the usual arrangement.
"""

from __future__ import annotations

import base64
import binascii
import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

#: Reachable without credentials. The platform health check arrives with no
#: password and must still get an answer, and a crawler has to be able to read
#: the refusal in robots.txt. Neither returns founder data.
OPEN_PATHS = frozenset({"/api/v1/health", "/robots.txt"})

#: Without this header a browser shows a bare error page instead of a login box,
#: which on a phone is indistinguishable from the app being broken.
CHALLENGE = {"WWW-Authenticate": 'Basic realm="FoodBrew", charset="UTF-8"'}

REFUSAL = "This instance is private. Ask for the password."


def supplied_password(header: str | None) -> str | None:
    """The password from an Authorization header, or None if there isn't one.

    Every malformed shape returns None rather than raising: this runs on the
    open internet, and a decoding error must be a 401, never a 500.
    """
    if not header:
        return None
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded.strip():
        return None
    try:
        raw = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if ":" not in raw:
        return None
    _, _, password = raw.partition(":")
    return password


def install_access_gate(app: FastAPI, password: str) -> None:
    """Refuse every request that does not carry `password`, except OPEN_PATHS."""

    @app.middleware("http")
    async def gate(request: Request, call_next):
        if request.url.path in OPEN_PATHS:
            return await call_next(request)
        offered = supplied_password(request.headers.get("authorization"))
        # compare_digest, not ==: a short-circuiting comparison leaks the length
        # of the shared prefix to anyone who can time the response.
        if offered is None or not hmac.compare_digest(offered, password):
            return JSONResponse(status_code=401, content={"detail": REFUSAL}, headers=CHALLENGE)
        return await call_next(request)
