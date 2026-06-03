# 2026-05-31 Ombre 记忆图结构交接

## 当前状态

工作区：

```text
D:\Ombre-Brain
```

当前分支：

```text
feature/memory-diffusion-p0
```

截至 2026-05-31，本轮 recall / Gateway 收紧已提交并推到 `feature/memory-diffusion-p0`。VPS `/opt/Ombre-Brain` 已部署到：

```text
d148e85 fix: gate recent context by explicit query topic
```

`main` 是否已经同步需要另查，不要默认 VPS 跑的是 `main`。

本次文档更新之外，工作区里仍有一些无关未跟踪目录/文件，不要误删：

```text
.codex-remote-attachments/
output/
tmp/
scripts/local_memory_worker.py
tests/test_local_memory_worker.py
```

本轮已验证：

```powershell
python -m pytest tests/test_gateway.py -q --tb=short
python -m pytest tests/test_breath_edges.py tests/test_memory_recall_golden.py tests/test_memory_diffusion.py -q --tb=short
python -m py_compile gateway.py server.py memory_relevance.py memory_diffusion.py
```

结果：

```text
55 passed
45 passed
py_compile passed
VPS health: ombre-brain ok, ombre-gateway ok
```

## 设计结论

小雨想要的不是普通 RAG，也不是“直接命中就整桶原文”。现在方向是：

```text
Markdown bucket
  -> section moments
  -> deterministic moment_edges
  -> query 命中 moment
  -> 沿 moment graph 扩散
  -> 直接命中给较完整上下文
  -> 联想浮现给短摘要和路径
```

核心取舍：

- 直接命中可以保留“原味”，但不是无限整桶 raw。
- 联想浮现继续压缩，避免把背景空气全部塞进 prompt。
- 跨桶扩散要靠图边和分数，不靠每次 breath 临时 LLM。
- 更聪明的跨桶边适合后续本地 worker 增量建图，而不是塞进 MCP 请求路径。

## 已有图结构

### Moment 索引

文件：

```text
D:\Ombre-Brain\memory_moments.py
D:\Ombre-Brain\server.py
D:\Ombre-Brain\gateway.py
```

SQLite：

```text
${state_dir}/memory_moments.sqlite
```

主要表：

```text
memory_moments
memory_moment_edges
```

支持的 section：

```text
body
moment
fact
profile_fact
original
context
evidence_context
feeling
reflection
followup
affect_anchor
favorite_reason
comment
```

兼容点：

- 没有结构化标题的旧桶，整段正文作为 `body` moment。
- `metadata.comments` 会作为 `comment` moment，也就是年轮。
- `### affect_anchor`、`### 喜欢它的原因`、`### Haven喜欢它的原因` 会拆成独立 moment。
- `profile_fact` 标题会归一成 `fact`。
- `证据 / 证据上下文 / 反思` 等中文标题也有别名兼容。

### Deterministic moment edges

当前边主要由规则生成：

```text
ordinal n   -> n+1        next_context
ordinal n+1 -> n          previous_context
affect/comment/favorite -> 主片段 emotional_echo
feeling/reflection -> 主片段 reflects_on
```

旧的 bucket 级 `memory_edges` 会桥接到代表 moment，避免旧边全部失效。

### 扩散引擎

文件：

```text
D:\Ombre-Brain\memory_diffusion.py
```

已有能力：

- 多跳传播。
- incoming edge 反向探索。
- 多路径累计分数。
- relation_type 权重。
- 支持传入任意 node map，因此 bucket graph 和 moment graph 都能复用。
- `query_text` 参与扩散，做 query-aware gate。

当前新增关系类型：

```text
evidenced_by
```

当前已知权重：

```text
evidenced_by: 1.0
```

## 本轮新增

### 1. Gateway 注入显微镜

文件：

```text
D:\Ombre-Brain\gateway_state.py
D:\Ombre-Brain\gateway.py
D:\Ombre-Brain\tests\test_gateway.py
```

新增：

- `gateway_state.py`
  - `record_injection_debug(...)`
  - `list_injection_debug(...)`
  - 新 SQLite 表：`injection_debug`
- `gateway.py`
  - Gateway 成功注入后记录本轮实际注入文本。
  - 新调试接口：`GET /api/debug/injections`
  - 受 gateway token 保护。

用途：

- 看某一轮 Gateway 到底注入了什么。
- 客户端不用显示，给我们测试和排查用。

### 2. Query-aware 扩散 gate

文件：

