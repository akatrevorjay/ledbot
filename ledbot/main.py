import asyncio
import logging

import jinja2
import sys

import aiohttp_jinja2
from aiohttp import web

from .views import setup as setup_routes


async def init(loop):
    app = web.Application(loop=loop)
    app['sockets'] = {}
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
