#!/usr/bin/env python3

import asyncio
import logging
import sys

import asyncio
import uvloop

from sanic import Sanic
from sanic_openapi import swagger_blueprint, openapi_blueprint

from . import blueprints

from . import di, signals, get_logger, utils, service, mqtt

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


@di.inject('config')
async def run(config, app):
    log.debug('run')

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

    await fut


def init(argv):
    log.info("init")
    service.set_service_name('main')
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def ainit():
    log.debug('ainit')
    await mqtt.mqtt_client_connect()


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
