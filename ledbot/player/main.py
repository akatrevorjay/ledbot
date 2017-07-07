#!/usr/bin/env python3

import asyncio
import sys
import uvloop

from ..log import get_logger
from .. import di, utils, mqtt, service
from . import ui_mpv

log = get_logger()


def init(argv):
    log.debug('init')
    service.set_service_name('player.main')
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def ainit():
    log.debug('ainit')
    await mqtt.mqtt_client_connect()


async def run():
    log.debug('run')
    await ui_mpv.main()


@di.inject('config')
def main(config, argv):
    log.info("begin")

    loop = asyncio.get_event_loop()
    loop.set_debug(config.DEBUG)

    loop.run_until_complete(ainit())

    fut = run()
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init(sys.argv)
    main(sys.argv)
