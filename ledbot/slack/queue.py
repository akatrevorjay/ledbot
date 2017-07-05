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

# import asyncio
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


@slack_client.on('file_shared')
async def _on_slack_message(event):
    """Slack file faucet."""
    """
    {'event_ts': '1499153563.056233',
    'file': {'id': 'F63F10Z6W'},
    'file_id': 'F63F10Z6W',
    'ts': '1499153563.056233',
    'type': 'file_shared',
    'user_id': 'U28T1J8GH'}
    """

    msg = await SlackMessage.from_aioslack_event(event, slack_client)
    await faucet_q(msg)


@slack_client.on('message')
async def _on_slack_message(event):
    """Slack message faucet."""

    msg = await SlackMessage.from_aioslack_event(event, slack_client)
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

    async def _work(msg: SlackMessage):
        log.debug('msg=%s', msg)

        await msg.play()

    async for msg in faucet_q:
        try:
            await _work(msg)
        except Exception:
            log.exception('Well fuck')


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
        text = self.get('text')

        user = self.user or self.event.get('username') or self.user_id
        channel = self.channel or self.channel_id
        team = self.event.get('team')

        return f'<{cls.__name__} {user}@{channel}.{team} text={text}>'


@attr.s(repr=False)
class SlackMessage(RtmEvent):
    ctx = attr.ib(default=attr.Factory(AttrDict))

    def iter_attachments(self):
        message = self.event.get('message', {})
        attachments = message.get('attachments', [])
        for attach in attachments:
            yield Attachment(attach)

    def iter_files(self):
        file = self.event.get('file')
        if file:
            yield File(file)

    async def play(self):
        for attach in itertools.chain(self.iter_files(), self.iter_attachments()):
            player = make_player(attach, msg=self)
            if not player:
                continue

            log.debug("Attachment: %r player=%r", attach, player)

            await attach.download()

            log.debug('I would play now')
            break


@attr.s
class Downloadable(utils.ProxyMutableMapping, metaclass=abc.ABCMeta):
    _store = attr.ib(repr=False)

    content: str = attr.ib(default=None, repr=False)
    content_type: str = attr.ib(default=None)
    content_length: int = attr.ib(default=None)
    is_downloaded: bool = attr.ib(validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        utils.ProxyMutableMapping.__init__(self, self._store)

    @abc.abstractproperty
    def uri(self) -> yarl.URL:
        pass

    @property
    def is_downloaded(self):
        return self.content is not None

    @utils.lazyclassproperty
    def _session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()

    async def download(self, session: aiohttp.ClientSession=None):
        if session is None:
            session = self._session

        log.info('Downloading %s', self)

        async with session.get(self.uri) as resp:  # type: aiohttp.ClientResponse
            resp.raise_for_status()

            # TODO Check content_length
            self.content = await resp.read()
            self.content_length = resp.content_length
            self.content_type = resp.content_type

        log.info('Downloaded %s', self)


@attr.s
class Attachment(Downloadable, utils.AttrDict):

    @utils.lazyproperty
    def uri(self) -> yarl.URL:
        uri = self.get('image_url')
        if not uri:
            return

        uri = yarl.URL(uri)
        return uri


@attr.s
class File(utils.AttrDict, Downloadable):

    @utils.lazyproperty
    def uri(self) -> yarl.URL:
        uri = self.get('url_private')
        if not uri:
            return

        uri = yarl.URL(uri)
        return uri


@attr.s
class Player:
    uri = attr.ib()


class YoutubePlayer(Player):
    service_names = ['youtube']

    @classmethod
    def is_supported(cls, attachment, msg: SlackMessage) -> bool:
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
    def is_supported(cls, attachment, msg: SlackMessage) -> bool:
        image_uri = attachment.get('image_url')
        return bool(image_uri)

    @classmethod
    def from_attachment(cls, attachment, msg: SlackMessage):
        uri = attachment['image_url']
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
