"""Password hashing, session tokens and login throttling (standard library only)."""
import base64
import hashlib
import hmac
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _DKLEN = 2**14, 8, 1, 32


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, n: int = _SCRYPT_N, r: int = _SCRYPT_R, p: int = _SCRYPT_P) -> str:
    """scrypt hash as `scrypt:N:r:p:salt:hash` (base64url).

    The format deliberately contains no `$`, which Docker Compose would try to
    interpolate when the value is read from a .env file.
    """
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=_DKLEN)
    return f"scrypt:{n}:{r}:{p}:{_b64e(salt)}:{_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split(":")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=_b64d(salt), n=int(n), r=int(r), p=int(p), dklen=_DKLEN
        )
        return hmac.compare_digest(digest, _b64d(expected))
    except (ValueError, TypeError):
        return False


def create_session_token(secret: str, subject: str, ttl_seconds: int, now: float | None = None) -> str:
    now = time.time() if now is None else now
    payload = _b64e(json.dumps({"sub": subject, "exp": int(now) + ttl_seconds}, separators=(",", ":")).encode())
    signature = _b64e(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_session_token(secret: str, token: str, now: float | None = None) -> str | None:
    """Return the subject if the token is authentic and unexpired, else None."""
    try:
        payload, signature = token.split(".")
        expected = _b64e(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_b64d(payload))
        if claims["exp"] <= (time.time() if now is None else now):
            return None
        return str(claims["sub"])
    except (ValueError, KeyError, TypeError):
        return None


class RateLimiter:
    """Counts failed logins per key. Uses Redis; falls back to process memory if
    Redis is unavailable so a cache outage never disables the protection."""

    def __init__(self, get_backend, max_attempts: int, window_seconds: int):
        self._get_backend = get_backend
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._memory: dict[str, tuple[int, float]] = {}

    def _key(self, key: str) -> str:
        return f"bmi:login-fail:{key}"

    def retry_after(self, key: str) -> int:
        """Seconds until the caller may try again; 0 if not blocked."""
        try:
            backend = self._get_backend()
            count = int(backend.get(self._key(key)) or 0)
            if count >= self.max_attempts:
                return max(int(backend.ttl(self._key(key))), 1)
            return 0
        except Exception:  # noqa: BLE001 - any backend failure => memory fallback
            logger.warning("login rate limiter: Redis unavailable, using in-process counter")
            count, reset_at = self._memory.get(key, (0, 0.0))
            if reset_at <= time.time():
                return 0
            return max(int(reset_at - time.time()), 1) if count >= self.max_attempts else 0

    def register_failure(self, key: str) -> None:
        try:
            backend = self._get_backend()
            if backend.incr(self._key(key)) == 1:
                backend.expire(self._key(key), self.window)
        except Exception:  # noqa: BLE001
            count, reset_at = self._memory.get(key, (0, 0.0))
            if reset_at <= time.time():
                count, reset_at = 0, time.time() + self.window
            self._memory[key] = (count + 1, reset_at)

    def reset(self, key: str) -> None:
        self._memory.pop(key, None)
        try:
            self._get_backend().delete(self._key(key))
        except Exception:  # noqa: BLE001
            pass
