# 循环（`loop`）

在容器内按固定次数重复执行一段子流程，并可在循环变量满足退出条件时提前结束。

## 用途

`loop` 是容器型节点，自身不产生 `text` 之类的输出，而是在内部维护一组**循环变量**（`loop_variables`）：每一轮由子节点（通常是 `assigner`）改写这些变量，循环结束后下游用 `[loop_id, <label>]` 读取终值。与 `iteration` 的区别是：`iteration` 遍历数组、每轮产出独立结果再汇总成数组；`loop` 是"计数器 + 状态累积"，轮次之间共享同一份变量状态。

## 何时用 / 何时不要用

**何时用**

- 需要"重试直到满足条件"，例如最多 5 轮、评分 ≥ 3 分就提前停。
- 每轮都要在上一轮结果上继续加工（累加、追加、改写草稿）。
- 固定次数轮询外部状态，且有明确退出判据。

**何时不要用**

- 输入是数组、要逐元素处理 → 用 `iteration`（见 `iteration.md`）。
- 只是两三条分支 → 用 `if-else`，不要为一个条件套循环。
- 容器内不能再套 `loop` / `iteration`，也不能放 `end`、`human-input`、`knowledge-index`、`datasource`。

## 字段表

`data` 载荷字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | `string` | 是 | 固定为 `loop`。 |
| `title` | `string` | 是 | 节点标题。 |
| `loop_count` | `number` | 是 | 最大轮数，必须是具体数字，作为兜底上限。 |
| `logical_operator` | `"and" \| "or"` | 否 | 多个 `break_conditions` 的组合方式，默认 `and`。 |
| `loop_variables` | `array` | 是 | 循环变量定义；无状态可维护时给 `[]`。 |
| `break_conditions` | `array` | 否 | 提前退出条件；为空表示跑满 `loop_count` 轮。 |
| `start_node_id` | `string` | 是 | 容器内 `loop-start` 节点的 `id`。 |
| `width` / `height` | `number` | 是 | 容器尺寸，**必须与 wrapper 上的 `width`/`height` 一致**。 |

`loop_variables[]` 子字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | `string` | 是 | DSL 内标识，惯例与 `label` 同值。 |
| `label` | `string` | 是 | 变量名，同时是节点输出名，下游用 `[loop_id, label]` 引用。 |
| `value` | `string` | 是 | 初值；常量时以字符串给出，如 `"0"`。 |
| `value_type` | `"constant" \| "variable"` | 是 | 初值来自字面量还是上游变量。 |
| `var_type` | `string` | 是 | 变量类型：`string` / `number` / `boolean` / `object` / `array[...]`。 |

`break_conditions[]` 子字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | `string` | 是 | 条件 ID（UUID 或短名）。 |
| `variable_selector` | `ValueSelector` | 是 | 判据变量，通常指向本循环的变量：`[loop_id, label]`。 |
| `comparison_operator` | `string` | 是 | 与 `if-else` 同族：`is` / `is not` / `contains` / `>` / `<` / `≥` / `≤` / `=` / `≠`。 |
| `value` | `string` | 是 | 比较值，写成字符串，如 `"3"`。 |
| `varType` | `string` | 是 | 比较值类型，需与 `variable_selector` 一致。 |

## 容器结构

- 容器：`type: custom`、`zIndex: 1`，`width`/`height` 在 wrapper 与 `data` 内各一份。
- `loop-start`：wrapper `type: custom-loop-start`，`data.type: loop-start`，`data.isInLoop: true`，`parentId` 指向容器，`draggable`/`selectable` 为 `false`，`zIndex: 1002`。
- 容器内子节点：`parentId` 指向容器，`data.isInLoop: true`、`data.loop_id` 指向容器，`zIndex: 1002`。
- 容器内边：`zIndex: 1002` 且 `data.loop_id` 有值；容器自身的进出边则无 `zIndex`、`isInLoop: false`。
- `loop-start` 的 `id` 惯例为 `<loop_id>_start`（也见过 `<loop_id>start`），只要与 `start_node_id` 一致即可，**以目标工作区导出的 DSL 为准**。

## 最小可导入示例

片段，置于 `workflow.graph.nodes` / `workflow.graph.edges` 下（0.7.0 形态）；上游 `start` 直接连到容器。

