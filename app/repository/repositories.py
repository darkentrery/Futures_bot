import datetime

from pydantic import TypeAdapter
from sqlalchemy import select, cast, Time, func, and_, or_, text, case, literal
from sqlalchemy.orm import joinedload, aliased

from app.config import config

from app.repository.base import SARepository
from app import models
from app import entity
from app.utils.datetime import utc_now



class OrderRepository(SARepository):
    model = models.Order
    schema = entity.Order
    name = "Order"
