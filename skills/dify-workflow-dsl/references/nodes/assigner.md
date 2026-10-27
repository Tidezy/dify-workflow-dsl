# 变量赋值（`assigner`）

把值写回一个**可写变量**（会话变量或 loop 变量），是 Chatflow 记忆与循环状态累积的唯一手段。

## 用途

- Chatflow 里维护跨轮状态：`memory`、`user_profile`、`last_intent`。
- `loop` 内累加计数器、拼接中间结果、推进迭代状态。
- 把上游 LLM / 代码节点的输出落到命名变量，供后续 Node 或下一轮对话直接引用。

## 何时用 / 何时不要用

适合：

- 值需要在**同一会话的后续轮次**继续有效（会话变量）。
- 值需要跨 `loop` 的多次迭代累积（loop 变量）。
- 需要条件性重置（`operation: clear`）或追加（`append`）。

不要用：

- 只是一次性的分支汇合 → 用 `variable-aggregator`。
- 只是想给下游换个名字、做一次变换 → 用 `template-transform` / `code`，无需落变量。
- 想改环境变量或 `sys.*`：环境变量只读，`sys.*` 不可写，写入目标必须在 `workflow.conversation_variables` 或 loop 的 `loop_variables` 中声明过。
- Workflow（非 Chatflow）模式：没有会话变量，`assigner` 的可写目标通常只剩 loop 变量。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | `assigner`；部分旧导出写作 `variable-assigner`，保留 workspace 原有写法。 |
| `title` | string | 是 | 画布标题。 |
| `version` | string | 否 | 缺省为 v1；v2 必须写字符串 `"2"`。 |
| `items` | array | 是 | 赋值项列表，至少一项。 |
| `items[].variable_selector` | string[] | 是 | 写入目标，如 `["conversation", "memory"]` 或 `["<loop_id>", "count"]`。 |
| `items[].input_type` | string | 是 | `variable`（取上游变量）或 `constant`（字面量）。 |
| `items[].value` | any | 是 | v1：`input_type: variable` 时为选择器数组，`constant` 时为字面量；**v2 一律在此存放值/选择器**。 |
| `items[].operation` | string | 是 | 写入运算，见下表。 |
| `items[].write_mode` | string | 否 | `over-write` / `append` / `clear`；v2 官方导出仍会写出。 |
| `isInLoop` | boolean | loop 内必填 | 在 loop 容器内为 `true`。 |
| `isInIteration` | boolean | 否 | 在 iteration 内为 `true`，loop 内为 `false`。 |
| `loop_id` | string | loop 内必填 | 所属 loop 节点 ID。 |
| `selected` | boolean | 是 | 导出固定 `false`。 |

### v1 与 v2 的区别

| | v1 | v2 |
|---|---|---|
| 标识 | 无 `version` 字段 | `version: "2"`（字符串，写数字会退化成 v1 解析） |
| 取值字段 | `value`（variable 时是选择器数组） | `value`（同样存选择器或字面量，**不再用 `value_selector`**） |
| 容器标记 | 视导出而定 | loop 内固定 `isInLoop: true` + `loop_id` |
| 典型来源 | Dify 1.15.x 及更早导出 | Dify 1.16.x 导出 |

v1 里 `items[]` 只有 `variable_selector` / `input_type` / `value` / `operation` / `write_mode` 五项；v2 结构相同但语义收敛到 `value` 一处。编辑既有文件时按导出原样保留，不要在两代之间混填。

### `operation` / `write_mode` 常用取值

| 值 | 说明 |
|---|---|
| `over-write` | 覆盖旧值（默认）。 |
| `append` | 追加到已有字符串或数组末尾。 |
| `clear` | 清空该变量。 |
| `"+="` | 数值累加（loop 计数器标准写法）。 |

`operation` 与 `write_mode` 语义有重叠，官方导出会同时写出，**两个都留**，不要只保留一个。其余算术/集合运算（`-=`、`*=`、`/=` 等）是否可用以目标工作区导出的 DSL 为准。

### 可写目标

| 目标 | 选择器 | 声明位置 | 作用域 |
|---|---|---|---|
| 会话变量 | `["conversation", "<name>"]` | `workflow.conversation_variables` | 同一会话跨轮持久，仅 `advanced-chat` |
| loop 变量 | `["<loop_id>", "<name>"]` | loop 节点的 `loop_variables` | 仅该 loop 的本次执行 |
| 环境变量 | `["env", "<KEY>"]` | `workflow.environment_variables` | **只读，不能作为写入目标** |

## 最小可导入示例

### v2：loop 内累加（0.7.0 真实导出形态）

```yaml
- id: "increase_count"
  parentId: "quality_loop"
  type: custom
  data:
    type: assigner
    title: "增加检查次数"
    version: "2"
    isInIteration: false
    isInLoop: true
    loop_id: "quality_loop"
    items:
      - variable_selector: ["quality_loop", "review_count"]
        input_type: constant
        operation: "+="
        value: 1
        write_mode: over-write
  position: {x: 190, y: 62}
  width: 244
  height: 86
  zIndex: 1002
```

### v1：写入 Chatflow 会话变量

```yaml
- id: "1770000000701"
  type: custom
  data:
    type: assigner
    title: "写入会话记忆"
    items:
      - variable_selector: ["conversation", "memory"]
        input_type: variable
        value: ["1770000000401", "text"]
        operation: over-write
        write_mode: over-write
    selected: false
  position: {x: 680, y: 282}
  width: 244
  height: 116
```

## 数据流

- 节点**不产生新的输出变量**；写入后，下游直接引用目标选择器本身（如 `["conversation", "memory"]`），而不是 `["<assigner_id>", ...]`。
- 目标必须先声明：会话变量在 `workflow.conversation_variables`（含 `id`、`name`、`value`、`value_type`、`description`），loop 变量在 loop 节点的 `loop_variables`。
- loop 内的 assigner 是一条普通容器子节点：`parentId` + `isInLoop: true` + `loop_id` + `zIndex: 1002` 缺一不可；对应边也要带 `isInLoop` / `loop_id` / `zIndex: 1002`。
- 出边 `sourceHandle` 固定为 `source`；赋值本身不分支，按结果分流请后接 `if-else`。
- 同一节点内多个 `items` 按数组顺序依次执行，后面的项可以读取前面刚写入的值（以目标版本运行时为准）。

## 常见导入失败原因

- v2 里写了 `value_selector`（v1 字段名）而不是 `value`，赋值项被静默丢弃或校验失败。
- `version: "2"` 写成 `version: 2`，被当作 v1 解析，`value` 里的选择器被当成字面量字符串。
- 写入目标用 `["env", "KEY"]`，环境变量只读，导入或运行时被拒。
- loop 内漏 `loop_id` / `isInLoop: true` / `parentId`，节点落在主图上或找不到目标变量。
- `variable_selector` 指向未在 `conversation_variables` / `loop_variables` 声明的名字，运行时报变量不存在。
- `items` 为空数组，或某项缺 `operation`。
