# LLM 节点（`llm`）

在流程里调用一个大语言模型：按 `prompt_template` 渲染消息，可选注入检索上下文、会话记忆与图片输入，输出文本。

## 用途

- 承担自然语言的理解与生成：总结、改写、翻译、抽取、判断。
- 作为知识库问答的最后一步，用 `context` 把知识检索节点返回的片段喂给模型。
- 在 Chatflow 中依托 `memory` 实现多轮对话，把历史消息自动拼进提示词。

## 何时用 / 何时不要用

适合：

- 需要模型推理或自由文本输出的任意环节。
- 需要把多个上游变量拼进同一段提示词（`{{#<node_id>.<key>#}}`）。

不要用：

- 只是把固定字符串和变量拼起来 → 用 `template-transform`，更便宜也更好预测。
- 只需要从文本里取几个结构化字段、要严格类型 → 用 `parameter-extractor`。
- 需要模型自主多轮调用工具 → 用 `agent`。
- 需要互斥分流 → 用 `if-else` 或 `question-classifier`。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 画布显示名 |
| `model` | object | 是 | 必须同时具备 `provider`、`name`、`mode`、`completion_params` 四项 |
| `model.provider` | string | 是 | 插件形态标识，如 `langgenius/tongyi/tongyi`，需与 `dependencies` 一致 |
| `model.name` | string | 是 | 模型名，必须在目标工作区已安装 |
| `model.mode` | string | 是 | `chat` 或 `completion` |
| `model.completion_params` | object | 是 | 如 `temperature`、`max_tokens`；没有额外参数也要写 `{}` |
| `prompt_template` | array | 是 | `chat` 模式下每条消息一个条目 |
| `prompt_template[].id` | string | 是 | uuid 形态的稳定 id，0.7.0 必带且条目间不可重复 |
| `prompt_template[].role` | string | 是 | `system` / `user` / `assistant` |
| `prompt_template[].text` | string | 是 | 提示词正文，支持 `{{#...#}}` 变量插入 |
| `prompt_template[].edition_type` | string | 否 | `basic`（默认）或 `jinja2`；用 `jinja2` 时正文写在 `jinja2_text` |
| `prompt_config.jinja2_variables` | array | 否 | `jinja2` 模式的变量映射，元素形如 `{variable, value_selector}` |
| `context` | object | 是 | 即使不启用也必须存在，形如 `{enabled: false, variable_selector: []}` |
| `context.variable_selector` | string[] | 是 | 指向知识检索节点，如 `["<kr_node_id>", "result"]` |
| `memory` | object | 否 | 仅 Chatflow 有意义，含 `query_prompt_template`、`role_prefix`、`window` |
| `memory.role_prefix` | object | 否 | `{assistant: "", user: ""}`，0.7.0 导出通常保留空串 |
| `memory.window` | object | 否 | `{enabled: false, size: 50}`，`size` 控制带几轮历史 |
| `memory.query_prompt_template` | string | 否 | 默认 `{{#sys.query#}}\n\n{{#sys.files#}}` |
| `vision` | object | 否 | `{enabled: false}`；开启时补 `configs.variable_selector` 与 `configs.detail` |
| `structured_output_enabled` | boolean | 否 | 结构化输出开关，模型需支持 |
| `structured_output.schema` | object | 否 | JSON Schema，根对象需 `additionalProperties: false` |
| `selected` | boolean | 是 | 导出固定为 `false` |

## 最小可导入示例

```yaml
- id: "1770000000101"
  type: custom
  data:
    type: llm
    title: "总结输入"
    model:
      provider: langgenius/tongyi/tongyi
      name: qwen3.5-flash
      mode: chat
      completion_params:
        temperature: 0.3
    prompt_template:
      - id: 9e05cb8e-0000-4000-9000-000000000001
        role: system
        text: "用三句话总结用户输入，不要添加额外信息。"
      - id: 9e05cb8e-0000-4000-9000-000000000002
        role: user
        text: "{{#sys.query#}}"
    context:
      enabled: false
      variable_selector: []
    memory:
      query_prompt_template: "{{#sys.query#}}\n\n{{#sys.files#}}"
      role_prefix:
        assistant: ""
        user: ""
      window:
        enabled: false
        size: 50
    vision:
      enabled: false
    selected: false
  position: {x: 380, y: 282}
  width: 244
  height: 98
```

## 数据流

输出变量（下游用 `["<node_id>", "<key>"]` 选择器或 `{{#<node_id>.<key>#}}` 模板语法引用）：

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `text` | string | 模型生成的文本，最常用 |
| `reasoning_content` | string | 思考过程，仅推理类模型返回 |
| `usage` | object | token 用量，含 `prompt_tokens` / `completion_tokens` |
| `structured_output.*` | 按 schema | 开启结构化输出后按声明字段展开 |

RAG 组合顺序：

1. `knowledge-retrieval` 节点产出 `result`；
2. LLM 的 `context.enabled: true`、`context.variable_selector: ["<kr_node_id>", "result"]`；
3. 在提示词里写 `{{#context#}}` 作为检索结果的占位。

## 常见导入失败原因

- `prompt_template` 条目缺 `id`，或多条复用同一个 `id`：0.7.0 每条都要独立的 uuid 形态 id。
- 省略了 `context`：即使不启用，也必须留 `{enabled: false, variable_selector: []}`。
- `model` 缺 `completion_params`（或写成 `null`），或 `provider` 不是 `langgenius/<plugin>/<provider>` 形态。
- `context.enabled: true` 但 `variable_selector` 为空，或指向不存在的节点、非 `result` 的键。
- 用到的模型插件没有写进顶层 `dependencies`，导入后节点显示模型不可用。
