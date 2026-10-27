# 开始（`start`）

工作流/对话流的唯一入口节点，用表单变量把外部输入转成下游可引用的类型化变量。

## 用途

- 声明应用启动时展示给用户的输入表单（`variables`）。
- 把用户输入固化成 `["<node_id>", "<variable>"]` 选择器，供任意下游节点引用。
- 提供系统变量上下文：`{{#sys.query#}}`、`{{#sys.files#}}`、`{{#sys.user_id#}}`、`{{#sys.workflow_run_id#}}` 等。
- `advanced-chat` 常见做法是 `variables: []`，用户输入直接走 `{{#sys.query#}}` 与 `{{#sys.files#}}`。

## 何时用 / 何时不要用

**用**：

- 任何 `workflow` / `advanced-chat` 应用都需要且只需要一个 `start`。
- 需要让调用方按固定字段传参（文本、下拉、数字、文件）时。

**不要用**：

- 定时、Webhook、插件事件驱动的图：用 `trigger-schedule` / `trigger-webhook` / `trigger-plugin`，**不要**再放 `start`。
- `iteration` / `loop` 内部：那层入口是自动生成的 `iteration-start` / `loop-start`，手写 `start` 会破坏容器结构。
- 同一张图放两个 `start`（`isSingleton`，导入时入口冲突）。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `start`。 |
| `title` | string | 是 | 画布标题，仅展示用。 |
| `variables` | array | 否 | 输入变量列表，缺省 `[]`；允许为空。 |
| `variables[].variable` | string | 是 | 变量键名，节点内唯一；下游用 `["<node_id>","<variable>"]` 引用。 |
| `variables[].label` | string | 是 | 表单显示名，节点内唯一。 |
| `variables[].type` | string | 是 | 表单控件类型，取值见下表。 |
| `variables[].required` | boolean | 是 | 是否必填。 |
| `variables[].max_length` | number | 否 | 文本类输入最大长度。 |
| `variables[].default` | string / number | 否 | 默认值。 |
| `variables[].options` | string[] | 否 | `type: select` 的候选项。 |
| `variables[].placeholder` | string | 否 | 输入框占位提示。 |
| `variables[].hint` | string | 否 | 字段下方帮助文本。 |
| `variables[].unit` | string | 否 | `type: number` 的单位后缀。 |
| `variables[].json_schema` | string / object | 否 | `json` / `json_object` 的结构约束。 |
| `variables[].hide` | boolean | 否 | 是否在表单中隐藏。 |
| `variables[].allowed_file_types` | string[] | 否 | 文件类：`image` / `document` / `audio` / `video` / `custom`。 |
| `variables[].allowed_file_extensions` | string[] | 否 | 文件类：如 `[.pdf, .docx]`；`custom` 必须给。 |
| `variables[].allowed_file_upload_methods` | string[] | 否 | 文件类：`local_file` / `remote_url`。 |
| `variables[].number_limits` | number | 否 | 文件类：最多允许几个文件。 |

`variables[].type` 取值：

| 值 | 说明 |
|---|---|
| `text-input` | 单行文本。 |
| `paragraph` | 多行文本。 |
| `select` | 下拉选择，需配 `options`。 |
| `number` | 数字。 |
| `url` | URL，带格式校验。 |
| `file` | 单个文件。 |
| `file-list` | 文件列表（`array[file]`）。 |
| `json` | JSON 文本。 |
| `checkbox` | 布尔勾选。 |

旧导出中还会出现 `files`、`json_object` 等历史值；新建 DSL 优先用上表值，遇到旧文件保持原样。

## 最小可导入示例

```yaml
- id: start_node
  type: custom
  data:
    type: start
    title: "开始"
    variables:
      - label: "输入文本"
        variable: input_text
        type: paragraph
        required: true
        max_length: 10000
      - label: "附件"
        variable: files
        type: file-list
        required: false
        allowed_file_types: [document]
        allowed_file_extensions: []
        allowed_file_upload_methods: [local_file]
        number_limits: 3
  position: {x: 40, y: 300}
  width: 244
  height: 90
```

## 数据流

