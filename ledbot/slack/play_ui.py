import asyncio
import os
import attr
import time
import sys
import glob

import hbmqtt.client
from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import (
    QImage,
    QPalette,
    QPixmap,
    QMovie,
)
from PyQt5.QtWidgets import (
    QApplication,
    QDesktopWidget,
    QMainWindow,
    QLabel,
    QScrollArea,
    QSizePolicy,
)
import quamash

from ..log import get_logger
from .. import utils
from ..debug import pp, pf, see

log = get_logger()


@attr.s
class LedbotUI(QMainWindow):
    window_size = attr.ib(default=(160, 320))
    window_title = attr.ib(default='ledbot')

    scale_factor = attr.ib(default=0.0)

    label = attr.ib(init=False)
    scroll_area = attr.ib(init=False)
    movie = attr.ib(init=False)

    def __attrs_post_init__(self):
        super(LedbotUI, self).__init__()

        self.setWindowTitle(self.window_title)
        self.resize(*self.window_size)

        self.label = self._label_factory()
        self.scroll_area = self._scroll_area_factory(self.label)
        self.setCentralWidget(self.scroll_area)
        self.movie = self._movie_factory()

        self.fit_to_window()

    def _label_factory(self):
        l = QLabel()
        l.setBackgroundRole(QPalette.Base)
        l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        l.setScaledContents(True)
        l.setAutoFillBackground(True)
        return l

    def _scroll_area_factory(self, widget):
        s = QScrollArea()
        s.setBackgroundRole(QPalette.Dark)
        s.setWidget(self.label)
        return s

    def _movie_factory(self):
        movie = QMovie(self)
        movie.setCacheMode(QMovie.CacheAll)
        return movie

    def play(self, filename: str):
        log.info('Play: %s', filename)

        self._play_movie(filename)

        self.scale_factor = 1.0
        self.label.adjustSize()

    def _play_movie(self, filename: str):
        self.movie.stop()
        self.movie.setFileName(filename)
        self.label.setMovie(self.movie)
        self.movie.start()

    def normal_size(self):
        self.scroll_area.setWidgetResizable(False)
        self.label.adjustSize()
        self.scale_factor = 1.0

    def fit_to_window(self):
        self.scroll_area.setWidgetResizable(True)

    def scale_image(self, factor: float=1.0, relative: bool=True):
        if relative:
            factor = self.scale_factor * factor
        self.scale_factor = factor

        native_size = self.label.pixmap().size()
        scaled_size = native_size * self.scale_factor

        self.label.resize(self.scale_factor * self.label.pixmap().size())

    def center_window(self):
        geom = self.frameGeometry()
        desk = QDesktopWidget()
        center = desk.availableGeometry().center()
        geom.moveCenter(center)
        self.move(geom.topLeft())


def init() -> (QApplication, asyncio.AbstractEventLoop):
    app = QApplication([])
    loop = quamash.QEventLoop(app)
    asyncio.set_event_loop(loop)
    return app, loop


async def mqtt_client_loop(loop: asyncio.AbstractEventLoop, ui: LedbotUI):
    client = MQTTClient(loop=loop)
    try:
        await client.connect(
            uri='mqtt://localhost',
        )

        # client.subscribe([
        topics = [
            ('$SYS/broker/uptime', QOS_1),
            ('$SYS/broker/load/#', QOS_2),
            ('play/#', QOS_0),
        ]
        await client.subscribe(topics)

        while True:
            message = await client.deliver_message()
            packet = message.publish_packet
            log.info("[%s] -> %s", packet.variable_header.topic_name, packet.payload.data)

            t = packet.variable_header.topic_name
            if t == 'play/image':
                d = packet.payload.data  # type: bytearray
                d = d.decode()
                ui.play(d)
    finally:
        await client.disconnect()


async def main(app: QApplication, loop: asyncio.AbstractEventLoop):
    ui = LedbotUI()
    ui.show()

    fut = mqtt_client_loop(loop, ui)
    asyncio.ensure_future(fut)

    await asyncio.sleep(10)
    fut.cancel()
    # await demo(ui)

    return ui


async def demo(ui: LedbotUI):
    await asyncio.sleep(0.5)
    images = glob.glob(os.path.expanduser('./images/*.*'))
    for img in images:
        ui.play(img)
        await asyncio.sleep(2)


if __name__ == '__main__':
    app, loop = init()
    fut = main(app, loop)
    with loop:
        loop.run_until_complete(fut)
