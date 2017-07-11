from ..log import get_logger
from . import aioslack, queue

log = get_logger()


async def ainit(loop):
    await queue.ainit(loop=loop)


async def run(loop):
    await aioslack.connect(loop=loop)
