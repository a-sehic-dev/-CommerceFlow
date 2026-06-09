"""Scope for clear/reset — guest workspace, one organization, or founder global wipe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResetScope:
    """organization_id=None → guest imports only; global_all → entire database."""

    organization_id: int | None = None
    global_all: bool = False

    @property
    def label(self) -> str:
        if self.global_all:
            return "all workspaces"
        if self.organization_id is None:
            return "guest demo workspace"
        return f"organization #{self.organization_id}"
