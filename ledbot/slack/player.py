max_size = (1024**3) * 4

play_queue = asyncio.Queue()


class QItem(collections.namedtuple('QItem', ['uri'])):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class QImage(QItem):
    pass


class QVideo(QItem):
    pass


async def handle_url(event, uri):
    log.debug('Image uri=%s', uri)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:  # type: aiohttp.ClientResponse
            resp.raise_for_status()

            if resp.content_type not in handled_mimes:
                log.error('URL did not contain a handled mimetype: type=%s url=%s', resp.content_type, url)
                raise ValueError(resp.content_type)

            if resp.content_length > max_size:
                log.error('Image size is too large: %s url=%s', resp.content_length, url)
                raise OverflowError(resp.content_length)

            content = resp.read()
            await handle_image(event, content)


async def handle_video(event, uri):
    log.debug('Video uri=%s', uri)


async def handle_image(event, uri):
    log.debug('Image uri=%s', uri)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:  # type: aiohttp.ClientResponse
            resp.raise_for_status()
            await play_image(resp)


async def play_image(resp):
    content = resp.read()
    log.debug('Playing image bytes=%d', len(content))


handled_mimes = [
    'image/png',
    'image/jpeg',
    'image/gif',
]
