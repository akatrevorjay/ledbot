
from . import di, utils


@di.inject('config')
def set_service_name(config, title=None, base='ledbot'):
    if not title:
        title = utils._namespace_from_calling_context()

    parts = [base, title]
    parts = [p for p in parts if p]
    title = '.'.join(parts)

    config.SERVICE_NAME = title
    utils.set_proc_title(title, base=None)

