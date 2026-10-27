# DSL 结构规范

适用于 DSL `0.6.0`（Dify 1.15.x）与 `0.7.0`（Dify 1.16.x）。字段以**目标工作区导出的 DSL 为准**；本文给出的是可直接导入的最小完整骨架。

## 文件与命名

- 格式：YAML（默认）或 JSON。YAML 用 2 空格缩进，字符串型 ID 必须加引号。
- 文件名：`<kebab-case>.dify.yml` / `<kebab-case>.dify.json`。
- 一个文件 = 一个应用。没有"多应用打包"的概念。

## 顶层骨架

### 图模式（workflow / advanced-chat）

```yaml
version: "0.7.0"
kind: app
app:
  name: "示例应用"
  description: "说明这个应用做什么"
  icon: "🤖"
  icon_type: emoji
  icon_background: "#FFEAD5"
  mode: advanced-chat          # 或 workflow
  use_icon_as_answer_icon: false
dependencies: []
workflow:
  environment_variables: []
  conversation_variables: []
  features:
    file_upload:
      enabled: false
    opening_statement: ""      # 仅 advanced-chat
    retriever_resource:
      enabled: false
    sensitive_word_avoidance:
      enabled: false
    speech_to_text:
      enabled: false
    suggested_questions: []    # 仅 advanced-chat
    suggested_questions_after_answer:
      enabled: false
    text_to_speech:
      enabled: false
  graph:
    nodes: []
    edges: []
    viewport:
      x: 0
      y: 0
      zoom: 0.7
```

### Agent 模式（仅 0.7.0）

```yaml
version: "0.7.0"
kind: app
app:
  name: "独立 Agent"
  mode: agent
  icon: "🧠"
  icon_type: emoji
  icon_background: "#F3E8FF"
  use_icon_as_answer_icon: false
agent:
  package_ref: main_agent
agent_packages:
  main_agent:
    schema_version: 1
    metadata: { name: "独立 Agent", description: "", role: assistant }
    soul: { schema_version: 1 }
    omitted_assets: []
dependencies: []
```

Agent 模式**没有 `workflow` 段**。不要把它和"workflow 里放一个 Agent 节点"混为一谈，后者见 `nodes/agent.md`。

## app 段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | 是 | 应用名，导入后显示在应用列表 |
| `mode` | enum | 是 | `workflow` / `advanced-chat` / `agent`（`agent` 仅 0.7.0） |
| `description` | string | 否 | 应用说明 |
| `icon` | string | 否 | emoji 字符或图片 URL |
| `icon_type` | enum | 否 | `emoji` / `image` |
| `icon_background` | string | 否 | 十六进制色值，如 `#FFEAD5` |
| `use_icon_as_answer_icon` | bool | 否 | 是否把应用图标当作回答头像 |

## workflow 段

| 字段 | 类型 | 说明 |
|---|---|---|
| `environment_variables` | array | 环境变量，节点内用 `["env", KEY]` 只读引用 |
| `conversation_variables` | array | 会话变量，仅 `advanced-chat` 有意义；用 assigner 写入 |
| `features` | object | 应用级能力开关，见上方骨架 |
| `graph.nodes` | array | 节点列表 |
| `graph.edges` | array | 边列表 |
| `graph.viewport` | object | 画布视口，`x` / `y` / `zoom` |

`features` 在不同版本导出的键不完全一致，缺失的键会被当成默认值。**不要臆造 `features` 子键**——写不确定的键比不写更容易触发导入校验失败。

## 节点 wrapper

顶层节点：

```yaml
- id: "1770000000001"
  type: custom
  data:
    type: llm
    title: "生成回答"
  position: { x: 380, y: 282 }
  positionAbsolute: { x: 380, y: 282 }
  sourcePosition: right
  targetPosition: left
  width: 244
  height: 98
```

容器子节点额外需要：

```yaml
  parentId: "1770000000000"
  zIndex: 1002
```

| 字段 | 说明 |
|---|---|
| `id` | 节点唯一标识。**字符串**，建议 13 位时间戳形态；引号不可省 |
| `type` | wrapper 类型。普通节点 `custom`；迭代起点 `custom-iteration-start`；循环起点 `custom-loop-start`；画布注释 `custom-note` |
| `data.type` | 真实节点类型，决定执行语义。注释节点此处可为空 |
| `position` | 顶层为画布坐标；容器子节点为**相对父容器**的坐标 |
| `positionAbsolute` | 绝对坐标（0.7.0 导出字段，可省） |
| `sourcePosition` / `targetPosition` | 连线锚点方位，`right` / `left`（可省） |
| `width` / `height` | 节点尺寸；容器类节点**同时**要在 `data` 内写一份 |
| `parentId` | 容器子节点必填，等于容器 id |
| `zIndex` | 容器子节点 `1002`，容器本身 `1` |

> 各 `nodes/*.md` 的示例为省篇幅只写到 `position`，`positionAbsolute` / `sourcePosition` / `targetPosition` 按上表补齐即可（可省略，但补上后画布排版正常）。

## 边

```yaml
- id: "1770000000001-source-1770000000002-target"
  source: "1770000000001"
  sourceHandle: source
  target: "1770000000002"
  targetHandle: target
  type: custom
  zIndex: 0
  data:
    sourceType: start
    targetType: llm
    isInIteration: false
    isInLoop: false
```

