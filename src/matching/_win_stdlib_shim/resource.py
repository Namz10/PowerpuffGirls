"""POSIX ``resource`` stand-in so the unmodified blocker CLI imports on Windows.

``src.blocking.generate`` imports ``resource`` at module level. That module is
not part of Windows CPython. This file is placed on ``PYTHONPATH`` only by
``src.matching.invoke_blocker``. It is not a change to blocker source, and the
reported RSS field stays zero because Windows does not provide ``ru_maxrss``.
"""

RUSAGE_SELF = 0
RUSAGE_CHILDREN = -1


class _Usage:
    ru_maxrss = 0


def getrusage(who=0):
    return _Usage()
