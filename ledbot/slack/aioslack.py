"""Blah"""

import asyncio
import types
import collections
import itertools
import json
import time
import uuid
import weakref
import typing as T

import aiohttp
import websockets
import attr
import aiorwlock
from rwlock.rwlock import RWLock

from functools import singledispatch

from ..debug import pp, pf, see
from .. import log, utils

log = log.get_logger()

_sentinel = object()


class StateItem(utils.AttrDict):
    def __repr__(self):
        return '<%s id=%s name=%s>' % (self.__class__.__name__, self.id, self.name)

    def __key(self):
        return (self.get('id'), self.get('name'))

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __hash__(self):
        return hash(self.__key())


class Channel(StateItem):
    pass


class User(StateItem):
    pass


@attr.s
class ProxyMutableSet(collections.MutableSet):
    _store: collections.MutableSet = attr.ib(default=attr.Factory(set))

    def __contains__(self, item):
        return item in self._store

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def add(self, value):
        self._store.add(value)

    def discard(self, value):
        self._store.discard(value)

    def update(self, iterable):
        """Add all values from an iterable (such as a list or file)."""
        [self.add(x) for x in iterable]


@attr.s
class TimedValueSet(ProxyMutableSet):
    """
    Set that tracks the time a value was added.
    """

    _added_at = attr.ib(default=attr.Factory(weakref.WeakKeyDictionary))

    def add(self, value):
        ret = super().add(value)
        self.touch(value)
        return ret

    def discard(self, value):
        ret = super().discard(value)
        if value in self._added_at:
            del self._added_at[value]

    def touch(self, value, ts=time.time):
        if callable(ts):
            ts = ts()
        self._added_at[value] = ts

    def added_at(self, value, default=None):
        ret = self._added_at.get(value, _sentinel)
        if ret is _sentinel:
            ret = default
        return ret


# class AttrIndexedIterable(utils.ProxyMutableMapping):
#     index_attrs = attr.ib(validator=attr.validators.instance_of(collections.Iterable))
#     indexes: T.Mapping[T.AnyStr, T.Any] = attr.ib(default=attr.Factory(dict))


@attr.s(repr=False)
class StateMapping(TimedValueSet):
    _parent = attr.ib(default=None)

    id_map = attr.ib(default=attr.Factory(weakref.WeakValueDictionary))
    name_map = attr.ib(default=attr.Factory(weakref.WeakValueDictionary))

    keys = attr.ib(default=['name', 'id'])

    _lock = attr.ib(default=attr.Factory(RWLock))

    def __getitem__(self, item):
        # TODO Re-populate every so often
        # TODO Re-populate on KeyError if staleness is sane
        with self._lock.reader_lock:
            try:
                return self.id_map[item]
            except KeyError:
                return self.name_map[item]

    def add(self, v):
        with self._lock.writer_lock:
            super().add(v)
            self.id_map[v.id] = v
            self.name_map[v.name] = v

    def discard(self, v):
        with self._lock.reader_lock:
            del self.id_map[v.id]
            del self.name_map[v.name]
            super().discard(v)

    _pop_lock = attr.ib(default=attr.Factory(
        lambda self: asyncio.Lock(loop=self._parent.client.loop),
        takes_self=True,
    ))

    def __repr__(self):
        return '<%s count=%d>' % (self.__class__.__name__, len(self))



@attr.s(repr=False)
class ChannelsMapping(StateMapping):

    async def populate(self, r_channels=None):
        just_waiting = False
        if self._pop_lock.locked():
            just_waiting = True

        async with self._pop_lock:
            if just_waiting:
                return

            client = self._parent.client

            log.info('Populating %s state', self)
            if r_channels is None:
                r_channels = await client.get("channels.list", callback=lambda response: response['channels'])
            for r_chan in r_channels:
                chan = Channel(r_chan)
                self.add(chan)


@attr.s(repr=False)
class UsersMapping(StateMapping):

    async def populate(self, r_members=None):
        just_waiting = False
        if self._pop_lock.locked():
            just_waiting = True

        async with self._pop_lock:
            if just_waiting:
                return

            client = self._parent.client

            if r_members is None:
                r_members = await client.get("users.list", callback=lambda response: response['members'])
            for r_user in r_members:
                user = User(r_user)
                self.add(user)

            log.info('Populated %r state: count=%d', self.__class__, len(self))


@attr.s()
class State:
    client = attr.ib()

    channels = attr.ib(default=attr.Factory(
        lambda self: ChannelsMapping(parent=self),
        takes_self=True,
    ))

    users = attr.ib(default=attr.Factory(
        lambda self: UsersMapping(parent=self),
        takes_self=True,
    ))

    async def populate(self, r_channels=None, r_members=None):
        await asyncio.gather(
            self.channels.populate(r_channels=r_channels),
            self.users.populate(r_members=r_members),
        )


