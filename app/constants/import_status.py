"""Import lifecycle states."""

IMPORTING = "importing"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"
PENDING_CONFIRM = "pending_confirm"

IN_PROGRESS = frozenset({IMPORTING, PROCESSING})
