#!/usr/bin/env python3

import asyncio
import uvloop

from ..log import get_logger
from .. import di, signals, mqtt, service

from . import aioslack, queue

log = get_logger()


def init():
    log.info('init')
    service.set_service_name('slack.main')
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def ainit(loop):
    await queue.ainit(loop=loop)

    await mqtt.mqtt_client_connect()

    await aioslack.connect(loop=loop)


def main():
    log.info('begin')

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    fut = ainit(loop=loop)
    loop.run_until_complete(fut)

    fut = queue.start(loop)

    # import aiomonitor
    # with aiomonitor.start_monitor(loop=loop):
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init()
    main()
