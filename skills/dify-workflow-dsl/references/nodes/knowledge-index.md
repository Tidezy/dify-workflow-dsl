# 知识库写入（`knowledge-index`）

把上游文本写入指定知识库并触发索引，让工作流能把新内容沉淀成可检索资产。

## 用途

- 把文档提取器/LLM 生成的文本切片写入知识库，形成可被 `knowledge-retrieval` 召回的语料。
- 定时同步场景：定时抓取 → 清洗 → 写入知识库。
- 闭环场景：用户上传资料 → 抽取 → 入库，下一轮问答即可命中。

## 何时用 / 何时不要用

**用**：

- 目标 Dify 版本支持在工作流内写知识库（较新的 1.x）。版本不确定时，先看目标工作区能否导出该节点，再决定是否写入 DSL。
- 输入已是纯文本，且目标知识库已建好、embedding 模型可用。

**不要用**：

- 老版本 Dify（节点类型未注册）：导入会被当成未知节点，图校验失败。
- 只想更新已有分段的内容——该节点是追加写入，不做原地更新。
- 知识库还在索引中或 embedding 模型未配置：写入会失败或长时间排队。
- `iteration` / `loop` 内部：容器内禁止该节点（同 `end` / `datasource` / `human-input`）。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `knowledge-index`。 |
| `title` | string | 是 | 画布标题。 |
| `dataset_id` | string | 是 | **单个**目标知识库 ID（注意：检索节点是复数 `dataset_ids`）。 |
| `index_chunk_variable_selector` | string[] | 是 | 待写入文本来源 `[node_id, key]`，必须是字符串。 |
| `keyword_number` | number | 否 | 关键词抽取条数，常见 10。 |
| `retrieval_model` | object | 否 | 写入时使用的检索/索引参数，见下表。 |

`retrieval_model`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `top_k` | number | 否 | 检索参数，常见 3。 |
| `score_threshold_enabled` | boolean | 否 | 是否启用相似度阈值。 |
| `score_threshold` | number | 否 | 阈值 0–1。 |

不同 Dify 版本对 `retrieval_model` 的必填项要求不同，字段缺失时以目标工作区导出的 DSL 为准，不要凭猜测补齐。

## 最小可导入示例

```yaml
- id: knowledge_index
  type: custom
  data:
    type: knowledge-index
    title: "写入知识库"
    dataset_id: "00000000-0000-0000-0000-000000000000"
    index_chunk_variable_selector: [doc_extractor, text]
    keyword_number: 10
    retrieval_model:
      top_k: 3
      score_threshold_enabled: false
      score_threshold: 0.5
  position: {x: 680, y: 300}
  width: 244
  height: 90
```

`dataset_id` 必须替换成目标工作区的真实知识库 ID；该节点的画布标题常被用来做写入来源标识。

## 数据流

- 输入：`index_chunk_variable_selector` 指向的字符串。上游通常是 `document-extractor.text`、`llm.text`、`template-transform.output` 或 `code` 输出。
- 输出：该节点是**汇点**，不产生可被下游引用的变量，**不要给它接出边**（连边校验会拒绝）。
- 入边 `targetHandle` 用 `target`，`sourceHandle` 用 `source`。
- 因为它不能有后继，若整条流程还需要返回结果，请把写入放在分支末端，另一条分支接 `end`；纯写入型工作流可以没有 `end`。是否需要 `end` 以目标版本校验为准。
- 写入是异步索引：节点返回成功不代表马上可被检索命中，下游立刻检索可能召回不到新内容。

## 典型链路

**上传即入库**：`start`（`file-list`）→ `document-extractor` → `knowledge-index`。提取器输出 `text` 直接作为 `index_chunk_variable_selector`，链路里不需要 `end`。

**定时同步**：`trigger-schedule` → `http-request` → `code`（清洗成字符串）→ `knowledge-index`。触发器入口没有 `start`，清洗结果依赖 `code` 的输出。

```yaml
# 定时链路的收尾：写入后直接结束，不要再接节点
- id: knowledge_index
  type: custom
  data:
    type: knowledge-index
    title: "同步写入"
    dataset_id: "00000000-0000-0000-0000-000000000000"
    index_chunk_variable_selector: [clean_code, result]
    keyword_number: 10
    retrieval_model:
      top_k: 3
      score_threshold_enabled: false
      score_threshold: 0.5
  position: {x: 980, y: 300}
  width: 244
  height: 90
```

**写入后立刻检索**：同一张图里 `knowledge-index` 之后不能再接 `knowledge-retrieval`（前者无出边）。需要「写+读」闭环时拆成两个工作流，由外部按顺序调用。

## 版本与依赖

- 节点可用性取决于目标 Dify 版本；版本不支持时导入表现为未知节点或图校验失败。
- 写入用的 embedding 与索引参数由知识库自身配置决定，DSL 里只声明 `dataset_id` 与阈值，不要试图在节点内覆盖 embedding 模型。
- 跨工作区迁移时 `dataset_id` 一定失效，需要人工替换；建议在 DSL 里保留占位 UUID 并在交付说明中标注。

## 常见导入失败原因

1. 字段写成 `dataset_ids`（复数）——本节点只认单数 `dataset_id`，写成数组会类型校验失败。
2. `index_chunk_variable_selector` 指向非字符串（如 `array[file]` 或 `array[string]`），运行时写入报错。
3. `dataset_id` 是源工作区的 UUID，导入后知识库不存在，节点显示未配置。
4. 目标 Dify 版本不支持 `knowledge-index`，导入报未知节点类型。
5. 给它接了出边，或放进 `iteration` / `loop` 容器内，图结构校验失败。
