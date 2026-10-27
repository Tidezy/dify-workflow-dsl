# 结束（`end`）

`workflow` 应用的终止节点，声明一次运行最终返回哪些字段。

## 用途

- 把上游任意节点的输出映射成工作流的正式返回值（API 响应里的 `outputs` 对象）。
- 允许存在多个 `end`，每条分支各自收口，形成多出口工作流。
- 与 `answer` 的区别：`end` 只返回结构化数据，不向用户流式输出文本。

## 何时用 / 何时不要用

**用**：

- `app.mode: workflow` 的应用。
- 需要固定返回结构（如 `{"result": ..., "docs": ...}`）给调用方或被其他工作流当工具调用时。

**不要用**：

- `advanced-chat`（Chatflow）：用 `answer` 向用户输出。
- 纯副作用触发器工作流（定时同步、Webhook 落库）：可以不写 `end`，此时不返回常规输出。
- `iteration` / `loop` 容器内部：容器内禁止出现 `end`。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `end`。 |
| `title` | string | 是 | 画布标题，多出口时建议按分支命名（如「审批通过」）。 |
| `outputs` | array | 是 | 输出映射列表，**不能为空**，至少一条。 |
| `outputs[].variable` | string | 是 | 输出键名，即返回值里的字段名；不能为空串。 |
| `outputs[].value_selector` | string[] | 是 | 取值路径 `[node_id, key]`，至少一个元素。 |
| `outputs[].value_type` | string | 否 | 声明类型，如 `string` / `number` / `object` / `array[string]` / `file`；0.7.0 导出通常显式写出。 |
| `outputs[].label` | string | 否 | 展示用标签。 |

`value_type` 常见取值：`string`、`number`、`integer`、`boolean`、`object`、`file`、`array`、`array[string]`、`array[number]`、`array[object]`、`array[file]`、`any`。不确定时省略，让后端按选择器推断。

## 最小可导入示例

```yaml
- id: end_node
  type: custom
  data:
    type: end
    title: "结束"
    outputs:
      - variable: result
        value_selector: [llm_node, text]
        value_type: string
  position: {x: 700, y: 300}
  width: 244
  height: 90
```

多输出写法，字段名即 API 返回键：

```yaml
      - variable: decision
        value_selector: [human_review, __action_id]
        value_type: string
      - variable: comment
        value_selector: [human_review, comment]
        value_type: string
```

### 多出口（分支收口）

每条分支可以有自己的 `end`，返回不同字段集合；需要统一结构时先经 `variable-aggregator` 汇总。

```yaml
- id: end_approved
  type: custom
  data:
    type: end
    title: "审批通过"
    outputs:
      - variable: decision
        value_selector: [human_review, __action_id]
        value_type: string
  position: {x: 730, y: 190}
  width: 244
  height: 120
```

对应入边要带上分支 handle（`if-else` 用 `true`/`false`/case id，`human-input` 用动作 id）：

```yaml
- id: human_review-approve-end_approved-target
  source: human_review
  sourceHandle: approve
  target: end_approved
  targetHandle: target
  type: custom
  data: {sourceType: human-input, targetType: end, isInIteration: false, isInLoop: false}
```

## 数据流

- `end` 是汇点：**不产生可被下游引用的变量**，图里不应给它接出边。
- 输入侧只通过 `value_selector` 取上游输出：`["<node_id>", "<field>"]`；无法在 `end` 里写模板字符串做拼接，需要拼接请先用 `template-transform`。
- 运行结果形如 `{"outputs": {"result": "...", "comment": "..."}}`，键名由 `outputs[].variable` 决定。
- 可引用的来源：`start` 变量、`llm.text`、`code` 自定义输出、`http-request.body`、`human-input.__action_id`、`sys.user_id` 等。
- 入边 `targetHandle` 用 `target`；从 `if-else` / `question-classifier` / `human-input` 汇入时，`sourceHandle` 用分支 id。

## 常见导入失败原因

1. `outputs: []` 为空数组，校验直接失败。
2. 某条输出缺 `variable`（或为空白字符串），或 `value_selector` 为空数组。
3. `value_selector` 指向不存在的节点 id——跨工作区复制时节点 id 会被重写，必须同步改。
4. 把 `end` 放进 `iteration` / `loop`（容器内禁止 `end`）。
5. 给 `end` 再接出边，或把 `end` 写在分支里但整条分支从入口不可达，导致「终端不可达」校验失败。
6. 在 `advanced-chat` 里用 `end` 收口，导入不报错但对话前端看不到流式回复。

## 终止方式对比

| 节点 | 适用模式 | 是否返回 `outputs` | 能否有后继 |
|---|---|---|---|
| `end` | `workflow` | 是，结构由 `outputs` 决定 | 否 |
| `answer` | `advanced-chat` | 否，只推流文本 | 可以（非终止） |
| `knowledge-index` | 两者皆可（版本支持时） | 否，只做写入 | 否 |

触发器型副作用工作流可以整条链路都没有 `end`，但此时调用方拿不到常规输出。
