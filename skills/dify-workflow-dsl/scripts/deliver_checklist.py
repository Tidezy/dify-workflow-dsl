#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 DSL 生成「导入后还要在工作区补什么」的交付清单。

DSL 只描述结构，不含运行环境：插件没装、凭据没绑、知识库 ID 是占位符、触发器 URL 被清空，
这些都不会写在图里，但每一条都会让应用跑不起来。这个脚本把它们逐条列出来，避免交付时靠回忆。

清单分两类：
- `[ ]` 待办——必须在目标工作区动手做的事；
- `-`   说明——交付时需要一并告知的事实（输出契约、人工节点表单、依赖模型等）。

用法：
    python scripts/deliver_checklist.py app.dify.yml
    python scripts/deliver_checklist.py app.dify.yml --format json

退出码：0 成功；1 文件无法解析。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("需要 PyYAML：pip install pyyaml\n")
    raise SystemExit(2)

Item = Dict[str, str]
Section = Tuple[str, List[Item]]


def todo(text: str) -> Item:
    return {"status": "todo", "text": text}


def info(text: str) -> Item:
    return {"status": "info", "text": text}


def warn(text: str) -> Item:
    return {"status": "warn", "text": text}


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def is_placeholder(value: Any) -> bool:
    return str(value).strip().startswith("<")


def node_label(node: Dict[str, Any]) -> str:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    title = data.get("title") or data.get("type") or "?"
    return f"{node.get('id')}（{title}）"


