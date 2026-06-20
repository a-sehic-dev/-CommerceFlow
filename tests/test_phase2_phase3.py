import pytest
from fastapi import HTTPException

from app.utils.oauth_state import create_oauth_state, parse_oauth_state
from app.utils.permissions import require_role
from app.utils.rate_limit import SlidingWindowLimiter


def test_sliding_window_limiter_blocks_burst():
    limiter = SlidingWindowLimiter(window_seconds=60, max_events=2)
    limiter.check("ip-1")
    limiter.check("ip-1")
    with pytest.raises(HTTPException) as exc:
        limiter.check("ip-1")
    assert exc.value.status_code == 429


def test_oauth_state_roundtrip():
    token = create_oauth_state(organization_id=9, user_id=3)
    org_id, user_id = parse_oauth_state(token)
    assert org_id == 9
    assert user_id == 3


def test_require_role_blocks_viewer():
    with pytest.raises(HTTPException) as exc:
        require_role("viewer", "analyst")
    assert exc.value.status_code == 403


def test_pdf_executive_summary_bytes():
    from app.services.pdf_export_service import build_executive_pdf

    content, filename = build_executive_pdf(
        company_name="Acme",
        metrics={"total_revenue": 12000, "gross_margin_pct": 42.5},
        analysis_id="abc123",
    )
    assert content.startswith(b"%PDF")
    assert filename.endswith(".pdf")
