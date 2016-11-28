from ledbot import signals, di
from mainline import Catalog
import uninhibited
import meinconf
import functools
import os


class EventfulConfig(meinconf.Config):
    """Glue to make configuration dynamic by sending events when keys change.
    """

    def __init__(self, *args, **kwargs):
        super(EventfulConfig, self).__init__(*args, **kwargs)
        self.on_change = uninhibited.Event()
        self.on_key_change = uninhibited.Dispatch()

    def __setitem__(self, key, value):
        super(EventfulConfig, self).__setitem__(key, value)
        self.on_change(key, value)
        self.on_key_change.fire(key, key, value)

    def register_key_callback(self, key, handler=None):
        if handler is None:
            return functools.partial(self.register_key_callback, key)

        self.on_key_change[key] += handler

        # Call handler now if we already have this key
        if key in self:
            handler(key, self[key])

        return handler


class ConfigCatalog(Catalog):
    @di.provider(scope='global')
    def config():
        config = EventfulConfig('ledbot')
        config.configure()
        return config


@signals.early_init.add
def _on_early_init():
    di.update(ConfigCatalog)
