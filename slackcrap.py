import logging
import json
import os
import re

import asyncio
import asyncio.queues
import asyncio.locks
import asyncio.events
import asyncio.futures
import asyncio.log

import aiohttp

import slack_sage
from slack_sage import handlers, bot


log = logging.getLogger(__name__)

# Create bot instance
bot = bot.SlackSage(os.environ['SLACK_API_TOKEN'])


RE_URL = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'


# class ImageHandler(handlers.AllChannelsHandler):
class ImageHandler(handlers.DirectMessageHandler):
    trigger_messages = [RE_URL]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = aiohttp.ClientSession()

    async def process(self):
        msg = self.message

        log.info('Triggered: %s', msg)

        urls = re.findall(RE_URL, msg.text)

        for url in urls:
            try:
                await self.handle_url(msg, url)
            except Exception as exc:
                continue

    handled_mimes = [
        'image/png',
        'image/jpeg',
    ]

    max_size = (1024 ** 3) * 4

    async def handle_url(self, msg, url):
        async with self.session.get(url) as resp:  # type: aiohttp.ClientResponse
            resp.raise_for_status()

            if resp.content_type not in self.handled_mimes:
                log.error('URL did not contain a handled mimetype: type=%s url=%s', resp.content_type, url)
                raise ValueError(resp.content_type)

            if resp.content_length > self.max_size:
                log.error('Image size is too large: %s url=%s', resp.content_length, url)
                raise OverflowError(resp.content_length)

            content = resp.read()
            await self.handle_image(content)

    async def handle_image(self, msg, image):
        pass



def main():
    logging.basicConfig(level=logging.DEBUG)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(bot.run())
    loop.close()


if __name__ == '__main__':
    main()
