# 文档提取器（`document-extractor`）

把上传的文件解析成纯文本，供下游 LLM / code / 模板节点消费。

## 用途

- 从 PDF、DOCX、DOC、TXT、Markdown、HTML、XLS/XLSX 等文档里抽取文本。
- 作为「文件输入 → 文本」的固定桥梁：`start.files` → 提取 → 塞进 LLM prompt。
- 在 `iteration` 内逐文件抽取，把一批文件变成一批文本。

## 何时用 / 何时不要用

**用**：

- 用户上传的是文档，而下游节点只吃字符串。
- 需要在进入 LLM 之前拿到原文做切片、关键词匹配或入库。

**不要用**：

- 输入已经是文本（直接用 `start` 变量或上游输出）。
- 需要理解图片内容：文档提取器只出文字，图片需走视觉模型或 OCR 类工具。
- 只想知道文件元信息（文件名、大小、URL）：用 `list-operator` 或 `code` 取字段，不要指望提取器返回。

## 字段表

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 是 | 固定 `document-extractor`。 |
| `title` | string | 是 | 画布标题。 |
| `variable_selector` | string[] | 是 | 文件来源路径 `[node_id, key]`，**扁平数组**，不要写成 `{value_selector: [...]}`。 |
| `is_array_file` | boolean | 否 | `true` 表示输入是 `array[file]`（此时输出 `text` 为 `array[string]`）；`false` 表示单文件。旧版导出中通常显式写出，新版若省略则以 `variable_selector` 指向的类型推断——以目标工作区导出的 DSL 为准。 |

## 最小可导入示例

```yaml
- id: doc_extractor
  type: custom
  data:
    type: document-extractor
    title: "文档提取器"
    variable_selector: [start_node, files]
  position: {x: 340, y: 300}
  width: 244
  height: 90
```

单文件、显式声明非数组输入的写法：

```yaml
    is_array_file: false
    variable_selector: [start_node, uploaded_doc]
```

### 在 `iteration` 内逐文件抽取

外层把 `array[file]` 交给迭代容器，内层提取器拿单个元素：

```yaml
- id: doc_extractor_in_iter
  type: custom
  parentId: iter_node
  data:
    type: document-extractor
    title: "逐文件提取"
    isInIteration: true
    iteration_id: iter_node
    variable_selector: [iter_node, item]
  position: {x: 128, y: 68}
  width: 244
  height: 90
```

容器自身的 `iterator_selector` 指向 `["start_node","files"]`，`output_selector` 指向迭代内最后一个节点的输出（例如 `[code_in_iter, result]`），`output_type` 相应写成 `array[string]` 或 `array[object]`。

## 数据流

- 唯一输出是 `text`：单文件时为 `string`，`array[file]` 时为 `array[string]`。
- 下游引用：模板 `{{#doc_extractor.text#}}`，结构化字段 `["doc_extractor", "text"]`。
- 接 LLM 时常见做法：提取 → `llm` 的 `prompt_template` 里写 `{{#doc_extractor.text#}}`；结果太长时先过 `code` 或 `template-transform` 截断/拼接。
- 接知识库写入时：`knowledge-index` 的 `index_chunk_variable_selector` 指向 `["doc_extractor", "text"]`。
- 在 `iteration` 内使用时，`variable_selector` 指向迭代容器的元素变量，形如 `[<iteration_id>, item]`，且输入是单文件（不要 `is_array_file: true`）；容器内的节点还要带 `parentId`、`isInIteration: true`、`iteration_id`。

## 输出处理

- 长文档通常会超出模型上下文，先按段落切分再喂 LLM，或只喂前 N 字符 + 摘要。
- `array[file]` 输入时 `text` 是数组，不能直接塞进 prompt；要么用 `iteration` 逐份处理，要么 `code` 里 `"\n\n".join(texts)` 合并。
- 表格/扫描件可能提取出空文本或乱码；上线前用真实样本验证，别假设 PDF 一定能抽出字。

## 常见导入失败原因

1. `variable_selector` 被写成对象列表 `[{value_selector: [...]}]`——本节点只接受扁平字符串数组。
2. `variable_selector` 指向的节点不存在或指向了非文件类型变量（如 `text`），运行时解析失败。
3. `is_array_file` 与实际类型不匹配：单文件却设 `true`，或文件列表设 `false`，抽取结果为空或报错。
4. 文件类型未在应用 `features.file_upload.allowed_file_types` 中开放，上传阶段即被拒，节点永远拿不到文件。
5. 把节点放在 `iteration` 里却漏了 `parentId` / `isInIteration`，导入后节点脱离容器、位置重置。
