# 工具节点（`tool`）

调用一个已安装的插件工具（内置、API、工作流、MCP），按工具 schema 传参并取回结果。

## 用途

- 直接复用插件市场的能力：网页抓取、搜索、图片生成、数据库查询、第三方 SaaS 操作。
- 把另一个已发布的工作流当作子流程调用（`provider_type: workflow`）。
- 接入 MCP Server 暴露的外部工具（`provider_type: mcp`）。

## 何时用 / 何时不要用

适合：

- 目标能力已有插件，且工作区已安装并配好凭证。
- 需要工具自带的参数校验、输出 schema、错误语义。

不要用：

- 目标服务只有普通 REST 接口、没有插件 → 用 `http-request`。
- 需要在工具前后做大量数据加工 → 拆成 `code` + `tool` 两步。
- 需要模型自主决定调哪个工具 → 用 `agent`，不要手工串一串 `tool` 节点。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 画布显示名 |
| `provider_id` | string | 是 | 提供方标识，通常形如 `langgenius/<plugin>/<provider>` |
| `provider_name` | string | 是 | 提供方名，导出里一般与 `provider_id` 相同 |
| `provider_type` | string | 是 | `builtin` / `api` / `workflow` / `mcp` |
| `tool_name` | string | 是 | 提供方下的工具名，如 `scrape` |
| `tool_label` | string | 是 | 工具的展示名 |
| `tool_description` | string | 否 | 工具描述，导出里常见 |
| `tool_parameters` | object | 是 | 参数名 → `{type, value}` 映射 |
| `tool_parameters.<name>.type` | string | 是 | `variable` / `constant` / `mixed` |
| `tool_parameters.<name>.value` | string \| string[] | 是 | `variable` 时为选择器数组，`constant` 时为字面量，`mixed` 时为可插值字符串 |
| `tool_configurations` | object | 否 | 工具级静态配置，同样形如 `{type, value}` |
| `tool_node_version` | string | 否 | 节点版本，常见 `"2"` |
| `plugin_id` | string | 否 | 插件标识，如 `langgenius/firecrawl` |
| `plugin_unique_identifier` | string | 否 | 带版本与哈希的插件标识 |
| `error_strategy` | string | 否 | `terminated` / `continue-on-error` / `remove-abnormal-output` |
| `selected` | boolean | 是 | 导出固定为 `false` |

### `provider_type` 取值

| 值 | 含义 |
| --- | --- |
| `builtin` | 插件市场里的内置工具 |
| `api` | 自建自定义 API 工具 |
| `workflow` | 另一条工作流被包装成工具 |
| `mcp` | MCP Server 暴露的工具 |

> `plugin_id`、`plugin_unique_identifier`、`tool_node_version` 在较新的市场/打包导出里很常见，但**并非所有类型都有**：内置、MCP、自定义 API、工作流工具都可能省略。从真实导出复制这些值，不要臆造插件标识或哈希，写错的 `plugin_unique_identifier` 会直接导致依赖解析失败。

## 最小可导入示例

```yaml
- id: "1770000000106"
  type: custom
  data:
    type: tool
    title: "网页抓取"
    provider_id: langgenius/firecrawl/firecrawl
    provider_name: langgenius/firecrawl/firecrawl
    provider_type: builtin
    # 以下两项从目标工作区的真实导出复制，不要手写版本与哈希
    plugin_id: langgenius/firecrawl
    plugin_unique_identifier: "langgenius/firecrawl:0.0.5@<从导出复制>"
    tool_name: scrape
    tool_label: "单页面抓取"
    tool_description: "Scrape a page"
    tool_node_version: "2"
    tool_configurations:
      formats:
        type: constant
        value: markdown
    tool_parameters:
      url:
        type: mixed
        value: "https://example.com?q={{#sys.query#}}"
    selected: false
  position: {x: 980, y: 282}
  width: 244
  height: 98
```

## 数据流

- 输出字段由工具自己的 `output_schema` 决定，常见命名：`text`、`data`、`result`、`json`、`files`、`output`。
- 下游引用：`["<node_id>", "text"]`、`{{#<node_id>.json#}}`。
- 拿不准输出键时，先做一次真实导出查看该工具的 schema，再写下游选择器。
- 出边 `sourceHandle` 固定为 `source`；需要按结果分流时接 `if-else`。
- 工具用到的插件必须出现在顶层 `dependencies` 中，否则导入后不可用。

## 常见导入失败原因

- `provider_type` 写成了 `builtin` / `builtIn` 之外的拼法（如 `plugin`、`custom`），合法值只有四个。
- `tool_parameters` 写成裸字符串（`url: "https://..."`），缺 `{type, value}` 外层结构。
- `type: variable` 的 `value` 写成字符串而非选择器数组，参数取值为空。
- 臆造 `plugin_unique_identifier`（版本号或哈希对不上），导入时报依赖无法解析。
- `tool_name` 与 `provider_id` 不匹配（复制了 A 插件的前缀却用 B 插件的工具名）。

## datasource 节点（`datasource`）

数据源节点与工具节点同属"插件驱动"，用来从外部系统只读取数（Notion 页面、数据库表等）。它没有入边，只能作为流程起点之一。

```yaml
- id: "1770000000107"
  type: custom
  data:
    type: datasource
    title: "读取 Notion 列表"
    provider_id: langgenius/notion/notion
    provider_name: langgenius/notion/notion
    provider_type: builtin
    datasource_name: pages
    datasource_label: "Pages"
    datasource_parameters: {}
    selected: false
  position: {x: 80, y: 282}
  width: 244
  height: 90
```

- 字段与 `tool` 基本同构，只是把 `tool_name` / `tool_label` / `tool_parameters` 换成 `datasource_name` / `datasource_label` / `datasource_parameters`。
- 不能有前置连线；容器（`iteration` / `loop`）内也不允许出现。
- 参数结构高度依赖具体插件，务必从真实导出复制，不要按工具节点猜字段。