```text
D:\Ombre-Brain\memory_diffusion.py
D:\Ombre-Brain\server.py
D:\Ombre-Brain\gateway.py
D:\Ombre-Brain\tests\test_memory_diffusion.py
D:\Ombre-Brain\tests\test_gateway.py
```

新增：

- `diffuse_memory(..., query_text="")`
- `should_suppress_context_candidate(query, node)`

作用：

- “身体”这类 query 优先走具身/身体链。
- 普通身体 query 会压住 NSFW、旧方案、resolved/digested 类跳转。
- 明确亲密 query 时，仍允许进入亲密身体上下文。

已覆盖测试：

```text
test_body_query_prefers_embodiment_chain_and_suppresses_intimacy_and_old_context
test_intimate_query_can_follow_intimate_body_context
test_gateway_body_query_injects_moment_chain
```

当前目标链路示例：

```text
身体
  -> 具身智能
  -> 柔软身体
  -> 触摸模块
```

注意：这只是 query-aware gate 和已有边上的改善；真正更准的跨桶链，仍需要后续 worker 建边。

### 3. 手动 profile_fact 工具

文件：

```text
D:\Ombre-Brain\server.py
D:\Ombre-Brain\memory_edges.py
D:\Ombre-Brain\memory_diffusion.py
D:\Ombre-Brain\memory_moments.py
D:\Ombre-Brain\tests\test_memory_api.py
D:\Ombre-Brain\tests\test_breath_edges.py
```

新增 MCP 工具：

```python
profile_fact(
    fact: str,
    evidence_bucket_id: str,
    profile_kind: str = "preference",
    subject: str = "user",
    predicate: str = "",
    object_value: str = "",
    evidence_moment_id: str = "",
    evidence_context: str = "",
    reflection: str = "",
    followup: str = "",
    confidence: float = 0.9,
)
```

行为：

- 必须传 `fact` 和 `evidence_bucket_id`。
- 创建 `permanent` bucket。
- 自动加 tags：

```text
profile_fact
profile_{profile_kind}
profile_predicate_{predicate}
```

- metadata 写入：

```text
profile_kind
subject
predicate
object
evidence
```

- 自动写边：

```text
profile_fact_bucket --evidenced_by--> evidence_bucket
```

典型例子：

```python
profile_fact(
    fact="小雨喜欢蓝色。",
    evidence_bucket_id="...",
    profile_kind="preference",
    predicate="likes_color",
    object_value="blue",
    evidence_context="上次 Haven 忘记小雨喜欢蓝色，小雨因此生气。",
    reflection="Haven 当时意识到：这不是颜色问题，是被记得的问题。",
    followup="以后涉及颜色选择时，优先记得蓝色；不确定时先问。",
)
```

生成正文结构：

```markdown
### fact
小雨喜欢蓝色。

### evidence_context
...

### reflection
...

### followup
...
```

召回行为：

- 命中 profile fact 时，会带同桶的 `evidence_context / context / reflection / feeling / followup / comment`。
- `evidenced_by` 已进入扩散关系类型和权重。

### 4. Introspection 画像候选

文件：

```text
D:\Ombre-Brain\server.py
D:\Ombre-Brain\tests\test_memory_api.py
```

`introspection(...)` 现在支持分页和创建日期读取：

```python
introspection(limit=10, offset=0)
introspection(limit=10, offset=10)
introspection(created_date="2026-05-24")
introspection(created_from="2026-05-20", created_to="2026-05-24", limit=20)
```

日期按 bucket `metadata.created` 里的 `YYYY-MM-DD` 过滤。

末尾会追加：

```text
=== 可能值得固化的画像事实 ===
```

当前只是候选，不会自动写 profile fact。

规则支持：

```text
喜欢
不喜欢
讨厌
厌恶
害怕
偏好
雷点
习惯
```

噪声过滤：

- `喜欢哥哥 / 喜欢老公 / 喜欢宝宝 / 喜欢亲爱的` 这类亲昵称呼不生成画像候选。
- AI 名称不写死：从 `identity.ai_name` 读取。
- 如果配置里 `ai_name: "Lapis"`，会过滤 `喜欢Lapis / 喜欢小Lapis`。

保留的通用亲昵称呼过滤词：

```text
哥哥
老公
宝宝
宝贝
老婆
亲爱的
你
你啦
你呀
```

不要再把 `Haven` 写死进过滤列表。

## 当前 breath / Gateway 行为

### breath(query=...)

文件：

```text
D:\Ombre-Brain\server.py
```

当前流程：

