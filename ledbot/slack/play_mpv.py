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


def mpv_factory() -> MPV:

    def mpv_log_handler(loglevel, component, message):
        mpv_log.info('[%s] %s: %s', loglevel, component, message)

    player = mpv.MPV(
        log_handler=mpv_log_handler,
        ytdl=True,
        input_default_bindings=True,
        input_vo_keyboard=True,
    )

    # Property access, these can be changed at runtime
    @player.property_observer('time-pos')
    def mpv_time_observer(_name, value):
        # Here, _value is either None if nothing is playing or a float containing
        # fractional seconds since the beginning of the file.
        mpv_log.info('Now playing at %.2fs', value)

    player.fullscreen = False

    player.loop = 'inf'

    # Option access, in general these require the core to reinitialize
    player['vo'] = 'opengl'

    return player


async def mqtt_client_loop(loop: asyncio.AbstractEventLoop):
    player = mpv_factory()
    client = MQTTClient(loop=loop)

    async def fetch_and_play_item():
        message = await client.deliver_message()
        packet = message.publish_packet
        log.info("[%s] -> %s", packet.variable_header.topic_name, packet.payload.data)

        t = packet.variable_header.topic_name
        if t.startswith('play/'):
            d = packet.payload.data  # type: bytearray
            url = d.decode()

            # player.playlist_clear()
            # player.playlist_append(url)
            # player.playlist_pos = 0

            fut = loop.run_in_executor(None, player.play, url)
            await fut

            fut = loop.run_in_executor(None, player.wait_for_playback)
            await fut

    try:
        await client.connect(
            uri='mqtt://localhost',
        )

        # client.subscribe([
        topics = [
            ('$SYS/broker/uptime', QOS_1),
            ('$SYS/broker/load/#', QOS_2),
            ('play/#', QOS_0),
        ]
        await client.subscribe(topics)

        while True:
            await fetch_and_play_item()
    finally:
        await client.disconnect()


# async def demo(ui: LedbotUI):
#     await asyncio.sleep(0.5)
#     images = glob.glob(os.path.expanduser('./images/*.*'))
#     for img in images:
#         ui.play(img)
#         await asyncio.sleep(2)


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

    futs = [mqtt_client_loop(loop)]

    fut = asyncio.gather(*futs)

    # import aiomonitor
    # with aiomonitor.start_monitor(loop=loop):
    #     loop.run_until_complete(fut)
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init()
    main()
