# import logging
# import json
# import collections
# import functools
# import operator
# import sys
import os
import re

# import asyncio
# import asyncio.queues
# import asyncio.locks
# import asyncio.events
# import asyncio.futures
# import asyncio.log
# import aiohttp
# import typing as T

import attr
# import paco
import kawaiisync
# import funcy
# import mpv
import yarl

from . import aioslack

from ..log import get_logger

from .. import utils, debug
from ..utils import AttrDict

from ..debug import pp, pf, see

log = get_logger()

SLACK_API_TOKEN = os.environ['SLACK_API_TOKEN']
slack_client = aioslack.Client(SLACK_API_TOKEN)


@slack_client.on('*')
async def _on_slack_all(event):
    """Slack debug handler for all events."""
    log.debug("Event: %s", pf(event))


@slack_client.on('message')
async def _on_slack_message(event):
    """Slack message faucet."""

    msg = await SlackMessage.from_aioslack_event(event)
    await faucet_q(msg)


RE_URL = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')


"""
Pipeline:
    Slack  ->  Extract  ->  Download  ->  Queue  ->  Play
"""

faucet_q = None
download_q = None
play_q = None


async def init(loop):
    log.debug('init')

    global faucet_q, download_q, play_q
    faucet_q = kawaiisync.BufferedChannel(maxsize=5, loop=loop)
    download_q = kawaiisync.BufferedChannel(maxsize=5, loop=loop)
    play_q = kawaiisync.BufferedChannel(maxsize=5, loop=loop)

    # workers = [
    #    extractor_worker(in_q=faucet_q, loop=loop)
    # ]


async def extractor_worker(loop):
    async for msg in faucet_q:
        log.debug('msg=%s', msg)

        players = await msg.iter_players()
        log.debug('players=%r', players)


@attr.s
class SlackMessage(utils.ProxyMutableMapping):
    event = attr.ib()

    user_id = attr.ib()
    channel_id = attr.ib()
    message = attr.ib()
    attachments = attr.ib(default=attr.Factory(list))

    ctx = attr.ib(default=attr.Factory(AttrDict))

    user = attr.ib(default=None)
    channel = attr.ib(default=None)

    @classmethod
    async def from_aioslack_event(cls, event, client=None):
        self = cls(
            user_id=event.get('user'),
            channel_id=event.get('channel'),

            attachments=event.get('attachments'),

            message=event.get('message'),
        )

        self.ctx.client = client

        if client:
            await self.populate(client)

        return self

    async def populate(self):
        self.user = await self._client.find_user(self.user_id)
        self.channel = await self._client.find_channel(self.channel_id)

    async def iter_players(self):
        log.debug('Finding players in %s', self)

        if not self.attachments:
            return

        players = []

        for attach in self.attachments:
            player = make_player(attach, msg=self)
            if not player:
                continue

            log.debug("Attachment: %r player=%r", attach, player)
            players.append(player)

        return players


@attr.s
class Player:
    uri = attr.ib()

    content = attr.ib(default=None)
    mime_type = attr.ib(default=None)

    is_ready = attr.ib(
        default=False,
        validator=attr.validators.instance_of(bool),
    )

    async def download(self):
        # download
        content = 'fuck'

        mime_type = 'text/plain'

        # done
        self.content = content
        self.mime_type = mime_type


class YoutubePlayer(Player):
    service_names = ['youtube']

    @classmethod
    def is_supported(cls, attachment, msg: SlackMessage):
        service_name = attachment.get('service_name', '').lower()
        if not service_name:
            return False

        return service_name in cls.service_names

    @classmethod
    def from_attachment(cls, attachment, msg: SlackMessage):
        uri = attachment['title_link']
        self = cls(uri=uri)
        return self


class ImagePlayer(Player):

    @classmethod
    def is_supported(cls, attachment, msg: SlackMessage):
        image_uri = attachment.get('image_url')
        return bool(image_uri)

    @classmethod
    def from_attachment(cls, attachment, msg: SlackMessage):
        uri = attachment['image_uri']
        self = cls(uri=uri)
        return self


# Priority
PLAYERS = [YoutubePlayer, ImagePlayer]


def iter_supported_players(attachment, msg: SlackMessage):
    log.debug(f"Finding supported players for attachment={attachment} msg={msg}")
    for factory in PLAYERS:
        if not factory.is_supported(attachment, msg=msg):
            continue
        yield factory


def make_player(attachment, msg: SlackMessage):
    log.debug(f"Making player for attachment={attachment} msg={msg}")
    for factory in iter_supported_players(attachment, msg=msg):
        inst = factory.from_attachment(attachment, msg=msg)
        return inst
