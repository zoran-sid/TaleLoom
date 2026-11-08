"""ZRS：桌面入口在缺少 Tcl/Tk 时说明原因并回退，不崩溃。"""

import io
import sys
import unittest
from contextlib import redirect_stderr
from unittest import mock

from taleloom import gui


class GuiEntryTest(unittest.TestCase):
    def test_missing_tkinter_explains_and_returns_1(self):
        with mock.patch.dict(sys.modules, {"tkinter": None}), \
                redirect_stderr(io.StringIO()) as err:
            code = gui.run(stories_dir=None, saves_dir=None)
        self.assertEqual(code, 1)
        self.assertIn("Tkinter", err.getvalue())


if __name__ == "__main__":
    unittest.main()
