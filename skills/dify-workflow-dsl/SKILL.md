---
name: dify-workflow-dsl
description: 从自然语言需求生成可直接导入 Dify 的工作流 DSL（YAML/JSON），目标为 DSL 0.7.0（Dify 1.16.x 及以上，实测 1.17.1）。用于新建 Dify 工作流/对话流/Agent 应用、改造已有 DSL、排查导入失败、补 Human Input / Loop / Iteration / Agent v2 节点结构。当用户提到 Dify、工作流 DSL、chatflow、导入报错、workflow.yml 时使用。
license: MIT
compatibility: Requires Python 3.9+ and PyYAML.
---

# Dify 工作流 DSL 生成

把一句需求变成**能直接导入**的 `.dify.yml`。核心不是"写出大概像的 YAML"，而是让节点字段、边句柄、选择器和版本结构与目标实例严格对齐。

## 先决条件：确认版本

目标实例是 Dify **1.17.1**，DSL 版本固定 `"0.7.0"`（Dify 1.16.x / 1.17.x / 1.18.x 都是这个结构）。

| 目标环境 | `version` | 能力 |
|---|---|---|
| Dify 1.16.x 及以上（含 1.17.1） | `"0.7.0"` | 全部 + Agent App、Agent v2、Human Input、节点 wrapper 布局字段 |
| 更早的 Dify | `"0.6.0"` 及更早 | 结构不同，本技能不覆盖；见 `references/target-version.md` |

**不要靠改版本字符串升级**。结构必须与版本匹配，详见 `references/target-version.md`。
编辑用户已有文件时，保留原版本，不要顺手升级。

## 生成流程

1. **判断模式**：一次性/批量/接口型 → `workflow`；多轮对话 → `advanced-chat`；独立可对话的 Agent 应用 → `agent`。拿不准时问一句，不要猜。
2. **列节点清单**：按下方路由表把需求映射成节点序列，先写出 `start → … → end/answer` 的骨架，再填细节。
3. **查节点字段**：每个节点读对应的 `references/nodes/*.md`，字段名逐字照抄，不要凭记忆写。
4. **写 YAML**：节点 id 用 13 位数字串（与 Dify 真实导出一致，如 `1770000000010`；语义化 id 便于阅读，但交付前应换成数字），边按 `{source}-{handle}-{target}-target` 命名。
5. **跑校验**：`python scripts/validate_dsl.py --strict --target-version 0.7.0 <文件>`，把 ERROR 全部修掉；WARN 要么修，要么在回复里说明为什么可接受。
   同一轮里**把本次改动过的字段单独打印一次解析后的值**（`yaml.safe_load` 之后 `repr()`），确认它不是你以为的样子——
   典型翻车是 `headers` 被 YAML 折叠成空格、数字型 id 被解析成 int，这两类校验器未必拦得住全部变体。
   改已有文件时优先**定点编辑**，不要整份覆写：整份重写会把所有已验证字段重新冒一次险。
6. **生成交付清单**：`python scripts/deliver_checklist.py <文件>`，把「导入后还要在目标工作区补什么」列成待办，不要靠回忆。
7. **交付**：给出文件路径 + 版本 + 校验结果 + 清单里尚未完成的项。

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
9. **只能引用真实存在的输出字段**：`["node", "field"]` 与 `{{#node.field#}}` 都算；字段不存在时导入不报错、运行期取到空值。各节点的输出字段见对应 `references/nodes/*.md` 的「数据流」小节。
10. **多个 `end` 节点的输出变量名必须全局唯一**。工作流的输出是一张扁平表，两个 End 都用 `decision` 会在发布检查里被拒（`输出节点变量重复`）。分支之间用前缀区分，如 `ok_result` / `back_result`。
11. **`http-request.authorization` 是必填字段**，无鉴权也要写 `{type: no-auth}`；缺了导入报 `authorization field required`。另外「鉴权 → API-Key」字段**不做变量替换**，把 `{{#env.TOKEN#}}` 写进去运行期会得到空值并报 `API key is required ... but was empty`——token 一律放 `headers`。
12. **`headers` / `params` 必须是「每行一个 `key: value`」的字符串**。写成 YAML 双引号多行会被折叠成空格，两个 key 挤一行，YAML 合法但导入失败。要换行就写 `"a: 1\nb: 2"` 的转义形式。
13. **运行期枚举字段只能取 Dify 真实枚举值**。`error_strategy` 只有 `fail-branch` / `default-value`——`terminated` / `continue-on-error` / `remove-abnormal-output` 属于 `error_handle_mode`（iteration / loop 用）；`start` 变量类型没有 `url` / `json`；`if-else` 的空值判断算子是 `null` / `not null`，不是 `is null`。这类错误导入期一律不拦，只在节点执行到那一步时抛 pydantic 报错。

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

