# 参数提取节点（`parameter-extractor`）

用一次 LLM 调用把自然语言压成若干具名字段，每个字段直接成为一个可引用的输出变量。

## 用途

- 在 `if-else` 或 `tool` 之前，把用户自由输入变成确定字段（SQL、日期、枚举、数量）。
- 从多轮对话或长文本里稳定抽取业务参数，避免下游再解析字符串。
- 产出"是否成功抽取"这类可用于分支的信号。

## 何时用 / 何时不要用

适合：

- 下游需要的是**少量**、**扁平**、**类型明确**的字段。
- 抽取结果要交给条件节点或工具参数，必须稳定命中。

不要用：

- 只要一段自由文本回答 → 用 `llm`。
- 类别互斥且数量固定（三五个选项） → 用 `question-classifier`，更省 token。
- 需要深层嵌套、数组元素还要再套对象的严格 schema → 用 `llm` 的 `structured_output`。
- 规则能直接命中（固定关键词、正则）→ 用 `code` 或 `if-else`。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 画布显示名 |
| `instruction` | string | 是 | 抽取规则说明，写清"没抽到怎么办" |
| `model` | object | 是 | 需含 `provider`、`name`、`mode`、`completion_params` |
| `parameters` | array | 是 | 待抽取字段清单，至少一项 |
| `parameters[].name` | string | 是 | 输出变量名，下游按此名引用 |
| `parameters[].type` | string | 是 | 见下方类型枚举 |
| `parameters[].description` | string | 是 | 给模型的字段说明，决定抽取准确率 |
| `parameters[].required` | boolean | 否 | 是否必须抽到 |
| `parameters[].options` | string[] | 否 | `type: select` 时的候选值 |
| `query` | string[] | 是 | 被抽取的输入，如 `["sys", "query"]` 或 `["<node_id>", "text"]` |
| `reasoning_mode` | string | 是 | `prompt` 或 `function_call`（后者需模型支持工具调用） |
| `memory` | object | 否 | 同 `llm`，仅 Chatflow 有意义 |
| `vision` | object | 否 | `{enabled: false}`；开启时补 `configs.variable_selector` |
| `selected` | boolean | 是 | 导出固定为 `false` |

### `parameters[].type` 取值

| 值 | 说明 |
| --- | --- |
| `string` | 文本 |
| `number` | 数值 |
| `boolean` | 布尔 |
| `select` | 枚举，配 `options` |
| `array[string]` | 字符串数组 |
| `array[number]` | 数值数组 |
| `array[boolean]` | 布尔数组 |
| `array[object]` | 对象数组 |

## 最小可导入示例

```yaml
- id: "1770000000104"
  type: custom
  data:
    type: parameter-extractor
    title: "提取 SQL"
    instruction: "从输入中提取一条只读 SELECT 语句；没有 SQL 时返回空字符串。"
    model:
      provider: langgenius/tongyi/tongyi
      name: qwen3.5-plus
      mode: chat
      completion_params:
        temperature: 0.1
    parameters:
      - name: sql
        type: string
        description: "只读 SELECT 语句，无则空串"
        required: false
    query: ["1770000000005", "text"]
    reasoning_mode: prompt
    vision:
      enabled: false
    selected: false
  position: {x: 680, y: 282}
  width: 244
  height: 90
```

## 数据流

- `parameters` 里每个 `name` 都是一个输出变量：`["<node_id>", "sql"]`、`{{#<node_id>.sql#}}`。
- 字段名大小写敏感，引用时必须与 `name` 完全一致；建议统一用 snake_case。
- 部分导出还会带 `__is_success` / `__reason` 之类的辅助信号，是否可用以目标工作区导出的 DSL 为准。
- 出边 `sourceHandle` 固定为 `source`；按抽取结果分流请在其后接 `if-else`。

## 常见导入失败原因

- `parameters` 为空数组，或某项缺 `name` / `description`。
- `query` 写成字符串而不是选择器数组（应为 `["<node_id>", "key"]`）。
- `reasoning_mode: function_call` 但所选模型不支持工具调用，运行期失败。
- `parameters[].name` 与已有节点输出重名或含空格、`-` 等非标识符字符，引用时解析失败。
- `type: select` 却没给 `options`，字段恒为空。