- 每个 `variables[].variable` 都成为节点输出：模板写 `{{#start_node.input_text#}}`，结构化字段写 `["start_node", "input_text"]`。
- 系统变量走独立前缀：模板 `{{#sys.query#}}`，选择器 `["sys", "query"]`；环境变量 `["env", "KEY"]`；会话变量 `["conversation", "name"]`（仅 `advanced-chat`）。
- `start` 不接受入边，出边 `sourceHandle` 用 `source`。

## 触发器节点（入口但非 `start`）

三种触发器都是图入口：**不能有入边**，**不产生 `start` 节点**，图里不要再新增 `start`。出边 `sourceHandle` 用 `source`（后端部分用例写作 `success`，以目标工作区导出的 DSL 为准）。

通用约束：

- 触发器工作流可以是副作用型（只做写入/通知），**允许没有 `end`**；需要返回结果时再加 `end`。
- 触发器节点不能放进 `iteration` / `loop`。
- 导出的节点 wrapper 与普通节点一致：`type: custom` + `data.type: trigger-*`。

### trigger-schedule

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mode` | string | 是 | `visual`（可视化配置）或 `cron`（Cron 表达式）。 |
| `frequency` | string | `mode: visual` 时 | `hourly` / `daily` / `weekly` / `monthly`。 |
| `timezone` | string | 否 | 如 `Asia/Shanghai`。 |
| `visual_config` | object | `mode: visual` 时 | 可视化配置，常见 `time: "09:00 AM"`；weekly/monthly 还会记录星期或日期，字段以目标工作区导出的 DSL 为准。 |
| `cron_expression` | string | `mode: cron` 时 | Cron 串；`mode: visual` 时导出为空串 `""`。 |

官方导出会重置调度配置，生产 DSL 请从目标工作区导出后复制该段。

### trigger-webhook

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `webhook_url` | string | 运行时必需 | **导出时被清空为空串**；导入后由目标工作区重新生成，不要写死地址。 |
| `webhook_debug_url` | string | 否 | 调试地址，同样在导出时被清空。 |
| `method` | string | 是 | 如 `POST`。 |
| `content_type` | string | 否 | 如 `application/json`。 |
| `headers` | array | 否 | 自定义请求头定义。 |
| `params` | array | 否 | Query 参数定义。 |
| `body` | array | 否 | 请求体字段定义，通常决定下游可引用的输出。 |
| `async_mode` | boolean | 否 | 是否异步响应。 |
| `status_code` | number | 否 | 同步响应状态码。 |
| `response_body` | string | 否 | 自定义响应体模板。 |
| `variables` | array | 否 | 对调用方暴露/接收的变量声明。 |

### trigger-plugin

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider_id` | string | 是 | Provider 标识，形如 `author/plugin/provider`。 |
| `provider_name` | string | 是 | 通常与 `provider_id` 相同。 |
| `provider_type` | string | 否 | 常见 `builtin`。 |
| `plugin_id` | string | 是 | 形如 `author/plugin`；插件必须同时出现在顶层 `dependencies`。 |
| `plugin_unique_identifier` | string | 否 | 精确版本标识，从导出复制，不要臆造。 |
| `event_name` | string | 是 | 订阅的事件名。 |
| `event_label` | string | 否 | 事件显示名。 |
| `event_parameters` | object | 否 | 事件参数默认值。 |
| `event_configurations` | object | 否 | 事件级配置。 |
| `output_schema` | object | 否 | 事件载荷结构，决定下游可引用的输出字段。 |
| `config` | object | 否 | 插件触发配置；`subscription_id` 在官方导出中被清空。 |

该节点高度依赖插件实现，不同插件字段差异大；声称可用于生产前，先用目标工作区导出一份最小样例对齐。

## 常见导入失败原因

1. 图里同时存在 `start` 与 trigger 节点，被判定为多入口。
2. `variables[].type` 填了 `text` / `string` / `textarea` 等非枚举值，表单控件渲染失败。
3. `variables[].variable` 或 `label` 重名，节点内唯一性校验不通过。
4. 文件类变量开了 `features.file_upload` 却没给 `allowed_file_types`，或反过来应用未开启上传，运行时被拒。
5. 触发器写成 `webhook_url: https://...` 并期望导入即生效——导出会清空，必须导入后在工作区重新生成。
6. `trigger-schedule` 的 `mode` 与配置不匹配（`cron` 却没有 `cron_expression`，或 `visual` 却填了 cron 串）。