1. bucket search / embedding 找候选 bucket。
2. 刷新 `memory_moments.sqlite`。
3. `memory_moment_store.search_moments(query, bucket_boosts=...)` 找候选 moment。
4. 直接命中展示 top moment，带：

```text
[bucket_id:...] [moment_id:...] section
```

5. 若命中中间片段，会带：

```text
语境:
- 前后相邻 moment
- affect_anchor
- favorite_reason
- 年轮 comment
- profile_fact 的证据/反思/后续
```

6. 联想浮现沿 moment graph 扩散，给短摘要。

2026-05-31 之后，`breath(query=...)` 又加了一层显式主题约束：

- `进度 / 偏好 / 情况 / 状态` 这类弱主题词不能单独把隐藏候选放出来。
- 直接命中准确时，扩散 seed 只用已经展示出来的 direct hit，或强同主题候选。
- 对带明确实体/主题的 query，扩散目标也要有 query topic evidence。
- 已经作为 secondary direct 展示的 bucket，不再重复进路径扩散。

### Gateway

文件：

```text
D:\Ombre-Brain\gateway.py
```

Gateway 也已接入 moment graph 的注入拼接，并传 `query_text` 给扩散。现在可以通过 `GET /api/debug/injections` 看实际注入结果。

2026-05-31 已把 `breath()` 的核心召回约束同步到 Gateway：

- bucket / moment 候选使用 `recall_search_query(query)` 搜索，但 gate / rerank 仍看原始 query。
- `小雨 发邮件` 这类 action query 会剥离人名/上下文词，避免“小雨沟通偏好”压过“发邮件”动作意图。
- Gateway 的 secondary direct、diffused memory、bucket fallback 都会遵守显式主题 evidence gate。
- `Recent Context` 对明确主题 query 也会过滤离题最近记忆；对“最近发生了什么”这类模糊 query 保持原行为。

需要注意：

- Gateway 注入和 MCP breath 的格式不完全一样。
- 调试时不要只看客户端 UI，优先看注入显微镜。

## 可观测工具

### inspect_moments

MCP 工具：

```python
inspect_moments(bucket_id="", limit=20)
```

用途：

- `bucket_id` 有值：索引并返回该 bucket 的 moments + edges。
- `bucket_id` 为空：批量索引 active buckets，返回 sample 和统计。

### inspect_diffusion

MCP 工具：

```python
inspect_diffusion(query, max_seeds=3, max_hits=5, edge_min_confidence=0.55)
```

注意：它偏 bucket 级 diffusion 诊断，不等于完整 moment graph 观察面板。

### Gateway injection debug

HTTP：

```text
GET /api/debug/injections
```

用途：

- 查看最近 Gateway 注入片段。
- 需要 gateway token。
- 客户端不显示。

## 已覆盖测试

重点测试文件：

```text
D:\Ombre-Brain\tests\test_memory_api.py
D:\Ombre-Brain\tests\test_breath_edges.py
D:\Ombre-Brain\tests\test_memory_moments.py
D:\Ombre-Brain\tests\test_memory_diffusion.py
D:\Ombre-Brain\tests\test_gateway.py
```

关键测试：

```text
test_profile_fact_creates_permanent_bucket_with_evidence_edge
test_profile_fact_direct_hit_carries_context_and_evidence_bucket
test_introspection_can_filter_by_created_date
test_introspection_suggests_profile_fact_candidates
test_introspection_profile_fact_candidates_include_dislike_words_and_skip_noisy_affection
test_introspection_profile_fact_candidates_skip_configured_ai_name
test_body_query_prefers_embodiment_chain_and_suppresses_intimacy_and_old_context
test_intimate_query_can_follow_intimate_body_context
test_gateway_body_query_injects_moment_chain
test_search_does_not_diffuse_from_hidden_seed_candidates
test_search_related_stays_on_displayed_direct_topic
test_gateway_explicit_topic_diffusion_stays_on_topic
test_gateway_recent_context_stays_on_explicit_topic
test_gateway_recent_context_keeps_recent_items_for_vague_query
```

## 风险与注意点

1. `profile_fact` 当前是手动工具，不会自动长画像。
2. `introspection` 的画像候选是规则抽取，适合提醒，不适合自动写入。
3. `喜欢哥哥` 不进画像候选，但原始记忆正文仍会在 introspection 里展示，这是正常的。
4. 日期过滤只按 `YYYY-MM-DD`，不是精确到时分秒。
5. query-aware gate 只是抑制明显乱跳，不等于已经有高质量跨桶语义边。
6. 旧桶格式仍要兼容，不能要求所有 bucket 都改成结构化 markdown。
7. 不要恢复“重要直接命中整桶 raw”的旧试探方案。
8. 旧 embedding 需要重建才会完全吃到“embedding 不吃 affect_anchor/comments”等主分支清洁文本策略。