校验器覆盖：版本与模式、节点字段、边端点与分支句柄、选择器根节点与**字段级引用**（引用不存在的输出、未声明的 `env` / `conversation` 变量）、模板引用合法性、容器结构、可达性与环、Agent 包引用、Human Input 结构、插件依赖、**运行期枚举值**（`error_strategy`、变量类型、比较算子）；以及一批「YAML 合法但 Dify 不认」的坑：**跨 End 输出变量重名**、**`http-request` 缺 `authorization`**、**`headers`/`params` 被折叠成一行**、**`code` 的 `main` 形参与 `variables` 不一致**、**文件带 BOM / CRLF**、**节点 id 非 13 位数字**。它**不**替代真实导入——最终以目标工作区导入弹窗与一次试跑为准。

## 交付清单

DSL 只描述结构，不含运行环境。`deliver_checklist.py` 把「插件没装、凭据没绑、知识库是占位符、触发器 URL 被清空、环境变量为空、Agent 包资产被剔」逐条列成待办，顺带给出输出契约：

```bash
python scripts/deliver_checklist.py app.dify.yml            # markdown 待办清单
python scripts/deliver_checklist.py app.dify.yml --format json
```

交付时把清单里没完成的部分原样告诉用户，不要只说"已生成，导入即可"。

另外两类**只有运行才会暴露**的问题，交付时必须主动提醒：

- **内网地址被 SSRF 拦**：HTTP 节点默认禁止访问私有网段，需在 Dify `.env` 设 `SSRF_PROXY_ALLOW_PRIVATE_IPS` 并重建 `ssrf_proxy` 容器。
- **工作区没有指定模型**：`model.provider` / `model.name` 必须在该实例已安装，否则运行期报 provider 校验失败。DSL 里只是占位，交付时明确要求使用者确认或替换。

## 输出规范

- 产物落在当前工作目录，文件名 `<kebab-case>.dify.yml`；中间产物放临时目录，不要混进交付目录。
- YAML 用 2 空格缩进，所有字符串型 id 加引号。
- 交付时说明三件事：目标版本、校验结果、交付清单里还没完成的项。

## 覆盖范围

| 用户要什么 | 怎么处理 |
|---|---|
| 方案 / 节点选型 / 改造思路 / Prompt 设计 | 直接给结论文字，不落文件 |
| 可导入的 DSL | 走「生成流程」，产出 `<kebab-case>.dify.yml` 并跑校验 |
| 导入失败排查 | 读现有 DSL 与报错，定位到节点、边句柄、选择器或版本，必要的给出修好的文件 |
| 交付前准备 | 跑 `deliver_checklist.py`，把插件、凭据、知识库、触发器、变量的待办列清楚 |

不负责：在 Dify 平台上点击搭建、发布、部署与验收；也不代为安装插件或填凭据。这些以目标工作区的实际状态为准，交付时列出需要在工作区补的项。

用户没要文件时不要擅自写盘；反过来，给了文件就必须跑过校验再说"可导入"。

## 参考文件

- `references/dsl-format.md` — 顶层结构、节点 wrapper、变量与选择器、dependencies
- `references/edge-and-layout.md` — 边、分支句柄、坐标与容器布局
- `references/target-version.md` — 目标版本基线（DSL 0.7.0 / Dify 1.17.1）与导入兼容判定
- `references/nodes/*.md` — 21 个节点的字段表与最小示例
