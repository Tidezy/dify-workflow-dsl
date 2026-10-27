# 迭代（`iteration`）

对一个数组的每个元素执行一遍内嵌子图，并把每次子图的输出收集成新数组。

## 用途

- 批量处理文件列表（逐个解析 PDF）、批量调用工具（逐个查订单）、批量生成（逐条改写）。
- 把"逐元素处理"与"主流程"隔离：内部节点的错误处理模式独立于主图。
- 输出一个与输入等长（或经过滤后变短）的数组，供 `variable-aggregator` / `end` 使用。

## 何时用 / 何时不要用

适合：

- 已知输入是数组，且元素之间**互不依赖**。
- 需要并发提速：`is_parallel: true` + `parallel_nums` 控制并发度。
- 每轮产物都要保留（数组语义）。

不要用：

- 有状态累积（计数器、上一轮结果喂下一轮）→ 用 `loop`。
- 只处理"第一个/最后一个"元素 → 用 `list-operator`，成本低得多。
- 需要重试直到满足条件 → 用 `loop` + `break_conditions`。
- 容器内再套 `iteration` / `loop` / `end` / `knowledge-index` / `human-input`：这些节点在容器内被禁用。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `iteration`。 |
| `title` | string | 是 | 画布标题。 |
| `iterator_selector` | string[] | 是 | 输入数组，如 `["<node_id>", "items"]`。 |
| `iterator_input_type` | string | 否 | 输入数组类型，`array[string]` / `array[number]` / `array[object]` / `array[file]`。 |
| `output_selector` | string[] | 是 | 取哪一路子节点输出作为单轮结果，如 `["<inner_node_id>", "output"]`。 |
| `output_type` | string | 是 | 收集后的数组类型，如 `array[string]`；与 `output_selector` 的元素类型一致。 |
| `start_node_id` | string | 是 | 指向容器内 `iteration-start` 子节点的 `id`。 |
| `is_parallel` | boolean | 否 | 是否并发执行，缺省 `false`。 |
| `parallel_nums` | number | 否 | 并发上限，缺省 `10`，仅 `is_parallel: true` 时有效。 |
| `error_handle_mode` | string | 否 | `terminated` / `continue-on-error` / `remove-abnormal-output`。 |
| `flatten_output` | boolean | 否 | 子图输出本身是数组时是否拍平，缺省 `true`。 |
| `width` / `height` | number | 是 | 容器尺寸；wrapper 与 `data` 内各写一份。 |
| `selected` | boolean | 是 | 导出固定 `false`。 |

`error_handle_mode` 取值：

| 值 | 行为 |
|---|---|
| `terminated` | 首个元素失败即整节点失败（默认）。 |
| `continue-on-error` | 跳过失败元素继续，输出中含占位。 |
| `remove-abnormal-output` | 继续执行，但失败元素从输出数组剔除。 |

## 最小可导入示例

容器 + `iteration-start` + 一个子节点，最小可导入形态：

```yaml
# 1) 容器节点：zIndex 为 1，宽高在 wrapper 与 data 内各写一份
- id: "1770000000501"
  type: custom
  data:
    type: iteration
    title: "逐条改写"
    iterator_selector: ["1770000000001", "items"]
    iterator_input_type: array[string]
    output_selector: ["1770000000503", "output"]
    output_type: array[string]
    is_parallel: false
    parallel_nums: 10
    error_handle_mode: terminated
    flatten_output: true
    start_node_id: "1770000000502"
    width: 520
    height: 200
    selected: false
  position: {x: 380, y: 250}
  width: 520
  height: 200
  zIndex: 1

# 2) iteration-start 辅助节点：wrapper type 为 custom-iteration-start
- id: "1770000000502"
  parentId: "1770000000501"
  type: custom-iteration-start
  draggable: false
  selectable: false
  data:
    type: iteration-start
    title: ""
    isInIteration: true
    isInLoop: false
  position: {x: 60, y: 80}
  width: 44
  height: 48
  zIndex: 1002

# 3) 容器内业务子节点：parentId + isInIteration + iteration_id + zIndex 1002
- id: "1770000000503"
  parentId: "1770000000501"
  type: custom
  data:
    type: template-transform
    title: "改写单条"
    isInIteration: true
    isInLoop: false
    iteration_id: "1770000000501"
    variables:
      - variable: item
        value_selector: ["1770000000501", "item"]
    template: "【已处理】{{ item }}"
    selected: false
  position: {x: 190, y: 62}
  width: 244
  height: 86
  zIndex: 1002
```

配套边（容器内边必须带 `isInIteration` / `iteration_id` / `zIndex: 1002`）：

```yaml
- id: "1770000000502-source-1770000000503-target"
  source: "1770000000502"
  sourceHandle: source
  target: "1770000000503"
  targetHandle: target
  type: custom
  zIndex: 1002
  data: {sourceType: iteration-start, targetType: template-transform, isInIteration: true, iteration_id: "1770000000501", isInLoop: false}
```

## 数据流

- 输入：`iterator_selector` 指向主图里的数组变量；容器元素互不共享状态。
- 容器内取值：当前元素 `["<iteration_node_id>", "item"]`，当前下标 `["<iteration_node_id>", "index"]`。
- 输出：`["<iteration_node_id>", "output"]`，元素来自 `output_selector` 指定的子节点输出。
- `output_type` 必须与实际收集结果匹配：子节点输出 `string` → `output_type: array[string]`；子节点输出 `array[number]` 且 `flatten_output: true` → `array[number]`，否则 `array[array[number]]`。
- 迭代 `array[file]` 时，容器内第一步通常放 `document-extractor`，`variable_selector` 指向 `["<iteration_node_id>", "item"]`。
- 容器内节点用 `isInIteration: true` + `iteration_id`；`loop` 内则是 `isInLoop: true` + `loop_id`，两套标记不要混用。

## 常见导入失败原因

- 子节点漏 `parentId`，或漏 `isInIteration: true` / `iteration_id`，导入后子图散落到主图。
- 子节点 `zIndex` 不是 `1002`，被容器遮住或层级错乱。
- `start_node_id` 与 `iteration-start` 的实际 `id` 不一致，或指向了容器自身，节点报"找不到起始节点"。
- `iteration-start` 的 wrapper `type` 写成 `custom`（应为 `custom-iteration-start`），或 `data.type` 写成 `iteration`。
- `output_type` 与 `output_selector` 的元素类型不匹配（如 selector 指向 `array[string]` 却写 `array[string]`、忽略 `flatten_output`）。
- 容器尺寸只写在 wrapper 或只写在 `data` 里，另一种情况下面板宽度塌陷、子节点溢出。
- 容器内放入 `iteration` / `loop` / `end` / `knowledge-index` / `human-input` 等被禁节点。
