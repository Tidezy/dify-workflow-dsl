# 知识检索（`knowledge-retrieval`）

在一个或多个知识库里检索相关分段，并把命中结果作为结构化列表输出。

## 用途

- 从已建好的知识库（dataset）里召回与问题最相关的文本分段。
- 给 LLM 提供 RAG 上下文：检索节点输出挂到 `llm.context.variable_selector`。
- 直接把命中结果做引用展示（`result[].metadata` 带文档名、分段位置、得分）。

## 何时用 / 何时不要用

**用**：

- 回答依赖私有文档、且知识库已在目标工作区建好并完成索引。
- 需要 top-k 截断、重排序或元数据过滤的召回。

**不要用**：

- 知识库还没建好、或索引未完成——节点会返回空结果，而不是报错。
- 只需要关键词精确匹配单个文档：用 `http-request` 或 `code`。
- 目标工作区没有对应 dataset：`dataset_ids` 里的 UUID 无法跨工作区复用。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `knowledge-retrieval`。 |
| `title` | string | 是 | 画布标题。 |
| `dataset_ids` | string[] | 是 | 目标工作区的知识库 UUID 列表，至少一个。 |
| `query_variable_selector` | string[] | 条件必填 | 查询文本来源 `[node_id, key]`，通常是 `["sys","query"]` 或 start 变量。 |
| `query_attachment_selector` | string[] | 条件必填 | 图片/附件查询来源（视觉检索用）。 |
| `retrieval_mode` | string | 是 | `multiple`（多库并行召回并合并）或 `single`（由 LLM 选库）。 |
| `multiple_retrieval_config` | object | `retrieval_mode: multiple` 时 | 多路召回参数，见下表。 |
| `single_retrieval_config` | object | `retrieval_mode: single` 时 | 含 `model`（`provider` / `name` / `mode` / `completion_params`）。 |
| `metadata_filtering_mode` | string | 否 | `disabled`（默认）/ `automatic` / `manual`。 |
| `metadata_filtering_conditions` | object | `manual` 时 | `logical_operator`（`and` / `or`）+ `conditions[]`（`name` / `comparison_operator` / `value`）。 |
| `metadata_model_config` | object | `automatic` 时 | 同 `model` 结构，用于让 LLM 生成过滤条件。 |

`query_variable_selector` 与 `query_attachment_selector` 至少给一个，否则节点无法执行。

`multiple_retrieval_config`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `top_k` | number | 是 | 返回分段数上限，常见 4。 |
| `score_threshold_enabled` | boolean | 否 | 是否启用相似度阈值（导出常见字段）。 |
| `score_threshold` | number | 否 | 阈值 0–1；未启用时写 `0`，旧导出可能写 `null`。 |
| `reranking_enable` | boolean | 否 | 是否开启重排序。 |
| `reranking_mode` | string | 否 | `reranking_model` 或 `weighted_score`。 |
| `reranking_model` | object | `reranking_mode: reranking_model` 时 | `provider` / `model`。 |
| `weights` | object | `reranking_mode: weighted_score` 时 | `weight_type`（`semantic_first` / `keyword_first` / `customized`）+ `vector_setting` / `keyword_setting` 权重。 |

`single` 模式会消耗一次 LLM 调用选库，库多且问题模糊时有收益；只有一个库时用 `multiple` 更省。

## 最小可导入示例

```yaml
- id: knowledge_retrieval
  type: custom
  data:
    type: knowledge-retrieval
    title: "知识检索"
    dataset_ids:
      - "00000000-0000-0000-0000-000000000000"
    query_variable_selector: [start_node, input_text]
    retrieval_mode: multiple
    multiple_retrieval_config:
      top_k: 4
      reranking_enable: false
      score_threshold_enabled: false
      score_threshold: 0
    metadata_filtering_mode: disabled
  position: {x: 340, y: 300}
  width: 244
  height: 90
```

`dataset_ids` 里的 UUID 必须替换成目标工作区真实存在的知识库 ID。

## 数据流

- 唯一输出是 `result`（`array[object]`），每个元素含：`content`、`title`、`url`、`icon`、`metadata`、`files`。
- `metadata` 内常见键：`dataset_id`、`dataset_name`、`document_id`、`document_name`、`segment_id`、`segment_position`、`score`。
- 喂给 LLM：`llm.context.enabled: true` + `llm.context.variable_selector: ["knowledge_retrieval", "result"]`。
- 直接拼文本：`template-transform` 的 `variables` 里挂 `["knowledge_retrieval","result"]`，模板中遍历 `row.content`。
- 模板插值：`{{#knowledge_retrieval.result#}}` 只适合调试，正式回复请先渲染成字符串。

## 常见导入失败原因

1. `dataset_ids` 为空，或填了源工作区的 UUID（目标工作区不存在该 ID），导入后节点显示未配置知识库。
2. `retrieval_mode` 与配置块不匹配：`multiple` 却只给 `single_retrieval_config`（或反之）。
3. `query_variable_selector` 指向不存在的节点/字段，或引用了 `array[object]` 等非文本变量。
4. `score_threshold` 写成字符串（`"0.5"`），类型不匹配导致校验失败。
5. `metadata_filtering_mode: manual` 但 `metadata_filtering_conditions.conditions` 为空，过滤条件无效。
