from ._version import __version__  # NOQA

# Only YOU can prevent namespace pollution fires.
import uninhibited as _uninhibited

# Package signals
signals = _uninhibited.Dispatch([
    # package
    'early_init', 'init',
    # http
    'startup', 'cleanup', 'shutdown',
])

from .injection import di  # NOQA

# Import anything that attaches to `on_early_init`
# Configuration and logger setup is our top priority
from . import configuration, log  # NOQA

# Eawly init is where gross things go to be initialized. Don't be gross.
# from ledbot import configuration, log, _gross
signals.fire('early_init')

# Run on_init. This is where any package initialization is done.
# from ledbot import db, plugins
signals.fire('init')

