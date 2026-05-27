"""Workspace mode labels for demo vs authenticated SaaS experiences."""

WORKSPACE_MODES: dict[str, dict[str, str]] = {
    "demo_workspace": {
        "title": "Demo Workspace",
        "subtitle": "Explore operational analytics instantly",
        "alt_subtitle": "Access sample ecommerce datasets without signup",
    },
    "authenticated_workspace": {
        "title": "Operational Workspace",
        "subtitle": "Private analytics environment",
        "alt_subtitle": "Signed-in workspace with saved history",
    },
}


def workspace_context(mode: str | None = None) -> dict[str, str]:
    key = (mode or "demo_workspace").strip()
    cfg = WORKSPACE_MODES.get(key, WORKSPACE_MODES["demo_workspace"])
    return {
        "workspace_mode": key,
        "workspace_title": cfg["title"],
        "workspace_subtitle": cfg["subtitle"],
        "workspace_alt_subtitle": cfg["alt_subtitle"],
    }
