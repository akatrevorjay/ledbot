@attr.s
class UrlExtractor:
    re_url = attr.ib(default=RE_URL)  # type: re._pattern_type

    in_q = attr.ib(default=attr.Factory(asyncio.Queue))  # type: asyncio.Queue

    #in_c = attr.ib(default=attr.Factory(Chan))  # type: Chan
    async def put(self, msg: SlackMessage):
        if not msg.message or not msg.attachments:
            log.debug("SKipping msg: %r", msg)
            return

        await self.in_q.put(msg)

    async def consumer(self):
        # async for msg in self.in_c:
        async for msg in self.in_q:

            res = await self.process(msg)

    async def process(self, msg):
        for attach in msg.attachments:
            service_name = attach.get('service_name')

            if service_name in ['YouTube']:
                video_uri = attach['title_link']
                # return await handle_video(event, uri)

            image_uri = attach.get('image_url')
            # if image_uri:
            #     return await handle_image(event, uri)

        # async def slack_extractor(q=url_q):
        #     async for

        # async def download_urls(urls: t.List[URL])
