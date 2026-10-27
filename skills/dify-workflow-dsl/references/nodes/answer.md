# 直接回复（`answer`）

`advanced-chat` 应用里向用户流式输出文本的节点，支持在模板中内联上游变量。

## 用途

- 把 LLM 结果、http 返回、模板渲染结果直接回复给对话前端，逐字流式呈现。
- 在一个 Chatflow 里做多段回复：流程中途先说一句，后续节点继续计算，再来一段。
- 分支式回复：`if-else` / `question-classifier` 的不同分支各接一个 `answer`。

## 何时用 / 何时不要用

**用**：

- `app.mode: advanced-chat`。
- 需要「边说边算」的交互，或多条分支各自给出不同话术。

**不要用**：

- `app.mode: workflow`：用 `end` 返回结构化数据；`workflow` 里放 `answer` 不会产生 API 输出。
- 需要返回结构化字段给调用方时（`answer` 只有文本流，不构成 `outputs` 对象）。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `answer`。 |
| `title` | string | 是 | 画布标题，多分支时建议按分支命名。 |
| `answer` | string | 是 | 回复模板，支持 `{{#node_id.field#}}` 插值；**不能为空**。 |
| `variables` | array | 否 | 模板引用的变量登记表，缺省 `[]`；不参与校验，空数组也能正常解析模板。 |
| `variables[].variable` | string | 否 | 登记名，通常写成 `node_id.field` 形式。 |
| `variables[].value_selector` | string[] | 否 | 对应取值路径 `[node_id, field]`。 |
| `variables[].value_type` | string | 否 | 声明类型，导出时常见。 |
| `variables[].label` | string | 否 | 展示用标签。 |

不支持在模板里渲染 `array[object]` 类型的变量（编辑器会把它从可选列表里过滤掉）；要展示列表内容，先用 `template-transform` 渲染成字符串。

## 最小可导入示例

```yaml
- id: answer_node
  type: custom
  data:
    type: answer
    title: "直接回复"
    answer: "{{#llm_node.text#}}"
    variables:
      - variable: llm_node.text
        value_selector: [llm_node, text]
        value_type: string
  position: {x: 700, y: 300}
  width: 244
  height: 90
```

混合静态文案与多个变量：

```yaml
    answer: |
      你好，关于「{{#start_node.topic#}}」的回答如下：

      {{#llm_node.text#}}

      ---
      会话 ID：{{#sys.conversation_id#}}
```

## 数据流

- 输入：模板里的 `{{#<node_id>.<field>#}}`，或 `variables[].value_selector` 的 `["<node_id>", "<field>"]` 形态。
- 输出：**不产生下游可引用的变量**，只是向用户推流。
- `answer` 不是终止节点——后面可以继续接节点（先回一句「正在检索…」，再继续跑检索）；但不要指望下游读取它。
- 入边 `targetHandle` 用 `target`；从分支节点汇入时 `sourceHandle` 用分支 id（`true` / `false` / case id / class id）。
- 纯静态文案时可直接 `variables: []` 并写死文本。

## 多段回复与分支回复

`answer` 不是终止节点，因此可以做「先回一句、再继续算」的分段流式体验：

```yaml
# 第一段：即时反馈
- id: ack_answer
  type: custom
  data:
    type: answer
    title: "确认收到"
    answer: "正在检索资料，请稍候…"
    variables: []
  position: {x: 340, y: 300}
  width: 244
  height: 90

# 第二段：拿到结果后的正式回复，接在 llm 之后
- id: final_answer
  type: custom
  data:
    type: answer
    title: "正式回复"
    answer: "{{#llm_node.text#}}"
    variables:
      - variable: llm_node.text
        value_selector: [llm_node, text]
        value_type: string
  position: {x: 1020, y: 300}
  width: 244
  height: 90
```

分支场景下每个分支各自收一个 `answer`，`sourceHandle` 用分支 id；不要在分支之后再汇到同一个 `answer`，除非先用 `variable-aggregator` 统一入参。

## 常见导入失败原因

1. `answer` 为空字符串或缺失——这是唯一强校验项。
2. `variables[].value_selector` 指向不存在的节点或字段，编辑器打开时变量显示为未解析。
3. 在 `workflow` 模式的 DSL 里用 `answer` 收口，运行时无 `outputs`，调用方拿不到结果。
4. 试图在 `answer` 里直接 `{{#<数组对象>#}}`，渲染为空或报错，应先用 `template-transform`。
5. `answer` 与 `end` 混用在同一分支末端，返回值与流式回复语义冲突，排查困难。
