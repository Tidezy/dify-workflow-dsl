---
name: dify-workflow-dsl
description: 从自然语言需求生成可直接导入 Dify 的工作流 DSL（YAML/JSON），支持 DSL 0.6.0（Dify 1.15.x）与 0.7.0（Dify 1.16.x）。用于新建 Dify 工作流/对话流/Agent 应用、改造已有 DSL、排查导入失败、补 Human Input / Loop / Iteration / Agent v2 节点结构。当用户提到 Dify、工作流 DSL、chatflow、导入报错、workflow.yml 时使用。
license: MIT
compatibility: Requires Python 3.9+ and PyYAML.
---

# Dify 工作流 DSL 生成

把一句需求变成**能直接导入**的 `.dify.yml`。核心不是"写出大概像的 YAML"，而是让节点字段、边句柄、选择器和版本结构与目标实例严格对齐。

## 先决条件：确认版本

| 目标环境 | `version` | 能力 |
|---|---|---|
| Dify 1.16.x 及以上 | `"0.7.0"` | 全部 + Agent App、Agent v2、Human Input、节点 wrapper 布局字段 |
| Dify 1.15.x | `"0.6.0"` | Workflow / Chatflow / Loop / assigner v2 / legacy Agent |
| 未知 | `"0.7.0"` | 并在回复里明确"按 1.16.x 假设生成" |

**不要靠改版本字符串升级**。结构必须与版本匹配，详见 `references/version-deltas.md`。
编辑用户已有文件时，保留原版本，不要顺手升级。

## 生成流程

1. **判断模式**：一次性/批量/接口型 → `workflow`；多轮对话 → `advanced-chat`；独立可对话的 Agent 应用 → `agent`（仅 0.7.0）。拿不准时问一句，不要猜。
2. **列节点清单**：按下方路由表把需求映射成节点序列，先写出 `start → … → end/answer` 的骨架，再填细节。
3. **查节点字段**：每个节点读对应的 `references/nodes/*.md`，字段名逐字照抄，不要凭记忆写。
4. **写 YAML**：节点 id 用字符串（建议 `n_start`、`n_llm` 这类下划线风格），边按 `{source}-{handle}-{target}-target` 命名。
5. **跑校验**：`python scripts/validate_dsl.py --strict --target-version <版本> <文件>`，把 ERROR 全部修掉；WARN 要么修，要么在回复里说明为什么可接受。
6. **交付**：给出文件路径 + 版本 + 剩余需要在工作区手工完成的事项（绑凭据、填知识库 ID、重配 webhook）。

## 节点路由表

| 需求 | `data.type` | 文档 |
|---|---|---|
| 用户输入 / 定时 / Webhook / 插件事件 | `start`、`trigger-schedule`、`trigger-webhook`、`trigger-plugin` | `references/nodes/start.md` |
| 工作流输出 | `end` | `references/nodes/end.md` |
| 对话流回复 | `answer` | `references/nodes/answer.md` |
| 大模型调用 | `llm` | `references/nodes/llm.md` |
| Agent（插件策略 / v2 / 独立 App） | `agent`、`mode: agent` | `references/nodes/agent.md` |
| 知识库检索 / 写入 | `knowledge-retrieval`、`knowledge-index` | `references/nodes/knowledge-retrieval.md`、`references/nodes/knowledge-index.md` |
| 问题分类 | `question-classifier` | `references/nodes/question-classifier.md` |
| 结构化参数抽取 | `parameter-extractor` | `references/nodes/parameter-extractor.md` |
| 条件分支 | `if-else` | `references/nodes/if-else.md` |
| 数组遍历 | `iteration` | `references/nodes/iteration.md` |
| 条件循环 | `loop` | `references/nodes/loop.md` |
| 合并分支 | `variable-aggregator` | `references/nodes/variable-aggregator.md` |
| 改变量 | `assigner` | `references/nodes/assigner.md` |
| 代码处理 | `code` | `references/nodes/code.md` |
| 文本模板 | `template-transform` | `references/nodes/template-transform.md` |
| 数组过滤/排序/取首尾 | `list-operator` | `references/nodes/list-operator.md` |
| 从文件取文本 | `document-extractor` | `references/nodes/document-extractor.md` |
| 调外部 API | `http-request` | `references/nodes/http-request.md` |
| 调插件工具 / 数据源 | `tool`、`datasource` | `references/nodes/tool.md` |
| 人工审批 / 补录 | `human-input` | `references/nodes/human-input.md` |

