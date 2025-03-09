import attr
import typing
import random
import sys
import six
import operator
import wrapt
import cachetools
import cachetools.func
import collections
import time
import itertools
import functools
import warnings
import weakref

from six.moves.urllib_parse import urlsplit, parse_qs, urlunsplit, urlencode

from .log import get_logger

_log = get_logger()

_sentinel = object()
_default = []  # evaluates to False

IS_PYPY = '__pypy__' in sys.builtin_module_names


def _get_object_init():
    if six.PY3 or IS_PYPY:
        return six.get_unbound_function(object.__init__)


OBJECT_INIT = _get_object_init()


class ProxyMutableMapping(typing.MutableMapping):
    """Proxies an existing Mapping."""

    def __init__(self, mapping):
        self.__mapping = mapping

    _fancy_repr = True

    def __repr__(self):
        if self._fancy_repr:
            return '<%s %s>' % (self.__class__.__name__, self.__mapping)
        else:
            return '%s' % dict(self)

    def __contains__(self, item):
        return item in self.__mapping

    def __getitem__(self, item):
        return self.__mapping[item]

    def __setitem__(self, key, value):
        self.__mapping[key] = value

    def __delitem__(self, key):
        del self.__mapping[key]

    def __iter__(self):
        return iter(self.__mapping)

    def __len__(self):
        return len(self.__mapping)


class MissingProxyMutableMapping(ProxyMutableMapping):

    def __getitem__(self, item):
        try:
            return super(MissingProxyMutableMapping, self).__getitem__(item)
        except KeyError:
            return self.__missing__(item)

    def __missing__(self, item):
        raise KeyError(item)


@attr.s
class ProxyMutableSet(typing.MutableSet):
    """Proxies an existing set-like object."""

    _store: typing.MutableSet = attr.ib(default=attr.Factory(set))

    def __contains__(self, item):
        return item in self._store

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def add(self, value):
        self._store.add(value)

    def discard(self, value):
        self._store.discard(value)

    def update(self, iterable):
        """Add all values from an iterable (such as a list or file)."""
        [self.add(x) for x in iterable]


@attr.s
class TimedValueSet(ProxyMutableSet):
    """
    Set that tracks the time a value was added.
    """

    _added_at = attr.ib(default=attr.Factory(weakref.WeakKeyDictionary))

    def add(self, value):
        ret = super().add(value)
        self.touch(value)
        return ret

    def discard(self, value):
        ret = super().discard(value)
        if value in self._added_at:
            del self._added_at[value]

    def touch(self, value, ts=time.time):
        if callable(ts):
            ts = ts()
        self._added_at[value] = ts

    def added_at(self, value, default=None):
        ret = self._added_at.get(value, _sentinel)
        if ret is _sentinel:
            ret = default
        return ret


def set_proc_title(title=None, base='ledbot'):
    import setproctitle

    if not title:
        title = namespace_from_calling_context()

    parts = [base, title]
    parts = [p for p in parts if p]
    title = '.'.join(parts)

    setproctitle.setproctitle(title)


def set_query_params(url, **kwargs):
    """
    Set or replace query parameters in a URL.

    >>> set_query_parameter('http://example.com?foo=bar&biz=baz', foo='stuff')
    'http://example.com?foo=stuff&biz=baz'

    :param url: URL
    :type url: str
    :param kwargs: Query parameters
    :type kwargs: dict
    :return: Modified URL
    :rtype: str
    """

    scheme, netloc, path, query_string, fragment = urlsplit(url)
    query_params = parse_qs(query_string)

    query_params.populate(kwargs)
    new_query_string = urlencode(query_params, doseq=True)

    return urlunsplit((scheme, netloc, path, new_query_string, fragment))


def ensure_encoded_bytes(s, encoding='utf-8', errors='strict', allowed_types=(bytes, bytearray, memoryview)):
    """
    Ensure string is encoded as byteslike; convert using specified parameters if we have to.

    :param str|bytes|bytesarray|memoryview s: string/byteslike
    :param str encoding: Decode using this encoding
    :param str errors: How to handle errors
    :return bytes|bytesarray|memoryview: Encoded string as str
    """
    if isinstance(s, allowed_types):
        return s
    else:
        return s.encode(encoding=encoding, errors=errors)


