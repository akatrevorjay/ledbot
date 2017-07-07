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

from .. import di, utils, debug
from ..log import get_logger

log = get_logger()
mpv_log = get_logger('%s.mpv' % log.name)


def mpv_log_handler(loglevel, component, message):
    mpv_log.info('[%s] %s: %s', loglevel, component, message)


@attr.s
class Player:
    player = attr.ib(default=attr.Factory(
        lambda self: self._mpv_factory(),
        takes_self=True,
    ))

    session = attr.ib(default=attr.Factory(aiohttp.ClientSession))

    loop = attr.ib(default=attr.Factory(asyncio.get_event_loop))

    @di.inject('config')
    def _mpv_factory(self, config):
        player = mpv.MPV(
            log_handler=mpv_log_handler,
            ytdl=True,
            input_default_bindings=True,
            input_vo_keyboard=True,
            cursor_autohide=250,
            vo=config.MPV_VO_DRIVER,
            keepaspect=False,
            keepaspect_window=False,
            x11_name=config.APP_NAME,
            fullscreen=False,
            geometry='%sx%s' % config.PLAYER_GEOMETRY,
            # force_window_position=True,
            loop_file=True,
            cache=True,
            cache_secs=30,
        )

        return player

    async def play_uri(self, uri: str, check=True):
        if check:
            ok = await self.check_uri(uri)
            if not ok:
                log.info('Failed check for uri=%s; not playing this.', uri)
                return

        log.info('Hitting play on uri=%s', uri)
        await self.loop.run_in_executor(None, self.player.play, uri)
        log.info('Playing should have started for uri=%s', uri)

    async def check_uri(self, uri: str):
        log.error('Checking uri=%s', uri)

        # Bare minimum to ensure it's likely playable
        async with self.session.get(uri) as resp:  # type: aiohttp.ClientResponse
            try:
                resp.raise_for_status()
            except Exception as exc:
                log.error('Failed to get uri=%s: %s', uri, exc)
                return False

            if resp.content_type.startswith('text'):
                log.info('Not playing content_type=%s', resp.content_type)
                return False

        return True

    async def on_mqtt_event(self, topic: str, data: bytearray):
        uri = data.decode()
        await self.play_uri(uri)


async def mqtt_client_loop(client: MQTTClient, player: Player):

    async def _on(message):
        packet = message.publish_packet
        topic = packet.variable_header.topic_name
        data = packet.payload.data  # type: bytearray

        log.info("[%s] -> %s", topic, data)

        try:
            if topic.startswith('ledbot/play'):
                await player.on_mqtt_event(topic, data)
        except Exception:
            log.exception('[%s] Failed to play item: data=%s', topic, data)

    while True:
        message = await client.deliver_message()
        await _on(message)


@di.inject('config')
async def main(config, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    client = MQTTClient(client_id=log.name, loop=loop)
    player = Player(loop=loop)

    try:
        await client.connect(config.MQTT_URL)

        topics = [
            # ('$SYS/broker/uptime', QOS_1),
            # ('$SYS/broker/load/#', QOS_2),
            ('ledbot/play/#', QOS_0),
        ]
        await client.subscribe(topics)

        await mqtt_client_loop(client, player)

    finally:
        await client.disconnect()
