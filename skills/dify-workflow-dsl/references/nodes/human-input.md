# 人工输入（`human-input`）

在流程中间挂起工作流，等真人填写表单并点击某个动作按钮，再按所选动作沿不同分支继续。

## 用途

`human-input` 是中断型节点：执行到这里工作流暂停并生成一条待办，收件人在 Web App（或已配置的投递渠道）填写 `inputs` 定义的表单、点击 `user_actions` 中的按钮。恢复执行后，按钮决定走哪条出边（动作 `id` 即 `sourceHandle`），每个 `output_variable_name` 成为一个节点输出，另外固定暴露 `__action_id`、`__action_value`、`__rendered_content` 三个元信息输出。

该节点只在 DSL 0.7.0（Dify 1.16.x）中存在，0.6.0 工作区导入会报未知节点类型。

## 何时用 / 何时不要用

**何时用**

- 需要人工审批/复核，且"通过"与"退回"要走不同后续逻辑。
- 机器无法判定的主观结论，需要人补一段意见或选一个等级。
- 需要人工上传佐证材料（`file` / `file-list`）再继续。

**何时不要用**

- 只是让用户多填几个初始参数 → 用 `start` 的 `variables`。
- 需要"人在环"但不阻塞流程 → 外部系统 + `http-request` 轮询。
- 想放进 `loop` / `iteration` 容器内 → 不支持，容器内不提供该节点。

## 字段表

`data` 载荷字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | `string` | 是 | 固定为 `human-input`。 |
| `title` | `string` | 是 | 节点标题，同时是待办标题。 |
| `delivery_methods` | `array` | 是 | 投递渠道，至少一项，每项含 `id` / `type` / `enabled`；当前以 `type: webapp` 为主，其他渠道配置是工作区相关的，**以目标工作区导出的 DSL 为准**。 |
| `form_content` | `string` | 是 | 表单说明文案，支持 `{{#node.var#}}` 插值，用来回显上游结果。 |
| `inputs` | `array` | 是 | 表单字段定义；纯动作确认时给 `[]`。 |
| `user_actions` | `array` | 是 | 动作按钮，至少一个；`id` 即分支句柄。 |
| `timeout` | `number` | 是 | 超时时长，配合 `timeout_unit`。 |
| `timeout_unit` | `"hour" \| "day"` | 是 | 超时单位，只有这两个值。 |

`inputs[]` 子字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | `string` | 是 | 仅 `paragraph` / `select` / `file` / `file-list`。 |
| `output_variable_name` | `string` | 是 | 输出变量名，**全节点唯一**，并成为该节点的一个输出。 |
| `default` | `object` | 否 | 默认值：`{type: constant, selector: [], value: ""}`。 |
| `option_source` | `object` | `select` 必填 | `{type: constant, selector: [], value: [选项...]}`，或 `{type: variable, selector: [node, arr]}`（选择器至少两段）。 |
| `allowed_file_types` | `array` | `file`/`file-list` 必填 | 类型族，如 `[document, image]`。 |
| `allowed_file_extensions` | `array` | 否 | 扩展名白名单；类型选 `custom` 时至少给一项。 |
| `allowed_file_upload_methods` | `array` | `file`/`file-list` 必填 | 仅 `local_file` / `remote_url`。 |
| `number_limits` | `number` | 否 | 文件数量上限，`file-list` 常用。 |

`user_actions[]` 子字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | `string` | 是 | 动作标识，**≤ 20 字符**，直接用作出边 `sourceHandle`。 |
| `title` | `string` | 是 | 按钮文案。 |
| `button_style` | `"primary" \| "default"` | 否 | 按钮样式，首个动作建议 `primary`。 |

### 节点输出

| 输出 | 说明 |
| --- | --- |
| `<output_variable_name>` | 每个表单字段一个输出：`paragraph` → `string`，`select` → `string`，`file` → `file`，`file-list` → `array[file]`。 |
| `__action_id` | 被点击动作的 `id`，适合直接回写"决策"字段。 |
| `__action_value` | 动作携带的值，纯动作按钮通常与 `__action_id` 相同。 |
| `__rendered_content` | 渲染后的 `form_content`，可用于存档。 |

### 分支句柄

普通分支的 `sourceHandle` 等于 `user_actions[].id`（如 `approve`、`reject`）；超时分支固定为 `__timeout`，布局上总是排在最后一条。

## 最小可导入示例

