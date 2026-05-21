from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.utils.app_timezone import as_local_iso

LocalDateTime = Annotated[
    datetime,
    PlainSerializer(lambda v: as_local_iso(v), return_type=str),
]
