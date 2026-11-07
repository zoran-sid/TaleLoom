"""YHT 测试用临时目录。

测试环境可能是受限沙箱：tempfile 创建的 0700 目录不允许再写入。
这里在测试包内创建普通权限目录，测试结束再删除。
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid

_BASE = Path(__file__).resolve().parent / "_tmp"


@contextmanager
def temp_dir():
    """在 tests/yht/_tmp 下创建唯一目录，退出时尽力清理。"""
    _BASE.mkdir(parents=True, exist_ok=True)
    path = _BASE / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