def collect(doc: Dict[str, Any], path: str) -> Dict[str, Any]:
    app = doc.get("app") if isinstance(doc.get("app"), dict) else {}
    workflow = doc.get("workflow") if isinstance(doc.get("workflow"), dict) else {}
    graph = workflow.get("graph") if isinstance(workflow.get("graph"), dict) else {}
    nodes = [n for n in as_list(graph.get("nodes")) if isinstance(n, dict)]
    deps = [d for d in as_list(doc.get("dependencies")) if isinstance(d, dict)]
    mode = str(app.get("mode") or "")
    version = str(doc.get("version") or "")
    sections: List[Section] = []

    def data_of(node: Dict[str, Any]) -> Dict[str, Any]:
        return node.get("data") if isinstance(node.get("data"), dict) else {}

    # ---- 插件与依赖 -------------------------------------------------------
    items: List[Item] = []
    identifiers: List[str] = []
    for dep in deps:
        value = dep.get("value") if isinstance(dep.get("value"), dict) else {}
        ident = value.get("marketplace_plugin_unique_identifier")
        if ident:
            identifiers.append(str(ident))
            if "<" in str(ident):   # 形如 author/plugin:ver@<sha256>，占位符在中间
                items.append(todo(f"插件标识 `{ident}` 是占位符，需从目标工作区导出的 DSL 复制真实值"))
            else:
                items.append(todo(f"在工作区安装插件 `{ident}`"))
        else:
            items.append(warn("dependencies 里有一项缺 `marketplace_plugin_unique_identifier`，导入后该节点会变成未安装插件"))

    plugin_users: Dict[str, List[str]] = {}
    for node in nodes:
        plugin_id = data_of(node).get("plugin_id")
        if plugin_id:
            plugin_users.setdefault(str(plugin_id), []).append(node_label(node))
    for plugin_id, users in plugin_users.items():
        declared = any(ident.split(":")[0] == plugin_id for ident in identifiers)
        if not declared:
            items.append(warn(f"节点 {', '.join(users)} 用到插件 `{plugin_id}`，但 dependencies 里没有声明"))
    if items:
        sections.append(("插件与依赖", items))

    # ---- 模型与凭据 -------------------------------------------------------
    items = []
    model_users: Dict[str, List[str]] = {}
    for node in nodes:
        data = data_of(node)
        if data.get("type") != "llm":
            continue
        model = data.get("model") if isinstance(data.get("model"), dict) else {}
        key = f'{model.get("provider") or "?"} · {model.get("name") or "?"}'
        model_users.setdefault(key, []).append(node_label(node))
    for key, users in model_users.items():
        items.append(todo(f"确认模型 `{key}` 在工作区可用并已绑定凭据（节点 {', '.join(users)}）"))

    packages = doc.get("agent_packages") if isinstance(doc.get("agent_packages"), dict) else {}
    for name, pkg in packages.items():
        soul = pkg.get("soul") if isinstance(pkg, dict) and isinstance(pkg.get("soul"), dict) else {}
        model = soul.get("model") if isinstance(soul.get("model"), dict) else {}
        if model:
            key = f'{model.get("model_provider") or "?"} · {model.get("model") or "?"}'
            items.append(todo(f"Agent 包 `{name}` 的模型 `{key}` 需绑定凭据（credential_ref 导出时被清空）"))
        if pkg.get("omitted_assets"):
            items.append(todo(f"Agent 包 `{name}` 的 omitted_assets 非空：技能/文件需重新补回"))
        contacts = soul.get("human_contacts")
        if isinstance(contacts, list) and contacts:
            items.append(todo(f"Agent 包 `{name}` 声明了 {len(contacts)} 个工作区联系人，需在目标工作区确认存在"))
    if items:
        sections.append(("模型与凭据", items))

    # ---- 知识库 -----------------------------------------------------------
    items = []
    for node in nodes:
        data = data_of(node)
        dtype = data.get("type")
        if dtype == "knowledge-retrieval":
            ids = as_list(data.get("dataset_ids"))
            if not ids:
                items.append(todo(f"节点 {node_label(node)} 的 `dataset_ids` 为空，需选知识库"))
            elif any(is_placeholder(d) for d in ids):
                items.append(todo(f"节点 {node_label(node)} 的知识库是占位符，需替换为真实 dataset id"))
            else:
                items.append(info(f"节点 {node_label(node)} 引用 {len(ids)} 个知识库，确认目标工作区存在同名同 ID 的知识库"))
        elif dtype == "knowledge-index":
            dataset_id = data.get("dataset_id")
            if not dataset_id:
                items.append(todo(f"节点 {node_label(node)} 缺少 `dataset_id`，需指定写入的知识库"))
            elif is_placeholder(dataset_id):
                items.append(todo(f"节点 {node_label(node)} 的 `dataset_id` 是占位符，需替换"))
    if items:
        sections.append(("知识库", items))

    # ---- 触发器 -----------------------------------------------------------
    items = []
    for node in nodes:
        dtype = data_of(node).get("type")
        if dtype in {"trigger-webhook", "trigger-schedule", "trigger-plugin"}:
            items.append(todo(f"节点 {node_label(node)} 是 {dtype}：导入后重新配置并取回新的 URL / 订阅 ID（导出时被清空）"))
    if items:
        sections.append(("触发器", items))

    # ---- 外部调用与工具 ---------------------------------------------------
    items = []
    for node in nodes:
        data = data_of(node)
        dtype = data.get("type")
        if dtype == "http-request":
            method = str(data.get("method") or "GET").upper()
            url = str(data.get("url") or "<未填>")
            items.append(todo(f"节点 {node_label(node)} 需能访问 `{method} {url}`（出网、鉴权、超时）"))
        elif dtype in {"tool", "datasource"}:
            provider = data.get("provider_id") or data.get("provider_name") or "?"
            tool = data.get("tool_name") or data.get("datasource_name") or ""
            items.append(todo(f"节点 {node_label(node)} 的工具 `{provider}{'/' + tool if tool else ''}` 需在工作区授权"))
    if items:
        sections.append(("外部调用与工具", items))

    # ---- 人工节点 ---------------------------------------------------------
    items = []
    for node in nodes:
        data = data_of(node)
        if data.get("type") != "human-input":
            continue
        actions = len(as_list(data.get("user_actions")))
        inputs = len(as_list(data.get("inputs")))
        timeout = data.get("timeout")
        suffix = f"，超时 {timeout} {data.get('timeout_unit') or ''}".rstrip() if timeout else ""
        items.append(todo(
            f"节点 {node_label(node)}：{actions} 个动作、{inputs} 个表单字段{suffix}；"
            f"需配置收件人与投递渠道（Web App / 邮件 / 群机器人）"
        ))
    if items:
        sections.append(("人工节点", items))

    # ---- 变量 -------------------------------------------------------------
    items = []
    for var in as_list(workflow.get("environment_variables")):
        if not isinstance(var, dict) or not var.get("name"):
            continue
        value = var.get("value")
        state = "当前为空，需填值" if value in (None, "") else "确认取值适用于目标环境"
        items.append(todo(f"环境变量 `{var['name']}`（{var.get('value_type') or 'string'}）：{state}"))
    conversation = [
        str(var.get("name")) for var in as_list(workflow.get("conversation_variables"))
        if isinstance(var, dict) and var.get("name")
    ]
    if conversation:
        items.append(info(f"会话变量：{', '.join(conversation)}（仅 advanced-chat 生效，初始值随 DSL 导入）"))
    if items:
        sections.append(("变量", items))

    # ---- 输出契约 ---------------------------------------------------------
    items = []
    for node in nodes:
        data = data_of(node)
        if data.get("type") != "end":
            continue
        outputs = [o for o in as_list(data.get("outputs")) if isinstance(o, dict)]
        described = ", ".join(
            f"{o.get('variable')} ← {'.'.join(str(p) for p in as_list(o.get('value_selector')))}"
            for o in outputs
        )
        items.append(info(f"节点 {node_label(node)} 输出 {len(outputs)} 项：{described or '无'}"))
    answers = sum(1 for node in nodes if data_of(node).get("type") == "answer")
    if answers:
        items.append(info(f"{answers} 个 answer 节点直接作为对话回复，无需配置"))
    if mode == "agent":
        agent = doc.get("agent") if isinstance(doc.get("agent"), dict) else {}
        items.append(info(f"agent 模式，包引用 `{agent.get('package_ref') or '?'}`，无 workflow 图"))
    if items:
        sections.append(("输出契约", items))

    # ---- 自查 -------------------------------------------------------------
    items = [todo(
        f"导入前跑 `python scripts/validate_dsl.py --strict --target-version {version or '<版本>'} {os.path.basename(path)}`，"
        f"导入后用一条最小输入试跑，确认变量不是空值"
    )]
    sections.append(("自查", items))

    return {
        "file": path,
        "app": {
            "name": str(app.get("name") or ""),
            "mode": mode,
            "version": version,
            "nodes": len(nodes),
            "edges": len(as_list(graph.get("edges"))),
            "has_graph": bool(nodes),
        },
        "sections": [{"title": title, "items": items} for title, items in sections],
    }


