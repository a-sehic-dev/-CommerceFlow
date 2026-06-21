from app.utils.plan_limits import get_plan_limits, normalize_plan


def test_normalize_plan_defaults_unknown():
    assert normalize_plan(None) == "starter"
    assert normalize_plan("enterprise") == "starter"


def test_pro_vs_team_vs_ultra_limits():
    pro = get_plan_limits("pro")
    team = get_plan_limits("team")
    ultra = get_plan_limits("ultra")

    assert pro.max_seats < team.max_seats < ultra.max_seats
    assert pro.max_stores == team.max_stores == 1
    assert ultra.max_stores == 3
    assert pro.team_invites is False
    assert team.team_invites is True
    assert ultra.team_invites is True
    assert pro.live_sync is True
    assert get_plan_limits("starter").live_sync is False


def test_starter_is_csv_only_tier():
    starter = get_plan_limits("starter")
    assert starter.max_stores == 0
    assert starter.pdf_export is False
    assert starter.weekly_email is False
