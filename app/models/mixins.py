import datetime

from sqlalchemy.orm import DeclarativeBase, declarative_mixin, Mapped, mapped_column

from app.utils.datetime import utc_now


class Base(DeclarativeBase):
    pass


@declarative_mixin
class IdMixin:
    # Field always first
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, sort_order=-99)


@declarative_mixin
class TimestampMixin:
    # Fields always last
    created_at: Mapped[datetime.datetime] = mapped_column(default=utc_now, sort_order=99)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=utc_now, onupdate=utc_now, sort_order=99, nullable=True
    )
