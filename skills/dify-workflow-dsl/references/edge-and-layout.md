# 边、分支句柄与画布布局

边写错是导入失败与"画布上连线消失"的首要原因。本文把句柄规则和坐标规则分开讲，两者互不影响，但都需要满足。

## 边的结构

```yaml
- id: "n1-source-n2-target"
  source: "n1"
  sourceHandle: source
  target: "n2"
  targetHandle: target
  type: custom
  zIndex: 0
  data:
    sourceType: start
    targetType: llm
    isInIteration: false
    isInLoop: false
```

| 字段 | 规则 |
|---|---|
| `id` | 全局唯一。约定 `{source}-{sourceHandle}-{target}-{targetHandle}`，Dify 不校验格式但重复会出问题 |
| `source` / `target` | 必须是已存在节点的 `id` |
| `sourceHandle` | 见下表，普通节点固定为 `"source"` |
| `targetHandle` | 恒为 `"target"` |
| `type` | 恒为 `"custom"` |
| `zIndex` | 顶层 `0`；容器内 `1002` |
| `data.sourceType` / `data.targetType` | 等于两端 `data.type`，写错不报错但画布渲染异常 |
| `data.isInIteration` / `isInLoop` | 与所在容器一致 |

## 分支句柄对照

| 源节点 | `sourceHandle` 取值 |
|---|---|
| 普通节点（start / llm / code / http-request / tool / template-transform / knowledge-retrieval / document-extractor / assigner / list-operator / aggregator / iteration / loop / end 等） | `"source"` |
| `if-else` | 各 `cases[].id`；ELSE 分支固定 `"false"` |
| `question-classifier` | 各 `classes[].id` |
| `human-input` | 各 `user_actions[].id`；超时分支 `"__timeout"` |
| 容器 `iteration` / `loop` | `"source"`（出口只有一条，接容器之后） |

易错点：

- `if-else` 的 `cases[].id`、`cases[].case_id`、边上 `sourceHandle` **三处必须完全相同**。有的导出两者都写，有的只写 `id`，跟目标工作区的导出一致即可。
- `question-classifier` 的 `classes[].id` 在 YAML 里建议加引号。写成 `id: 1` 会解析成数字，而边 handle 是字符串 `"1"`，匹配不上。
- `human-input` 的 `user_actions[].id` 上限 20 字符，且不能为空；它同时是按钮标识和分支句柄。
- 分支数 ≠ 出边数是被允许的（某个分支不接后续节点），但**句柄拼错**不会被拦，表现为该分支永远走不到。

## 坐标布局

Dify 画布是左上原点、x 向右、y 向下的网格。布局不影响执行，只影响可读性与节点是否重叠。

推荐参数：

| 项 | 值 |
|---|---|
| start 起点 | `{ x: 80, y: 282 }` |
| 水平步长 | 300（节点宽 244 + 间距 56） |
| 垂直分支间距 | 200 |
| 常见节点尺寸 | 244 × 54（start/end）、244 × 90~120（处理节点）、280 × 180（human-input）、520 × 210（loop） |

一条链的写法：

```yaml
# n1 x=80, n2 x=380, n3 x=680，纵向都取 282
```

分支（if-else 两个出口）的写法：目标节点保持 x 递增，y 分别取 `182` 与 `482`，避免连线交叉。

## 容器布局

容器（`iteration` / `loop`）有两个坐标系：

- **容器本身**：用顶层 `position` 定位，`width` / `height` 同时写在 wrapper 和 `data` 里，缺一处画布会显示为默认尺寸。
- **容器子节点**：`position` 是**相对容器内部**的坐标，`positionAbsolute` 才是全局坐标（= 容器 position + 相对坐标）。

容器内的入口是辅助节点，不是普通节点：

| 容器 | wrapper `type` | `data.type` | 说明 |
|---|---|---|---|
| iteration | `custom-iteration-start` | `iteration-start` | `draggable: false`，`selectable: false` |
| loop | `custom-loop-start` | `loop-start` | 同上 |

容器子节点必须同时具备：

- `parentId` = 容器 id
- `data.isInIteration: true` 或 `data.isInLoop: true`
- `data.iteration_id` 或 `data.loop_id` = 容器 id
- `zIndex: 1002`

容器内的边还要额外带 `data.isInIteration` / `data.isInLoop` 与对应 id，`zIndex: 1002`。

## 结构与可达性

- 每个图模式必须有**唯一** `start`（或触发器）作为入口。
- `workflow` 模式要求至少一个可达的 `end`；`advanced-chat` 要求至少一个可达的 `answer`。
- 除容器内部外，图不允许出现环。需要反复执行请用 `loop` 节点，不要用回边硬连。
- 所有执行节点都应从入口可达；孤岛节点不会被校验拦住，但永远不会执行。
- 容器节点的出口边只能从容器本身引出，不能从容器内的子节点直接连到外部。

## 自检清单

1. 每条边的 `source` / `target` 都在 `nodes[].id` 里；
2. 分支节点的出边 handle 与分支定义逐字一致（含引号与大小写）；
3. 容器子节点的 `parentId` / `zIndex` / `isIn*` 三件套齐全；
4. 没有孤立节点、没有意外回边；
5. `data.sourceType` / `data.targetType` 与两端 `data.type` 对齐。

前四条由 `scripts/validate_dsl.py` 覆盖，第 5 条目前只做告警。

## 相关

- `dsl-format.md` — 节点 wrapper 与变量引用
- `nodes/if-else.md`、`nodes/question-classifier.md`、`nodes/human-input.md` — 三类分支节点
- `nodes/iteration.md`、`nodes/loop.md` — 容器内部结构
