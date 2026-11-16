import time

import jwt
import pytest

from app.core.auth import CurrentUser, verify_access_token

SECRET = "test-jwt-secret-padded-to-32-bytes-min"
ISSUER = "https://test-project.supabase.co/auth/v1"


def _token(**claim_overrides):
    now = int(time.time())
    claims = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
        "user_role": "user",
    }
    claims.update(claim_overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def hs256_secret(monkeypatch):
    monkeypatch.setattr("app.core.auth.SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setattr("app.core.auth.SUPABASE_URL", "https://test-project.supabase.co")


class TestVerifyAccessToken:
    def test_valid_token_returns_current_user(self):
        user = verify_access_token(_token())
        assert isinstance(user, CurrentUser)
        assert user.id == "11111111-1111-1111-1111-111111111111"
        assert user.claims["user_role"] == "user"

    def test_admin_role_claim_is_preserved(self):
        user = verify_access_token(_token(user_role="admin"))
        assert user.claims["user_role"] == "admin"

    def test_expired_token_is_rejected(self):
        now = int(time.time())
        token = _token(iat=now - 7200, exp=now - 3600)
        with pytest.raises(jwt.PyJWTError):
            verify_access_token(token)

    def test_wrong_secret_is_rejected(self):
        now = int(time.time())
        bad_token = jwt.encode(
            {"sub": "x", "aud": "authenticated", "iss": ISSUER, "iat": now, "exp": now + 3600},
            "a-completely-different-secret",
            algorithm="HS256",
        )
        with pytest.raises(jwt.PyJWTError):
            verify_access_token(bad_token)

    def test_wrong_audience_is_rejected(self):
        with pytest.raises(jwt.PyJWTError):
            verify_access_token(_token(aud="not-authenticated"))

    def test_wrong_issuer_is_rejected(self):
        with pytest.raises(jwt.PyJWTError):
            verify_access_token(_token(iss="https://someone-elses-project.supabase.co/auth/v1"))

    def test_missing_subject_is_rejected(self):
        now = int(time.time())
        token = jwt.encode(
            {"aud": "authenticated", "iss": ISSUER, "iat": now, "exp": now + 3600},
            SECRET,
            algorithm="HS256",
        )
        with pytest.raises(ValueError):
            verify_access_token(token)
