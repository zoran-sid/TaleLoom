"""ZC：运行 ZC 负责模块中的 doctest（文档字符串里的小例子）。"""

import doctest

import taleloom.legacy_session
from tools import package


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(taleloom.legacy_session))
    tests.addTests(doctest.DocTestSuite(package))
    return tests