```yaml
    nodes:
      - id: loop_input
        type: custom
        data:
          type: start
          title: "开始"
          variables: []
        position: {x: 40, y: 280}
        width: 244
        height: 54
      # 容器：wrapper 与 data 各一份 width/height，zIndex 为 1
      - id: quality_loop
        type: custom
        data:
          type: loop
          title: "质量检查循环"
          loop_count: 5
          logical_operator: and
          loop_variables:
            - id: review-count
              label: review_count
              value: "0"
              value_type: constant
              var_type: number
          break_conditions:
            - id: enough-reviews
              variable_selector: [quality_loop, review_count]
              comparison_operator: "≥"
              value: "3"
              varType: number
          start_node_id: quality_loop_start
          width: 520
          height: 210
        position: {x: 350, y: 250}
        width: 520
        height: 210
        zIndex: 1
      # loop-start：wrapper type 是 custom-loop-start，data.type 是 loop-start
      - id: quality_loop_start
        parentId: quality_loop
        type: custom-loop-start
        draggable: false
        selectable: false
        data:
          type: loop-start
          title: ""
          isInLoop: true
        position: {x: 60, y: 80}
        width: 44
        height: 48
        zIndex: 1002
      # 唯一的子节点：改写循环变量
      - id: increase_count
        parentId: quality_loop
        type: custom
        data:
          type: assigner
          title: "增加检查次数"
          version: "2"
          isInIteration: false
          isInLoop: true
          loop_id: quality_loop
          items:
            - variable_selector: [quality_loop, review_count]
              input_type: constant
              operation: "+="
              value: 1
              write_mode: over-write
        position: {x: 190, y: 62}
        width: 244
        height: 86
        zIndex: 1002
      - id: loop_end
        type: custom
        data:
          type: end
          title: "输出检查次数"
          outputs:
            - variable: review_count
              value_selector: [quality_loop, review_count]
              value_type: number
        position: {x: 940, y: 280}
        width: 244
        height: 90
    edges:
      # 容器级边：无 zIndex，isInLoop 为 false
      - id: loop_input-source-quality_loop-target
        source: loop_input
        sourceHandle: source
        target: quality_loop
        targetHandle: target
        type: custom
        data: {sourceType: start, targetType: loop, isInIteration: false, isInLoop: false}
      # 容器内边：zIndex 1002 + loop_id
      - id: quality_loop_start-source-increase_count-target
        source: quality_loop_start
        sourceHandle: source
        target: increase_count
        targetHandle: target
        type: custom
        zIndex: 1002
        data:
          sourceType: loop-start
          targetType: assigner
          isInIteration: false
          isInLoop: true
          loop_id: quality_loop
      - id: quality_loop-source-loop_end-target
        source: quality_loop
        sourceHandle: source
        target: loop_end
        targetHandle: target
        type: custom
        data: {sourceType: loop, targetType: end, isInIteration: false, isInLoop: false}
```

## 数据流

1. 进入容器时按 `value` / `value_type` 初始化 `loop_variables`，得到 `[loop_id, <label>]` 这一组可变状态。
2. 每轮从 `loop-start` 开始跑子图：子节点读 `[loop_id, <label>]`，再由 `assigner` 用 `+=` / `over-write` 写回同一变量。
3. 每轮结束按 `logical_operator` 检查 `break_conditions`，命中即跳出；否则继续，直到 `loop_count` 用尽。
4. 循环没有"结果数组"，输出就是循环变量的终值；容器内中间值必须落到循环变量上才能带出容器。

## 常见导入失败原因

- **尺寸只写一份**：`width`/`height` 只在 wrapper 或只在 `data` 内——两处都必须有且数值一致，否则画布上是空容器。
- **`start_node_id` 与 `loop-start` 的 `id` 不一致**：容器找不到入口，循环体不执行。
- **`loop-start` 类型写反**：wrapper 必须是 `custom-loop-start`、`data.type` 必须是 `loop-start`；写成 `custom` + `loop-start` 会退化成普通节点。
- **子节点缺 `loop_id` / `isInLoop` / `zIndex: 1002`**：只写 `parentId` 不够，节点会被画到容器外。
- **`break_conditions[].varType` 与变量类型不符**：如 `review_count` 是 `number` 却写 `varType: string`，条件永不成立，循环跑满 `loop_count`。
