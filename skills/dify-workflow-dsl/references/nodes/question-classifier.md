# 问题分类器（`question-classifier`）

用一次 LLM 调用把输入文本判定到预定义类别，每个类别对应一条固定出口边。

## 用途

- 语义级意图路由：把用户问题分到"上传文件 / 查询历史 / 闲聊"等互斥类别。
- 替代一串 `if-else` 关键词判断，降低维护成本。
- 与 `parameter-extractor` 的分工：分类器只给"属于哪一类"，抽取器给"具体字段"。

## 何时用 / 何时不要用

适合：

- 类别数量固定且语义边界清晰，每个类别都能用一句 `name` 描述。
- 后续每条分支的流程差异明显（不同工具、不同知识库、不同话术）。

不要用：

- 规则可枚举（含某关键词、长度阈值、是否为空）→ 用 `if-else`，省 token 且确定。
- 需要同时拿到类别和结构化字段 → 先用 `parameter-extractor` 抽出 `type` 字段，再用 `if-else`。
- 类别数量会随数据增长（如按业务线无限扩展）→ 改为检索或 `llm` 输出标签。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `question-classifier`。 |
| `title` | string | 是 | 画布标题。 |
| `query_variable_selector` | string[] | 是 | 待分类文本，如 `["sys", "query"]` 或 `["<node_id>", "text"]`。 |
| `model` | object | 是 | 模型配置，含 `provider` / `name` / `mode` / `completion_params`。 |
| `model.provider` | string | 是 | 形如 `langgenius/tongyi/tongyi`，需在 `dependencies` 中覆盖。 |
| `model.name` | string | 是 | 模型名，如 `qwen3.5-flash`。 |
| `model.mode` | string | 是 | 通常 `chat`。 |
| `model.completion_params` | object | 否 | 常用 `temperature: 0`，分类任务不要发散。 |
| `classes` | array | 是 | 类别列表，**至少 2 个**；顺序即分支顺序。 |
| `classes[].id` | string | 是 | 类别 ID，**同时是出边 `sourceHandle`**。 |
| `classes[].name` | string | 是 | 类别语义描述，直接进提示词，写得越具体判定越稳。 |
| `instruction` | string | 否 | 补充分类规则（优先级、边界情况、禁止自行发明类别）。 |
| `memory` | object | 否 | 仅 Chatflow 有意义，结构同 `llm`。 |
| `vision` | object | 否 | `{enabled: false}`；开启时补 `configs.variable_selector`。 |
| `selected` | boolean | 是 | 导出固定 `false`。 |

类别数量：UI 侧下限为 2；上限与"模型无法归类时的行为"（落到某一类还是节点报错）随版本变化，**以目标工作区导出的 DSL 与运行结果为准**。需要确定性兜底时，额外加一个 `name: "其他"` 的类别，或在分类器后接 `if-else`。

## 最小可导入示例

```yaml
- id: "1770000000201"
  type: custom
  data:
    type: question-classifier
    title: "问题分类"
    query_variable_selector: ["sys", "query"]
    model:
      provider: langgenius/tongyi/tongyi
      name: qwen3.5-flash
      mode: chat
      completion_params:
        temperature: 0
    classes:
      - id: "upload"
        name: "用户要上传或解析文件"
      - id: "history"
        name: "用户要查询历史记录"
      - id: "other"
        name: "以上都不符合的其它问题"
    instruction: "只能选择已有类别，不要新建类别；信息不足时归入 other。"
    vision:
      enabled: false
    selected: false
  position: {x: 380, y: 282}
  width: 244
  height: 180
```

## 数据流

- 节点的主要作用是按判定结果激活一条出边；出口数量 = `classes` 数量，没有隐式的 ELSE 出口。
- 部分版本会额外暴露 `class_name`（命中类别的显示名）供下游引用，能否使用以目标工作区导出为准；`deliver_checklist.py` 与校验器都不会因引用它报错。
- `sourceHandle` 必须等于命中的 `classes[].id`：

```yaml
edges:
  - id: "1770000000201-upload-1770000000401-target"
    source: "1770000000201"
    sourceHandle: "upload"
    target: "1770000000401"
    targetHandle: target
    type: custom
    data: {sourceType: question-classifier, targetType: document-extractor}
```

- `id` 在 YAML 里建议加引号；`id: 1` 会被解析成整数 `1`，与出边写入的字符串 `"1"` 对不上。
- 分支汇合仍需 `variable-aggregator`；分类器本身不做合并。
- 老版本导出可能带 `_targetBranches`，那是前端加载时由 `classes` 派生出来的运行时字段，手写无意义，导入时也会被重建。

## 常见导入失败原因

- `classes` 少于 2 项，或两项 `id` 重复，节点校验不通过。
- 出边 `sourceHandle` 用了类别的 `name`、序号或 UUID，而 `classes[].id` 是另一套值，导致分支悬空。
- `classes[].id` 写成未加引号的数字，YAML 解析成 number，与边的字符串 handle 不匹配。
- `query_variable_selector` 写成字符串（`"{{#sys.query#}}"`）或一维数组缺节点前缀。
- `model.provider` 未出现在顶层 `dependencies`，导入时提示插件/模型未安装。
- 手写 `_targetBranches` 并与 `classes` 不一致，覆盖了真实分支。
