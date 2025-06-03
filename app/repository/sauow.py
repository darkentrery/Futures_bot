import abc

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import config
from app.repository.repositories import (
    OrderRepository,
)


engine = create_async_engine(config.async_dsn)
pg_async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class AbstractUnitOfWork(abc.ABC):

    @abc.abstractmethod
    async def __aenter__(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def __aexit__(self, *args):
        raise NotImplementedError

    @abc.abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def rollback(self):
        raise NotImplementedError


class SAUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()

        self.order = OrderRepository(self.session)

        return self

    async def __aexit__(self, *args):
        await self.rollback()
        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
