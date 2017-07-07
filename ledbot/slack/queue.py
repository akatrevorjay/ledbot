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

from .. import utils, debug
from ..utils import AttrDict

from ..debug import pp, pf, see

log = get_logger()

SLACK_API_TOKEN = os.environ['SLACK_API_TOKEN']
slack_client = None
mqttc = None


@attr.s(repr=False)
class RtmEvent(utils.ProxyMutableMapping):
    event = attr.ib()
    client = attr.ib()

    def __attrs_post_init__(self):
        utils.ProxyMutableMapping.__init__(self, self.event)

    def __getattr__(self, attr):
        try:
            return self.event[attr]
        except KeyError:
            raise AttributeError(attr)

    user = attr.ib(default=None)
    channel = attr.ib(default=None)

    @property
    def user_id(self):
        return self.event.get('user')

    @property
    def channel_id(self):
        return self.event.get('channel')

    @utils.lazyproperty
    def event_ts(self):
        return float(self.event['event_ts'])

    @classmethod
    async def from_aioslack_event(cls, event, client):
        event = event.copy()

        self = cls(
            event=event,
            client=client,
        )

        if client:
            await self.populate()

        return self

    async def populate(self):
        self.user = await self.client.find_user(self.user_id)
        self.channel = await self.client.find_channel(self.channel_id)

    def __repr__(self):
        cls = self.__class__
        message = self.get('message', {})
        text = message.get('text')

        user = self.user or self.event.get('username') or self.user_id
        channel = self.channel or self.channel_id
        team = self.event.get('team')

        return f'<{cls.__name__} {user}@{channel}.{team} text={text}>'


@attr.s(repr=False)
class SlackMessage(RtmEvent):
    ctx = attr.ib(default=attr.Factory(AttrDict))

    def iter_attachments(self):
        message = self.get('message', {})
        attachments = message.get('attachments', [])
        for attach in attachments:
            yield Attachment(attach)

    def iter_files(self):
        file = self.event.get('file')
        if file:
            yield File(file)

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


@attr.s(repr=False)
class Attachment(utils.ProxyMutableMapping):
    _store = attr.ib()

    def __attrs_post_init__(self):
        utils.ProxyMutableMapping.__init__(self, self._store)

    def _get_generic_uri(self):
        return self.get('from_url')

    def get_uri(self) -> yarl.URL:
        uri = self._get_generic_uri()
        if not uri:
            return

        uri = yarl.URL(uri)
        return uri


@attr.s(repr=False)
class File(utils.ProxyMutableMapping):
    _store = attr.ib()

    def __attrs_post_init__(self):
        utils.ProxyMutableMapping.__init__(self, self._store)

    def _get_image_uri(self):
        return self.get('url_private')

    def get_uri(self) -> yarl.URL:
        uri = self._get_image_uri()
        if not uri:
            return

        uri = yarl.URL(uri)
        return uri


async def ainit(loop):
    log.debug('init')

    global slack_client, mqttc

    slack_client = aioslack.Client(SLACK_API_TOKEN)
    slack_client.on('*')(_on_slack_all)
    slack_client.on('message')(_on_slack_message)

    mqttc = MQTTClient(client_id=log.name, loop=loop)


async def start(loop):
    global slack_client, mqttc

    mqtt_ret = await mqttc.connect('mqtt://localhost/')
    log.debug('mqtt_ret=%s', mqtt_ret)

    m = await mqttc.publish('up', log.name.encode())
    log.debug('m=%s', m)

    s_ret = await slack_client.start_ws_connection()
    log.debug('s_ret=%s', s_ret)


async def _on_slack_all(event):
    """Slack debug handler for all events."""
    log.debug("Event: %s", pf(event))


async def _on_slack_message(event):
    """Slack message faucet."""
    msg = await SlackMessage.from_aioslack_event(event, slack_client)
    log.debug('msg=%s', msg)

    ret = await msg.queue_to_play()
    log.debug('ret=%s', ret)
