import asyncio
import logging

import jinja2
import sys
import random
import uninhibited

import aiohttp_jinja2
from aiohttp import web

from .views import setup as setup_routes
from . import text
from . import signals

log = logging.getLogger(__name__)


@signals.startup
async def start_background_tasks(app):
    log.info('Startup: %s', app)

    # app['idler'] = app.loop.create_task(idler(app))


@signals.cleanup
async def cleanup_background_tasks(app):
    log.info('Cleanup: %s', app)

    # app['idler'].cancel()
    # await app['idler']


async def init(loop):
    app = web.Application(loop=loop)

    app['sockets'] = {}

    app.on_startup.append(signals.startup)
    app.on_cleanup.append(signals.cleanup)
    app.on_shutdown.append(signals.shutdown)

    aiohttp_jinja2.setup(app, loader=jinja2.PackageLoader('ledbot', 'templates'))

    setup_routes(app)

    return app


async def shutdown(app):
    for ws in app['sockets'].values():
        await ws.close()
    app['sockets'].clear()


def main(argv):
    # init logging
    logging.basicConfig(level=logging.DEBUG)

    loop = asyncio.get_event_loop()

    app = loop.run_until_complete(init(loop))

    web.run_app(app, port=80)

    return app


if __name__ == '__main__':
    main(sys.argv)
