from ..log import get_logger
from . import queue, bot

log = get_logger()


async def ainit(loop):
    await queue.ainit(loop=loop)


async def run(loop):
    await bot.run(loop=loop)

