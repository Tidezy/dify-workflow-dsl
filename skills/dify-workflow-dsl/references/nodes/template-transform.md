# 模板转换节点（`template-transform`）

用 Jinja2 模板把若干上游变量渲染成一段字符串，作为单个 `output` 输出。

## 用途

- 拼装长提示词：把用户输入、检索结果、历史摘要合成一段文本再交给 `llm`。
- 生成最终答复正文（Markdown、表格、邮件体），直接接 `answer` / `end`。
- 把数组渲染成列表文本，比如逐个文件输出「文件名: 摘要」。

## 何时用 / 何时不要用

适合：

- 输出只关心"一段文本"，不需要结构化字段。
- 需要循环、条件、过滤器（`for`、`if`、`join`、`length`、`default`）来排版。

不要用：

- 需要输出 JSON 对象或做类型转换 → 用 `code`。
- 需要严格 schema 的字段抽取 → 用 `parameter-extractor`。
- 只是把单个变量原样透传 → 直接在 `answer` / `end` 里引用，不必加这一层。
- 需要调用外部服务 → `http-request` / `tool`。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 画布显示名 |
| `template` | string | 是 | Jinja2 模板正文，多行用 YAML `\|` 块 |
| `variables` | array | 是 | 模板可用的变量清单；模板里出现的名字都应在此声明 |
| `variables[].variable` | string | 是 | 模板中的变量名，即 `{{ name }}` 里的 `name` |
| `variables[].value_selector` | string[] | 是 | 上游引用，如 `["<node_id>", "result"]` |
| `variables[].value_type` | string | 否 | 类型提示；数组/对象建议标注，便于 UI 校验 |
| `error_strategy` | string | 否 | `terminated` / `continue-on-error` / `remove-abnormal-output` |
| `selected` | boolean | 是 | 导出固定为 `false` |

### 模板语法要点

| 写法 | 作用 |
| --- | --- |
| `{{ name }}` | 插入变量值 |
| `{% for row in rows %} ... {% endfor %}` | 遍历数组 |
| `{% if cond %} ... {% else %} ... {% endif %}` | 条件分支 |
| `{{ rows \| length }}` | 取数组长度 |
| `{{ rows \| join(", ") }}` | 拼接数组元素 |
| `{{ name \| default("") }}` | 空值兜底 |

## 最小可导入示例

```yaml
- id: "1770000000103"
  type: custom
  data:
    type: template-transform
    title: "拼装文件摘要"
    variables:
      - variable: rows
        value_selector: ["1770000000102", "items"]
        value_type: array[object]
      - variable: question
        value_selector: ["sys", "query"]
        value_type: string
    template: |
      用户问题：{{ question }}

      参考资料：
      {% for row in rows %}
      - {{ row.file_name }}: {{ row.document_summary }}
      {% endfor %}
    selected: false
  position: {x: 980, y: 282}
  width: 244
  height: 90
```

## 数据流

- 输出变量固定只有一个：`output`（string）。
- 下游引用写法：`["<node_id>", "output"]`，或模板里的 `{{#<node_id>.output#}}`。
- 常见接法：`knowledge-retrieval` → `template-transform`（排版检索结果）→ `llm`（把 `output` 塞进 `prompt_template`）。
- 出边 `sourceHandle` 固定为 `source`。

## 常见导入失败原因

- `template` 里用了没在 `variables` 中声明的名字，渲染结果为空白或报 undefined。
- `variables` 条目缺 `variable` 名，或 `value_selector` 为空数组。
- 在 `template` 里直接写 `{{#<node_id>.<key>#}}`：该语法用于 `llm` / `answer` 提示词，模板节点应通过 `variables` 映射传值。
- 上游给的是数组却按字符串直接插入，忘记用 `{% for %}` 展开。
- YAML 里用了 `>` 折叠块，导致模板换行被合并、缩进错乱。
