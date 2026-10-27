#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dify DSL 静态校验器（支持 DSL 0.6.0 / 0.7.0）。

只做静态检查，不替代真实工作区导入与运行测试。检查项：
版本与模式、节点字段、边与分支句柄、选择器与模板引用、容器结构、
可达性与环、Agent 包、Human Input、插件依赖。

用法：
    python scripts/validate_dsl.py app.dify.yml
    python scripts/validate_dsl.py --target-version 0.7.0 --strict app.dify.yml
    python scripts/validate_dsl.py --format json file1.yml file2.yml

退出码：0 通过；1 有 ERROR（--strict 下 WARN 也计为失败）；2 无法解析。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("需要 PyYAML：pip install pyyaml\n")
    raise SystemExit(2)

SUPPORTED_VERSIONS = {"0.6.0", "0.7.0"}
APP_MODES = {"workflow", "advanced-chat", "agent"}
GRAPH_MODES = {"workflow", "advanced-chat"}

KNOWN_NODE_TYPES = {
    # 基础
    "start", "end", "answer",
    # AI
    "llm", "agent", "knowledge-retrieval", "knowledge-index",
    "question-classifier", "parameter-extractor",
    # 逻辑
    "if-else", "iteration", "loop", "variable-aggregator",
    "assigner", "variable-assigner",
    # 数据
    "code", "template-transform", "list-operator", "document-extractor", "datasource",
    # 外部
    "http-request", "tool",
    # 交互 / 触发 / 容器辅助
    "human-input", "trigger-schedule", "trigger-webhook", "trigger-plugin",
    "iteration-start", "loop-start",
}

ENTRY_TYPES = {"start", "trigger-schedule", "trigger-webhook", "trigger-plugin"}
CONTAINER_TYPES = {"iteration", "loop"}
WRAPPER_TYPES = {"custom", "custom-iteration-start", "custom-loop-start", "custom-note"}
TERMINAL_TYPES = {"end", "answer"}

PROVIDER_TYPES = {"builtin", "api", "workflow", "mcp"}
SELECTOR_KEYS = {
    "value_selector", "variable_selector", "query_variable_selector",
    "iterator_selector", "output_selector", "query_attachment_selector",
    "index_chunk_variable_selector", "context_selector",
}
ROOT_SELECTORS = {"sys", "env", "conversation"}
TEMPLATE_RE = re.compile(r"\{\{#([^#{}]*)#\}\}")
NODE_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,50}$")


class Report:
    def __init__(self, path: str) -> None:
        self.path = path
        self.items: List[Dict[str, str]] = []

    def add(self, level: str, code: str, message: str, where: str = "") -> None:
        self.items.append({"level": level, "code": code, "message": message, "where": where})

    def error(self, code: str, message: str, where: str = "") -> None:
        self.add("ERROR", code, message, where)

    def warn(self, code: str, message: str, where: str = "") -> None:
        self.add("WARN", code, message, where)

    @property
    def errors(self) -> List[Dict[str, str]]:
        return [i for i in self.items if i["level"] == "ERROR"]

    @property
    def warnings(self) -> List[Dict[str, str]]:
        return [i for i in self.items if i["level"] == "WARN"]


def _walk(node: Any, path: str = "") -> Iterable[Tuple[str, Any]]:
    """深度遍历 data，产出 (路径, 值)。"""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            yield child, value
            yield from _walk(value, child)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            child = f"{path}[{idx}]"
            yield child, value
            yield from _walk(value, child)


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _node_label(node: Dict[str, Any]) -> str:
    data = node.get("data") or {}
    nid = node.get("id", "?")
    ntype = data.get("type", "?")
    title = data.get("title") or ""
    return f"{nid}({ntype}{'/' + title if title else ''})"


def check_document(doc: Any, rep: Report, target_version: Optional[str]) -> None:
    if not isinstance(doc, dict):
        rep.error("doc.not-mapping", "顶层不是映射（YAML 对象）")
        return

    version = doc.get("version")
    if version is None:
        rep.error("version.missing", "缺少顶层 version")
    else:
        if not isinstance(version, str):
            rep.error("version.not-string", f"version 必须是字符串，当前是 {type(version).__name__}（写成 {version!r} 会被当成数字）")
        elif version not in SUPPORTED_VERSIONS:
            rep.warn("version.unsupported", f"version={version} 不在本校验器覆盖范围（{sorted(SUPPORTED_VERSIONS)}），仅做通用结构检查")
        elif target_version and version != target_version:
            rep.error("version.mismatch", f"version={version} 与 --target-version={target_version} 不一致")

    if doc.get("kind") != "app":
        rep.error("kind.invalid", f"kind 必须为 app，当前为 {doc.get('kind')!r}")

    app = doc.get("app")
    if not isinstance(app, dict):
        rep.error("app.missing", "缺少 app 段")
        return
    mode = app.get("mode")
    if mode not in APP_MODES:
        rep.error("app.mode-invalid", f"app.mode={mode!r} 不合法，应为 {sorted(APP_MODES)}")
        return
    if not app.get("name"):
        rep.warn("app.name-missing", "app.name 为空，导入后应用名会退化为默认值")
    if mode == "agent" and version != "0.7.0":
        rep.error("app.agent-mode-version", f"mode: agent 仅 0.7.0 支持，当前 version={version}")

    if mode == "agent":
        check_agent_app(doc, rep)
        return

    check_graph(doc, rep, mode)
    check_dependencies(doc, rep)


