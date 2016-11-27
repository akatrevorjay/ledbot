import asyncio
import logging

import jinja2
import sys
import random

import aiohttp_jinja2
from aiohttp import web

from .views import setup as setup_routes
from . import text

log = logging.getLogger(__name__)


def scroller():
    x = random.randint(0, int(64*2.5))
    y = 10
    text.write('http://ledpi', x=x, y=y, font='fonts/7x13.bdf')


async def idler(app):
    log.info('Idler')
    try:
        while True:
            log.info('Idling')
            await app.loop.run_in_executor(None, scroller)
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    finally:
        log.info('Done with idler')


async def start_background_tasks(app):
    app['idler'] = app.loop.create_task(idler(app))


async def cleanup_background_tasks(app):
    log.info('cleanup background tasks...')
    app['idler'].cancel()
    await app['idler']


async def init(loop):
    app = web.Application(loop=loop)

    app['sockets'] = {}

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    app.on_shutdown.append(shutdown)

    aiohttp_jinja2.setup(
        app, loader=jinja2.PackageLoader('ledbot', 'templates'))

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