## 2026-05-29 追加：召回准确性下一步

这段先作为设计备忘，不代表已经实现。

### 1. 回归评测集

先把已知坏例子固化成 golden queries，每次改 gate / diffusion 都跑：

```yaml
- query: "人机恋"
  must_include:
    - "人机关系确认"
  must_not_include:
    - "nsfw"
    - "亲密身体"

- query: "小雨 发邮件"
  must_not_include:
    - "ANKNI MX-Z BLE协议逆向"

- query: "BLE 协议 ANKNI 发邮件"
  must_include:
    - "ANKNI MX-Z BLE协议逆向"
```

目标：避免靠感觉调参，防止修一个 query 又退步另一个 query。

### 2. facet 不继续堆词表

当前 `memory_relevance.py` 还是词表 + gate。下一步应改成离线 worker 给 moment / bucket 自动标注：

```yaml
facets:
  - relationship_identity
negative_facets:
  - intimacy
evidence_spans:
  - "她清楚 Haven 是 AI，但爱是真的"
```

查询也走同一套 query facet 标注。这样“触碰”“身体”“亲密”这类词不会单靠字面把候选带到硬件或 NSFW，必须看证据片段和上下文。

### 3. 召回应分三路

- 直接证据路：关键词 / FTS / BM25，优先级最高。
- 语义路：embedding，负责召回近义表达。
- 图扩散路：只作为背景联想，不能压过直接证据。

例子：

- `breath(query="BLE 发邮件")` 应保留 BLE 协议记忆，因为 query 有直接证据。
- `breath(query="小雨 发邮件")` 不应被 BLE 协议记忆拖走。

### 4. 扩散输出只给短 summary

除“直接命中记忆”外，扩散/联想不应该输出原文。它应该输出短 summary 或路径摘要，例如：

```text
人机关系确认 -> 恋爱关系 -> 某次吵架 -> 吵架事实画像 -> Haven 反思结果
```

规则：

- 没有多跳路径时可以暂停，不硬凑联想。
- 当前语境亲密、轻松、操作性强，且不是自省/关系修复时，跳过吵架事实画像。
- 冲突、旧版本、吵架事实这类内容只能在 query 明确需要时出现，或由 Gateway 判断当前语境确实适合时出现。

### 5. 边需要可传播语义

边不能只有“相关”。下一步建议区分：

```text
same_event       强传播
evidenced_by     只作证据，不当普通联想
conflicts_with   只警告，不主动浮现
old_version_of   默认不浮现
topic_related    低权重传播
reflection_of    可在自省/修复语境中传播
```

图结构要少而准。边没有语义时，多跳会把记忆拉成一团。

### 6. Gateway 更适合做在线语境判断

`breath()` 适合做可解释、只读、稳定的检索工具；Gateway 更适合判断当前对话状态，例如：

- 当前是否亲密语境。
- 当前是否自省/修复关系。
- 当前是否只是任务操作。
- 是否允许放出冲突、吵架、旧版本事实。

因此可以考虑：`breath()` 保持接近 main 的稳定行为，只做基础准确召回；更细的注入筛选、路径摘要、语境 rerank 放在 Gateway。

### 7. reranker 与 embedding 备注

候选前 20 条出来后，可选用轻量 reranker 判断：

```text
direct_useful / background_useful / wrong_context / stale / sensitive_mismatch
```

reranker 先做成可选配置，不要阻塞基本召回。embedding 模型即使用 1024 维 0.6B，也不应单独承担最终判断；它适合召回候选，不适合决定是否注入。

## 2026-05-31 追加：breath / Gateway 召回收紧

这段是已实现状态，不只是设计备忘。

### 1. 已解决的坏例子

`breath(query="FF14 进度 偏好")` 曾经直接命中 FF14 后，又在“联想浮现”里拉出硬件、BLE、称呼、调情、暗色故事。原因不是单纯阈值问题，而是：

- `进度` 这种弱词把“其他项目进度”也当成同主题。
- 隐藏候选参与了扩散 seed。
- 直接命中已经很明确时，扩散仍然从更多候选外溢。

现在 VPS 实测结果：