# --------------------------------------------------------------------------- #
# Agent App
# --------------------------------------------------------------------------- #

def check_agent_app(doc: Dict[str, Any], rep: Report) -> None:
    if "workflow" in doc:
        rep.warn("agent.workflow-present", "mode: agent 的应用不应包含 workflow 段（agent 模式无图）")

    agent = doc.get("agent")
    if not isinstance(agent, dict):
        rep.error("agent.missing", "mode: agent 需要顶层 agent 段")
        return
    ref = agent.get("package_ref")
    packages = doc.get("agent_packages")
    if not ref:
        rep.error("agent.package-ref-missing", "agent.package_ref 为空")
        return
    if not isinstance(packages, dict) or not packages:
        rep.error("agent.packages-missing", "缺少顶层 agent_packages")
        return
    if ref not in packages:
        rep.error("agent.package-ref-dangling", f"agent.package_ref={ref!r} 在 agent_packages 中不存在")

    for name, pkg in packages.items():
        where = f"agent_packages.{name}"
        if not isinstance(pkg, dict):
            rep.error("agent.package-shape", f"{where} 不是映射")
            continue
        if "schema_version" not in pkg:
            rep.error("agent.package-schema-version", f"{where} 缺少 schema_version")
        meta = pkg.get("metadata")
        if not isinstance(meta, dict) or not meta.get("name"):
            rep.warn("agent.package-metadata", f"{where}.metadata 缺少 name")
        soul = pkg.get("soul")
        if not isinstance(soul, dict):
            rep.warn("agent.package-soul", f"{where}.soul 缺失，导入后 Agent 无系统提示词")
            continue
        model = soul.get("model")
        if isinstance(model, dict):
            for key in ("model_provider", "model"):
                if not model.get(key):
                    rep.warn("agent.package-model", f"{where}.soul.model 缺少 {key}")
            if model.get("credential_ref") is None and "credential_ref" in model:
                rep.warn("agent.package-credential", f"{where}.soul.model.credential_ref 为 null，导入后需重新绑定凭据")
        if pkg.get("omitted_assets"):
            rep.warn("agent.package-omitted", f"{where}.omitted_assets 非空，导出时剔除了技能/文件，导入后需补回")


# --------------------------------------------------------------------------- #
# 图结构
# --------------------------------------------------------------------------- #

def check_graph(doc: Dict[str, Any], rep: Report, mode: str) -> None:
    workflow = doc.get("workflow")
    if not isinstance(workflow, dict):
        rep.error("workflow.missing", "缺少 workflow 段")
        return
    graph = workflow.get("graph")
    if not isinstance(graph, dict):
        rep.error("graph.missing", "缺少 workflow.graph")
        return

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list):
        rep.error("graph.nodes", "workflow.graph.nodes 必须是数组")
        return
    if not isinstance(edges, list):
        rep.error("graph.edges", "workflow.graph.edges 必须是数组")
        edges = []

    if mode == "advanced-chat" and isinstance(workflow.get("conversation_variables"), list) is False:
        rep.warn("workflow.conversation-variables", "advanced-chat 通常需要 conversation_variables（可为空数组）")

    node_map, type_map = index_nodes(nodes, rep, doc)
    check_nodes(nodes, node_map, type_map, rep, mode, doc)
    check_edges(edges, node_map, type_map, rep)
    check_entries_and_terminals(nodes, edges, node_map, type_map, rep, mode)
    check_reachability(nodes, edges, node_map, type_map, rep, mode)
    check_selectors(nodes, node_map, rep)
    check_templates(doc, node_map, rep)


