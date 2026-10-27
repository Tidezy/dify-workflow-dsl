# 条件分支（`if-else`）

按条件把执行流导向不同分支（IF / ELIF / ELSE），本身不产出任何变量。

## 用途

- 对上游变量做字符串、数值、布尔、数组或文件属性比较，决定走哪条边。
- 多路互斥判定：`cases` 顺序即 IF → ELIF，最后一个隐式 `false` 是 ELSE。
- 作为 `question-classifier` / `parameter-extractor` 之后的确定性兜底。

## 何时用 / 何时不要用

适合：

- 判断规则明确（关键词、阈值、空值、存在性），不需要模型参与。
- 需要在某条分支上做"降级/异常"处理，而 `question-classifier` 只认语义类别。

不要用：

- 判定本质是语义归类（意图识别）→ 用 `question-classifier`。
- 只是按类型/空值过滤一个列表 → 用 `list-operator` 或 `code`。
- 需要在同一节点里既分流又合并结果 → 分流后仍需 `variable-aggregator` 汇合。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `if-else`。 |
| `title` | string | 是 | 画布标题。 |
| `cases` | array | 是 | 分支数组，顺序即 IF/ELIF；ELSE 不写在这里。 |
| `cases[].id` | string | 是 | 分支 ID，**必须与出边 `sourceHandle` 完全一致**。 |
| `cases[].case_id` | string | 是 | 与 `cases[].id` 同值；0.7.0 官方导出两份都写。 |
| `cases[].logical_operator` | string | 否 | `and` / `or`，缺省 `and`，只作用于本分支内的 `conditions`。 |
| `cases[].conditions` | array | 是 | 该分支的条件列表。 |
| `cases[].conditions[].id` | string | 是 | 条件 UUID，节点内唯一。 |
| `cases[].conditions[].variable_selector` | string[] | 是 | 被比较变量，形如 `["<node_id>", "field"]`。 |
| `cases[].conditions[].comparison_operator` | string | 是 | 见下方算子表。 |
| `cases[].conditions[].value` | string / number / boolean | 视算子 | 比较值；`empty`、`not empty`、`exists` 等不需要。 |
| `cases[].conditions[].varType` | string | 是 | 被比较变量的类型，**注意是 camelCase `varType`**。 |
| `cases[].conditions[].key` | string | 否 | 文件属性比较（如 `type`、`transfer_method`）时的子键。 |
| `cases[].conditions[].sub_variable_condition` | object | 否 | 对象/文件子字段的嵌套条件。 |
| `cases[].conditions[].numberVarType` | string | 否 | 来自工具节点的数值子类型提示。 |
| `logical_operator` / `conditions` | — | 否 | data 顶层的旧式写法，已废弃；新生成只写 `cases`。 |
| `selected` | boolean | 是 | 导出固定 `false`。 |

### `comparison_operator` 常用取值

| 值 | 适用类型 | 需要 `value` |
|---|---|---|
| `contains` / `not contains` | string、`array[*]` | 是 |
| `start with` / `end with` | string | 是 |
| `is` / `is not` | string、boolean | 是 |
| `empty` / `not empty` | string、number、array | 否 |
| `=` / `≠` | number、integer | 是 |
| `>` / `<` / `≥` / `≤` | number、integer | 是 |
| `is null` / `is not null` | 任意 | 否 |
| `exists` / `not exists` | file | 否 |
| `in` / `not in` | 文件属性 | 是 |
| `all of` | `array[file]` | 是 |

数值比较用的是 `≥` `≤` `≠` 这类 Unicode 符号，**不是** `>=`、`<=`、`!=`。

## 最小可导入示例

```yaml
- id: "1770000000301"
  type: custom
  data:
    type: if-else
    title: "是否合同类"
    cases:
      - id: "case-contract"
        case_id: "case-contract"
        logical_operator: and
        conditions:
          - id: 0b5f09ef-0000-4000-9000-000000000301
            variable_selector: ["1770000000001", "input_text"]
            comparison_operator: contains
            value: "合同"
            varType: string
      - id: "case-long"
        case_id: "case-long"
        logical_operator: or
        conditions:
          - id: 0b5f09ef-0000-4000-9000-000000000302
            variable_selector: ["1770000000001", "input_text"]
            comparison_operator: end with
            value: ".pdf"
            varType: string
          - id: 0b5f09ef-0000-4000-9000-000000000303
            variable_selector: ["1770000000001", "input_text"]
            comparison_operator: not empty
            varType: string
    selected: false
  position: {x: 380, y: 282}
  width: 244
  height: 180
```

## 数据流

- 节点**没有输出变量**：不产生 `["<node_id>", ...]`，只决定哪条边被激活。
- 出口数量 = `cases` 数量 + 1 个 ELSE；每个出口靠 `sourceHandle` 区分：

```yaml
edges:
  - id: "1770000000301-case-contract-1770000000401-target"
    source: "1770000000301"
    sourceHandle: "case-contract"     # = cases[].id
    target: "1770000000401"
    targetHandle: target
    type: custom
    data: {sourceType: if-else, targetType: llm}
  - id: "1770000000301-false-1770000000402-target"
    source: "1770000000301"
    sourceHandle: "false"             # ELSE，固定字符串
    target: "1770000000402"
    targetHandle: target
    type: custom
    data: {sourceType: if-else, targetType: answer}
```

- 第一条 case 的历史写法把 ID 定为 `"true"`；沿用 `"true"` 或改用 UUID 都可以，只要 `id`、`case_id`、`sourceHandle` 三处一致。
- 分支汇合时用一个 `variable-aggregator` 收集各路输出，再进 `end` / `answer`。
- 一个 handle 只应连一条边；同一 handle 重复连边属于行为风险，不是硬错误。

## 常见导入失败原因

- `cases[].id` 与 `case_id` 不一致，或漏写 `case_id`，导入后画布上分支丢失。
- 出边 `sourceHandle` 写成展示名（`IF`、`ELSE`、`CASE 1`）而不是 case ID，条件节点变成"无出口"。
- 需要 ELSE 出口却没画 `sourceHandle: "false"` 的边，运行到 else 时链路中断。
- 数值算子写成 `>=` / `!=`，与枚举值 `≥` / `≠` 不匹配，导入或运行时报未知算子。
- 条件字段写成 `var_type`（snake_case）或漏 `varType`，类型推断失败导致算子不可用。
- 只写了 data 顶层的旧式 `conditions`，`cases` 为空数组。