@attr.s(repr=False)
class Client:
    PRODUCER_DELAY = 0.5
    BASE_URI = 'https://slack.com/api'

    token = attr.ib()
    handlers = attr.ib(default=attr.Factory(
        lambda: collections.defaultdict(list),
    ))
    requests = attr.ib(default=attr.Factory(list))
    producers = attr.ib(default=attr.Factory(
        lambda self: itertools.cycle(self.requests),
        takes_self=True,
    ))

    state = attr.ib(default=attr.Factory(
        lambda self: State(self),
        takes_self=True,
    ))

    loop = attr.ib(default=attr.Factory(asyncio.get_event_loop))

    def on(self, event, **options):

        def _decorator(callback):
            self.handlers[event].append(callback)
            return callback

        return _decorator

    def unregister(self, event_type, callback):
        self.handlers[event_type].remove(callback)

    def send_forever(self, request):
        self.requests.append(request)

    async def find_channel(self, channel_name):
        try:
            return self.state.channels[channel_name]
        except KeyError:
            pass

    async def find_user(self, user_name):
        try:
            return self.state.users[user_name]
        except KeyError:
            pass

    async def get(self, path, extraParams={}, extraHeaders={}, callback=None):

        async def get_request(session, headers, params):
            async with session.get('{}/{}'.format(self.BASE_URI, path), headers=headers, params=params) as resp:
                return await self.handle_http_response(resp, path, callback)

        return await self.make_http_request(get_request, extraParams, extraHeaders)

    async def post(self, path, extraData={}, extraHeaders={}, callback=None):

        async def post_request(session, headers, data):
            async with session.post('{}/{}'.format(self.BASE_URI, path), headers=headers, data=data) as resp:
                return await self.handle_http_response(resp, path, callback)

        return await self.make_http_request(post_request, extraData, extraHeaders)

    @utils.lazyproperty
    def session(self):
        return aiohttp.ClientSession()

    async def start(self):
        log.info("Connecting to Slack websocket API. base_uri=%s", self.BASE_URI)

    async def start_ws_connection(self):

        def retrieve(data):
            return (data["url"], data["channels"], data["users"])

        log.info('handshaking rtm.start')
        url, r_channels, r_members = await self.post("rtm.start", callback=retrieve)

        await self.state.populate(r_channels=r_channels, r_members=r_members)

        log.info('connecting to websocket url=%s', url)
        async with websockets.connect(url) as websocket:
            log.info('initializing websocket url=%s', url)
            await self.ws_server_loop(websocket)

    async def make_http_request(self, request, extraData={}, extraHeaders={}):
        headers = {'user-agent': 'slackclient/12 Python/3.6.0 Darwin/15.5.0', **extraHeaders}
        data = {'token': self.token, **extraData}

        async with aiohttp.ClientSession() as session:
            return await request(session, headers, data)

    async def handle_http_response(self, resp, req_name, callback=None):
        resp.raise_for_status()

        data = await resp.json()
        if not data['ok']:
            raise ValueError('Response did not contain "ok" field. req_name=%s' % req_name)

        if callback:
            return callback(data)

        return data

    async def ws_server_loop(self, websocket):
        tasks = collections.defaultdict()

        while True:
            if 'listener' not in tasks:
                tasks['listener'] = asyncio.ensure_future(websocket.recv())

            if 'producer' not in tasks and self.requests:
                tasks['producer'] = asyncio.ensure_future(self.producer())

            done, pending = await asyncio.wait(
                tasks.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            if tasks.get('listener') in done:
                message = tasks['listener'].result()
                del tasks['listener']

                await self.consumer(message)

            if tasks.get('producer') in done:
                message = tasks['producer'].result()
                del tasks['producer']

                if message:
                    await websocket.send(message)

            if len(done) == len(tasks):
                time.sleep(0.1)

    async def consumer(self, message):
        jsonified = json.loads(message)
        log.info('received {}'.format(jsonified["type"]))
        for handler in itertools.chain(self.handlers[jsonified['type']], self.handlers['*']):
            asyncio.ensure_future(handler(jsonified))

    async def producer(self):
        time.sleep(self.PRODUCER_DELAY)
        data = await self.retrieve_data(self.producers.__next__())
        if data:
            return json.dumps({"id": uuid.uuid4().int, **data})

    @singledispatch
    async def retrieve_data(producer):
        log.warn("Unknown producer type. Skipping...")

    @retrieve_data.register(dict)
    async def _(producer):
        return producer

    @retrieve_data.register(types.FunctionType)
    async def _(producer):
        return await producer()
