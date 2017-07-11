import os

from .utils import AttrDict
from . import __version__

APP_NAME = 'ledbot'
APP_DESC = '{name}/{version}'.format(name=APP_NAME, version=__version__)
PACKAGE_PATH = os.path.dirname(__file__)

SERVICE_NAME = None

DEBUG = False
PROFILING = False
TESTING = False
DEBUG_AUTORELOAD = True

BIND = '127.0.0.1:8080'

LOGGING = {
    'version': 1,
    # 'disable_existing_loggers': False,
    # 'incremental': True,
    'formatters':
        {
            'standard':
                {
                    '()': 'colorlog.ColoredFormatter',
                    'format':
                        '%(bg_black)s%(log_color)s'
                        '[%(asctime)s] '
                        '[%(name)s/%(process)d] '
                        '%(message)s '
                        '%(blue)s@%(funcName)s:%(lineno)d '
                        '#%(levelname)s'
                        '%(reset)s',
                    'datefmt': '%H:%M:%S',
                },
            'simple':
                {
                    'format':
                        '%(asctime)s| %(name)s/%(processName)s[%(process)d]-%(threadName)s[%(thread)d]: '
                        '%(message)s @%(funcName)s:%(lineno)d #%(levelname)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                },
        },
    'handlers':
        {
            'console': {
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
            # 'logfile': {
            #     'formatter': 'standard',
            #     'class': 'logging.FileHandler',
            #     'filename': 'var/%s.log' % APP_NAME,
            # },
        },
    'root': {
        'handlers': ['console'],
        # 'level': 'INFO',
        'level': 'DEBUG',
    },
    'loggers': {
        # 'ledbot': dict(level='DEBUG', propogate=True),
        'hbmqtt': dict(level='INFO', propogate=True),
        'websockets': dict(level='INFO', propogate=True),
    }
}

MQTT_URL = 'mqtt://localhost/'

MPV_VO_DRIVER = 'opengl'

PLAYER_GEOMETRY = (160, 320)