def to_markdown(data: Dict[str, Any]) -> str:
    app = data["app"]
    meta = " · ".join(
        part for part in [
            app["mode"] or "未知模式",
            f"DSL {app['version']}" if app["version"] else "",
            f"{app['nodes']} 个节点" if app["has_graph"] else "",
            f"{app['edges']} 条边" if app["has_graph"] else "",
        ] if part
    )
    lines = [
        f"# 交付清单 · {app['name'] or '未命名应用'}",
        "",
        meta,
        "",
        f"来源：`{os.path.basename(data['file'])}`　·　`[ ]` 为导入后必须在工作区完成的事项",
        "",
    ]
    for section in data["sections"]:
        lines.append(f"## {section['title']}")
        for item in section["items"]:
            if item["status"] == "todo":
                lines.append(f"- [ ] {item['text']}")
            elif item["status"] == "warn":
                lines.append(f"- **注意**　{item['text']}")
            else:
                lines.append(f"- {item['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="从 Dify DSL 生成交付清单")
    parser.add_argument("files", nargs="+", help="待分析的 .dify.yml / .json 文件")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    args = parser.parse_args(argv)

    failed = 0
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
        except FileNotFoundError:
            print(f"[FAIL] {path}：文件不存在", file=sys.stderr)
            failed += 1
            continue
        except yaml.YAMLError as exc:
            print(f"[FAIL] {path}：YAML 解析失败：{exc}", file=sys.stderr)
            failed += 1
            continue

        if not isinstance(doc, dict):
            print(f"[FAIL] {path}：顶层不是映射（YAML 对象）", file=sys.stderr)
            failed += 1
            continue

        data = collect(doc, path)
        if args.format == "json":
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            if len(args.files) > 1:
                print(f"\n<!-- {path} -->")
            print(to_markdown(data), end="")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
