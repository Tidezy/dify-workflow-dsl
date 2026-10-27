#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_dsl.py 的回归测试。

    python -m unittest discover -s tests -v
"""

import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import validate_dsl  # noqa: E402


def codes(report):
    return {item["code"] for item in report.items}


class ValidFiles(unittest.TestCase):
    def test_examples_have_no_errors(self):
        files = sorted(glob.glob(os.path.join(ROOT, "examples", "*.yml")))
        self.assertTrue(files, "examples 目录下没有样本")
        for path in files:
            with self.subTest(path=os.path.basename(path)):
                rep = validate_dsl.validate_file(path, "0.7.0")
                self.assertEqual([], rep.errors, msg=f"{path}: {rep.errors}")

    def test_templates_have_no_errors(self):
        files = sorted(glob.glob(os.path.join(ROOT, "references", "templates", "*.yml")))
        self.assertTrue(files, "templates 目录下没有样本")
        for path in files:
            with self.subTest(path=os.path.basename(path)):
                rep = validate_dsl.validate_file(path, "0.7.0")
                self.assertEqual([], rep.errors, msg=f"{path}: {rep.errors}")

    def test_valid_fixtures(self):
        for path in sorted(glob.glob(os.path.join(ROOT, "tests", "fixtures", "valid", "*.yml"))):
            with self.subTest(path=os.path.basename(path)):
                rep = validate_dsl.validate_file(path, None)
                self.assertEqual([], rep.errors, msg=f"{path}: {rep.errors}")


class InvalidFixtures(unittest.TestCase):
    EXPECTED = {
        "bad-branch-handle.yml": "edge.branch-handle",
        "llm-missing-context.yml": "llm.context",
        "template-hyphen-id.yml": "template.node-id",
        "agent-package-dangling.yml": "agent.v2-package-dangling",
    }

    def test_invalid_fixtures_are_caught(self):
        found = set()
        for path in sorted(glob.glob(os.path.join(ROOT, "tests", "fixtures", "invalid", "*.yml"))):
            name = os.path.basename(path)
            rep = validate_dsl.validate_file(path, None)
            with self.subTest(path=name):
                self.assertTrue(rep.errors, msg=f"{name} 应该报错但没有")
            found.add(name)
            expected = self.EXPECTED.get(name)
            if expected:
                self.assertIn(expected, codes(rep), msg=f"{name} 未报出 {expected}，实际 {codes(rep)}")
        self.assertEqual(set(self.EXPECTED), found, "invalid 夹具与期望表不一致")


class VersionPolicy(unittest.TestCase):
    def test_target_version_mismatch(self):
        path = os.path.join(ROOT, "tests", "fixtures", "valid", "minimal-workflow-0.7.yml")
        rep = validate_dsl.validate_file(path, "0.6.0")
        self.assertIn("version.mismatch", codes(rep))

    def test_agent_mode_rejected_before_070(self):
        doc = {
            "version": "0.6.0",
            "kind": "app",
            "app": {"name": "旧版 Agent", "mode": "agent"},
            "agent": {"package_ref": "pkg"},
            "agent_packages": {"pkg": {"schema_version": 1}},
        }
        rep = validate_dsl.Report("<inline>")
        validate_dsl.check_document(doc, rep, None)
        self.assertIn("app.agent-mode-version", codes(rep))


if __name__ == "__main__":
    unittest.main()
