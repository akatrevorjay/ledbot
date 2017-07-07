#!/usr/bin/env python3

import asyncio
import os
import attr
import time
import sys
import glob

import hbmqtt.client
from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
import mpv

from ..log import get_logger
from .. import utils
from ..debug import pp, pf, see

log = get_logger()
mpv_log = get_logger('%s.mpv' % log.name)


def mpv_factory() -> mpv.MPV:

    def mpv_log_handler(loglevel, component, message):
        mpv_log.info('[%s] %s: %s', loglevel, component, message)

    player = mpv.MPV(
        log_handler=mpv_log_handler,
        ytdl=True,
        input_default_bindings=True,
        input_vo_keyboard=True,
        vo='opengl',
        # loop='inf',
        fullscreen=False,
        # window_scale=1.0,
        geometry='160x320+0+0',
        # autofit='320:160',
        keepaspect=False,
        # loop='inf',
        loop_file=True,
    )

    return player


async def mqtt_client_loop(loop: asyncio.AbstractEventLoop):
    player = mpv_factory()
    client = MQTTClient(client_id=log.name, loop=loop)

    async def fetch_and_play_item():
        message = await client.deliver_message()
        packet = message.publish_packet
        log.info("[%s] -> %s", packet.variable_header.topic_name, packet.payload.data)

        t = packet.variable_header.topic_name
        if not t.startswith('ledbot/play'):
            return

        d = packet.payload.data  # type: bytearray
        url = d.decode()

        log.info('Playing: %s', url)

        # player.playlist_clear()
        # for _ in range(5):
        #     player.playlist_append(url)
        # player.playlist_pos = 0

        fut = loop.run_in_executor(None, player.play, url)
        await fut

        # log.info('Waiting for playback: %s', url)
        # fut = loop.run_in_executor(None, player.wait_for_playback)
        # await fut

        log.info('Done playing: %s', url)

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
            await fetch_and_play_item()
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
