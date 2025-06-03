import abc

import pydantic
from sqlalchemy import exc as saexc
from sqlalchemy import insert, select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import exc
from app.entity import AnyModel, Entity, FindAllResult


class AbstractRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, data: AnyModel) -> Entity:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, filter_by: AnyModel):
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, id: int, data: AnyModel) -> Entity:
        raise NotImplementedError

    @abc.abstractmethod
    async def patch(self, id: int, data: AnyModel) -> Entity:
        raise NotImplementedError

    @abc.abstractmethod
    async def find_or_none(self, filter_by: AnyModel) -> Entity | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def find(self, filter_by: AnyModel) -> Entity:
        raise NotImplementedError

    @abc.abstractmethod
    async def find_all(self, filter_by: AnyModel, offset: int, limit: int, order: str, order_by: str) -> FindAllResult:
        raise NotImplementedError

    @abc.abstractmethod
    async def bulk_add(self, data: list[AnyModel]) -> list[Entity]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_or_create(
            self, data: list[pydantic.BaseModel], by_fields: list[str], fields: list[str]
    ) -> list[Entity]:
        raise NotImplementedError


class SARepository(AbstractRepository):
    model = None
    schema = None
    name = 'Undefined'
    type_adapter = pydantic.TypeAdapter(schema)

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, data: AnyModel) -> Entity:
        try:
            stmt = insert(self.model).values(**data).returning(self.model)
            res = (await self.session.execute(stmt)).scalars().first()
            return self.to_read_model(res)
        except Exception as e:
            self._handle_error(e)

    async def delete(self, filter_by: AnyModel):
        try:
            stmt = delete(self.model).filter_by(**filter_by)
            await self.session.execute(stmt)
        except Exception as e:
            self._handle_error(e)

    async def update(self, id: int, data: AnyModel) -> Entity:
        try:
            stmt = update(self.model).values(**data).filter_by(id=id).returning(self.model)
            result = await self.session.execute(stmt)
            return self.to_read_model(result.scalars().first())

        except Exception as e:
            self._handle_error(e)

    async def patch(self, id: int, data: AnyModel) -> Entity:
        try:
            stmt = update(self.model).values(**data).filter_by(id=id).returning(self.model)
            result = await self.session.execute(stmt)
            return self.to_read_model(result.scalars().first())

        except Exception as e:
            self._handle_error(e)

    async def _find(self, filter_by: AnyModel):
        try:
            stmt = select(self.model).filter_by(**filter_by)
            res = (await self.session.execute(stmt)).scalar_one()
            return res
        except saexc.NoResultFound:
            return None
        except Exception:
            raise

    async def find_or_none(self, filter_by: AnyModel) -> Entity | None:
        res = await self._find(filter_by)
        if res is None:
            return None
        return self.to_read_model(res)

    async def find(self, filter_by: AnyModel) -> Entity:
        row = await self.find_or_none(filter_by)
        if row is None:
            raise exc.NotFoundError(f"{self.name} not found")

        return row

    async def find_all(
        self, filter_by: AnyModel, offset: int = 0, limit: int = 100, order: str = "desc", order_by: str = "id"
    ) -> FindAllResult:
        filter_by = filter_by or {}
        order = getattr(self.model, order_by).desc() if order == "desc" else getattr(self.model, order_by).asc()
        count = (await self.session.execute(
            select(func.count(self.model.id)).filter_by(**filter_by)
        )).scalar_one()

        rows = (await self.session.execute(
            select(self.model)
            .offset(offset)
            .limit(limit)
            .filter_by(**filter_by)
            .order_by(order)
        )).scalars().all()

        return count, self.to_read_models(rows)

    def to_read_model(self, obj) -> pydantic.BaseModel | None:
        if self.schema is None:
            return obj
        return pydantic.TypeAdapter(self.schema).validate_python(obj)

    def to_read_models(self, obj) -> list[pydantic.BaseModel] | None:
        if self.schema is None:
            return obj
        return pydantic.TypeAdapter(list[self.schema]).validate_python(obj)

    def _handle_error(self, e: Exception):
        if isinstance(e, saexc.IntegrityError):
            # Postgres error codes
            # https://www.postgresql.org/docs/current/errcodes-appendix.html
            match e.orig.pgcode:
                case '23503':  # foreign_key_violation
                    raise exc.NotFoundError("Related object not found")
                case '23505':  # unique_violation
                    raise exc.AlreadyExists(f"{self.name} already exists")
                case _:
                    raise
        elif isinstance(e, saexc.DBAPIError):
            match e.orig.pgcode:
                case "22003":
                    raise exc.InvalidRequest(str(e))
                case _:
                    raise e
        raise e

    async def update_or_create(
            self, data: list[pydantic.BaseModel], by_fields: list[str], fields: list[str]
    ) -> list[Entity]:
        query = pg_insert(self.model).values(
            [item.model_dump() for item in data]
        )
        properties = {field: getattr(query.excluded, field) for field in fields}
        try:
            query = query.on_conflict_do_update(
                index_elements=[getattr(self.model, by_field) for by_field in by_fields],
                set_=properties
            ).returning(self.model)
            obj = (await self.session.execute(query)).scalars().all()
            return self.to_read_models(obj)
        except Exception as e:
            self._handle_error(e)

    async def bulk_add(self, data: list[AnyModel]) -> list[Entity]:
        try:
            stmt = insert(self.model).returning(self.model)
            rows = (await self.session.execute(stmt, data)).scalars().all()
            return self.to_read_models(rows)
        except Exception as e:
            self._handle_error(e)

    async def find_all_by_list(
        self, filter_by: dict[str, list], order: str = "desc", order_by: str = "created_at"
    ) -> list[Entity]:
        filter_by = filter_by or {}
        order = getattr(self.model, order_by).desc() if order == "desc" else getattr(self.model, order_by).asc()
        stmt = select(self.model).order_by(order)
        for key, value in filter_by.items():
            stmt = stmt.filter(getattr(self.model, key).in_(value))

        rows = (await self.session.execute(stmt)).scalars().all()
        return self.to_read_models(rows)
