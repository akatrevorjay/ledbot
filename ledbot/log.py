from ledbot import signals, di
import logging
import logging.config
import inspect


def _namespace_from_calling_context():
    """
    Derive a namespace from the module containing the caller's caller.

    :return: the fully qualified python name of a module.
    :rtype: str
    """
    return inspect.currentframe().f_back.f_back.f_globals['__name__']


def get_logger(name=None):
    if not name:
        name = _namespace_from_calling_context()

    return logging.getLogger(name)


@signals.early_init.add
@di.inject('config')
def _on_early_init(config):

    @config.register_key_callback('LOGGING')
    def _configure(key, value):
        logging.config.dictConfig(value)
