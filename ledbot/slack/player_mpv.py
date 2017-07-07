#!/usr/bin/env python3

import asyncio
import os
import attr
import time
import sys
import glob

import aiohttp
import mpv

from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from ..log import get_logger
from .. import utils
from ..debug import pp, pf, see

log = get_logger()
mpv_log = get_logger('%s.mpv' % log.name)


def mpv_log_handler(loglevel, component, message):
    mpv_log.info('[%s] %s: %s', loglevel, component, message)


def mpv_factory() -> mpv.MPV:
    player = mpv.MPV(
        log_handler=mpv_log_handler,
        ytdl=True,
        input_default_bindings=True,
        input_vo_keyboard=True,
        vo='opengl',
        fullscreen=False,
        keepaspect=False,
        geometry='160x320+0+0',
        # autofit='320:160',
        loop_file=True,
    )

    return player


async def play(player: mpv.MPV, uri: str, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    log.info('Hitting play on uri=%s', uri)
    await loop.run_in_executor(None, player.play, uri)

    log.info('Playing should have started for uri=%s', uri)


async def mqtt_client_loop(loop: asyncio.AbstractEventLoop):
    player = mpv_factory()
    client = MQTTClient(client_id=log.name, loop=loop)
    session = aiohttp.ClientSession()

    async def fetch_and_play_item():
        message = await client.deliver_message()
        packet = message.publish_packet
        log.info("[%s] -> %s", packet.variable_header.topic_name, packet.payload.data)

        topic = packet.variable_header.topic_name
        data = packet.payload.data  # type: bytearray

        if topic.startswith('ledbot/play'):
            uri = data.decode()

            async with session.get(uri) as resp:
                resp.raise_for_status()

                if resp.content_type.startswith('text'):
                    log.info('Not playing content_type=%s', resp.content_type)
                    return

            await play(player, uri)

    try:
        await client.connect('mqtt://localhost/')

        # client.subscribe([
        topics = [
            # ('$SYS/broker/uptime', QOS_1),
            # ('$SYS/broker/load/#', QOS_2),
            ('ledbot/play/#', QOS_0),
        ]
        await client.subscribe(topics)

        while True:
            try:
                await fetch_and_play_item()
            except Exception:
                log.exception('Failed to fetch and play item')

    finally:
        await client.disconnect()


def init():
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def ainit(loop):
    pass


def main():
    log.info("START")

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    fut = ainit(loop)
    loop.run_until_complete(fut)

    fut = mqtt_client_loop(loop)
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init()
    main()
