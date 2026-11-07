"""YHT：Mermaid 场景图。"""

import contextlib
import io
import json
import unittest

import main
from taleloom.loader import parse_story
from taleloom.validator import render_mermaid
from tests.fixtures import mini_raw, mini_story
from tests.yht.tmp import temp_dir


class MermaidTest(unittest.TestCase):
    def test_nodes_edges_and_ending_class(self):
        text = render_mermaid(mini_story())
        self.assertIn("flowchart TD", text)
        self.assertIn('__start__(["开始"])', text)
        self.assertIn('n0["a<br/>门厅"]', text)
        self.assertIn('n1["b<br/>门后"]', text)
        self.assertIn('-->|"开门"| n1', text)
        self.assertIn("classDef ending", text)
        self.assertIn("class n1 ending", text)

    def test_once_choice_is_labelled(self):
        raw = mini_raw()
        raw["scenes"][0]["choices"][1]["once"] = True
        text = render_mermaid(parse_story(raw))
        self.assertIn("（一次性）", text)

    def test_global_exit_node(self):
        raw = mini_raw(triggers=[
            {"id": "timeout", "when": {"flag": "never"}, "effects": [{"goto": "b"}]},
        ])
        text = render_mermaid(parse_story(raw))
        self.assertIn("__global__", text)
        self.assertIn("任意时刻", text)

    def test_quotes_are_escaped(self):
        raw = mini_raw()
        raw["scenes"][0]["title"] = '他说"走"'
        text = render_mermaid(parse_story(raw))
        self.assertNotIn('n0["a<br/>他说"走""', text)
        self.assertIn("#quot;", text)


class GraphCommandTest(unittest.TestCase):
    def test_graph_command_prints_mermaid(self):
        with temp_dir() as tmp:
            (tmp / "story.json").write_text(
                json.dumps(mini_raw(), ensure_ascii=False), encoding="utf-8"
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main.main(["graph", str(tmp)])
            self.assertEqual(code, 0)
            self.assertIn("flowchart TD", out.getvalue())


if __name__ == "__main__":
    unittest.main()
