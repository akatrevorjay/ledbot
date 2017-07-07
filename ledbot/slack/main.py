#!/usr/bin/env python3

import asyncio

from . import queue
from ..log import get_logger

log = get_logger()


def init():
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def main():
    log.info("START")

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    fut = queue.ainit(loop)
    loop.run_until_complete(fut)

    fut = queue.start(loop)

    # import aiomonitor
    # with aiomonitor.start_monitor(loop=loop):
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init()
    main()
