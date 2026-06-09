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
