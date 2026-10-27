# 代码执行节点（`code`）

在流程内运行一段 Python 3 或 JavaScript，把上游变量作为入参，把 `outputs` 声明的键作为出参。

## 用途

- 对上一步的输出做确定性加工：解析 JSON、拆分字段、去重、排序、日期换算。
- 组装请求体或提示词片段，再交给 `http-request` / `tool` / `llm`。
- 做布尔判断、数值统计，把结果压成 `if-else` 能直接用的单值。

## 何时用 / 何时不要用

适合：

- 纯确定性、无外网、无状态的数据处理。
- 一次执行里需要多步字符串或数组操作，Jinja2 表达式写不动。

不要用：

- 只是拼一段文本 → `template-transform`。
- 需要访问外部 API → `http-request`。
- 需要遍历数组并逐项跑子流程 → `iteration` 包住代码节点。
- 依赖未预装的第三方库 → 沙箱只有受限依赖，先确认目标工作区支持。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 画布显示名 |
| `code_language` | string | 是 | 仅 `python3` / `javascript`；旧写法 `json` 不是合法值 |
| `code` | string | 是 | 源码，多行用 YAML `\|` 块写法 |
| `variables` | array | 是 | 入口参数映射；无入参时写 `[]` |
| `variables[].variable` | string | 是 | 代码里的参数名，与 `main` 的形参一致 |
| `variables[].value_selector` | string[] | 是 | 上游引用，如 `["<node_id>", "text"]` |
| `variables[].value_type` | string | 否 | 类型提示，如 `string`、`array[object]` |
| `outputs` | object | 是 | **dict**，键为输出名，值为 `{type, children}` |
| `outputs.<key>.type` | string | 是 | `string` / `number` / `boolean` / `object` / `array` / `array[string]` / `array[object]` / `array[file]` / `any` 等 |
| `outputs.<key>.children` | object \| null | 否 | 嵌套结构描述，普通标量写 `null` |
| `error_strategy` | string | 否 | `terminated` / `continue-on-error` / `remove-abnormal-output` |
| `retry_config.retry_enabled` | boolean | 否 | 失败重试开关（部分导出用 `enabled`，以目标工作区导出的 DSL 为准） |
| `retry_config.max_retries` | number | 否 | 最大重试次数 |
| `retry_config.retry_interval` | number | 否 | 重试间隔，毫秒 |
| `selected` | boolean | 是 | 导出固定为 `false` |

### Python 契约

- 入口函数必须叫 `main`，形参名与 `variables[].variable` 一一对应。
- 必须返回 `dict`，键集合与 `outputs` 的键完全一致；多键或少键在运行期直接报错。
- 类型注解只作提示，不参与运行时校验。

### JavaScript 契约

- 同样需要 `main`，入参是一个对象，键为 `variables[].variable`。
- `return { result: ... }` 返回对象，键与 `outputs` 一致。

## 最小可导入示例

```yaml
- id: "1770000000102"
  type: custom
  data:
    type: code
    title: "清洗 JSON"
    code_language: python3
    code: |
      import json

      def main(text: str) -> dict:
          data = json.loads(text)
          items = data.get("items", [])
          return {"items": items, "count": len(items)}
    variables:
      - variable: text
        value_selector: ["1770000000101", "text"]
    outputs:
      items:
        type: array[object]
        children: null
      count:
        type: number
        children: null
    selected: false
  position: {x: 680, y: 282}
  width: 244
  height: 90
```

## 数据流

- 每个 `outputs` 键都会成为一个输出变量：`["<node_id>", "items"]`、`{{#<node_id>.count#}}`。
- 数组输出可直接接到 `iteration` 的 `iterator_selector`，或 `list-operator` 的 `variable`。
- 对象输出可被下游用点路径继续取值，路径深度以目标工作区导出的 DSL 为准。
- 节点只有单一出口，出边 `sourceHandle` 固定为 `source`。

## 常见导入失败原因

- `outputs` 写成了数组（`- result:` 形式），它必须是键值映射。
- `code` 里函数名不是 `main`，或把逻辑写在模块顶层 / `if __name__ == "__main__"` 里。
- 返回 dict 的键与 `outputs` 声明的键不一致，运行期取不到值。
- `code_language` 仍写成 `json`（早期 0.6.0 文档的写法），应改为 `python3` 加 `json.loads`。
- `variables[].value_selector` 为空数组，或指向了上游并不存在的输出键。
