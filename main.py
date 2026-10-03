import asyncio
import logging

import uvicorn

from config import API_HOST, API_PORT, validate_config


async def main() -> None:
    validate_config()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Import after configuration validation, so an empty token gets a clear message.
    from api import app
    from bot import bot, run_bot
    import db

    await db.init()

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=API_HOST,
            port=API_PORT,
            log_level="info",
            loop="asyncio",
            access_log=False,
        )
    )
    api_task = asyncio.create_task(server.serve())
    bot_task = asyncio.create_task(run_bot())
    try:
        await asyncio.gather(api_task, bot_task)
    finally:
        server.should_exit = True
        for task in (api_task, bot_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(api_task, bot_task, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
