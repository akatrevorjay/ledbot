# import logging
# import json
# import collections
# import functools
# import operator
# import sys
import abc
import os
import re
import itertools

import asyncio
# import asyncio.queues
# import asyncio.locks
# import asyncio.events
# import asyncio.futures
# import asyncio.log
# import aiohttp
import typing as T

import six
import aiohttp
import attr
# import paco
import kawaiisync
# import funcy
# import mpv
import yarl
import youtube_dl

from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from . import aioslack

from ..log import get_logger

from .. import di, utils, debug
from ..utils import AttrDict

from ..debug import pp, pf, see

log = get_logger()

slack_client = None
mqttc = None


@attr.s(repr=False)
class SlackMessage(aioslack.RtmEvent):

    async def queue_to_play(self):
        log.debug('Trying to play %s', self)

        for attach in itertools.chain(self.iter_files(), self.iter_attachments()):
            log.debug('Checking attachment=%s', attach)

            uri = attach.get_uri()
            if not uri:
                continue

            log.debug("Playing attachment=%s", attach)
            await queue_to_play(uri)
            return

        log.error('Not playable %s', self)


async def queue_to_play(uri: yarl.URL, content_type: str='generic'):
    global mqttc

    log.debug("Queuing uri=%s content_type=%s", uri, content_type)

    topic = 'ledbot/play/%s' % content_type

    buri = str(uri).encode()
    log.debug("topic=%s buri=%s", topic, buri)

    m = await mqttc.publish(topic, buri, qos=QOS_0)

    log.debug('m=%s', m)

    log.info('Queued buri=%s', buri)


@di.inject('config')
async def ainit(config, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    log.debug('init')

    global slack_client, mqttc

    slack_client = aioslack.Client(config.SLACK_API_TOKEN)
    slack_client.on('*')(_on_slack_all)
    slack_client.on('message')(_on_slack_message)

    mqttc = MQTTClient(client_id=log.name, loop=loop)


@di.inject('config')
async def start(config, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    global slack_client, mqttc

    log.debug('Connecting to Slack and MQTT')

    await mqttc.connect(config.MQTT_URL)
    await slack_client.start_ws_connection()


async def _on_slack_all(event):
    """Slack debug handler for all events."""
    log.debug("Event: %s", pf(event))


async def _on_slack_message(event):
    """Slack message faucet."""
    msg = await SlackMessage.from_aioslack_event(event.event, event.client)
    await msg.queue_to_play()
