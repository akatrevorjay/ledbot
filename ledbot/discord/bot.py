import asyncio
import itertools

import six
import attr
import yarl
import discord
from typing import Optional

from .. import di, utils
from ..log import get_logger
from ..debug import pp, pf, see

from .queue import queue_to_play

log = get_logger()


class LedbotDiscordClient(discord.Client):
    async def on_ready(self):
        log.info(f"logged in as user={self.user!r}")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            # don't respond to ourselves
            return

        if message.content == 'ping':
            await message.channel.send('pong')
            return

        log.info(f"got message: {message.author}: {message.content}")

        uri: Optional[str] = None

        if message.content.startswith('http'):
            # This does better uri checking
            uri = message.content

        elif message.attachments:
            for attachment in message.attachments:
                # if attachment.content_type.startswith('image'):
                if attachment.url:
                    uri = attachment.url

        if uri:
            await queue_to_play(uri)

            # add heart on message that was sent
            emoji = '👀'
            await message.add_reaction(emoji)
            return


@di.inject('config')
def discord_client_factory(config):
    log.info('Creating Discord client')

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.messages = True

    client = LedbotDiscordClient(intents=intents)

    return client

di.register_factory(LedbotDiscordClient, discord_client_factory, scope='global')


@di.inject('config', LedbotDiscordClient)
async def run(config, client: LedbotDiscordClient, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    log.debug('Connecting to Discord')
    await client.start(config.DISCORD_TOKEN)

