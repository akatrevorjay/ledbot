#!/usr/bin/env python3

import asyncio
import logging
import sys

import asyncio
import uvloop

from sanic import Sanic
from sanic_openapi import swagger_blueprint, openapi_blueprint

from . import blueprints

from . import di, signals, get_logger, utils, service, mqtt, slack

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


async def app_factory() -> Sanic:
    app = bare_app_factory()
    add_blueprints(app)
    configure_app(app)
    return app


def init(argv):
    log.info("init")
    service.set_service_name('main')
    # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def ainit(loop):
    log.debug('ainit')

    await mqtt.mqtt_client_connect()

    await slack.ainit(loop)

    # app = await app_factory()  # type: Sanic
    # return app


@di.inject('config')
async def serve(config, app, loop):
    host, port = config.BIND.split(':', 1)
    port = int(port)

    # await app.create_server(
    #     host=host,
    #     port=port,
    #     debug=config.DEBUG,
    #     log_config=config.LOGGING,
    # )


async def run(loop):
    app = await ainit(loop)

    await serve(app, loop)

    futs = [
        slack.run(loop),
    ]

    f = asyncio.wait(futs, return_when=asyncio.FIRST_COMPLETED)
    await f


@di.inject('config')
def main(config, argv):
    log.info("begin")

    loop = asyncio.get_event_loop()
    loop.set_debug(config.DEBUG)

    loop.run_until_complete(run(loop))

    log.info('Done. Closing event loop and exiting.')
    loop.close()


if __name__ == "__main__":
    init(sys.argv)
    main(sys.argv)