def ensure_decoded_text(s, encoding='utf-8', errors='strict', allowed_types=(six.text_type,)):
    """
    Ensure string is decoded (eg unicode); convert using specified parameters if we have to.

    :param str|bytes|bytesarray|memoryview s: string/bytes
    :param str encoding: Decode using this encoding
    :param str errors: How to handle errors
    :return bytes|bytesarray|memoryview: Decoded string as bytes

    :return: Encoded string
    :rtype: bytes
    """
    if not isinstance(s, allowed_types):
        return s.decode(encoding=encoding, errors=errors)
    else:
        return s


def accumulate(iterable, func=operator.add):
    """
    Iterate over running totals, ie [a,b,c,d] -> func( func( func(a, b), c), d) with each func result yielded.
    Func is operator.add by default.

    >>> list(accumulate([1,2,3,4,5]))
    [1, 3, 6, 10, 15]
    >>> list(accumulate([1,2,3,4,5], operator.mul))
    [1, 2, 6, 24, 120]

    :param iterable: Iterable
    :param func: method (default=operator.add) to call for each pair of (last call result or first item, next item)
    :return generator: Generator
    """
    it = iter(iterable)
    try:
        total = next(it)
    except StopIteration:
        return
    yield total
    for element in it:
        total = func(total, element)
        yield total


def consume(iterator, n=None):
    """
    Efficiently advance an iterator n-steps ahead. If n is none, consume entirely.
    Consumes at C level (and therefore speed) in cpython.
    """
    if n is None:
        # feed the entire iterator into a zero-length deque
        collections.deque(iterator, maxlen=0)
    else:
        # advance to the empty slice starting at position n
        next(itertools.islice(iterator, n, n), None)


def dedupe_iter(iterator):
    """"
    Deduplicates an iterator iteratively using a set.
    Not exactly memory efficient because of that of course.
    If you have a large dataset with high cardinality look HyperLogLog instead.

    :return generator: Iterator of deduplicated results.
    """
    done = set()
    for item in iterator:
        if item in done:
            continue
        done.add(item)
        yield item


@wrapt.decorator
def dedupe(f, instance, args, kwargs):
    """
    Decorator to dedupe it's output iterable automatically.

    :param f: Wrapped meth
    :param instance: wrapt provided property for decorating hydrated class instances (unused)
    :param args: Passthrough args
    :param kwargs: Passthrough kwargs
    :return decorator: Decorator method that ingests iterables and dedupes them iteratively.
    """
    gen = f(*args, **kwargs)
    return dedupe_iter(gen)


def pycharm_workaround_multiprocessing():
    """
    Workaround PyCharm stupidity where stdin is missing a close method.
    """
    if not hasattr(sys.stdin, 'close'):

        def dummy_close():
            pass

        sys.stdin.close = dummy_close


def rand_hex(length=8):
    """
    Create a random hex string of a specific length performantly.

    :param int length: length of hex string to generate
    :return: random hex string
    """
    return '%0{}x'.format(length) % random.randrange(16**length)


# This is cached because tldextract is SLOW
@cachetools.func.ttl_cache(maxsize=1024, ttl=600)
def split_domain_into_subdomains(domain, split_tld=False):
    if not hasattr(split_domain_into_subdomains, '_tldex'):
        import tldextract
        # Do not request latest TLS list on init == suffix_list_url=False
        split_domain_into_subdomains._tldex = tldextract.TLDExtract(suffix_list_url=False)
    _tldex = split_domain_into_subdomains._tldex

    # Requires unicode
    domain = ensure_decoded_text(domain)

    tx = _tldex(domain)

    domains = []
    if tx.subdomain:
        domains.extend(tx.subdomain.split('.'))

    # tx.registered_domain returns only if domain AND suffix are not none
    # There are cases where we have domain and not suffix; ie short hostnames
    registered_domain = [tx.domain]
    if tx.suffix:
        registered_domain.append(tx.suffix)

    if split_tld:
        domains.extend(registered_domain)
    else:
        domains.append('.'.join(registered_domain))

    # Musical chairs. Change places!
    domains.reverse()

    def join_dom(a, b):
        return '.'.join([b, a])

    # Take each part and add it to the previous part, returning all results
    domains = list(accumulate(domains, func=join_dom))
    # Change places!
    domains.reverse()

    return domains


class Messenger(object):
    """
    >>> m = Messenger(omg=True, whoa='yes')
    """

    def __init__(self, **kwargs):
        self.__dict__ = kwargs


class AttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class classproperty(object):
    """
    Class-level property descriptor factory/decorator.
    """

    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class setter_property(object):

    def __init__(self, func, doc=None):
        self.func = func
        self.__doc__ = doc if doc is not None else func.__doc__

    def __set__(self, obj, value):
        return self.func(obj, value)


