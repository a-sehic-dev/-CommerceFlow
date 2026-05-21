from app.competitors.base import CompetitorTrackerBase


class CompetitorTrackerRegistry:
    """Registry for pluggable competitor trackers (scrapers, APIs, marketplaces)."""

    _trackers: dict[str, type[CompetitorTrackerBase]] = {}

    @classmethod
    def register(cls, name: str, tracker_class: type[CompetitorTrackerBase]) -> None:
        cls._trackers[name] = tracker_class

    @classmethod
    def get(cls, name: str) -> type[CompetitorTrackerBase] | None:
        return cls._trackers.get(name)

    @classmethod
    def list_trackers(cls) -> list[str]:
        return list(cls._trackers.keys())
