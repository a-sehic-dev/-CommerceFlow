from app.services.auth_service import hash_password, validate_password, verify_password
from app.utils.session_auth import create_session_token, parse_session_token, slugify


def test_slugify():
    assert slugify("Acme Corp!") == "acme-corp"


def test_session_token_roundtrip():
    token = create_session_token(1, 2, "test@example.com")
    session = parse_session_token(token)
    assert session is not None
    assert session.user_id == 1
    assert session.organization_id == 2
    assert session.email == "test@example.com"


def test_password_hash_roundtrip():
    hashed = hash_password("MySecurePass123")
    assert verify_password("MySecurePass123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_validate_password_rejects_too_long():
    try:
        validate_password("x" * 73)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "72" in str(exc)