def lazyperclassproperty(fn):
    """
    Lazy/Cached class property that stores separate instances per class/inheritor so there's no overlap.
    """

    @classproperty
    def _lazyclassprop(cls):
        attr_name = '_%s_lazy_%s' % (cls.__name__, fn.__name__)
        if not hasattr(cls, attr_name):
            setattr(cls, attr_name, fn(cls))
        return getattr(cls, attr_name)

    return _lazyclassprop


def lazyclassproperty(fn):
    """
    Lazy/Cached class property.
    """
    attr_name = '_lazy_' + fn.__name__

    @classproperty
    def _lazyclassprop(cls):
        if not hasattr(cls, attr_name):
            setattr(cls, attr_name, fn(cls))
        return getattr(cls, attr_name)

    return _lazyclassprop


def lazyproperty(fn):
    """
    Lazy/Cached property.
    """
    attr_name = '_lazy_' + fn.__name__

    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    return _lazyprop


class CachedException(object):

    def __init__(self, ex):
        self.ex = ex

    def throw(self):
        raise self.ex

    __call__ = throw


def cachedmethod(cache, key=_default, lock=None, typed=_default, cached_exception=None):
    """Decorator to wrap a class or instance method with a memoizing
    callable that saves results in a cache.

    You can also specify a cached exception to cache and re-throw as well.

    Originally from cachetools, but modified to support caching certain exceptions.
    """
    if key is not _default and not callable(key):
        key, typed = _default, key
    if typed is not _default:
        warnings.warn("Passing 'typed' to cachedmethod() is deprecated, " "use 'key=typedkey' instead", DeprecationWarning, 2)

    def decorator(method):
        # pass method to default key function for backwards compatibilty
        if key is _default:
            makekey = functools.partial(cachetools.typedkey if typed else cachetools.hashkey, method)
        else:
            makekey = key  # custom key function always receive method args

        @six.wraps(method)
        def wrapper(self, *args, **kwargs):
            c = cache(self)
            ret = _sentinel

            if c is not None:
                k = makekey(self, *args, **kwargs)
                try:
                    if lock is not None:
                        with lock(self):
                            ret = c[k]
                    else:
                        ret = c[k]
                except KeyError:
                    pass  # key not found

            if ret is _sentinel:
                try:
                    ret = method(self, *args, **kwargs)
                except cached_exception as e:
                    ret = CachedException(e)

                if c is not None:
                    try:
                        if lock is not None:
                            with lock(self):
                                c[k] = ret
                        else:
                            c[k] = ret
                    except ValueError:
                        pass  # value too large

            if isinstance(ret, CachedException):
                ret()
            else:
                return ret

        # deprecated wrapper attribute
        def getter(self):
            warnings.warn('%s.cache is deprecated' % method.__name__, DeprecationWarning, 2)
            return cache(self)

        wrapper.cache = getter
        return wrapper

    return decorator


class Timer(object):
    """
    Context manager that times it's execution.
    """

    def __init__(self, name='', verbose=False):
        self.name = name
        self.verbose = verbose

    def __repr__(self):
        return '{cls_name}({name})'.format(cls_name=self.__class__.__name__, name=self.name)

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.secs = self.end - self.start
        self.msecs = self.secs * 1000  # millisecs

        if self.verbose:
            _log.debug('%s: Elapsed time: %f ms', self, self.msecs)


ALL = object()


def traverse_tree(mapping, keys=[ALL], __level=0):
    """
    Traverse dictionary `mapping` on the specified `traverse_keys`, yielding each node. NOT thread safe.
    If `traverse_tree.ALL` is included in `keys`, then every edge node will be yielded.

    :param mapping typing.Mapping: Dictionary
    :param keys collections.Iterable: Iterable of keys to walk down

    >>> data = {'count': 2,
    ...         'text': '1',
    ...         'kids': [{'count': 3,
    ...                   'text': '1.1',
    ...                   'kids': [{'count': 1,
    ...                             'text': '1.1.1',
    ...                             'kids': [{'count':0,
    ...                                       'text': '1.1.1.1',
    ...                                       'kids': []}]},
    ...                            {'count': 0,
    ...                             'text': '1.1.2',
    ...                             'kids': []},
    ...                            {'count': 0,
    ...                             'text': '1.1.3',
    ...                             'kids': []}]},
    ...                  {'count': 0,
    ...                   'text': '1.2',
    ...                   'kids': []}]}
    >>> traverse(data, 'kids')
    """
    iter_keys = ALL in keys and mapping.keys() or keys
    for key in iter_keys:
        for child in mapping[key]:
            __level += 1
            yield child
            yield traverse_tree(child, keys=keys, __level=__level)
            __level -= 1


