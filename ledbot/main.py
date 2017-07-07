#!/usr/bin/env python3

import asyncio
import logging
import sys

import asyncio
import uvloop

from sanic import Sanic
from sanic_openapi import swagger_blueprint, openapi_blueprint

from blueprints.car import blueprint as car_blueprint
from blueprints.driver import blueprint as driver_blueprint
from blueprints.garage import blueprint as garage_blueprint
from blueprints.manufacturer import blueprint as manufacturer_blueprint

from . import signals, get_logger

log = get_logger()


@signals.startup
async def start_background_tasks(app):
    log.info('Startup: %s', app)


@signals.cleanup
async def cleanup_background_tasks(app):
    log.info('Cleanup: %s', app)


def app_factory():
    app = Sanic()
    return app


def configure_app(app):
    app.blueprint(openapi_blueprint)
    app.blueprint(swagger_blueprint)
    app.blueprint(car_blueprint)
    app.blueprint(driver_blueprint)
    app.blueprint(garage_blueprint)
    app.blueprint(manufacturer_blueprint)

    app.config.API_VERSION = '1.0.0'
    app.config.API_TITLE = 'Car API'
    app.config.API_TERMS_OF_SERVICE = 'Use with caution!'
    app.config.API_CONTACT_EMAIL = 'channelcat@gmail.com'


async def run_app(app):
    app.run(debug=True)


def init(argv):
    log.info("init")

    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def main(argv):
    log.info("begin")

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    app = app_factory()
    configure_app(app)

    # fut = app.run(
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init(sys.argv)
    main(sys.argv)
