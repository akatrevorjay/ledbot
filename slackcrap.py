import asyncio
import json
import os
import re

import slack_sage
from slack_sage import handlers, bot

import aiohttp

import asyncio.queues
import asyncio.locks
import asyncio.events
import asyncio.futures
import asyncio.log


# Create bot instance
bot = bot.SlackSage(os.environ['SLACK_API_TOKEN'])


class AiohttpMixin:
    session = aiohttp.ClientSession()

    async def _request(self, method, url, **kwargs):
        async with getattr(self.session, method)(url, **kwargs) as resp:
            return await resp.text()

    async def get(self, url, **kwargs):
        return await self._request("get", url, **kwargs)


class ImageHandler(handlers.AllChannelsHandler):
    trigger_messages = [r"https?://[^\s]+\.(jpg|png|gif|jpeg|svg|webp)"]

    async def process(self):
        if todos.get(self.message.user.user_id) is None:
            todos[self.message.user.user_id] = []

        user_todos = todos[self.message.user.user_id]
        new_task = self.message.text
        user_todos.append(new_task)

        await self.message.channel.post_message(
            "Hey! I add <{task}> as task. There are {tasks_count} in your list.".format(
                task=new_task, tasks_count=len(user_todos)
            )
        )


def main():
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(bot.run())
    loop.close()


if __name__ == '__main__':
    main()
