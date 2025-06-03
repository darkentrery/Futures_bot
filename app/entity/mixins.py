import datetime

from pydantic import BaseModel, ConfigDict


class IdMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DateTimeMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime.datetime
    updated_at: datetime.datetime | None
