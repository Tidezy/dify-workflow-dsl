# HTTP 请求节点（`http-request`）

在工作流内直接发起一次 HTTP 调用，把响应体、状态码与响应头交给下游。

## 用途

- 调用自建或第三方的 REST 接口，取回数据供后续节点加工。
- 把流程结果回写业务系统（表单提交、消息推送、状态更新）。
- 在没有对应插件的情况下，用裸 HTTP 打通任意外部服务。

## 何时用 / 何时不要用

适合：

- 目标服务有清晰 HTTP 契约，且不需要工作区凭证体系托管。
- 需要完全控制 method、headers、body、超时与重试。

不要用：

- 目标服务已有官方插件/工具 → 用 `tool`，鉴权与参数校验更稳。
- 只是从知识库取数 → `knowledge-retrieval`。
- 需要 OAuth 授权码、多步换取 token → 优先插件的凭证机制，或拆成多个请求用变量传递。
- 请求需要在沙箱里做复杂签名 → 用 `code` 生成签名后再由本节点发送。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 画布显示名 |
| `method` | string | 是 | `get` / `post` / `put` / `patch` / `delete` / `head`（导出为小写） |
| `url` | string | 是 | 完整地址，支持 `{{#<node_id>.<key>#}}` 插值 |
| `headers` | string | 是 | `key: value` 按行分隔的字符串；无则写 `""` |
| `params` | string | 是 | 查询参数，同样按 `key: value` 换行；无则写 `""` |
| `body.type` | string | 是 | 见下方枚举；无请求体时写 `none` |
| `body.data` | array | 是 | 键值条目数组，`body.type` 为 `none` 时写 `[]` |
| `body.data[].id` | string | 否 | 条目 id，重排/回显用 |
| `body.data[].key` | string | 否 | 字段名 |
| `body.data[].type` | string | 是 | `text` 或 `file`；部分导出把文本条目写作 `string`，以目标工作区导出的 DSL 为准 |
| `body.data[].value` | string | 否 | `type: text` 时的取值，可插值 |
| `body.data[].file` | string[] | 否 | `type: file` 时的文件选择器 |
| `authorization.type` | string | 是 | `no-auth` 或 `api-key` |
| `authorization.config.type` | string | 否 | `api-key` 时必填：`basic` / `bearer` / `custom` |
| `authorization.config.api_key` | string | 否 | 密钥或 token，建议用环境变量引用而不是明文 |
| `authorization.config.header` | string | 否 | `custom` 时的自定义头名 |
| `timeout.connect` | number | 否 | 连接超时，单位秒 |
| `timeout.read` | number | 否 | 读取超时，单位秒 |
| `timeout.write` | number | 否 | 写入超时，单位秒 |
| `retry_config.retry_enabled` | boolean | 否 | 失败重试开关（部分导出写作 `enabled`，以目标工作区导出的 DSL 为准） |
| `retry_config.max_retries` | number | 否 | 最大重试次数 |
| `retry_config.retry_interval` | number | 否 | 重试间隔，毫秒 |
| `ssl_verify` | boolean | 否 | 是否校验证书，默认 `true` |
| `selected` | boolean | 是 | 导出固定为 `false` |

### `body.type` 取值

| 值 | 说明 |
| --- | --- |
| `none` | 无请求体 |
| `json` | JSON 体，`body.data` 每个条目是一个字段 |
| `raw-text` | 纯文本体 |
| `x-www-form-urlencoded` | 表单编码 |
| `form-data` | multipart 表单 |
| `binary` | 二进制上传，首条目需给出 `file` |

## 最小可导入示例

```yaml
- id: "1770000000105"
  type: custom
  data:
    type: http-request
    title: "解析文本"
    method: post
    url: "https://api.example.com/parse"
    headers: "Content-Type: application/json"
    params: ""
    body:
      type: json
      data:
        - id: body-1
          key: text
          type: text
          value: "{{#1770000000101.text#}}"
    authorization:
      type: no-auth
    timeout:
      connect: 10
      read: 60
      write: 10
    retry_config:
      retry_enabled: false
    selected: false
  position: {x: 980, y: 282}
  width: 244
  height: 90
```

## 数据流

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `body` | string | 响应体原文，JSON 也只是字符串 |
| `status_code` | number | HTTP 状态码 |
| `headers` | object | 响应头 |
| `files` | array[file] | 响应中解析出的文件 |

- 下游引用：`["<node_id>", "body"]`、`{{#<node_id>.status_code#}}`。
- `body` 是字符串；要取 JSON 字段，先接 `code` 节点做 `json.loads`，或用 `tool` 的 JSON 处理能力。
- 想做"状态码非 2xx 就走另一条路"，在本节点后接 `if-else`，条件用 `status_code` 比较。
- 出边 `sourceHandle` 固定为 `source`。

## 常见导入失败原因

- `body.type: json` 但 `body.data` 不是数组（写成了对象或字符串）。
- `authorization.type: api-key` 却没给 `config.api_key`，或 `custom` 时漏了 `config.header`。
- `method` 写成大写 `GET`：导出与校验按小写比对，保持小写最稳。
- `headers` / `params` 用了 YAML 列表形式，这两个字段要求 `key: value` 的换行字符串。
- `timeout` 写成 `max_connect_timeout` 之类边界字段而缺 `connect` / `read` / `write`，导入后超时被重置。
