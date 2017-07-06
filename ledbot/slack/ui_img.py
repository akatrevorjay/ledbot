import asyncio
import os
import attr
import time
import sys
import glob

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QMovie
from PyQt5.QtWidgets import (
    QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy
)
import quamash

from ..log import get_logger
from .. import utils

log = get_logger()


@attr.s
class LedbotUI(QMainWindow):
    scale_factor = attr.ib(default=0.0)

    window_size = attr.ib(default=(160, 320))
    window_title = attr.ib(default='ledbot')

    _fake_hack_init = attr.ib(default=attr.Factory(
        lambda self: self._fake_hack_init_factory(),
        takes_self=True,
    ))

    def _fake_hack_init_factory(self):
        """I didn't ask for your judgement."""
        super(LedbotUI, self).__init__()

    image_label = attr.ib(default=attr.Factory(
        lambda self: self._image_label_factory(),
        takes_self=True,
    ))

    scroll_area = attr.ib(default=attr.Factory(
        lambda self: self._scroll_area_factory(self.image_label),
        takes_self=True,
    ))

    movie = attr.ib(default=attr.Factory(
        lambda self: self._movie_factory(),
        takes_self=True,
    ))

    def _image_label_factory(self):
        l = QLabel()
        l.setBackgroundRole(QPalette.Base)
        l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        l.setScaledContents(True)
        l.setAutoFillBackground(True)
        return l

    def _scroll_area_factory(self, widget):
        s = QScrollArea()
        s.setBackgroundRole(QPalette.Dark)
        s.setWidget(self.image_label)
        return s

    def _movie_factory(self):
        movie = QMovie(self)
        movie.setCacheMode(QMovie.CacheAll)
        return movie

    def __attrs_post_init__(self):
        self.setWindowTitle(self.window_title)
        self.resize(*self.window_size)

        self.setCentralWidget(self.scroll_area)

        self.fit_to_window()

    def play(self, filename: str):
        log.info('Play: %s', filename)

        _, ext = os.path.splitext(filename)
        is_animation = ext.lower() in ['.gif']
        is_animation = True

        if is_animation:
            self.play_movie(filename)
        else:
            self.play_image(filename)

        self.scale_factor = 1.0
        self.image_label.adjustSize()

    def play_image(self, filename: str):
        log.info('Play image: %s', filename)
        self.movie.stop()

        image = QImage(filename)
        if image.isNull():
            log.error('Could not load image=%s', filename)
            raise ValueError(filename)
        pixmap = QPixmap.fromImage(image)

        self.image_label.setPixmap(pixmap)

    def play_movie(self, filename: str):
        log.info('Play movie: %s', filename)
        self.movie.stop()

        self.movie.setFileName(filename)

        self.image_label.setMovie(self.movie)
        self.movie.start()

    def normal_size(self):
        self.scroll_area.setWidgetResizable(False)
        self.image_label.adjustSize()
        self.scale_factor = 1.0

    def fit_to_window(self):
        self.scroll_area.setWidgetResizable(True)

    def scale_image(self, factor: float=1.0, relative: bool=True):
        if relative:
            factor = self.scale_factor * factor
        self.scale_factor = factor

        native_size = self.image_label.pixmap().size()
        scaled_size = native_size * self.scale_factor

        self.image_label.resize(self.scale_factor * self.image_label.pixmap().size())


def init() -> (QApplication, asyncio.AbstractEventLoop):
    app = QApplication([])
    loop = quamash.QEventLoop(app)
    asyncio.set_event_loop(loop)
    return app, loop


async def main(app: QApplication, loop: asyncio.AbstractEventLoop):
    ui = LedbotUI()
    ui.show()

    await demo(ui)

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
