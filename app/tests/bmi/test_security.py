import pytest

from bmi_dashboard.security import RateLimiter, create_session_token, hash_password, verify_password, verify_session_token

SECRET = "s" * 40


def test_hash_has_no_dollar_sign_and_verifies():
    stored = hash_password("a-long-passphrase", n=2**10)
    assert "$" not in stored and stored.startswith("scrypt:")
    assert verify_password("a-long-passphrase", stored)
    assert not verify_password("wrong", stored)


def test_hash_is_salted():
    assert hash_password("same-password-123", n=2**10) != hash_password("same-password-123", n=2**10)


@pytest.mark.parametrize("stored", ["", "plaintext", "scrypt:1:2", "bcrypt:1:2:3:4:5", "scrypt:x:y:z:a:b"])
def test_malformed_hash_never_verifies_and_never_raises(stored):
    assert verify_password("anything", stored) is False


def test_token_roundtrip_expiry_and_tampering():
    token = create_session_token(SECRET, "owner", 60, now=1000)
    assert verify_session_token(SECRET, token, now=1030) == "owner"
    assert verify_session_token(SECRET, token, now=1061) is None          # expired
    assert verify_session_token("x" * 40, token, now=1030) is None        # wrong secret
    payload, sig = token.split(".")
    assert verify_session_token(SECRET, f"{payload}x.{sig}", now=1030) is None  # tampered payload
    for junk in ("", "abc", "a.b", "a.b.c"):
        assert verify_session_token(SECRET, junk) is None


class _Backend:
    def __init__(self):
        self.d, self.t = {}, {}

    def get(self, k):
        return self.d.get(k)

    def incr(self, k):
        self.d[k] = int(self.d.get(k, 0)) + 1
        return self.d[k]

    def expire(self, k, s):
        self.t[k] = s

    def ttl(self, k):
        return self.t.get(k, -1)

    def delete(self, k):
        self.d.pop(k, None)


def test_rate_limiter_blocks_after_max_and_resets():
    backend = _Backend()
    rl = RateLimiter(lambda: backend, 3, 900)
    for _ in range(3):
        assert rl.retry_after("1.2.3.4") == 0
        rl.register_failure("1.2.3.4")
    assert rl.retry_after("1.2.3.4") == 900
    assert rl.retry_after("5.6.7.8") == 0  # other clients unaffected
    rl.reset("1.2.3.4")
    assert rl.retry_after("1.2.3.4") == 0


def test_rate_limiter_falls_back_to_memory_when_redis_is_down():
    def broken():
        raise ConnectionError("redis down")

    rl = RateLimiter(broken, 2, 900)
    rl.register_failure("ip")
    rl.register_failure("ip")
    assert rl.retry_after("ip") > 0
    rl.reset("ip")
    assert rl.retry_after("ip") == 0
