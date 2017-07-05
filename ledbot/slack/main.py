#!/usr/bin/env python3

import asyncio
import logging

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

    fut = queue.init(loop)
    loop.run_until_complete(fut)

    futs = [
        queue.slack_client.start_ws_connection(),
        queue.extractor_worker(loop),
    ]

    fut = asyncio.gather(*futs)

    import aiomonitor
    with aiomonitor.start_monitor(loop=loop):
        loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init()
    main()
