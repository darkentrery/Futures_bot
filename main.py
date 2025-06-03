import asyncio

from app.repository import SAUnitOfWork, pg_async_session_maker
from app.services.api import BybitAPI
from app.services.manager import Manager


async def main() -> None:
    api = BybitAPI()
    manager = Manager(SAUnitOfWork(pg_async_session_maker), api)
    await manager.run()


if __name__ == '__main__':
    asyncio.run(main())
