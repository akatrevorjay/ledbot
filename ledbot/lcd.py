import asyncio


def scroller():
    x = random.randint(0, int(64 * 2.5))
    y = 10
    text.write('http://ledpi', x=x, y=y, font='fonts/7x13.bdf')


async def idler(app):
    log.info('Idler')
    try:
        while True:
            log.info('Idling')
            await app.loop.run_in_executor(None, scroller)
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    finally:
        log.info('Done with idler')