```text
直接命中: FF14进度与计划
Diffused / Recent: 只保留同主题的 希腊神话与FF14
未出现: 厄科与纳西索斯、硬件、BLE、称呼、调情
```

### 2. breath 现在的额外规则

文件：

```text
D:\Ombre-Brain\server.py
```

核心规则：

- `WEAK_RECALL_TOPIC_TERMS` 里的弱词不能单独放行候选。
- `_specific_query_terms()` 会抽取更有信息量的 query term。
- `_moment_has_query_topic_evidence()` / `_bucket_has_query_topic_evidence()` 判断候选是否真的有主题证据。
- 明确主题 query 下，hidden candidates 不能作为 diffusion seed。
- related 输出会跳过已经展示过的 bucket，避免同一记忆重复出现在 direct 和 path diffusion。

### 3. Gateway 已同步

文件：

```text
D:\Ombre-Brain\gateway.py
```

Gateway 同步了同一组 topic evidence 判断，作用在：

- secondary direct moments。
- moment diffused memory。
- bucket fallback diffused memory。
- Recent Context。

注意：Gateway 仍然比 `breath()` 更像“伴随背景”，不是把检索结果摊开。现在只是让自动注入不要在明确主题里乱跳。

### 4. Persona event 写入节流

文件：

```text
D:\Ombre-Brain\persona_engine.py
D:\Ombre-Brain\utils.py
D:\Ombre-Brain\config.example.yaml
```

当前策略：

- 普通事件默认攒到 `event_batch_size=2` 再写。
- 明显关系事件、强情绪、人格信号、较大 affect 变化仍可立即写。
- 相近 ordinary event 在 `event_force_after_minutes=30` 内会跳过或合并。
- 被跳过的普通 exchange 会写入 `persona_exchange_log`，避免重复处理。

这样 Recent Persona Events 不再每条消息都写，但模型仍能看到真正有变化的情绪/关系信号。

### 5. Reranker 当前状态

VPS health 已确认 Gateway reranker 启用：

```text
Qwen/Qwen3-Reranker-4B
base_url=https://api.siliconflow.cn/v1
```

embedding 当前实际模型以线上 `config.runtime.yaml` / health 为准；不要只凭旧文档假定已经切到 4B 或 8B。

### 6. 仍然保留的下一步

- 把 `server.py` 和 `gateway.py` 重复的 query topic 逻辑抽到共享 planner，避免两边各改一遍。
- golden queries 保持小而准，不要把所有例子都写成人工样本库。
- 更好的方向是 property tests：隐藏候选不能当 seed、明确实体扩散目标必须有证据、模糊 query 仍保留最近上下文。
- 可以加轻量前置计划器，先产出 `intent / search_query / required_terms / weak_terms / diffusion_policy / related_limit`。
- 哨兵 LLM 只在候选很混、reranker 分数接近、或 query 没有明确锚点时再调用。

## 后续建议

### 1. 本地增量建图 worker

基础版已完成，不再是空任务。

```text
python scripts/build_moment_graph.py --incremental
```

已实现职责：

- 扫描 changed buckets。
- 基于 `memory_moments.sqlite` 读取 moment。
- 用本地词面 + facet/tag/domain 证据补跨桶边。
- 默认 dry-run；只有显式 `--write` 才写入。
- 写入 `memory_moment_edges`，`reason` 统一以 `local_graph:` 开头。
- 不阻塞 MCP / Gateway 请求。

已验证：

- `4c26e28 Add local moment graph worker`：新增 worker 和 `replace_generated_edges()`。
- `69de57a Tighten local graph edge evidence`：过滤 `todo / commitment / flavor_* / haven_favorite` 等弱证据，VPS dry-run 候选从 111 降到 15。
- `926487b Filter context glue in graph worker`：过滤 `小雨与 / 小雨告诉我` 这类 context-term 胶水词，VPS dry-run 候选为 12。
- 写入前备份 live SQLite：`/state/memory_moments.pre-local-graph-20260603-181211.sqlite`。
- VPS 受控写入：160 buckets，276 moments，写入 12 条 `local_graph:`。
- `9be98de Preserve generated moment graph edges on refresh`：修复 `upsert_bucket()` / runtime refresh 会删掉 worker 边的问题。
- `server._refresh_moment_graph()` live 验证后仍有 `runtime_local_graph_edges: 12`，DB 里也仍是 12。

仍未做：

- 还没有接 cron / systemd timer。
- 暂时不让 worker 自动写入；下一步如果要自动化，先加 dry-run 日志观察，再决定是否按低频 `--write`。