- `id` 约定：`{source}-{sourceHandle}-{target}-{targetHandle}`。
- `sourceHandle` 默认 `"source"`；分支节点用分支标识（见 `edge-and-layout.md`）。
- `targetHandle` 恒为 `"target"`。
- `data.sourceType` / `data.targetType` 必须与两端 `data.type` 一致，写错会导致画布显示异常。
- 容器内的边额外加 `isInIteration` / `isInLoop` 与对应的 `iteration_id` / `loop_id`，`zIndex: 1002`。

## 变量与选择器

Dify 有两套引用语法，用途不同，不要混：

| 语法 | 用在哪 | 例子 |
|---|---|---|
| `["node_id", "field"]` | 所有 `*_selector` 字段（数组） | `value_selector: ["1770000000001", "text"]` |
| `{{#node_id.field#}}` | 字符串模板内部（prompt、url、body、form_content） | `"{{#1770000000001.text#}}"` |

系统变量：

| 选择器 | 含义 | 可用范围 |
|---|---|---|
| `["sys", "query"]` | 用户本轮输入 | 仅 `advanced-chat` |
| `["sys", "files"]` | 用户上传文件数组 | 仅 `advanced-chat` 且开启文件上传 |
| `["sys", "user_id"]` | 终端用户标识 | 两者 |
| `["sys", "conversation_id"]` | 会话 ID | `advanced-chat` |
| `["env", "KEY"]` | 环境变量，只读 | 两者 |

**`workflow` 模式不存在 `sys.query`**。这是最常见的运行时错误来源：workflow 的用户输入必须来自 `start` 节点的变量，LLM 节点也不能带 `memory` 块。

### 引用硬约束

- 模板里 `{{#...#}}` 的节点 id 只能由**字母、数字、下划线**组成，长度 1–50。带连字符的 id 在边和数组选择器里可用，但放进模板会解析失败。
- 只能引用上游已声明的输出。输出名不存在 → 运行期取到空值，且不会报错，极难排查。
- 引用 `start` 节点用 `[start_id, var_name]`；少数导出写 `[start_id, "sys.query"]`，两种都能被识别。

## dependencies 段

引用了工作区没有的插件（模型供应商、工具、触发器、数据源）时，必须在此声明，否则导入后节点变成"未安装插件"的灰色节点。

```yaml
dependencies:
  - current_identifier: null
    type: marketplace
    value:
      marketplace_plugin_unique_identifier: langgenius/openai:0.2.6@<sha256>
      version: null
```

- `marketplace_plugin_unique_identifier` 的真实值**只能从导出文件复制**，不要自己拼版本号。
- 只用内置模型供应商（如 `langgenius/openai/openai` 已在工作区安装）时，`dependencies: []` 是合法的。
- 引用 `provider_type: mcp` / `api` / `workflow` 的本地工具时，导出会带上工作区本地标识，通常**不可跨实例移植**，导入后需重新绑定。

## 模型引用

```yaml
model:
  provider: langgenius/deepseek/deepseek   # 插件供应商全路径
  name: deepseek-chat                      # 真实存在的模型名
  mode: chat                               # chat / completion
  completion_params:
    temperature: 0.3
```

- `provider` 三段式：`<作者>/<插件>/<provider>`。
- `name` 必须是该供应商真实提供的模型名。**编造的模型名会在运行期报 provider 校验失败**，导入阶段不一定拦住。
- 不确定时从目标工作区 `/console/api/workspaces/current/model-providers` 拉取，或让用户确认拼写。

## 三种模式的最小结构差异

| 项 | `workflow` | `advanced-chat` | `agent`（0.7.0） |
|---|---|---|---|
| 入口 | `start` 或触发器 | `start`（必须） | 无图 |
| 出口 | 至少一个可达 `end` | 至少一个可达 `answer` | 无图 |
| `sys.query` | 不存在 | 存在 | 由 Agent 运行时提供 |
| `conversation_variables` | 空 | 可用 | 不适用 |
| `memory` 块 | 禁止 | 可开 | 不适用 |
| 触发器 | 可用 | 不可用 | 不可用 |

副作用型 workflow（例如只写知识库、只发 HTTP）允许没有 `end`，但必须有明确的可达终点节点。

## 导入前后检查

导入前（本地）：

1. `version` 是带引号的字符串；
2. 所有节点 `id` 唯一且为字符串；
3. 每条边两端都存在；
4. 每个可达终点能追溯到 `start` / 触发器；
5. 引用的插件都写进了 `dependencies`；
6. 跑 `python scripts/validate_dsl.py --strict --target-version 0.7.0 <file>`。

导入后（工作区）：

1. 看导入弹窗的警告：缺插件、凭据未绑定、触发器配置被重置都会在这里出现；
2. Agent 节点检查 `credential_ref`、`human_contacts`；
3. Webhook / 定时触发器重新配置并取回新 URL；
4. 用一条最小输入跑一遍，确认变量不是空值。

## 相关

- `edge-and-layout.md` — 边、分支 handle、坐标布局
- `version-deltas.md` — 0.6.0 与 0.7.0 的差异与迁移清单
- `nodes/*.md` — 各节点字段表与最小示例