traverse_tree.ALL = ALL


def get_tree_node(mapping, key, default=_sentinel, parent=False):
    """
    Fetch arbitrary node from a tree-like mapping structure with traversal help:
    Dimension can be specified via ':'

    Arguments:
        mapping typing.Mapping: Mapping to fetch from
        key str|unicode: Key to lookup, allowing for : notation
        default object: Default value. If set to `:module:_sentinel`, raise KeyError if not found.
        parent bool: If True, return parent node. Defaults to False.

    Returns:
        object: Value at specified key
    """
    key = key.split(':')
    if parent:
        key = key[:-1]

    # TODO Unlist my shit. Stop calling me please.

    node = mapping
    for node in key.split(':'):
        try:
            node = node[node]
        except KeyError as exc:
            node = default
            break

    if node is _sentinel:
        raise exc
    return node


def set_tree_node(mapping, key, value):
    """
    Set arbitrary node on a tree-like mapping structure, allowing for : notation to signify dimension.

    Arguments:
        mapping typing.Mapping: Mapping to fetch from
        key str|unicode: Key to set, allowing for : notation
        value str|unicode: Value to set `key` to
        parent bool: If True, return parent node. Defaults to False.

    Returns:
        object: Parent node.

    """
    basename, dirname = key.rsplit(':', 2)
    parent_node = get_tree_node(mapping, dirname)
    parent_node[basename] = value
    return parent_node


def tree():
    """Extremely simple one-lined tree based on defaultdict."""
    return collections.defaultdict(tree)


class Tree(collections.defaultdict):
    """
    Same extremely simple tree based on defaultdict as `tree`, but implemented as a class for extensibility.
    Use ':' to delve down into dimensions without choosing doors [][][] .
    Supports specifying a namespace that acts as a key prefix.
    """
    namespace = None

    def __init__(self, initial=None, namespace='', initial_is_ref=False):
        if initial is not None and initial_is_ref:
            self.data = initial_is_ref
        self.namespace = namespace
        super(Tree, self).__init__(self.__class__)
        if initial is not None:
            self.update(initial)

    def _namespace_key(self, key, namespace=_sentinel):
        if namespace is _sentinel:
            namespace = self.namespace
        if namespace:
            key = '%s:%s' % (namespace, key)
        return key

    def __setitem__(self, key, value, namespace=None):
        key = self._namespace_key(key, namespace=namespace)
        return utils.set_tree_node(self, key, value)

    def __getitem__(self, key, default=_sentinel, namespace=None):
        key = self._namespace_key(key, namespace=namespace)
        return utils.get_tree_node(self, key, default=default)

    get = __getitem__


class RegistryTree(Tree):

    # Alias
    register = Tree.__setitem__


def namespace_from_calling_context():
    """
    Derive a namespace from the module containing the caller's caller.

    :return: the fully qualified python name of a module.
    :rtype: str
    """
    return inspect.stack()[2][0].f_globals["__name__"]


def ignore_exc(on_fail=_sentinel, label=None, exceptions=(), silent_exceptions=()):
    """
    Decorator to ignore exceptions and log them, unless they are also in `silent_exceptions`.

    :param object on_fail: What to return on fail. Can be `callable` with argspec `(fn, instance, args, kwargs, exc)`.
    :param str label: Label to use in the exception log message. Defaults to __name__ of the caller.
    :param collections.Iterable[Exception] exceptions: Iterable of exceptions to ignore.
    :param collections.Iterable[Exception] silent_exceptions: Iterable of exceptions to *not* log when hit. SBD.
    """
    if not label:
        label = _namespace_from_calling_context()

    # short circuit
    if not exceptions:
        def saranwrap(fn):
            return fn
        return saranwrap

    @wrapt.decorator
    def wrapper(fn, instance, args, kwargs):
        try:
            return fn(*args, **kwargs)
        except exceptions as exc:
            if not isinstance(exc, silent_exceptions):
                log.exception("Ignored %s exception in %s(*%s, **%s) on_fail=%s: %s",
                            label, fn, args, kwargs, on_fail, exc)

            if callable(on_fail):
                return on_fail(fn, instance, args, kwargs, exc)

            return on_fail

    return wrapper

