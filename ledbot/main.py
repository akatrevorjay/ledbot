#!/usr/bin/env python3

import asyncio
import logging
import sys

import asyncio
import uvloop

from sanic import Sanic
from sanic_openapi import swagger_blueprint, openapi_blueprint

from . import blueprints

from . import di, signals, get_logger

log = get_logger()


@signals.startup
async def start_background_tasks(app):
    log.info('Startup: %s', app)


@signals.cleanup
async def cleanup_background_tasks(app):
    log.info('Cleanup: %s', app)


@di.inject('config')
def bare_app_factory(config):
    app = Sanic()
    app.config.update(config)
    return app


def add_blueprints(app):
    app.blueprint(openapi_blueprint)
    app.blueprint(swagger_blueprint)

    app.blueprint(blueprints.play_bp)


def configure_app(app):
    app.config.API_VERSION = '0.0.1'
    app.config.API_TITLE = 'Ledbot API'
    app.config.API_TERMS_OF_SERVICE = 'Whoa nelly!'
    app.config.API_CONTACT_EMAIL = 'github@trevor.joynson.io'


def app_factory() -> Sanic:
    app = bare_app_factory()
    add_blueprints(app)
    configure_app(app)
    return app


async def run(app):
    app.run(debug=True)


def init(argv):
    log.info("init")
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


@di.inject('config')
def main(config, argv):
    log.info("begin")

    loop = asyncio.get_event_loop()
    loop.set_debug(config.DEBUG)

    app = app_factory()  # type: Sanic

    host, port = config.BIND.split(':', 1)
    port = int(port)

    fut = app.run(
        host=host,
        port=port,
        debug=config.DEBUG,
        # sock=None,
        # workers=1,
        # backlog=100,
        # protocol=None,
        log_config=config.LOGGING,
    )
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init(sys.argv)
    main(sys.argv)
