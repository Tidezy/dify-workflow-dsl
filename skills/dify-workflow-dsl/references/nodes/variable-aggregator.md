# 变量聚合（`variable-aggregator`）

把多条互斥分支的输出收成一个变量，取"实际跑过的那一路"的值。

## 用途

- `if-else` / `question-classifier` 分流后，在汇合点统一成一个变量，避免每个分支各接一个 `end`。
- 合并同类型但来源不同的结果（不同 LLM 节点、不同模板节点、不同工具节点）。
- 分组模式下一次汇合多组变量（每组一个出口）。

## 何时用 / 何时不要用

适合：

- 分支互斥，任意时刻只有一个上游有值。
- 下游只需要"一个值"，不想按分支复制下游节点。

不要用：

- 需要把多个值**同时**保留（拼成对象/数组）→ 用 `code` 或 `template-transform`。
- 需要类型转换（string → number）→ 聚合器不做转换，先在上游转好。
- 同一条链路上串行覆盖同一个值 → 用 `assigner`。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `variable-aggregator`。 |
| `title` | string | 是 | 画布标题。 |
| `output_type` | string | 是 | 聚合结果类型，见下表；缺省 `any` 但建议显式写。 |
| `variables` | array | 是（简单模式） | **裸嵌套数组**：`[["<node_id>", "field"], ...]`，不是对象数组。 |
| `advanced_settings.group_enabled` | boolean | 否 | 是否启用分组模式。 |
| `advanced_settings.groups` | array | 否 | 分组模式下的组列表。 |
| `advanced_settings.groups[].groupId` | string | 是 | 组 UUID。 |
| `advanced_settings.groups[].group_name` | string | 是 | 组名，**会进入下游选择器路径**。 |
| `advanced_settings.groups[].output_type` | string | 是 | 该组输出类型。 |
| `advanced_settings.groups[].variables` | array | 是 | 同上的裸嵌套数组。 |
| `selected` | boolean | 是 | 导出固定 `false`。 |

`output_type` 常用取值：`string`、`number`、`integer`、`boolean`、`object`、`file`、`array[string]`、`array[number]`、`array[object]`、`array[file]`、`any`。

同一组（或扁平列表）内所有变量的类型必须一致，并与 `output_type` 对齐。

## 最小可导入示例

```yaml
- id: "1770000000601"
  type: custom
  data:
    type: variable-aggregator
    title: "合并分支结果"
    output_type: string
    variables:
      - ["1770000000401", "text"]
      - ["1770000000402", "output"]
    selected: false
  position: {x: 980, y: 282}
  width: 244
  height: 116
```

等价的块状写法也合法，但**必须是数组套数组**，不能出现 `variable:` / `value_selector:` 这类键：

```yaml
    variables:
      - - "1770000000401"
        - "text"
```

## 数据流

- 输入：每个元素都是 `["<node_id>", "<field>"]`；运行时按顺序取**第一个有值**的结果。
- 输出（简单模式）：`["<node_id>", "output"]`，模板写 `{{#<node_id>.output#}}`。
- 输出（分组模式）：每组一个出口，`["<node_id>", "<group_name>", "output"]`。

```yaml
    advanced_settings:
      group_enabled: true
      groups:
        - groupId: a924f802-235c-47c1-85f6-922569221a39
          group_name: Group1
          output_type: string
          variables:
            - ["1770000000401", "text"]
            - ["1770000000402", "text"]
```

- 出边 `sourceHandle` 固定为 `source`；聚合器只有单出口，分支选择已在运行时完成。
- 分组模式下下游必须带 `group_name` 这一层，漏掉会解析不到变量。

## 常见导入失败原因

- `variables` 写成对象数组：`- variable: [...]`、`- value_selector: [...]` 或 `- selector: ...`——这是最常见的导入失败点，必须是裸嵌套数组。
- `variables` 元素写成字符串 `"1770000000401.text"`，或只给一个字段名，缺少节点 ID。
- 块状 YAML 缩进差一格，整条被解析成字符串而不是两元素数组。
- `output_type` 写成 `string[]`、`Array<string>` 等非枚举值，或与实际类型不符（如上游是 `array[file]` 却写 `string`）。
- `group_enabled: true` 但 `groups` 为空，或某组缺 `group_name`，下游选择器断链。
- 同一组内混入不同类型（string 与 number），运行时取值失败。
