"""Configuration."""

import functools
import os
import attr

import uninhibited
import meinconf
from mainline import Catalog

from ledbot import signals, di


class ConfigCatalog(Catalog):
    """Config catalog."""

    @di.provider(scope='global')
    def config():
        config = meinconf.EventfulConfig('ledbot')
        config.configure()
        return config


@signals.early_init.add
def _on_early_init():
    di.update(ConfigCatalog)