## 硬规则（违反必导入失败或运行期空值）

1. **节点 id 必须是字符串**，且铺进 `{{#...#}}` 的部分只能是字母/数字/下划线、1–50 字符。带连字符的 id 在边和数组选择器里能用，但放进模板会解析失败。
2. **`llm` 必须有 `context`**，即使关闭也要写 `{enabled: false, variable_selector: []}`；`prompt_template` 不能为空。
3. **`workflow` 模式没有 `sys.query`**，也不能给 LLM 开 `memory`；用户输入一律走 `start` 变量。
4. **`variable-aggregator.variables` 是裸嵌套数组** `[["node","field"]]`，不是对象数组。
5. **分支句柄逐字匹配**：`if-else` 用 `cases[].id`（ELSE 是 `"false"`）、`question-classifier` 用 `classes[].id`、`human-input` 用 `user_actions[].id`（超时是 `"__timeout"`）。
6. **容器三件套**：子节点要 `parentId` + `isInIteration`/`isInLoop` + `zIndex: 1002`；容器的 `start_node_id` 指向辅助起点节点（`custom-iteration-start` / `custom-loop-start`）。
7. **插件必须进 `dependencies`**，`marketplace_plugin_unique_identifier` 只能从真实导出复制，不许自己拼。
8. **模型名要真实**：`model.provider` 三段式、`model.name` 用该供应商实际提供的名称，编造名会在运行期报 provider 校验失败。

## 模板

从最接近的骨架起步，再改字段：

| 模板 | 适用 |
|---|---|
| `references/templates/chatbot.yml` | 单轮问答 / 多轮对话骨架（advanced-chat） |
| `references/templates/rag.yml` | 知识库问答（检索结果喂 `context`） |
| `references/templates/translation.yml` | 有输入输出的 Workflow 骨架 |
| `references/templates/agent-v2.yml` | Workflow 内嵌 Agent v2 节点 |

完整可导入样例见 `examples/`：人工审批、Loop 计数、Iteration 批量、Agent App、问题分流。

## 校验

```bash
# 单文件
python scripts/validate_dsl.py app.dify.yml

# 指定目标版本 + 严格模式（WARN 也算失败）
python scripts/validate_dsl.py --strict --target-version 0.7.0 app.dify.yml

# 批量，机器可读
python scripts/validate_dsl.py --format json examples/*.yml
```

依赖 Python 3.9+ 与 PyYAML；缺失时先安装 PyYAML。

校验器覆盖：版本与模式、节点字段、边端点与分支句柄、选择器根节点、模板引用合法性、容器结构、可达性与环、Agent 包引用、Human Input 结构、插件依赖。它**不**替代真实导入——最终以目标工作区导入弹窗与一次试跑为准。

## 输出规范

- 产物落在当前工作目录，文件名 `<kebab-case>.dify.yml`；中间产物放临时目录，不要混进交付目录。
- YAML 用 2 空格缩进，所有字符串型 id 加引号。
- 交付时说明三件事：目标版本、校验结果、导入后需要人工补的配置。

## 覆盖范围

| 用户要什么 | 怎么处理 |
|---|---|
| 方案 / 节点选型 / 改造思路 / Prompt 设计 | 直接给结论文字，不落文件 |
| 可导入的 DSL | 走「生成流程」，产出 `<kebab-case>.dify.yml` 并跑校验 |
| 导入失败排查 | 读现有 DSL 与报错，定位到节点、边句柄、选择器或版本，必要的给出修好的文件 |

不负责：在 Dify 平台上点击搭建、发布、部署与验收；也不代为安装插件或填凭据。这些以目标工作区的实际状态为准，交付时列出需要在工作区补的项。

用户没要文件时不要擅自写盘；反过来，给了文件就必须跑过校验再说"可导入"。

## 参考文件

- `references/dsl-format.md` — 顶层结构、节点 wrapper、变量与选择器、dependencies
- `references/edge-and-layout.md` — 边、分支句柄、坐标与容器布局
- `references/version-deltas.md` — 0.6.0 ↔ 0.7.0 差异与迁移清单
- `references/nodes/*.md` — 21 个节点的字段表与最小示例
