# 列表操作（`list-operator`）

对一个数组做过滤、排序或取首尾元素，输出处理后的数组（或单个元素）。

## 用途

- 从 `sys.files` 这类文件列表里取第一个文件，再交给 `document-extractor`。
- 按字段过滤数组（只留 `status == "open"` 的项）。
- 按字段升/降序排列后取头部若干条，喂给 `llm` 做摘要。

## 何时用 / 何时不要用

适合：

- 只需"选/排/取一条"，不想为此写 `code` 节点。
- 输入是标准数组类型（`array[file]`、`array[object]`、`array[string]`）。
- 需要确定性、零模型成本的数据整理。

不要用：

- 需要对每个元素逐个处理 → 用 `iteration`。
- 需要聚合（求和、拼字符串、去重后计数）→ 用 `code`。
- 需要复杂条件（多字段组合、正则）→ 用 `code`，`list-operator` 只支持单条件过滤。
- 输入是单个对象或字符串而非数组，`var_type` 与 `variable` 类型不符时导入后节点不可用。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `list-operator`。 |
| `title` | string | 是 | 画布标题。 |
| `variable` | string[] | 是 | 输入数组选择器，如 `["sys", "files"]`。 |
| `var_type` | string | 是 | 输入数组类型，见下表。 |
| `filter_by.enabled` | boolean | 是 | 是否启用过滤，三项操作通常只开一个。 |
| `filter_by.filter_by.comparison_operator` | string | 启用时 | 与 `if-else` 同一套算子（`contains` / `is` / `>` / `empty` …）。 |
| `filter_by.filter_by.value` | string / number / boolean | 视算子 | 过滤比较值。 |
| `filter_by.filter_by.varType` | string | 否 | 被比较字段类型。 |
| `filter_by.filter_by.key` | string | 否 | `array[object]` 时比较的字段名。 |
| `order_by.enabled` | boolean | 是 | 是否启用排序。 |
| `order_by.order_by.value` | string[] | 启用时 | 排序依据的选择器（对象数组取某字段）。 |
| `order_by.order_by.order` | string | 启用时 | `asc` / `desc`。 |
| `extract_by.enabled` | boolean | 是 | 是否启用取首/尾。 |
| `extract_by.serial` | string | 启用时 | `first` 或 `last`。 |
| `selected` | boolean | 是 | 导出固定 `false`。 |

`var_type` 取值：`array[string]`、`array[number]`、`array[boolean]`、`array[object]`、`array[file]`。

嵌套结构（`filter_by.filter_by` / `order_by.order_by` 是双层同名键，容易写漏一层）：

```yaml
filter_by:
  enabled: false
  filter_by:
    comparison_operator: is
    value: "open"
    varType: string
order_by:
  enabled: false
  order_by:
    value: ["<node_id>", "created_at"]
    order: desc
extract_by:
  enabled: true
  serial: first
```

过滤/排序的具体子字段随版本有细微差异，**以目标工作区导出的 DSL 为准**；不确定时从导出复制整段，不要凭记忆补字段。

## 最小可导入示例

取 `sys.files` 的第一个文件：

```yaml
- id: "1770000000801"
  type: custom
  data:
    type: list-operator
    title: "取第一个文件"
    filter_by:
      enabled: false
    order_by:
      enabled: false
    extract_by:
      enabled: true
      serial: first
    var_type: array[file]
    variable: ["sys", "files"]
    selected: false
  position: {x: 380, y: 282}
  width: 244
  height: 116
```

## 数据流

- 输出主变量为 `["<node_id>", "result"]`：处理后的结果（`extract_by` 时为单个元素，其余情况为数组）。
- 部分版本还会暴露 `first_record` / `last_record` 等便捷字段，是否可用以目标工作区导出的 DSL 为准。
- 接到 `document-extractor` 时要注意类型：`extract_by: first` 出来的是单个 `file`，`document-extractor` 的 `variable_selector` 指向 `["<list_node_id>", "result"]` 即可；若输出仍是 `array[file]`，需要再确认提取器是否按数组处理。
- 出边 `sourceHandle` 固定为 `source`，单出口；按结果分流请后接 `if-else`（例如判断 `result` 是否为空）。
- 空数组不会报错，但 `extract_by` 会产生空值，下游要判空。

## 常见导入失败原因

- `var_type` 与实际输入不匹配（输入 `array[file]` 却写 `array[object]`），导入后节点不可编辑或运行期类型报错。
- `variable` 写成字符串 `"sys.files"` 或漏掉节点前缀，只给一维数组。
- `extract_by.enabled: true` 但缺 `serial`，或写成 `1` / `0` / `first_record` 等非枚举值（只接受 `first` / `last`）。
- 双层键写漏一层：`filter_by: {enabled: true, comparison_operator: ...}`，缺少内层 `filter_by`。
- 同时开启 `filter_by` / `order_by` / `extract_by`，行为不可预期；按导出只保留一个。
- 把 `list-operator` 放进 `iteration` 内部去处理 `item` 的同层列表，容易与容器 `item` 选择器混淆，先用导出样例对齐。
