#!/usr/bin/env python3

from . import ui_mpv


def init():
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def main():
    log.info("begin")

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    fut = ui_mpv.ainit(loop)
    loop.run_until_complete(fut)

    fut = ui_mpv.main(loop)
    loop.run_until_complete(fut)

    loop.close()


if __name__ == "__main__":
    init()
    main()
