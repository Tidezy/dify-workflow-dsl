#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deliver_checklist.py 的回归测试。

    python -m unittest discover -s tests -v
"""

import glob
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_ROOT = os.path.join(REPO_ROOT, "skills", "dify-workflow-dsl")
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

import deliver_checklist  # noqa: E402


def run_json(path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deliver_checklist.main([path, "--format", "json"])
    return code, json.loads(buf.getvalue())


def texts(data):
    return [item["text"] for section in data["sections"] for item in section["items"]]


def titles(data):
    return [section["title"] for section in data["sections"]]


class Checklist(unittest.TestCase):
    def test_all_examples_produce_checklist(self):
        files = sorted(glob.glob(os.path.join(SKILL_ROOT, "examples", "*.yml")))
        self.assertTrue(files, "examples 目录下没有样本")
        for path in files:
            with self.subTest(path=os.path.basename(path)):
                code, data = run_json(path)
                self.assertEqual(0, code)
                self.assertIn("自查", titles(data))
                self.assertTrue(data["sections"])
                self.assertEqual(os.path.basename(path), os.path.basename(data["file"]))

    def test_knowledge_placeholder_is_flagged(self):
        path = os.path.join(SKILL_ROOT, "references", "templates", "rag.yml")
        code, data = run_json(path)
        self.assertEqual(0, code)
        self.assertIn("知识库", titles(data))
        self.assertTrue(any("占位符" in t for t in texts(data)), msg=texts(data))

    def test_model_is_listed(self):
        path = os.path.join(SKILL_ROOT, "references", "templates", "rag.yml")
        _, data = run_json(path)
        self.assertIn("模型与凭据", titles(data))
        self.assertTrue(any("gpt-4o-mini" in t for t in texts(data)), msg=texts(data))

    def test_agent_package_needs_credential(self):
        path = os.path.join(SKILL_ROOT, "examples", "04-agent-app.dify.yml")
        _, data = run_json(path)
        self.assertIn("模型与凭据", titles(data))
        self.assertTrue(any("credential_ref" in t for t in texts(data)), msg=texts(data))
        self.assertFalse(data["app"]["has_graph"])

    def test_human_input_actions_are_counted(self):
        path = os.path.join(SKILL_ROOT, "examples", "01-human-approval.dify.yml")
        _, data = run_json(path)
        self.assertIn("人工节点", titles(data))
        self.assertTrue(any("2 个动作" in t and "3 个表单字段" in t for t in texts(data)), msg=texts(data))

    def test_output_contract_lists_every_end(self):
        path = os.path.join(SKILL_ROOT, "examples", "01-human-approval.dify.yml")
        _, data = run_json(path)
        ends = [t for t in texts(data) if "输出" in t and "项" in t]
        self.assertEqual(2, len(ends), msg=ends)

    def test_markdown_has_checkboxes(self):
        path = os.path.join(SKILL_ROOT, "examples", "02-loop-quality.dify.yml")
        buf = io.StringIO()
        with redirect_stdout(buf):
            deliver_checklist.main([path])
        md = buf.getvalue()
        self.assertIn("# 交付清单", md)
        self.assertIn("- [ ]", md)

    def test_missing_file_fails(self):
        buf = io.StringIO()
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stdout(buf), redirect_stderr(err):
            code = deliver_checklist.main([os.path.join(SKILL_ROOT, "nope.yml")])
        self.assertEqual(1, code)


if __name__ == "__main__":
    unittest.main()