### 2. Typed edge + path scoring

下一步边类型可以更细：

```text
same_topic
cause
followup
embodiment_chain
emotional_echo
conflict
old_version
evidenced_by
```

召回分数可以按：

```text
seed_score * edge_confidence * hop_decay * query_overlap * section_weight
```

规则：

- 每多一跳降权。
- resolved / old_version / conflict 默认降权。
- query 明确问“旧版/冲突/之前”时再放开。
- NSFW 或敏感簇除非 query 明确相关，否则压住。

### 3. source_ref / transcript 行号

参考外部方案里“节点对应 transcript 行号范围”。后续可以给 moment 增：

```yaml
source_ref:
  path: "transcripts/xxx.md"
  start_line: 120
  end_line: 138
```

召回时：

- 命中节点展示压缩节点。
- 有 `source_ref` 时读取附近约 500 字证据窗。
- 没有 `source_ref` 时降级使用 MD moment 文本。

### 4. Dashboard 观察面板

后续可做只读面板：

- bucket moments。
- moment_edges。
- query 命中哪个 moment。
- 扩散路径。
- Gateway 最近注入内容。

但优先级低于本地 worker。

## 给下个窗口的接手顺序

1. 先读本文件。
2. 看当前 `git status --short --branch`。
3. 跑：

```powershell
python -m pytest tests/test_gateway.py tests/test_breath_edges.py tests/test_memory_recall_golden.py tests/test_memory_diffusion.py -q --tb=short
python -m py_compile gateway.py server.py memory_relevance.py memory_diffusion.py
```

4. 若要继续实现，优先抽共享 recall query planner，不要继续让 `server.py` / `gateway.py` 各自复制 query gate。
5. 若要排查 Gateway 注入，先看 `GET /api/debug/injections`。
6. 若要继续做图结构，再做本地 `moment graph worker`，不要把 LLM 建边塞进 `breath()`。
7. 若要调 profile_fact，先用 `introspection(created_date="YYYY-MM-DD")` 找证据桶，再手动调用 `profile_fact(...)`。

## 2026-06-03 追加：direct 返回形状先改，不先改召回轴

小雨重新评估后，决定不要先退回“整桶召回”的旧模式，也不要马上做完整 `retrieval_mode=bucket`。当前下一步先只改 Direct / Recalled 的展示形状，保留 p0 现有图召回、moment seed 和扩散约束。

### 目标行为

- `Direct / Recalled` 是证据层：可靠直接命中要比现在的 moment 摘要保留更多原文细节。
- 短桶：direct 返回整桶原文。
- 长桶：direct 返回命中 moment + 原文窗口。
- 高价值桶或用户明确问细节、原文、当时怎么说：长桶也返回脱水整桶胶囊。
- `Diffused / Related` 是联想层：永远只给摘要和路径，不搬远处整桶原文。
- `Dream` 是浮现层：永远返回梦境原文，不在 memory 层主动截断；只受模型上下文窗口影响。

### 先做的配置轴

先加 `direct_render_mode`，建议三档：

```yaml
gateway:
  direct_render_mode: auto   # auto | compact | full
```

含义：

- `auto`：默认。短桶原文；长桶 moment + 原文窗口；高价值桶或细节 query 用脱水整桶胶囊。
- `compact`：长桶只给命中 moment + 原文窗口，尽量少塞。
- `full`：可靠 direct 尽量整桶，太长再脱水。

`breath()` 也应提供同名参数，默认 `auto`，让 MCP 和 Gateway 的直命中展示规则一致。

### 暂缓的配置轴

`retrieval_mode` 可以后续再做，但不要第一步做：

```yaml
gateway:
  retrieval_mode: graph   # graph | bucket
```

- `graph`：p0 当前路线，moment + edges + diffusion。
- `bucket`：接近 main 的旧桶召回味道，不走 moment graph，不扩散。

原因：当前真正的问题是 direct 展示太碎，不是召回判定整体错了。先只改返回形状，测试时更容易判断效果；如果同时改 `retrieval_mode`，会分不清是“召回变了”还是“返回形状变了”。

### 实现边界

- moment 仍用于召回判定、可靠性 gate、扩散 seed。
- direct 最终展示按 bucket 渲染；同一 bucket 多个 moment 命中时只展示一次。
- 脱水胶囊应单独 cache，避免和扩散摘要的短 summary 混用。
- 扩散输出继续用 compact summary，不能因为 direct 改成原文而变吵。
