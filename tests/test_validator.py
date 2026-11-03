#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_dsl.py 的回归测试。

    python -m unittest discover -s tests -v
"""

import glob
import os
import sys
import unittest

# 避免在技能包的 scripts/ 下生成 __pycache__
sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_ROOT = os.path.join(REPO_ROOT, "skills", "dify-workflow-dsl")
TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

import validate_dsl  # noqa: E402


def codes(report):
    return {item["code"] for item in report.items}


class ValidFiles(unittest.TestCase):
    def test_examples_have_no_errors(self):
        files = sorted(glob.glob(os.path.join(SKILL_ROOT, "examples", "*.yml")))
        self.assertTrue(files, "examples 目录下没有样本")
        for path in files:
            with self.subTest(path=os.path.basename(path)):
                rep = validate_dsl.validate_file(path, "0.7.0")
                self.assertEqual([], rep.errors, msg=f"{path}: {rep.errors}")

    def test_templates_have_no_errors(self):
        files = sorted(glob.glob(os.path.join(SKILL_ROOT, "references", "templates", "*.yml")))
        self.assertTrue(files, "templates 目录下没有样本")
        for path in files:
            with self.subTest(path=os.path.basename(path)):
                rep = validate_dsl.validate_file(path, "0.7.0")
                self.assertEqual([], rep.errors, msg=f"{path}: {rep.errors}")

    def test_valid_fixtures(self):
        for path in sorted(glob.glob(os.path.join(TEST_ROOT, "fixtures", "valid", "*.yml"))):
            with self.subTest(path=os.path.basename(path)):
                rep = validate_dsl.validate_file(path, None)
                self.assertEqual([], rep.errors, msg=f"{path}: {rep.errors}")


class InvalidFixtures(unittest.TestCase):
    EXPECTED = {
        "bad-branch-handle.yml": "edge.branch-handle",
        "llm-missing-context.yml": "llm.context",
        "template-hyphen-id.yml": "template.node-id",
        "agent-package-dangling.yml": "agent.v2-package-dangling",
        "end-output-duplicate.yml": "end.output-duplicate",
        "http-missing-authorization.yml": "http.authorization",
        "http-headers-folded.yml": "http.kv-folded",
        "code-signature-mismatch.yml": "code.signature",
        "bad-enum-values.yml": "enum.error-strategy",
    }

    def test_invalid_fixtures_are_caught(self):
        found = set()
        for path in sorted(glob.glob(os.path.join(TEST_ROOT, "fixtures", "invalid", "*.yml"))):
            name = os.path.basename(path)
            rep = validate_dsl.validate_file(path, None)
            with self.subTest(path=name):
                self.assertTrue(rep.errors, msg=f"{name} 应该报错但没有")
            found.add(name)
            expected = self.EXPECTED.get(name)
            if expected:
                self.assertIn(expected, codes(rep), msg=f"{name} 未报出 {expected}，实际 {codes(rep)}")
        self.assertEqual(set(self.EXPECTED), found, "invalid 夹具与期望表不一致")


def make_node(nid, dtype, **data):
    return {
        "id": nid,
        "type": "custom",
        "data": {"type": dtype, "title": nid, **data},
        "position": {"x": 0, "y": 0},
    }


def make_edge(src, tgt, handle="source"):
    return {
        "id": f"{src}-{handle}-{tgt}-target",
        "source": src,
        "sourceHandle": handle,
        "target": tgt,
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
        "data": {},
    }


def make_doc(nodes, edges, env=None):
    return {
        "version": "0.7.0",
        "kind": "app",
        "app": {"name": "字段引用用例", "mode": "workflow"},
        "dependencies": [],
        "workflow": {
            "environment_variables": env or [],
            "conversation_variables": [],
            "graph": {"nodes": nodes, "edges": edges},
        },
    }


def llm_node(nid, prompt="hi"):
    return make_node(
        nid,
        "llm",
        model={"provider": "a/b/c", "name": "m", "mode": "chat"},
        prompt_template=[{"role": "user", "text": prompt}],
        context={"enabled": False, "variable_selector": []},
    )


class FieldReferences(unittest.TestCase):
    """下游引用不存在的输出字段：导入不报错、运行期空值，必须在静态阶段拦住。"""

    def check(self, doc):
        rep = validate_dsl.Report("<inline>")
        validate_dsl.check_document(doc, rep, None)
        return rep

    def test_unknown_selector_field(self):
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "text", "type": "text-input", "required": True}]),
            llm_node("n_llm"),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_llm", "text2"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_llm"), make_edge("n_llm", "n_end")]
        self.assertIn("selector.unknown-field", codes(self.check(make_doc(nodes, edges))))

    def test_unknown_template_field(self):
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "text", "type": "text-input", "required": True}]),
            make_node("n_tpl", "template-transform", template="{{#n_start.text2#}}", variables=[]),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_tpl", "output"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_tpl"), make_edge("n_tpl", "n_end")]
        self.assertIn("template.unknown-field", codes(self.check(make_doc(nodes, edges))))

    def test_known_fields_pass(self):
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "text", "type": "text-input", "required": True}]),
            llm_node("n_llm"),
            make_node("n_code", "code", code="def main(x):\n    return {'items': []}", code_language="python3",
                      outputs={"items": {"type": "array[string]", "children": None}},
                      variables=[{"variable": "x", "value_selector": ["n_llm", "text"]}]),
            make_node("n_end", "end", outputs=[
                {"variable": "items", "value_selector": ["n_code", "items"], "value_type": "array[string]"},
                {"variable": "t", "value_selector": ["n_llm", "text"], "value_type": "string"},
            ]),
        ]
        edges = [make_edge("n_start", "n_llm"), make_edge("n_llm", "n_code"), make_edge("n_code", "n_end")]
        rep = self.check(make_doc(nodes, edges))
        self.assertEqual([], rep.errors, msg=rep.errors)

    def test_code_output_typo_is_caught(self):
        nodes = [
            make_node("n_start", "start", variables=[]),
            make_node("n_code", "code", code="def main():\n    return {'items': []}", code_language="python3",
                      outputs={"items": {"type": "array[string]", "children": None}}),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_code", "item"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_code"), make_edge("n_code", "n_end")]
        self.assertIn("selector.unknown-field", codes(self.check(make_doc(nodes, edges))))

    def test_plugin_outputs_are_not_checked(self):
        """tool 的输出字段由插件 schema 决定，静态不可判，不能误报。"""
        nodes = [
            make_node("n_start", "start", variables=[]),
            make_node("n_tool", "tool", provider_type="builtin", provider_id="p/t", tool_name="search",
                      tool_parameters={}, plugin_id="p/t"),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_tool", "whatever"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_tool"), make_edge("n_tool", "n_end")]
        rep = self.check(make_doc(nodes, edges))
        self.assertNotIn("selector.unknown-field", codes(rep))

    def test_env_must_be_declared(self):
        nodes = [
            make_node("n_start", "start", variables=[]),
            make_node("n_code", "code", code="def main(a):\n    return {'o': a}", code_language="python3",
                      outputs={"o": {"type": "string", "children": None}},
                      variables=[{"variable": "a", "value_selector": ["env", "API_KEY"]}]),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_code", "o"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_code"), make_edge("n_code", "n_end")]
        self.assertIn("selector.unknown-env", codes(self.check(make_doc(nodes, edges))))

        declared = [{"name": "API_KEY", "value": "", "value_type": "string"}]
        rep = self.check(make_doc(nodes, edges, env=declared))
        self.assertNotIn("selector.unknown-env", codes(rep))

    def test_iteration_item_is_available_inside(self):
        """容器内引用 iteration 的 item/index 必须放行。"""
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "text", "type": "text-input", "required": True}]),
            make_node("n_iter", "iteration", iterator_selector=["n_start", "text"], output_selector=["n_in", "output"],
                      output_type="array[string]", start_node_id="n_iter_start", is_parallel=False),
            make_node("n_iter_start", "iteration-start"),
            make_node("n_in", "template-transform", template="{{#n_iter.item#}}-{{#n_iter.index#}}", variables=[]),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_iter", "output"], "value_type": "array[string]"}]),
        ]
        nodes[2]["parentId"] = "n_iter"
        nodes[2]["zIndex"] = 1002
        nodes[2]["data"]["isInIteration"] = True
        edges = [make_edge("n_start", "n_iter"), make_edge("n_iter_start", "n_in"), make_edge("n_iter", "n_end")]
        rep = self.check(make_doc(nodes, edges))
        merged = {item["code"] for item in rep.items if item["code"].startswith(("selector.", "template."))}
        self.assertEqual(set(), merged, msg=rep.items)


class RuntimeEnums(unittest.TestCase):
    """运行期枚举写错时导入期不报错，必须在静态阶段拦下。"""

    def check(self, doc):
        rep = validate_dsl.Report("<inline>")
        validate_dsl.check_document(doc, rep, None)
        return rep

    def test_error_strategy_must_be_fail_branch_or_default_value(self):
        nodes = [
            make_node("n_start", "start", variables=[]),
            make_node("n_tpl", "template-transform", template="x", variables=[], error_strategy="terminated"),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_tpl", "output"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_tpl"), make_edge("n_tpl", "n_end")]
        self.assertIn("enum.error-strategy", codes(self.check(make_doc(nodes, edges))))

    def test_valid_error_strategy_passes(self):
        nodes = [
            make_node("n_start", "start", variables=[]),
            make_node("n_tpl", "template-transform", template="x", variables=[], error_strategy="fail-branch"),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_tpl", "output"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_tpl"), make_edge("n_tpl", "n_end")]
        self.assertNotIn("enum.error-strategy", codes(self.check(make_doc(nodes, edges))))

    def test_start_variable_type_is_validated(self):
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "link", "type": "url", "required": True}]),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_start", "link"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_end")]
        self.assertIn("enum.start-variable-type", codes(self.check(make_doc(nodes, edges))))

    def test_if_else_comparison_operator_is_validated(self):
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "t", "type": "text-input", "required": True}]),
            make_node("n_if", "if-else", cases=[{"id": "c1", "logical_operator": "and", "conditions": [
                {"variable_selector": ["n_start", "t"], "comparison_operator": "is null", "value": ""},
            ]}]),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_start", "t"], "value_type": "string"}]),
        ]
        edges = [make_edge("n_start", "n_if"), make_edge("n_if", "n_end", handle="c1")]
        self.assertIn("enum.comparison-operator", codes(self.check(make_doc(nodes, edges))))

    def test_list_operator_rejects_if_else_only_operators(self):
        nodes = [
            make_node("n_start", "start", variables=[{"variable": "t", "type": "text-input", "required": True}]),
            make_node("n_list", "list-operator", variable=["n_start", "t"], var_type="array[string]",
                      filter_by={"enabled": True, "filter_by": {"comparison_operator": "exists", "value": ""}},
                      order_by={"enabled": False}, limit={"enabled": False}),
            make_node("n_end", "end", outputs=[{"variable": "v", "value_selector": ["n_list", "result"], "value_type": "array[string]"}]),
        ]
        edges = [make_edge("n_start", "n_list"), make_edge("n_list", "n_end")]
        self.assertIn("enum.comparison-operator", codes(self.check(make_doc(nodes, edges))))


class VersionPolicy(unittest.TestCase):
    """目标版本只有 DSL 0.7.0；更早的版本既不该被生成，也不该被静默放过。"""

    OLD_DOC = {
        "version": "0.6.0",
        "kind": "app",
        "app": {"name": "旧版工作流", "mode": "workflow"},
        "dependencies": [],
        "workflow": {
            "environment_variables": [],
            "conversation_variables": [],
            "graph": {"nodes": [], "edges": []},
        },
    }

    def test_old_version_file_is_rejected_against_current_target(self):
        rep = validate_dsl.Report("<inline>")
        validate_dsl.check_document(self.OLD_DOC, rep, "0.7.0")
        self.assertIn("version.mismatch", codes(rep))

    def test_old_version_file_is_flagged_without_target(self):
        rep = validate_dsl.Report("<inline>")
        validate_dsl.check_document(self.OLD_DOC, rep, None)
        self.assertIn("version.unsupported", codes(rep))

    def test_current_version_passes(self):
        path = os.path.join(TEST_ROOT, "fixtures", "valid", "minimal-workflow-0.7.yml")
        rep = validate_dsl.validate_file(path, "0.7.0")
        self.assertEqual([], rep.errors, msg=rep.errors)

    def test_agent_mode_requires_current_version(self):
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
