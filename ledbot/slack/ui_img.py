import asyncio
import os
import attr
import time

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QMovie
from PyQt5.QtWidgets import (
    QAction, QApplication, QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy
)
from quamash import QEventLoop, QThreadExecutor

from ..log import get_logger
from .. import utils

log = get_logger()



@attr.s
class LedbotUI(QMainWindow):
    scale_factor = attr.ib(default=0.0)

    window_size = attr.ib(default=(160, 320))
    window_title = attr.ib(default='ledbot')

    image_label = attr.ib(default=attr.Factory(
        lambda self: self._image_label_factory(),
        takes_self=True,
    ))

    scroll_area = attr.ib(default=attr.Factory(
        lambda self: self._scroll_area_factory(self.image_label),
        takes_self=True,
    ))

    def _image_label_factory(self):
        l = QLabel()
        l.setBackgroundRole(QPalette.Base)
        l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        l.setScaledContents(True)
        return l

    def _scroll_area_factory(self, widget):
        s = QScrollArea()
        s.setBackgroundRole(QPalette.Dark)
        s.setWidget(self.image_label)
        return s

    def __attrs_post_init__(self):
        super(LedbotUI, self).__init__()

        self.setWindowTitle(self.window_title)
        self.resize(*self.window_size)

        self.setCentralWidget(self.scroll_area)

        self.fit_to_window()

    def image(self, filename: str, is_animation: bool=None):
        if is_animation is None:
            _, ext = os.path.splitext(filename)
            is_animation = ext.lower() in ['.gif']

        log.info('Image: %s is_animation=%s', filename, is_animation)

        if is_animation:
            movie = QMovie(filename)
            self.image_label.setMovie(movie)
            movie.start()
        else:
            image = QImage(filename)
            if image.isNull():
                log.error('Could not load image=%s', filename)
                raise ValueError(filename)
            self.image_label.setPixmap(QPixmap.fromImage(image))

        self.scale_factor = 1.0
        self.image_label.adjustSize()

    def scale_to_normal_size(self):
        self.scroll_area.setWidgetResizable(False)
        self.image_label.adjustSize()
        self.scale_factor = 1.0

    def scale_to_fit_window(self):
        self.scroll_area.setWidgetResizable(True)

    def scale_image(self, factor: float=1.0, relative: bool=True):
        if relative:
            factor = self.scale_factor * factor
        self.scale_factor = factor

        native_size = self.image_label.pixmap().size()
        scaled_size = native_size * self.scale_factor
        self.image_label.resize(self.scale_factor * self.image_label.pixmap().size())


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    ui = LedbotUI()
    ui.show()

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop) # NEW must set the event loop

    async def run(app: QApplication, loop: asyncio.AbstractEventLoop):
        import glob

        images = glob.glob(os.path.expanduser('./images/*.*'))
        for img in images:
            log.info('img=%s', img)
            ui.image(img)
            await asyncio.sleep(2)

    with loop:
        fut = run(app, loop)
        loop.run_until_complete(fut)