def index_nodes(nodes: List[Any], rep: Report, doc: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    node_map: Dict[str, Dict[str, Any]] = {}
    type_map: Dict[str, str] = {}
    for idx, node in enumerate(nodes):
        where = f"nodes[{idx}]"
        if not isinstance(node, dict):
            rep.error("node.shape", f"{where} 不是映射")
            continue
        nid = node.get("id")
        if nid is None:
            rep.error("node.id-missing", f"{where} 缺少 id")
            continue
        if not isinstance(nid, str):
            rep.error("node.id-not-string", f"{where}.id={nid!r} 必须是字符串（数字 id 会在选择器中失配）")
            nid = str(nid)
        if nid in node_map:
            rep.error("node.id-duplicate", f"节点 id 重复：{nid}")
            continue
        node_map[nid] = node
        data = node.get("data")
        dtype = data.get("type") if isinstance(data, dict) else None
        type_map[nid] = dtype if isinstance(dtype, str) else ""
        wrapper = node.get("type")
        if wrapper not in WRAPPER_TYPES:
            rep.error("node.wrapper-type", f"{where}.type={wrapper!r} 不合法，应为 {sorted(WRAPPER_TYPES)}")
        if not dtype:
            if wrapper == "custom-note":
                continue
            rep.error("node.data-type-missing", f"{where}（id={nid}）缺少 data.type")
        elif dtype not in KNOWN_NODE_TYPES:
            rep.error("node.data-type-unknown", f"{where}（id={nid}）data.type={dtype!r} 不是已知节点类型")
        if not node.get("position"):
            rep.warn("node.position-missing", f"{where}（id={nid}）缺少 position，导入后节点会叠在一起")
    return node_map, type_map


def check_nodes(
    nodes: List[Any],
    node_map: Dict[str, Dict[str, Any]],
    type_map: Dict[str, str],
    rep: Report,
    mode: str,
    doc: Dict[str, Any],
) -> None:
    packages = doc.get("agent_packages") or {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id"))
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        dtype = data.get("type")
        label = _node_label(node)

        parent = node.get("parentId")
        if parent:
            if parent not in node_map:
                rep.error("node.parent-dangling", f"{label} 的 parentId={parent!r} 不存在")
            elif type_map.get(parent) not in CONTAINER_TYPES:
                rep.error("node.parent-not-container", f"{label} 的 parentId={parent!r} 不是容器节点")
            if not (data.get("isInIteration") or data.get("isInLoop")):
                rep.warn("node.container-flag", f"{label} 在容器内但未标记 isInIteration/isInLoop")
            if node.get("zIndex") != 1002:
                rep.warn("node.container-zindex", f"{label} 容器子节点 zIndex 应为 1002，当前 {node.get('zIndex')}")

        if dtype == "llm":
            check_llm(data, label, rep, mode)
        elif dtype == "code":
            check_code(data, label, rep)
        elif dtype == "if-else":
            check_if_else(data, label, rep)
        elif dtype == "question-classifier":
            check_classifier(data, label, rep)
        elif dtype == "human-input":
            check_human_input(data, label, rep)
        elif dtype == "agent":
            check_agent_node(data, label, rep, packages)
        elif dtype == "iteration":
            check_iteration(node, data, label, rep, node_map, type_map)
        elif dtype == "loop":
            check_loop(node, data, label, rep, node_map, type_map)
        elif dtype == "end":
            check_end(data, label, rep)
        elif dtype == "answer":
            if not (data.get("answer") or "").strip():
                rep.error("answer.empty", f"{label} 的 answer 为空")
        elif dtype == "assigner" or dtype == "variable-assigner":
            check_assigner(data, label, rep)
        elif dtype == "tool":
            check_tool(data, label, rep)
        elif dtype == "http-request":
            if not data.get("url"):
                rep.warn("http.url-missing", f"{label} 缺少 url")
            if not data.get("method"):
                rep.error("http.method-missing", f"{label} 缺少 method")
        elif dtype == "knowledge-retrieval":
            datasets = data.get("dataset_ids")
            if not isinstance(datasets, list) or not datasets:
                rep.error("kb.dataset-ids", f"{label} 的 dataset_ids 为空")
            elif any(str(d).startswith("<") for d in datasets):
                rep.warn("kb.dataset-placeholder", f"{label} 的 dataset_ids 含占位值，导入后需替换为真实知识库 ID")
        elif dtype == "knowledge-index":
            if not data.get("dataset_id"):
                rep.error("kb-index.dataset-id", f"{label} 是知识库写入节点，必须有单数 dataset_id")
        elif dtype == "document-extractor":
            sel = data.get("variable_selector")
            if not isinstance(sel, list) or len(sel) < 2:
                rep.error("doc-extractor.selector", f"{label} 的 variable_selector 必须是扁平数组 [node_id, field]")
        elif dtype in ENTRY_TYPES and parent:
            rep.warn("trigger.in-container", f"{label} 是入口节点，不应出现在容器内")

    if mode == "workflow":
        for node in nodes:
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            if data.get("type") == "llm" and isinstance(data.get("memory"), dict):
                if data["memory"].get("window", {}).get("enabled"):
                    rep.error("llm.memory-in-workflow", f"{_node_label(node)} 在 workflow 模式开启了 memory；workflow 无会话记忆，需移除或改为 advanced-chat")


def check_llm(data: Dict[str, Any], label: str, rep: Report, mode: str) -> None:
    model = data.get("model")
    if not isinstance(model, dict):
        rep.error("llm.model", f"{label} 缺少 model")
    else:
        for key in ("provider", "name", "mode"):
            if not model.get(key):
                rep.error("llm.model-field", f"{label}.model 缺少 {key}")
        provider = str(model.get("provider") or "")
        if provider and provider.count("/") != 2:
            rep.warn("llm.provider-shape", f"{label}.model.provider={provider!r} 应为 <author>/<plugin>/<provider> 三段式")
    prompt = data.get("prompt_template")
    if not isinstance(prompt, list) or not prompt:
        rep.error("llm.prompt-template", f"{label} 的 prompt_template 不能为空")
    else:
        for i, item in enumerate(prompt):
            if not isinstance(item, dict):
                rep.error("llm.prompt-item", f"{label}.prompt_template[{i}] 不是映射")
                continue
            if not item.get("role"):
                rep.error("llm.prompt-role", f"{label}.prompt_template[{i}] 缺少 role")
            if "text" not in item:
                rep.error("llm.prompt-text", f"{label}.prompt_template[{i}] 缺少 text")
            if "id" not in item:
                rep.warn("llm.prompt-id", f"{label}.prompt_template[{i}] 缺少 id（新版导出通常带 uuid）")
    if not isinstance(data.get("context"), dict):
        rep.error("llm.context", f"{label} 缺少 context；即使关闭也必须写 {{enabled: false, variable_selector: []}}")


def check_code(data: Dict[str, Any], label: str, rep: Report) -> None:
    lang = data.get("code_language")
    if lang not in {"python3", "javascript"}:
        rep.error("code.language", f"{label}.code_language={lang!r} 不合法，应为 python3 或 javascript")
    code = data.get("code") or ""
    if not code.strip():
        rep.error("code.empty", f"{label} 的 code 为空")
    elif lang == "python3" and not re.search(r"def\s+main\s*\(", code):
        rep.error("code.main-missing", f"{label} 是 python3 但找不到 def main(...)")
    outputs = data.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        rep.error("code.outputs", f"{label} 的 outputs 必须是非空映射（变量名 → {{type, children}}）")


def check_if_else(data: Dict[str, Any], label: str, rep: Report) -> None:
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        rep.error("ifelse.cases", f"{label} 的 cases 不能为空")
        return
    seen: Set[str] = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            rep.error("ifelse.case-shape", f"{label}.cases[{i}] 不是映射")
            continue
        cid = case.get("id") or case.get("case_id")
        if not cid:
            rep.error("ifelse.case-id", f"{label}.cases[{i}] 缺少 id/case_id")
            continue
        cid = str(cid)
        if cid in seen:
            rep.error("ifelse.case-duplicate", f"{label} 的 case id 重复：{cid}")
        seen.add(cid)
        conds = case.get("conditions")
        if not isinstance(conds, list) or not conds:
            rep.error("ifelse.conditions", f"{label}.cases[{i}]（{cid}）缺少 conditions")


def check_classifier(data: Dict[str, Any], label: str, rep: Report) -> None:
    classes = data.get("classes")
    if not isinstance(classes, list) or not classes:
        rep.error("classifier.classes", f"{label} 的 classes 不能为空")
        return
    for i, cls in enumerate(classes):
        if not isinstance(cls, dict) or not cls.get("id") or not cls.get("name"):
            rep.error("classifier.class-shape", f"{label}.classes[{i}] 需要同时有 id 与 name")
        elif not isinstance(cls.get("id"), str):
            rep.warn("classifier.class-id-type", f"{label}.classes[{i}].id 建议用引号包成字符串，否则与边 handle 失配")


def check_human_input(data: Dict[str, Any], label: str, rep: Report) -> None:
    actions = data.get("user_actions")
    if not isinstance(actions, list) or not actions:
        rep.error("human.actions", f"{label} 的 user_actions 不能为空（否则无分支可走）")
    else:
        seen: Set[str] = set()
        for i, act in enumerate(actions):
            if not isinstance(act, dict):
                rep.error("human.action-shape", f"{label}.user_actions[{i}] 不是映射")
                continue
            aid = act.get("id")
            if not aid:
                rep.error("human.action-id", f"{label}.user_actions[{i}] 缺少 id")
                continue
            if not isinstance(aid, str):
                rep.error("human.action-id-type", f"{label}.user_actions[{i}].id 必须是字符串")
            if len(str(aid)) > 20:
                rep.error("human.action-id-length", f"{label}.user_actions[{i}].id={aid!r} 超过 20 字符上限")
            if aid in seen:
                rep.error("human.action-duplicate", f"{label} 的 action id 重复：{aid}")
            seen.add(aid)
            if not act.get("title"):
                rep.warn("human.action-title", f"{label}.user_actions[{i}] 缺少 title")

    inputs = data.get("inputs")
    if inputs is not None:
        if not isinstance(inputs, list):
            rep.error("human.inputs-shape", f"{label}.inputs 必须是数组")
            inputs = []
        names: Set[str] = set()
        for i, item in enumerate(inputs):
            if not isinstance(item, dict):
                rep.error("human.input-shape", f"{label}.inputs[{i}] 不是映射")
                continue
            name = item.get("output_variable_name")
            if not name:
                rep.error("human.input-name", f"{label}.inputs[{i}] 缺少 output_variable_name")
                continue
            if name in names:
                rep.error("human.input-duplicate", f"{label} 的输入输出名重复：{name}")
            names.add(name)
            itype = item.get("type")
            if itype not in {"paragraph", "select", "file", "file-list"}:
                rep.error("human.input-type", f"{label}.inputs[{i}].type={itype!r} 不合法，应为 paragraph/select/file/file-list")
            if itype == "select":
                src = item.get("option_source")
                if not isinstance(src, dict):
                    rep.error("human.select-source", f"{label}.inputs[{i}] 是 select 但缺少 option_source")
                elif src.get("type") == "constant":
                    if not isinstance(src.get("value"), list):
                        rep.error("human.select-constant", f"{label}.inputs[{i}].option_source 为 constant 时 value 必须是字符串数组")
                elif src.get("type") == "variable":
                    sel = src.get("selector")
                    if not isinstance(sel, list) or len(sel) < 2:
                        rep.error("human.select-variable", f"{label}.inputs[{i}].option_source 为 variable 时 selector 至少两段")
                else:
                    rep.error("human.select-type", f"{label}.inputs[{i}].option_source.type 应为 constant 或 variable")
            if itype in {"file", "file-list"}:
                methods = item.get("allowed_file_upload_methods")
                if methods is not None:
                    bad = [m for m in _as_list(methods) if m not in {"local_file", "remote_url"}]
                    if bad:
                        rep.error("human.file-methods", f"{label}.inputs[{i}] 上传方式非法：{bad}（只能 local_file/remote_url）")

    unit = data.get("timeout_unit")
    if unit is not None and unit not in {"hour", "day"}:
        rep.error("human.timeout-unit", f"{label}.timeout_unit={unit!r} 只能是 hour 或 day")


def check_agent_node(data: Dict[str, Any], label: str, rep: Report, packages: Any) -> None:
    if data.get("version") == "2" or data.get("agent_node_kind"):
        if data.get("version") != "2":
            rep.error("agent.v2-version", f"{label} 是 Agent v2 但 version 必须是字符串 \"2\"，当前 {data.get('version')!r}")
        if data.get("agent_node_kind") != "dify_agent":
            rep.error("agent.v2-kind", f"{label}.agent_node_kind 应为 dify_agent")
        binding = data.get("agent_binding")
        if not isinstance(binding, dict):
            rep.error("agent.v2-binding", f"{label} 缺少 agent_binding")
        else:
            ref = binding.get("package_ref")
            if not ref:
                rep.error("agent.v2-package-ref", f"{label}.agent_binding.package_ref 为空")
            elif not isinstance(packages, dict) or ref not in packages:
                rep.error("agent.v2-package-dangling", f"{label} 引用的 agent_packages.{ref} 不存在")
        job = data.get("agent_job")
        if not isinstance(job, dict):
            rep.error("agent.v2-job", f"{label} 缺少 agent_job")
        else:
            if not job.get("workflow_prompt"):
                rep.warn("agent.v2-prompt", f"{label}.agent_job.workflow_prompt 为空")
            outs = job.get("declared_outputs")
            if isinstance(outs, list):
                for i, out in enumerate(outs):
                    if not isinstance(out, dict) or not out.get("name") or not out.get("type"):
                        rep.error("agent.v2-output", f"{label}.agent_job.declared_outputs[{i}] 需要 name 与 type")
            elif outs is not None:
                rep.error("agent.v2-output-shape", f"{label}.agent_job.declared_outputs 必须是数组")
    else:
        # legacy 插件策略 Agent
        if not data.get("agent_strategy_provider_name"):
            rep.error("agent.legacy-provider", f"{label} 缺少 agent_strategy_provider_name（或改用 Agent v2 结构）")
        if not isinstance(data.get("agent_parameters"), dict):
            rep.error("agent.legacy-params", f"{label} 缺少 agent_parameters")


def check_iteration(
    node: Dict[str, Any],
    data: Dict[str, Any],
    label: str,
    rep: Report,
    node_map: Dict[str, Dict[str, Any]],
    type_map: Dict[str, str],
) -> None:
    for key in ("iterator_selector", "output_selector"):
        sel = data.get(key)
        if not isinstance(sel, list) or len(sel) < 2:
            rep.error("iteration.selector", f"{label} 的 {key} 必须是 [node_id, field]")
    start_id = data.get("start_node_id")
    if not start_id:
        rep.error("iteration.start-node", f"{label} 缺少 start_node_id")
    else:
        if start_id not in node_map:
            rep.error("iteration.start-dangling", f"{label}.start_node_id={start_id!r} 不存在")
        elif type_map.get(str(start_id)) != "iteration-start":
            rep.error("iteration.start-type", f"{label}.start_node_id 指向的节点 data.type 应为 iteration-start")
        elif node_map[str(start_id)].get("parentId") != node.get("id"):
            rep.error("iteration.start-parent", f"{label}.start_node_id 指向的节点 parentId 不匹配")
    if data.get("is_parallel") and not isinstance(data.get("parallel_nums"), int):
        rep.warn("iteration.parallel-nums", f"{label} 开启并行但 parallel_nums 不是整数")


def check_loop(
    node: Dict[str, Any],
    data: Dict[str, Any],
    label: str,
    rep: Report,
    node_map: Dict[str, Dict[str, Any]],
    type_map: Dict[str, str],
) -> None:
    count = data.get("loop_count")
    if not isinstance(count, int) or count <= 0:
        rep.error("loop.count", f"{label}.loop_count 必须是正整数，当前 {count!r}")
    start_id = data.get("start_node_id")
    if not start_id:
        rep.error("loop.start-node", f"{label} 缺少 start_node_id")
    else:
        if start_id not in node_map:
            rep.error("loop.start-dangling", f"{label}.start_node_id={start_id!r} 不存在")
        elif type_map.get(str(start_id)) != "loop-start":
            rep.error("loop.start-type", f"{label}.start_node_id 指向的节点 data.type 应为 loop-start")
    if ("width" not in data) or ("height" not in data):
        rep.warn("loop.dimensions", f"{label} 建议在 data 内也写 width/height（容器尺寸需两处一致）")
    if node.get("zIndex") != 1:
        rep.warn("loop.zindex", f"{label} 容器本身 zIndex 建议为 1，当前 {node.get('zIndex')}")
    for i, var in enumerate(_as_list(data.get("loop_variables"))):
        if not isinstance(var, dict) or not var.get("label"):
            rep.error("loop.var-shape", f"{label}.loop_variables[{i}] 缺少 label")
    for i, cond in enumerate(_as_list(data.get("break_conditions"))):
        if not isinstance(cond, dict):
            rep.error("loop.break-shape", f"{label}.break_conditions[{i}] 不是映射")
            continue
        if not isinstance(cond.get("variable_selector"), list):
            rep.error("loop.break-selector", f"{label}.break_conditions[{i}] 缺少 variable_selector")


def check_end(data: Dict[str, Any], label: str, rep: Report) -> None:
    outputs = data.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        rep.error("end.outputs", f"{label} 的 outputs 不能为空")
        return
    for i, out in enumerate(outputs):
        if not isinstance(out, dict):
            rep.error("end.output-shape", f"{label}.outputs[{i}] 不是映射")
            continue
        if not out.get("variable"):
            rep.error("end.output-variable", f"{label}.outputs[{i}] 缺少 variable")
        if not isinstance(out.get("value_selector"), list):
            rep.error("end.output-selector", f"{label}.outputs[{i}] 缺少 value_selector")


def check_assigner(data: Dict[str, Any], label: str, rep: Report) -> None:
    items = data.get("items")
    if not isinstance(items, list) or not items:
        rep.error("assigner.items", f"{label} 的 items 不能为空")
        return
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            rep.error("assigner.item-shape", f"{label}.items[{i}] 不是映射")
            continue
        if not isinstance(item.get("variable_selector"), list):
            rep.error("assigner.var-selector", f"{label}.items[{i}] 缺少 variable_selector")
        if not item.get("operation"):
            rep.error("assigner.operation", f"{label}.items[{i}] 缺少 operation")
        itype = item.get("input_type")
        if itype == "variable" and not isinstance(item.get("value"), list):
            rep.error("assigner.value-selector", f"{label}.items[{i}] input_type=variable 时 value 必须放选择器数组")
        if data.get("version") == "2" and "value_selector" in item:
            rep.warn("assigner.v2-mixed", f"{label}.items[{i}] 是 assigner v2 却用了 value_selector，v2 把选择器放在 value 里")


def check_tool(data: Dict[str, Any], label: str, rep: Report) -> None:
    ptype = data.get("provider_type")
    if ptype not in PROVIDER_TYPES:
        rep.error("tool.provider-type", f"{label}.provider_type={ptype!r} 不合法，应为 {sorted(PROVIDER_TYPES)}")
    for key in ("provider_id", "tool_name"):
        if not data.get(key):
            rep.error("tool.field", f"{label} 缺少 {key}")
    params = data.get("tool_parameters")
    if isinstance(params, dict):
        for key, value in params.items():
            if not isinstance(value, dict) or "type" not in value:
                rep.error("tool.param-shape", f"{label}.tool_parameters.{key} 必须是 {{type, value}} 结构")


def check_edges(
    edges: List[Any],
    node_map: Dict[str, Dict[str, Any]],
    type_map: Dict[str, str],
    rep: Report,
) -> None:
    seen_ids: Set[str] = set()
    for idx, edge in enumerate(edges):
        where = f"edges[{idx}]"
        if not isinstance(edge, dict):
            rep.error("edge.shape", f"{where} 不是映射")
            continue
        eid = edge.get("id")
        if eid:
            if str(eid) in seen_ids:
                rep.error("edge.id-duplicate", f"边 id 重复：{eid}")
            seen_ids.add(str(eid))
        src = edge.get("source")
        tgt = edge.get("target")
        if src not in node_map:
            rep.error("edge.source-dangling", f"{where} 的 source={src!r} 不存在")
            continue
        if tgt not in node_map:
            rep.error("edge.target-dangling", f"{where} 的 target={tgt!r} 不存在")
            continue
        if edge.get("targetHandle") != "target":
            rep.error("edge.target-handle", f"{where}.targetHandle 必须是 target，当前 {edge.get('targetHandle')!r}")

        handle = edge.get("sourceHandle")
        src_data = node_map[str(src)].get("data") or {}
        src_type = type_map.get(str(src))
        if src_type == "if-else":
            valid = {str(c.get("id") or c.get("case_id")) for c in _as_list(src_data.get("cases")) if isinstance(c, dict)}
            valid.add("false")
            if handle not in valid:
                rep.error("edge.branch-handle", f"{where} 源是 if-else，sourceHandle={handle!r} 不在 {sorted(valid)} 中")
        elif src_type == "question-classifier":
            valid = {str(c.get("id")) for c in _as_list(src_data.get("classes")) if isinstance(c, dict)}
            if handle not in valid:
                rep.error("edge.branch-handle", f"{where} 源是 question-classifier，sourceHandle={handle!r} 不在 {sorted(valid)} 中")
        elif src_type == "human-input":
            valid = {str(a.get("id")) for a in _as_list(src_data.get("user_actions")) if isinstance(a, dict)}
            valid.add("__timeout")
            if handle not in valid:
                rep.error("edge.branch-handle", f"{where} 源是 human-input，sourceHandle={handle!r} 不在 {sorted(valid)} 中")
        elif src_type not in {"custom-note", ""}:
            if handle not in (None, "source"):
                rep.error("edge.handle", f"{where} 源是 {src_type}，sourceHandle 应为 source，当前 {handle!r}")

        data = edge.get("data") or {}
        if isinstance(data, dict):
            if data.get("sourceType") and data["sourceType"] != src_type:
                rep.warn("edge.source-type", f"{where}.data.sourceType={data['sourceType']!r} 与源节点 {src_type!r} 不一致")
            if data.get("targetType") and data["targetType"] != type_map.get(str(tgt)):
                rep.warn("edge.target-type", f"{where}.data.targetType={data['targetType']!r} 与目标节点 {type_map.get(str(tgt))!r} 不一致")
            if data.get("isInIteration") or data.get("isInLoop"):
                if edge.get("zIndex") != 1002:
                    rep.warn("edge.container-zindex", f"{where} 位于容器内，zIndex 应为 1002")


def check_entries_and_terminals(
    nodes: List[Any],
    edges: List[Any],
    node_map: Dict[str, Dict[str, Any]],
    type_map: Dict[str, str],
    rep: Report,
    mode: str,
) -> None:
    entries = [nid for nid, t in type_map.items() if t in ENTRY_TYPES and not node_map[nid].get("parentId")]
    if mode == "advanced-chat" and len(entries) != 1:
        rep.error("graph.entry", f"advanced-chat 需要且仅需要一个入口节点，当前 {len(entries)} 个：{entries}")
    elif mode == "workflow" and len(entries) == 0:
        rep.error("graph.entry", "workflow 缺少入口节点（start 或触发器）")

    terminals = [nid for nid, t in type_map.items() if t in TERMINAL_TYPES]
    if mode == "workflow" and not terminals:
        rep.error("graph.terminal", "workflow 没有 end/answer 节点")
    if mode == "advanced-chat" and not any(type_map.get(n) == "answer" for n in terminals):
        rep.error("graph.terminal", "advanced-chat 缺少 answer 节点")

    if len(entries) > 1:
        rep.warn("graph.multi-entry", f"存在多个入口节点：{entries}（触发器场景可能是故意为之）")


def check_reachability(
    nodes: List[Any],
    edges: List[Any],
    node_map: Dict[str, Dict[str, Any]],
    type_map: Dict[str, str],
    rep: Report,
    mode: str,
) -> None:
    adjacency: Dict[str, List[str]] = {nid: [] for nid in node_map}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src, tgt = edge.get("source"), edge.get("target")
        if src in adjacency and tgt in adjacency:
            adjacency[src].append(tgt)

    entries = [nid for nid, t in type_map.items() if t in ENTRY_TYPES and not node_map[nid].get("parentId")]
    if not entries:
        return

    seen: Set[str] = set()
    stack = list(entries)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(adjacency.get(cur, []))

    for nid, node in node_map.items():
        dtype = type_map.get(nid)
        if dtype == "custom-note" or not dtype:
            continue
        if node.get("parentId"):
            continue
        if nid not in seen:
            rep.warn("graph.unreachable", f"节点 {_node_label(node)} 从入口不可达")

    outs = {t for src in adjacency for t in adjacency[src]}
    for nid, dtype in type_map.items():
        if dtype in TERMINAL_TYPES or dtype == "knowledge-index" or not dtype:
            continue
        if not adjacency.get(nid) and not node_map[nid].get("parentId") and nid not in outs:
            if dtype in CONTAINER_TYPES:
                continue
            rep.warn("graph.dead-end", f"节点 {_node_label(node_map[nid])} 没有出边")

    # 环检测（容器内部不计）
    color: Dict[str, int] = {}

    def dfs(u: str) -> None:
        color[u] = 1
        for v in adjacency.get(u, []):
            if node_map.get(v, {}).get("parentId"):
                continue
            if color.get(v) == 1:
                rep.error("graph.cycle", f"检测到环：{u} → {v}")
            elif color.get(v) is None:
                dfs(v)
        color[u] = 2

    for start in entries:
        if color.get(start) is None:
            dfs(start)


def check_selectors(nodes: List[Any], node_map: Dict[str, Dict[str, Any]], rep: Report) -> None:
    valid_roots = set(node_map) | ROOT_SELECTORS
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        label = _node_label(node)
        for path, value in _walk(data):
            key = path.rsplit(".", 1)[-1]
            if key not in SELECTOR_KEYS:
                continue
            if not isinstance(value, list) or len(value) < 2:
                if value not in (None, [], ""):
                    rep.warn("selector.shape", f"{label}.{path} 不是 [node_id, field] 形态")
                continue
            root = value[0]
            if not isinstance(root, str):
                rep.error("selector.root-type", f"{label}.{path}[0] 必须是字符串，当前 {root!r}")
                continue
            if root in valid_roots:
                continue
            rep.error("selector.unknown-node", f"{label}.{path} 引用了不存在的节点 {root!r}")


def check_templates(doc: Dict[str, Any], node_map: Dict[str, Dict[str, Any]], rep: Report) -> None:
    for path, value in _walk(doc):
        if not isinstance(value, str) or "{{#" not in value:
            continue
        for match in TEMPLATE_RE.findall(value):
            ref = match.strip()
            if "." not in ref:
                rep.warn("template.shape", f"{path} 中的 {{{{#{ref}#}}}} 缺少 .字段 部分")
                continue
            node_part, field_part = ref.split(".", 1)
            if not node_part:
                continue
            if "-" in node_part or not NODE_ID_RE.match(node_part):
                rep.error(
                    "template.node-id",
                    f"{path} 引用了 {{{{#{ref}#}}}}，但模板里的节点 id 只能是字母/数字/下划线（1-50 字符），含连字符的 id 在运行期解析失败",
                )
                continue
            if node_part not in node_map and node_part not in {"sys", "env", "conversation"}:
                rep.warn("template.unknown-node", f"{path} 引用了不存在的节点 {node_part!r}")


def check_dependencies(doc: Dict[str, Any], rep: Report) -> None:
    deps = doc.get("dependencies")
    if deps is None:
        rep.warn("deps.missing", "缺少顶层 dependencies（无插件时可以写空数组）")
        return
    if not isinstance(deps, list):
        rep.error("deps.shape", "dependencies 必须是数组")
        return
    plugin_users: List[str] = []
    for node in _as_list((doc.get("workflow") or {}).get("graph", {}).get("nodes")):
        if not isinstance(node, dict):
            continue
        data = node.get("data") or {}
        if data.get("type") in {"tool", "trigger-plugin", "datasource"} and data.get("plugin_id"):
            plugin_users.append(f"{node.get('id')}({data.get('type')})")
    if plugin_users and not deps:
        rep.warn("deps.missing-plugin", f"节点 {plugin_users} 引用插件但 dependencies 为空，导入后可能变成未安装插件")
    for i, dep in enumerate(deps):
        if not isinstance(dep, dict):
            rep.error("deps.item-shape", f"dependencies[{i}] 不是映射")
            continue
        if dep.get("type") == "marketplace":
            value = dep.get("value") or {}
            ident = value.get("marketplace_plugin_unique_identifier") if isinstance(value, dict) else None
            if not ident:
                rep.error("deps.identifier", f"dependencies[{i}] 缺少 marketplace_plugin_unique_identifier")
            elif "@" not in str(ident):
                rep.warn("deps.identifier-shape", f"dependencies[{i}] 的 plugin_unique_identifier 通常形如 author/plugin:ver@sha256")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def validate_file(path: str, target_version: Optional[str]) -> Report:
    rep = Report(path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except FileNotFoundError:
        rep.error("io.not-found", "文件不存在")
        return rep
    except yaml.YAMLError as exc:
        rep.error("yaml.parse", f"YAML 解析失败：{exc}")
        return rep

    if doc is None:
        rep.error("doc.empty", "文件为空")
        return rep

    check_document(doc, rep, target_version)
    return rep


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="校验 Dify App DSL（支持 0.6.0 / 0.7.0）")
    parser.add_argument("files", nargs="+", help="待校验的 .yml / .json 文件")
    parser.add_argument("--target-version", choices=sorted(SUPPORTED_VERSIONS), help="要求文件声明的 version 与之匹配")
    parser.add_argument("--strict", action="store_true", help="WARN 也作为失败")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    reports = [validate_file(path, args.target_version) for path in args.files]
    failed = 0
    for rep in reports:
        ok = not rep.errors and (not args.strict or not rep.warnings)
        if not ok:
            failed += 1
        if args.format == "text":
            status = "OK  " if ok else "FAIL"
            print(f"[{status}] {rep.path}  errors={len(rep.errors)} warnings={len(rep.warnings)}")
            for item in rep.items:
                where = f" @ {item['where']}" if item["where"] else ""
                print(f"  {item['level']:5s} {item['code']:26s} {item['message']}{where}")

    if args.format == "json":
        print(json.dumps(
            {
                "files": [
                    {
                        "path": r.path,
                        "ok": not r.errors and (not args.strict or not r.warnings),
                        "errors": r.errors,
                        "warnings": r.warnings,
                    }
                    for r in reports
                ],
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        ))

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
