from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalTrueColorFormatter
from pprint import pformat, pprint

from see import see


def pformat_color(obj):
    return highlight(pformat(obj), PythonLexer(), TerminalTrueColorFormatter())


def pprint_color(obj):
    print(pformat_color(obj))


pf = pformat_color
pp = pprint_color