`start` → `human-input`（意见 + 风险等级 + 附件）→ 通过 / 超时两条 `end`；片段置于 `workflow.graph.nodes` / `edges` 下（0.7.0 形态）。

```yaml
    nodes:
      - id: approval_start
        type: custom
        data:
          type: start
          title: "提交审批"
          variables:
            - label: "审批内容"
              variable: proposal
              type: paragraph
              required: true
              max_length: 10000
        position: {x: 40, y: 300}
        width: 244
        height: 90
      - id: human_review
        type: custom
        data:
          type: human-input
          title: "人工复核"
          delivery_methods:
            - id: webapp
              type: webapp
              enabled: true
          form_content: "请复核以下内容：\n\n{{#approval_start.proposal#}}"
          inputs:
            - type: paragraph
              output_variable_name: comment
              default:
                type: constant
                selector: []
                value: ""
            - type: select
              output_variable_name: risk_level
              option_source:           # select 必须有 option_source
                type: constant
                selector: []
                value: [低, 中, 高]
            - type: file-list
              output_variable_name: evidence
              allowed_file_types: [document, image]
              allowed_file_extensions: []
              allowed_file_upload_methods: [local_file]
              number_limits: 3
          user_actions:
            - id: approve              # id ≤ 20 字符，且就是出边句柄
              title: "通过"
              button_style: primary
            - id: reject
              title: "退回"
              button_style: default
          timeout: 24
          timeout_unit: hour
        position: {x: 370, y: 300}
        width: 280
        height: 210
      - id: approved_end
        type: custom
        data:
          type: end
          title: "审批通过"
          outputs:
            - variable: decision
              value_selector: [human_review, __action_id]
              value_type: string
            - variable: comment
              value_selector: [human_review, comment]
              value_type: string
            - variable: risk_level
              value_selector: [human_review, risk_level]
              value_type: string
        position: {x: 730, y: 190}
        width: 244
        height: 120
      - id: timeout_end
        type: custom
        data:
          type: end
          title: "超时关闭"
          outputs:
            - variable: decision
              value_selector: [human_review, __action_id]
              value_type: string
        position: {x: 730, y: 430}
        width: 244
        height: 90
    edges:
      - id: approval_start-source-human_review-target
        source: approval_start
        sourceHandle: source
        target: human_review
        targetHandle: target
        type: custom
        data: {sourceType: start, targetType: human-input, isInIteration: false, isInLoop: false}
      - id: human_review-approve-approved_end-target
        source: human_review
        sourceHandle: approve         # 动作 id 作为句柄
        target: approved_end
        targetHandle: target
        type: custom
        data: {sourceType: human-input, targetType: end, isInIteration: false, isInLoop: false}
      - id: human_review-__timeout-timeout_end-target
        source: human_review
        sourceHandle: __timeout       # 超时分支固定用 __timeout
        target: timeout_end
        targetHandle: target
        type: custom
        data: {sourceType: human-input, targetType: end, isInIteration: false, isInLoop: false}
```

## 数据流

1. 上游输出通过 `form_content` 的 `{{#node.var#}}` 展示给填写人，这是把上下文带进表单的唯一通道。
2. 填写人提交后，`inputs` 每项按 `output_variable_name` 变成节点输出。
3. 被点击的按钮决定走哪条出边：`approve` 继续自动化流程，`reject` 通常回到人工或修正节点。
4. 超时后走 `__timeout` 分支；没连这条边时超时后没有后续路径，需要自己保证兜底出口。
5. 下游常用 `[human_review, __action_id]` 记录"谁按了哪个按钮"，用 `[human_review, __rendered_content]` 存档当时的表单快照。

## 常见导入失败原因

- **`user_actions[].id` 超过 20 字符**（如 `request-more-information`），保存或导入时报动作标识非法。
- **`select` 缺 `option_source`**，或 `type: variable` 只给了一段选择器——必须 `constant` + 字符串数组，或 `variable` + 至少两段选择器。
- **`file` / `file-list` 缺 `allowed_file_types` 或 `allowed_file_upload_methods`**，或上传方式写成 `local` / `url`（只能是 `local_file`、`remote_url`）。
- **`output_variable_name` 重名**：两个字段同名会互相覆盖，节点只暴露一个输出。
- **`timeout_unit` 写成 `hours` / `minutes`，或超时句柄写成 `timeout`**：后者会让边变成孤立分支，正确值是 `__timeout`。
