# Ombre Brain - Haven/Rain Fork

这是 [P0luz/Ombre-Brain](https://github.com/P0luz/Ombre-Brain) 的二次开发版本。原版是一套给 Claude 使用的长期情绪记忆 MCP；这个 fork 在原版的 Markdown bucket、情绪坐标、遗忘曲线、MCP 工具、Dashboard、向量检索基础上，增加了 Gateway 自动注入、Memory Moment/Edge 图召回、Word Map Lite、Persona State、Portrait/Handoff、profile_fact 事实画像、长期锚点、关系天气、年轮评论、whisper、Darkroom、跨窗口短时上下文、Night Dream / Dream Context、自动写入门卫、Supabase 同步和 ChatGPT / Claude Connector OAuth。

本 README 以本 fork 的运行方式为准。原版 Docker Hub 预构建镜像、`docker-compose.user.yml`、Render / Zeabur 快速部署方式不包含这些 fork 能力，因此这里不再保留原版快速部署教程。

## 先读这个

- 这是一个个性化 fork，不是原版 Ombre-Brain 的无改动镜像。
- 当前 `main` 是新版主线，已包含原 `feature/memory-diffusion-p0` 的 Gateway、图结构召回、画像、handoff、Darkroom 和短时上下文能力；旧主线留档在 `archive/main-before-p0-20260607`。
- 原版代码仍遵循原项目 MIT License；本 fork 新增内容允许个人学习、自用和非商业二改，商业使用需另行取得授权。详见 [`NOTICE.md`](NOTICE.md)。
- 默认人设、提示词和年轮作者使用 `config.yaml` 里的 `identity` 名字；示例默认是 `Haven`、`Rain`、`小雨/xiaoyu`。
- 生产部署建议使用源码构建，并同时运行 `ombre-brain` 和 `ombre-gateway` 两个服务；旧 `docker-compose.user.yml` / `docker-compose.yml` 只适合历史参考，不是当前新版入口。
- bucket 数据和运行状态必须放在持久化目录里；`state` 不建议放进任何双向同步目录。
- `X-Ombre-Session-Id` 是本 fork 的 Gateway 会话头，不是 OpenAI 标准字段。它像 Persona 的“房间号”：同一个值会共用同一份 persona_state 和召回冷却记录。可以自己起，比如 `my-main`、`chat-main`，不要照抄旧文档里的 `xiaoyu-main`。
- 给 Operit 或其它聊天平台写工具使用清单时，先区分 MCP 工具模式和 Gateway 自动注入模式，参考 [`docs/Tool Guide.md`](<docs/Tool Guide.md>)。记得重新复制这份 Tool Guide 到客户端；旧工具说明不会知道 `is_session_start`、`mode="handoff"`、query breath、`darkroom_enter` 和调试工具边界。

## 2026-06-07 主线提醒

这次把原 `feature/memory-diffusion-p0` 的新版能力扶正为 `main`。如果需要旧主线，请切 `archive/main-before-p0-20260607`。

- 新窗口/醒来/换窗：优先 `breath(is_session_start=true)` 或 `breath(mode="handoff")`，返回 Persona、User Portrait、Relationship Portrait、Recent Continuity 和少量 Optional Anchors；具体事件继续用 `breath(query="关键词或原句")` 查。
- `Recent Continuity` 由按真实日期维护的 handoff recent summary、关系天气和短 trace 组成，不再把初次画像初始化摘要伪装成当天日记。
- Gateway 会记录轻量 `conversation_turns`。遇到“刚刚/刚才/刚说/上一句/暗号”等短时跨窗口问题时，优先注入 Just Now Chat Context，并跳过默认记忆查询。
- Gateway 的日期问题会给小段 Date Persona Trace；如果本轮已有 Handoff Context，默认跳过泛泛的 Recent Context，避免 handoff、recent_context 和 query breath 重复塞。
- Daily Portrait Maintainer 会维护用户画像、Haven persona、关系画像和“最近在做什么”，只写 `state/portrait_state.json`，不直接写长期记忆；Dashboard 可手动生成/刷新。
- 图结构召回的当前主路是 `retrieval_mode=graph`：先找可靠 direct seed，再沿 moment / bucket 边做短摘要联想；`retrieval_mode=bucket` 只是对照模式。
- 旧桶格式已经按新版边界迁移过：事实/事件进 `### moment`，Haven 的理解进 `### assistant_reflection`，`### affect_anchor` 只留和弦、温度和诗性标记。
- Darkroom 用来放未想透、不该给用户看、不该进普通记忆的内在反思；外部工具清单只暴露 `darkroom_enter`。
- Dream surfacing 和 Gateway Dream Context 是两层开关：`surface_enabled` 控制 `breath()` 梦境浮现，`inject_enabled` 控制 Gateway 隐藏注入，默认不注入。
- 外部 MCP 工具清单已收窄：日常只保留使用者该调用的工具，`enrich_backfill`、`edge_backfill`、`inspect_diffusion`、`inspect_moments` 等调试工具只在明确修记忆系统时使用。
- embedding 推荐用 `OMBRE_EMBEDDING_*` 环境变量。不要把 `embedding.api_key_env` 当成推荐写法；`api_key_env` 是 `gateway.upstreams[*]` 引用上游模型 key 的字段。

## 二次开发能力

先分清楚：这些是原仓库已经有的基础，不算本 fork 的二次开发：

| 原版已有基础 | 说明 |
| --- | --- |
| Markdown bucket | 每条记忆是 Obsidian 友好的 Markdown + YAML frontmatter |
| Russell 情绪坐标 | `valence / arousal` 情绪打标 |
| 遗忘曲线与归档 | inactive 记忆会衰减、归档，feel 不参与普通浮现 |
| MCP 工具 | 原版已有 `breath / hold / grow / trace / pulse`；本 fork 给原 `dream` 自省入口新增名称 `introspection`，原入口仍可用 |
| Dashboard | 原版已有桶列表、详情页、记忆网络、导入面板 |
| 双通道检索 | fuzzy 关键词 + embedding 语义检索 |
| 脱水与打标 | LLM 生成压缩正文、domain/tags/情绪等元数据 |
| 历史导入 | Claude/ChatGPT/Markdown/文本导入为 bucket |

下面才是这个 fork 额外加的能力：

| 能力 | 说明 | 主要文件 |
| --- | --- | --- |
| OpenAI / Anthropic-compatible Gateway | 提供 `/v1/chat/completions`、`/v1/messages`、`/v1/models`，聊天客户端可直接接入 | `gateway.py` |
| 自动记忆注入 | 请求转发前按策略注入 Recent Context、Recalled Memory、Diffused Memory；Long-term State Summary 按间隔出现 | `gateway.py` |
| Persona State Engine | 保存 AI 回复后的全局人格、关系状态、每个 session 的短期心情 | `persona_engine.py` |
| Portrait / Handoff | 每日维护 Persona、用户画像、关系画像和近期状态；新窗口用 `is_session_start=true` 或 `mode="handoff"` 恢复身份与生活背景 | `portrait_engine.py`、`server.py`、`dashboard.html` |
| 召回冷却 | 按 `X-Ombre-Session-Id` 记录轮次和最近注入，避免同一条记忆反复贴脸 | `gateway_state.py` |
| 跨窗口短时上下文 | Gateway 记录成功聊天轮次；遇到“刚刚/刚才/上一句/暗号”等短时问题时注入 Just Now Chat Context，优先回答最近几轮而不是查长期记忆 | `gateway.py`、`gateway_state.py` |
| 多上游模型路由和备用 key | `gateway.upstreams` 可配置多个 OpenAI-compatible provider，按请求里的 `model` 路由；同一上游可配置多个 key，失败时自动尝试下一个 | `gateway.py`、`config.example.yaml` |
| 工具调用和流式兼容 | 透传 `tools / tool_choice / tool_calls`，支持 SSE 流式响应，兼容部分 reasoning_content 场景；Persona post-reply 评估会跳过带 `tool_calls` 的 assistant 中间态，只评估最终自然语言回复 | `gateway.py` |
| Memory Edge / Node | 自动生成显式记忆关系边；`memory_nodes.sqlite` 为 bucket 生成 salience 与 facets，Gateway 和 `breath()` 可沿边做多跳联想浮现 | `memory_edges.py`、`memory_nodes.py`、`memory_diffusion.py`、`reflection_engine.py` |
| Memory Moment | 将 Markdown bucket 解析成 `body / moment / original / context / feeling / followup / affect_anchor / favorite_reason / comment` 等片段，写入 `memory_moments.sqlite`，并生成同桶前后文边、年轮/情绪温度边；`breath(query=...)` 以 moment 为单位召回和扩散 | `memory_moments.py`、`server.py` |
| Word Map Lite | 从 bucket/moment 派生关键词和共现边，用于 Dashboard 诊断和未来召回提示；默认不注入 Gateway | `word_map.py`、`scripts/build_word_map.py` |
| Query Planner / Detail Recall | Gateway 可把长句或低置信问题拆成少量短查询；可选的内部 `memory_detail` 二次读取默认关闭，只允许已召回 bucket id | `gateway.py`、`server.py` |
| Profile Fact / 事实画像 | `profile_fact` 是带证据 bucket/moment 的用户画像事实；自动流程只提候选，确认后才写事实 bucket | `server.py`、`portrait_engine.py`、`dashboard.html` |
| 长期锚点 Anchor | 介于普通浮现和 pinned/permanent 之间的长期记忆位。`anchor=true` 的普通 bucket 不混入普通权重池，`breath()` 会用独立槽位少量带出，适合经过时间验证、未来仍需要被想起的关系锚点或项目锚点 | `server.py`、`dashboard.html` |
| Relationship Weather | 日印象保存为 `type=feel`，默认不单独注入，可在面板观察或按配置开启注入 | `reflection_engine.py` |
| Night Dream / Dream Context | 后台夜里用小模型生成潜伏梦；`breath()` 可共振浮现一次，Gateway 也可在 `dream.inject_enabled=true` 时注入一条 Dream Context | `dream_engine.py`、`gateway.py`、`server.py`、`dashboard.html` |
| Darkroom | 保存未想透、不该给用户看、不该进普通记忆的内在反思；默认只作为私密暗房保留，外部工具清单只开放 `darkroom_enter` | `darkroom.py`、`server.py`、`dashboard.html` |
| 年轮 comments | 将再次阅读某条记忆时的感受挂到源 bucket 的 `metadata.comments` 下；旧 feel 可迁移成源记忆年轮 | `bucket_manager.py`、`server.py`、`dashboard.html` |
| whisper | 无源碎碎念/悄悄话独立保存为 `type=feel + whisper` 标签，可用 `breath(domain="whisper")` 单独读取 | `server.py` |
| Dashboard 编辑 | 支持正文编辑、前端用户年轮写入/删除、桶列表多选删除、日印象月历、Persona 面板、网络图、手动 reflect；日印象页按日期显示完整日印象，不再做情绪天气图 | `dashboard.html`、`server.py` |
| 可选 Haven-diary/RiJi 摘记 | 完整日记留在 [Yinglianchun/RiJi](https://github.com/Yinglianchun/RiJi) 这类外部日记系统，Ombre 只提取少量长期有用记忆；不用可关闭 | `reflection_engine.py` |
| Supabase 同步 | 本地 bucket 与 Supabase memories 表同步，支持 tombstone 删除墓碑 | `scripts/sync_to_supabase.py` |
| ChatGPT / Claude Connector OAuth | 为 `/ombre/mcp` 提供 OAuth authorize/token 元数据，并允许 Claude hosted callback | `server.py` |
| 自动写入门卫 | `grow(auto=true)` 或 worker/Operit 自动总结先过 novelty / durability / repeat gate，低价值候选只记录或 pending | `memory_write_gate.py`、`server.py` |

## 系统架构

```text
聊天客户端
  -> Ombre Gateway :18002
    -> 读取 buckets / embeddings / persona_state / portrait_state / gateway_state / memory_moments / memory_edges
    -> 拼隐藏上下文
    -> 转发上游模型
    -> 回复成功后更新 Persona State 和召回记录

MCP / Dashboard / 写入 API
  -> Ombre-Brain server :18001
    -> 写 Markdown bucket
    -> 写 embeddings.db
    -> 自动 enrich 记忆与关系边
    -> 生成日印象

维护脚本
  -> Supabase memories
  -> Tombstones
  -> 旧 feel 桶清理
```

## 数据模型

bucket 是 Markdown 文件，正文保存记忆内容，frontmatter 保存元数据。当前主要类型：

| 类型 | 作用 |
| --- | --- |
| `dynamic` | 普通事件、项目状态、关系片段 |
| `permanent` | pinned / protected 长期准则 |
| `feel` | AI 主观感受、日印象、whisper |
| `archive` | 已归档旧记忆 |
| `metadata.comments` | 年轮：源记忆下的多次补充感受，不是独立 bucket |

重要运行时文件建议放在独立 state 目录：

```text
embeddings.db       # 向量语义检索
gateway_state.db    # 每个 session 的轮次、最近注入、冷却、轻量 conversation_turns
persona_state.db    # Persona 全局状态、关系状态、会话心情
portrait_state.json # 每日维护的 Persona/User/Relationship/Recent portrait
memory_edges.jsonl  # 显式记忆关系边
memory_moments.sqlite # bucket 片段索引
memory_nodes.sqlite   # salience / facets
.dashboard_auth.json
config.runtime.yaml # Dashboard 写入的运行时配置补丁
dreams/dream_*.md   # 潜伏梦正文；浮现一次后删除
dreams/logs/events.jsonl # 夜梦生成、浮现、删除事件
darkroom/           # 私密暗房笔记
```

时间默认使用 `Asia/Shanghai`。`utils.now_iso()` 会生成东八区时间。

### 当前 bucket 正文结构

新版写入和迁移后的 bucket 正文尽量拆成可索引的 section：

```md
### moment
事件事实、背景或可被召回的短片段。

### original
当时原话或证据文本。

### assistant_reflection
Haven 对这件事的理解、回应规则、喜欢原因或自我确认。

### followup
后续承诺、待办、选择或状态变化。

### affect_anchor
和弦、温度、诗性标记；不放普通事实，不放用户画像事实。
```

`metadata.comments` 是年轮评论，仍挂在源 bucket 上，不再作为独立 feel bucket 浮现。当前生产数据已经跑过旧 `affect_anchor` 结构迁移：旧桶里的事实/事件被移到 `### moment`，Haven 解释被移到 `### assistant_reflection`，`### affect_anchor` 只保留温度。其它部署迁移旧数据时仍应先 dry-run，再确认 apply，并刷新 embedding / moment index。

## 图结构记忆如何浮现

当前 main 不是把所有记忆塞进一个 prompt，也不是用一棵全局树找记忆。底层更像一张可诊断的局部图：

1. 原始长期记忆仍然是 Markdown bucket。
2. bucket 会被解析成 moment，写入 `memory_moments.sqlite`。
3. 同桶 moment 会生成 `next_context / previous_context / emotional_echo / reflects_on` 这类局部上下文边。
4. `memory_edges.jsonl` 里的显式 bucket 边会桥接到代表 moment。
5. 当前 query 先经过关键词、embedding、reranker、Query Planner 和 RecallPolicy，得到少数可靠 direct seed。
6. seed 再沿 moment/bucket 边做带权扩散，得到 `Diffused Memory`，只按摘要和路径提示注入。

这里和最初的“图结构记忆如何浮现”备忘相比，有几处已经收紧：

- `comment`、`affect_anchor`、`favorite_reason` 会进索引，但属于 context-only section；它们不能单独当 direct seed，也不能单独证明一个 bucket 与 query 相关。
- vague query 会被 `RecallPolicy.is_auto_query_too_vague()` 拦住；Gateway/Bridge 自动注入不会因为一句泛泛的“想起来了吗”硬捞语义 top1。
- `Diffused Memory` 必须从可靠 direct seed 出发；明确主题 query 还要有 topic evidence。联想结果是背景提示，不是当前事实。
- `Recent Context`、`Just Now Chat Context`、`Date Persona Trace` 和图扩散是不同层。刚刚/上一句优先走短时 `conversation_turns`，日期问题优先给小段日期 trace。
- `breath(mode="handoff")` / 新窗口 handoff 不跑动态图扩散；它读 Persona、User Portrait、Relationship Portrait、Recent Continuity、少量 anchors 和 Darkroom Door 状态。
- Word Map Lite 只是派生词图和诊断视图，默认不参与 Gateway 注入；它不是替代 `memory_edges` 的主图。
- `retrieval_mode="bucket"` 只保留旧桶召回口感作对照；当前主路是 `retrieval_mode="graph"`。

一句话：direct memory 负责“这件事确实命中了”，diffused memory 负责“有一条可靠路径可以轻轻提醒”，recent/just-now/handoff 负责“窗口和时间的连续性”。这几层不要混成一个大上下文。

## 从原版仓库来要注意

这个 fork 不是“直接换镜像就能跑”的版本。原版用户迁移时要注意：

| 项 | 为什么要改 |
| --- | --- |
| 原版 Docker Hub 镜像 | 不包含本 fork 的 Gateway、Persona、Relationship Weather、年轮、whisper 和 Supabase 脚本 |
| 原版 quick start | 只启动 MCP server，不会启动 Gateway，也不会分离 state 目录 |
| `identity` 名字配置 | `identity.ai_name / user_name / user_display_name / user_aliases` 会影响 prompt、MCP 年轮作者、Dashboard 年轮作者 |
| `gateway.default_session_id` | 只有兼容路由缺少 `X-Ombre-Session-Id` 时才使用；通用部署建议改成自己的默认房间名 |
| `persona.profile_id` | 配置示例里是 `haven_xiaoyu`，通用部署应改成自己的稳定 id |
| `X-Ombre-Session-Id` | 这是本 fork 自定义的 Gateway session，不是 OpenAI 标准头 |
| 数据目录 | `buckets` 与 `state` 都要持久化；`state` 不要放进任何双向同步目录 |
| Supabase | 不需要就先关掉；需要时先建表、RPC、cron 和 tombstone 策略 |

至少检查这些位置：

```text
identity.py             # prompt 和年轮作者的名字来源
persona_engine.py       # Persona prompt、Long-term State Summary 文案
portrait_engine.py      # Persona/User/Relationship portrait 和 handoff recent summary
reflection_engine.py    # 日印象、日记摘记、user/AI 改写规则
dream_engine.py         # 后台夜梦、潜伏存储、breath 共振浮现
darkroom.py             # 私密暗房存储与只进不出的默认边界
dehydrator.py           # 长内容摘记命名规则
server.py               # MCP / Dashboard 年轮作者
dashboard.html          # Dashboard：桶列表、年轮删除、日印象月历、梦境记录、Persona、网络、配置和导入
config.example.yaml     # identity、persona.profile_id、gateway、reflection、dream
README.md               # 示例文本
```

## 部署方式

当前推荐方式：源码构建 + Docker Compose 双服务。

### 目录建议

```text
/opt/Ombre-Brain                 # 仓库
/srv/ombre-brain/buckets         # Markdown buckets
/srv/ombre-brain/state           # sqlite/jsonl/auth 等运行状态
/srv/ombre-brain/config.yaml     # 生产配置
/opt/Ombre-Brain/.env            # 密钥环境变量，不提交
```

### 拉取代码

```bash
git clone https://github.com/Yinglianchun/Ombre-Brain.git /opt/Ombre-Brain
cd /opt/Ombre-Brain
```

### 准备目录和配置

```bash
mkdir -p /srv/ombre-brain/buckets /srv/ombre-brain/state
cp config.example.yaml /srv/ombre-brain/config.yaml
```

编辑 `/srv/ombre-brain/config.yaml`：

- `gateway.upstreams`：配置上游 OpenAI-compatible provider；同一上游多个 key 用 `api_key_envs`。
- `gateway.default_session_id`：少数兼容路由没传 `X-Ombre-Session-Id` 时的默认房间名，通用部署不要照抄旧示例名。
- `gateway.cooldown_hours`：动态记忆再次出现的冷却小时，默认 `6`。
- `gateway.skip_recent_rounds`：最近几轮里已经注入过的记忆优先避开，默认 `5`。
- `gateway.recent_context_cooldown_hours`：`Recent Context` 自动注入后的冷却小时，默认 `6`。
- `gateway.recent_context_reentry_idle_hours`：闲置多久算长时间再进入，默认 `24`；设 `0` 可关闭再进入触发。
- `gateway.recent_context_budget`：`Recent Context` 预算，默认 `300`；设 `0` 可关闭这块自动注入。
- `gateway.just_now_context_*`：控制“刚刚/刚才/上一句/暗号”这类跨窗口短时上下文，默认开启。
- `gateway.date_persona_trace_*`：控制“昨天/昨晚/前天/明确日期”这类问题的小段日期 trace，默认开启。
- `gateway.recalled_memory_budget`：`Recalled Memory` 直命中预算，默认 `400`。
- `gateway.related_memory_budget`：`Diffused Memory` 扩散背景预算，默认 `220`；设 `0` 可关闭 Gateway 扩散注入。
- `gateway.direct_render_mode` / `retrieval_mode`：控制直命中展示形状和 `graph|bucket` 召回路线；默认 `auto` + `graph`。
- `gateway.portrait_memory_*`：控制 Gateway 是否注入只读画像事实缓存，默认开启，只读取 `profile_fact` 和选中的 anchor，不读 pinned/protected。
- `gateway.query_planner_*`：长句或低置信问题可额外拆成 1-3 个短查询；只是补候选，不直接注入。
- `gateway.memory_detail_recall_*`：可选内部二次取细节，默认关闭；只允许已召回过的 bucket id。
- `recall.query_resurface_enabled`：是否允许有 query 的 `breath()` 随机追加久未碰过的旧记忆，默认 `false`。
- `memory_diffusion.*`：控制图扩散、链式扩散、hop 衰减和关系权重；默认启用普通短扩散，可靠链式扩散默认关闭。
- `word_map.*`：派生词图诊断，默认关闭，不自动注入 Gateway。
- `embedding.model/base_url`：embedding 模型和地址；key 推荐放 `.env` 的 `OMBRE_EMBEDDING_API_KEY`。
- `write_path.semantic_search_timeout_seconds`：写入时找“只读相关旧记忆”的语义检索最多等待几秒，默认 `3`。网络慢时会跳过语义部分，不影响写入成功。
- `dream.*`：夜梦后台配置；`surface_enabled` 管 `breath()` 浮现，`inject_enabled` 管 Gateway Dream Context 注入，默认不注入。
- `identity.*`：改 AI 名、前端用户作者名、prompt 里的用户称呼和亲密称呼。
- `persona.profile_id`：改成自己的稳定 id，避免和示例部署共用同一份 Persona 状态身份。
- `persona.*`：改成自己的 Persona 模型和关系默认值。
- `portrait.*`：每日维护 Persona/User/Relationship/Recent portrait；默认不开自动初次全库初始化，第一次建议在 Dashboard 手动生成。
- `reflection.timezone`：默认 `Asia/Shanghai`。
- `reflection.enrich_backfill_enabled/enrich_backfill_limit`：默认每次反思定时器顺手补少量缺失 enrich 的普通 bucket，用来恢复 tags/confidence/memory_edges。
- `reflection.diary_mcp_url` / `diary_mcp_token_env`：只有接 Haven-diary/RiJi 时再启用；不使用日记系统就留空，并关闭 `reflection.diary_memory_extract_enabled`。

### 准备 `.env`

在 `/opt/Ombre-Brain/.env` 写密钥。示例只列字段，不要照抄值：

```text
OMBRE_API_KEY=
OMBRE_EMBEDDING_API_KEY=
OMBRE_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
OMBRE_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
OMBRE_EMBEDDING_ENABLED=true

OMBRE_GATEWAY_TOKEN=

OMBRE_GATEWAY_PROVIDER_A_API_KEY=
OMBRE_GATEWAY_PROVIDER_A_API_KEY_2=
OMBRE_GATEWAY_PROVIDER_B_API_KEY=
OMBRE_PERSONA_API_KEY=
OMBRE_REFLECTION_API_KEY=
OMBRE_DREAM_API_KEY=

MCP_BEARER_TOKEN=

OMBRE_CHATGPT_OAUTH_CLIENT_ID=
OMBRE_CHATGPT_OAUTH_CLIENT_SECRET=
OMBRE_CHATGPT_OAUTH_ACCESS_TOKEN=
OMBRE_CHATGPT_OAUTH_REFRESH_TOKEN=
OMBRE_CHATGPT_OAUTH_PUBLIC_BASE_URL=
OMBRE_CHATGPT_OAUTH_REDIRECT_URIS=https://claude.ai/api/mcp/auth_callback
```

`MCP_BEARER_TOKEN` 只在接 RiJi/Haven-diary 摘记时需要；不接外部日记系统就不要配置 diary URL/token。

`OMBRE_DREAM_API_KEY` 默认按 DeepSeek 官方 OpenAI-compatible API 使用；如果换别的服务，可再加：

```text
OMBRE_DREAM_BASE_URL=
OMBRE_DREAM_MODEL=
OMBRE_DREAM_ENABLED=true
```

embedding 推荐这样配：

```yaml
embedding:
  enabled: true
  model: "Qwen/Qwen3-Embedding-0.6B"
  base_url: "https://api.siliconflow.cn/v1"
```

不要写成：

```yaml
embedding:
  api_key_env: "OMBRE_EMBEDDING_API_KEY"
```

`api_key_env` 是 `gateway.upstreams[*]` 用的字段。

### 上游模型和备用 key

`gateway.upstreams` 可以配多个站点，也可以给同一个站点配多个 key。常用字段如下：

- `name`：上游站点的内部名字，可以继续用 `provider-a` / `provider-b` / `provider-c`；不一定要和模型别名一致。
- `base_url`：模型站 OpenAI-compatible 地址，通常以 `/v1` 结尾。
- `api_key_env`：单个 key 时继续用这个。
- `api_key_envs`：多个备用 key 时用这个列表。
- `models`：客户端可选择的模型列表；字符串写法会原样转发，字典写法可设置别名。

单个站点、单个 key、模型名不会重复时，保持最简单写法就行：

```yaml
gateway:
  upstreams:
    - name: "provider-c"
      base_url: "https://c.example.com/v1"
      api_key_env: "OMBRE_GATEWAY_PROVIDER_C_API_KEY"
      models:
        - "deepseek-v4-pro"
        - "deepseek-v4-flash"
```

上面等价于把 `id` 和 `upstream_model` 写成同一个值，不需要特意改成字典。

同一个站点多个备用 key 时，把 `api_key_env` 换成 `api_key_envs`：

```yaml
gateway:
  upstreams:
    - name: "provider-a"
      base_url: "https://api.example.com/v1"
      default_model: "model-a"
      api_key_envs:
        - "OMBRE_GATEWAY_PROVIDER_A_API_KEY"
        - "OMBRE_GATEWAY_PROVIDER_A_API_KEY_2"
      models:
        - "model-a"
        - "model-a-fast"
```

如果两个站点都有同名模型，或想让客户端模型名更清楚，用 `id` 暴露不同的客户端模型名，用 `upstream_model` 写上游真实模型名：

```yaml
gateway:
  upstream_default_model: "site-a/deepseek-v4"
  upstreams:
    - name: "site-a"
      base_url: "https://a.example.com/v1"
      api_key_env: "OMBRE_GATEWAY_SITE_A_API_KEY"
      models:
        - id: "site-a/deepseek-v4"
          upstream_model: "deepseek-v4"
    - name: "site-b"
      base_url: "https://b.example.com/v1"
      api_key_env: "OMBRE_GATEWAY_SITE_B_API_KEY"
      models:
        - id: "site-b/deepseek-v4"
          upstream_model: "deepseek-v4"
```

客户端请求 `site-b/deepseek-v4` 时，Gateway 会路由到 `site-b`，再把发给上游的 `model` 改成 `deepseek-v4`。

一个站点里多个别名模型可以连续写：

```yaml
models:
  - id: "provider-a/deepseek-v4"
    upstream_model: "deepseek-v4"
  - id: "provider-a/xxxxx"
    upstream_model: "xxxxx"
```

`gateway.upstream_default_model` 可写可不写。它只在客户端请求没有传 `model` 时生效；如果客户端总会传模型名，可以不写。需要默认模型时，填客户端看到的名字，例如：

```yaml
gateway:
  upstream_default_model: "provider-a/deepseek-v4"
```

Gateway 会按请求里的 `model` 找上游。遇到 `401/403/429/500/502/503/504` 或网络错误，会临时冷却当前 key，并尝试同上游的下一个 key。`400`、模型名错误、上下文太长这类请求本身的问题不会换 key。冷却时间由 `gateway.upstream_key_cooldown_seconds` 控制，默认 300 秒。

`prompt_cache: "openai"` 和 `prompt_cache_retention: "24h"` 是 OpenAI prompt cache 提示。Gateway 会给上游请求加 `prompt_cache_key` 和 `prompt_cache_retention`，只适合确认支持这些字段的上游；不确定时保持关闭：

```yaml
prompt_cache: ""
# prompt_cache_retention: ""
```

### Compose

本仓库当前生产用 `compose.hk.yml`，它启动两个容器：

```text
ombre-brain
  command: python server.py
  ports: 18001:8000
  environment:
    OMBRE_GATEWAY_ADMIN_URL: http://ombre-gateway:8010/api/config
  volumes:
    /srv/ombre-brain/buckets:/data
    /srv/ombre-brain/state:/state
    /srv/ombre-brain/config.yaml:/app/config.yaml:ro

ombre-gateway
  command: python gateway.py
  ports: 18002:8010
  volumes 同上
```

新机器可以复制 `compose.hk.yml` 再按自己的路径、端口和镜像策略调整。

`OMBRE_GATEWAY_ADMIN_URL` 用来让 Dashboard 改“记忆浮现”里的参数后，现场通知 `ombre-gateway`。目前会热更新冷却时间/轮数、直命中展示形状、召回模式，以及 `memory_diffusion` 的扩散和链式扩散参数。不加这条也能跑；Dashboard 仍会更新 `ombre-brain` 运行时和 yaml，但 Gateway 要重启后才读到这些值。

### 配置文件和 runtime 配置

最终配置按这个顺序合并：

```text
代码默认值
-> /app/config.yaml
-> ${state_dir}/config.runtime.yaml
-> 环境变量
```

Docker/VPS 常把 `/app/config.yaml` 挂成只读：

```text
/srv/ombre-brain/config.yaml:/app/config.yaml:ro
```

Dashboard 点“应用并写入 config.yaml”时，如果写不进去，会自动写到 `${state_dir}/config.runtime.yaml`。Docker/VPS 常见路径是 `/state/config.runtime.yaml`，宿主机上通常对应 `/srv/ombre-brain/state/config.runtime.yaml`。这是正常行为。密钥继续放 `.env`，不要写进 yaml。

### 启动和更新

```bash
cd /opt/Ombre-Brain
docker compose -f compose.hk.yml up -d --build --force-recreate ombre-brain ombre-gateway
docker compose -f compose.hk.yml ps
curl -sS http://127.0.0.1:18001/health
curl -sS http://127.0.0.1:18002/health
```

后续更新：

```bash
cd /opt/Ombre-Brain
git status --short
bash scripts/one_click.sh
# 菜单：2. 更新版本 -> 选择部署环境 -> 默认备份记忆桶 -> 更新
curl -sS http://127.0.0.1:18001/health
curl -sS http://127.0.0.1:18002/health
```

熟悉 Docker 的部署也可以直接跑：

```bash
COMPOSE_FILE=compose.hk.yml bash scripts/update_deploy.sh
```

2026-06-07 之后，旧 `main` 已换到新版主线，旧版留档在 `archive/main-before-p0-20260607`。老部署目录如果还停在旧 `main`，不要手动普通 `git pull`；优先运行 `bash scripts/one_click.sh` 里的“更新版本”。脚本会先询问是否备份记忆桶，默认备份 `buckets/data`、`state`、`config.yaml` 和 `.env`；更新代码时会在 tracked 文件干净的情况下把旧 HEAD 备份成 `archive/local-main-before-reset-*`，再切到新版 `origin/main`。如果当前 checkout 本身就在 `archive/*` 分支，且没有显式设置 `OMBRE_BRANCH`，更新目标也会默认改成 `main`。`.env`、`buckets/`、`state/` 这类未跟踪/挂载文件不会因为 git reset 被删除。

如果 VPS 上有直接改过仓库里的 tracked 文件，脚本会停下。先 `git stash push -u -m pre-deploy-direct-vps-edits-$(date +%Y%m%d-%H%M%S)`，再重新运行更新脚本。

## 客户端接入

### OpenAI-compatible 客户端

```text
Base URL: http://<host>:18002/v1
API Key:  OMBRE_GATEWAY_TOKEN 的值
Header:   X-Ombre-Session-Id: my-main
```

示例：

```bash
curl http://127.0.0.1:18002/v1/chat/completions \
  -H "Authorization: Bearer $OMBRE_GATEWAY_TOKEN" \
  -H "X-Ombre-Session-Id: my-main" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.5",
    "messages": [{"role": "user", "content": "今天想起什么？"}]
  }'
```

### Anthropic-compatible 客户端

```text
Endpoint: http://<host>:18002/v1/messages
API Key:  OMBRE_GATEWAY_TOKEN 的值，可用 x-api-key
Header:   X-Ombre-Session-Id: my-main
```

即使某些兼容路径有历史 fallback，也建议总是显式传 `X-Ombre-Session-Id`。

### Favorite Memory 手动触发

默认不会每隔几轮自动注入 favorite。需要时可以：

```text
Header: X-Ombre-Include-Favorite-Memory: 1
```

或在用户消息里临时加：

```text
[[ombre:favorite]]
```

这个文本开关会在转发给上游模型前移除。

写入、enrich 或审阅时如果要使用 `haven_favorite` / `flavor_*`，正文必须包含 `### 喜欢它的原因` 或同义字段。缺少原因会被拒绝，避免模型把“偏爱”当普通高分标签乱贴。

### Gateway 注入策略

当前不是每轮把所有记忆块塞满。

```text
每个新 user turn：
1. Recent Context
2. Recalled Memory
3. Diffused Memory

第 1 / 15 / 30 ... 个新 user turn：
4. Long-term State Summary

默认不自动注入：
5. Relationship Weather
6. Core Memory
7. `<identity.ai_name> Favorite Memory`
```

工具调用续接轮不重新做动态召回，也不写 recalled ids 冷却，避免一次工具链路中途换记忆。
Persona 评估前会清理客户端自动附带的时间、时间戳、电量、battery 等状态行；这些内容只当背景，不作为 `perceived_intent` / `residue` 的重点。
`Long-term State Summary` 只是一小段自然语言，例如：

```text
Long-term State Summary
最近基调：更亲近、更安稳，偶尔有一点想念和保护欲。
使用方式：只在语气上轻轻参考，不替你做判断。不要提到你的状态。
```

这么改是为了让记忆更安静：当前问题相关的记忆每轮都给，长期状态只给自然语言摘要，不暴露数值，不替上游模型决定怎么回复。`Reply Strategy` 不再作为注入块；`Relationship Weather` 默认只作为日印象数据留在 bucket 和面板里，需要时再按配置开启。

动态记忆重复出现由两个参数控制：

```yaml
gateway:
  skip_recent_rounds: 5
  cooldown_hours: 6
```

`skip_recent_rounds` 是最近几轮避开刚注入过的 bucket；`cooldown_hours` 是冷却曲线恢复到正常分数所需的小时数。Dashboard 的“配置 -> 记忆浮现”还可以改：

- `recent_context_cooldown_hours`、`recent_context_reentry_idle_hours`、`recent_context_budget`：控制 `Recent Context` 什么时候自动出现、冷却多久、最多占多少预算。
- `recalled_memory_budget`、`related_memory_budget`：分别控制 `Recalled Memory` 直命中和 `Diffused Memory` 扩散背景的 Gateway 注入预算。
- `recall.query_resurface_enabled`：控制有 query 的 `breath()` 是否允许随机旧记忆回响；默认关掉，旧记忆抽卡更推荐直接用 `resurface()`。
- `direct_render_mode`：`auto | compact | full`，控制可靠直命中是原文、窗口还是脱水胶囊。
- `retrieval_mode`：`graph | bucket`，默认 `graph`；`bucket` 只作为接近 main 旧桶召回的对照档。
- `memory_diffusion`：图扩散开关、返回条数、最小激活、链式扩散、链路深度/置信/前沿。

如果设置了 `OMBRE_GATEWAY_ADMIN_URL`，共享召回参数保存后会同时热更新 `breath()` 和 Gateway；Recent Context 这类 Gateway 专属参数会热更新 Gateway。如果没有设置，Gateway 需要重启后才读取 yaml/runtime config。

### Night Dream

夜梦由 `ombre-brain` 后台生成，不是客户端主动调用工具。默认配置：

```yaml
dream:
  enabled: true
  auto_enabled: true
  surface_enabled: true
  inject_enabled: false
  retain_after_inject: false
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-flash"
  thinking_mode: "disabled"
  timezone: "Asia/Shanghai"
  daily_hour: 3
  daily_probability: 0.4
  min_material_count: 5
  material_window_hours: 48
  material_limit: 5
  old_echo_enabled: true
  old_echo_min_age_hours: 72
  min_surface_age_hours: 3
  spontaneous_surface_prob: 0.02
```

素材规则：

```text
普通 dynamic 记忆 + whisper
最近 material_window_hours 内，created / updated_at 取较新的时间
如果 old_echo_enabled=true，会额外混入 1 条至少 old_echo_min_age_hours 以前的普通旧记忆，不占 material_limit
不读 relationship_weather / daily_impression
不读 permanent / pinned / protected / anchor / archive
不吃 last_active，避免只是被召回过的旧记忆挤进梦里
```

梦正文写在 `${state_dir}/dreams/dream_*.md`，Docker/VPS 常见路径是 `/state/dreams/dream_*.md`。Dashboard 只显示“某天某 AI 做了一个梦”。

梦浮现还要满足这些条件：

```text
已有未浮现的潜伏梦
surface_enabled=true
已超过 min_surface_age_hours
本次 breath 有 query / 情绪坐标，或走非 handoff 的普通浮现语境
cue 或情绪分数达到阈值，或 spontaneous_surface_prob 掷中
```

无 query/domain 的 `is_session_start=True` 现在会先走 handoff，不靠夜梦恢复身份背景。`breath(query="...")` 或普通 breath 如果和梦的 cue 或情绪坐标共振，会追加：

```text
===== 梦境 =====
2026年05月25日 Haven的梦
...
```

浮现一次后，梦正文文件会删除，只留事件记录。`introspection()` 是原 `dream()` 自省入口的新名字；原 `dream()` 入口仍可用，但它不是夜梦生成入口。

Gateway Dream Context 另有一层开关：

```yaml
dream:
  inject_enabled: false
  retain_after_inject: false
```

`inject_enabled=true` 时，Gateway 可以在转发前注入一条共振梦作为 `Dream Context`。`retain_after_inject=true` 时，注入后只标记 surfaced，不删除梦记录；旧的 `breath()` 梦境浮现仍按原来的“一次后删除正文”语义运行。

### MCP / ChatGPT / Claude Connector

本 fork 的 MCP 仍由 `ombre-brain` 服务提供：

```text
Local MCP: http://<host>:18001/mcp
Dashboard: http://<host>:18001/dashboard
```

如果使用 ChatGPT / Claude 远程 Connector OAuth，需要配置：

```text
MCP server URL: https://<domain>/ombre/mcp
Authentication: OAuth
Authorization URL: https://<domain>/ombre/oauth/authorize
Token URL: https://<domain>/ombre/oauth/token
Token endpoint auth method: client_secret_post
OAuth Client ID/Secret: 使用 OMBRE_CHATGPT_OAUTH_CLIENT_ID / OMBRE_CHATGPT_OAUTH_CLIENT_SECRET
Scopes: 留空
```

Claude 网页远程 connector 的 Advanced settings 里，`OAuth Client ID` 填 `.env` 中 `OMBRE_CHATGPT_OAUTH_CLIENT_ID` 的值，`OAuth Client Secret` 填 `.env` 中 `OMBRE_CHATGPT_OAUTH_CLIENT_SECRET` 的值；不要填变量名本身。

默认允许 ChatGPT connector 回调和 Claude hosted connector 回调。Claude 网页远程 connector 的回调地址是 `https://claude.ai/api/mcp/auth_callback`；如需覆盖，设置 `OMBRE_CHATGPT_OAUTH_REDIRECT_URIS` 为逗号分隔的精确回调地址列表。

### Dashboard 登录

Dashboard 有单独的网页登录，不等同于 Gateway 的 `OMBRE_GATEWAY_TOKEN`，也不等同于 ChatGPT / Claude Connector OAuth。

```text
Dashboard: http://<host>:18001/dashboard
```

首次打开 Dashboard 时，如果没有配置 `OMBRE_DASHBOARD_PASSWORD`，页面会要求设置一个至少 6 位的访问密码。密码不会明文保存；服务端会把 salted sha256 hash 写到 state 目录：

```text
本地默认: ./state/.dashboard_auth.json
Docker/VPS 常见: /srv/ombre-brain/state/.dashboard_auth.json
```

也可以直接用环境变量固定 Dashboard 密码：

```env
OMBRE_DASHBOARD_PASSWORD=your-dashboard-password
```

配置了 `OMBRE_DASHBOARD_PASSWORD` 后，Dashboard 会跳过首次设置流程，登录时只校验这个环境变量；已有 `.dashboard_auth.json` 不再生效。

登录成功后，服务端会下发 `ombre_session` cookie，有效期 7 天。session 只保存在当前进程内存里，所以容器重启后需要重新登录。

忘记 Dashboard 密码时：

```bash
# 如果用的是 OMBRE_DASHBOARD_PASSWORD：改 .env / compose 环境变量后重启服务

# 如果用的是首次设置生成的密码：停服务后删除 auth 文件，再启动并重新设置
rm /srv/ombre-brain/state/.dashboard_auth.json
```

对外部署时建议至少保留 Dashboard 密码；公开域名访问时再配合反向代理 HTTPS / 防火墙限制。

## MCP 工具口径

给 Operit 或其它平台配置指令时，不要把 MCP 工具模式和 Gateway 自动注入模式混在一起。可直接复制的工具清单见 [`docs/Tool Guide.md`](<docs/Tool Guide.md>)。

| 工具 | 口径 |
| --- | --- |
| `breath` | 只读浮现或检索记忆；新窗口用 `is_session_start=true` 轻交接；默认不读 feel，可用 `domain="feel"`；夜梦命中共振时会追加梦境块 |
| `read_bucket` | 精确读取完整 bucket，不刷新 last_active |
| `hold` | 写单条长期记忆；`whisper=True` 写无源悄悄话；`feel=True` 是旧兼容入口 |
| `grow` | 长内容摘记；不要把整篇日记默认拆进 Ombre |
| `comment_bucket` | 年轮主入口：给旧记忆追加年轮，作者固定取 `identity.ai_name` |
| `trace` | 改 metadata、正文、resolved、delete 等 |
| `profile_fact` | 手动固化带证据的用户画像事实；需要 evidence bucket/moment |
| `pulse` | 系统状态和桶列表 |
| `introspection` | 原 `dream()` 自省入口的新名字，不替代日记，也不是梦境生成；原 `dream()` 入口仍可用 |
| `darkroom_enter` | 写入私密暗房，只返回门口状态，不回显正文；外部工具清单只暴露这个暗房入口 |
| `resurface` | 只读浮现久未触碰的旧记忆 |
| `reflect` | 生成 daily relationship_weather feel |
| `edge_backfill` | 只补旧 bucket 的 memory_edges 关系边；不改正文、tags、importance、confidence |
| `inspect_diffusion` | 只读诊断 query 如何沿 memory_edges 扩散 |
| `inspect_moments` | 只读诊断 bucket 如何被拆成 moment，并刷新 `memory_moments.sqlite` |

原 `dream()` 入口仍可用，会提示新名字并返回 `introspection()` 内容；真正的夜梦不需要客户端主动调用。

### MCP 工具参数与返回

#### `breath(...) -> str`

输入：

```text
query: str = ""                 # 空=权重池浮现；有值=关键词+向量检索
max_tokens: int = 10000
domain: str = ""                # "feel" / "whisper" 有独立只读通道；其它值作为检索 domain filter
valence: float = -1             # 0~1 时参与情绪检索/展示微调
arousal: float = -1             # 0~1 时参与情绪检索
max_results: int = 20           # 1~50
include_related: bool = True
related_per_memory: int = 1
edge_min_confidence: float = 0.55
include_core: bool = True
core_limit: int = 3
is_session_start: bool = False  # 新会话开头可传 True；无 query/domain 时直接走 handoff
mode: str = ""                  # "handoff" 显式返回轻交接画像，不跑动态召回
session_id: str = ""            # handoff 调试/调用方标识，可空
direct_render_mode: str = "auto" # auto | compact | full；直命中展示形状
retrieval_mode: str = "graph"    # graph | bucket；bucket 不走 moment graph 扩散
```

返回：纯文本。

```text
无 query：可能返回 === 核心准则 === / === 长期锚点 === / === 浮现记忆 === / === 联想浮现 ===。
  - 核心准则：pinned/protected，受 include_core/core_limit 控制。
  - 长期锚点：anchor=true 的普通 bucket，最多从独立槽位返回 2 条，不混入普通未解决池。
  - 浮现记忆：未解决、非 feel、非 permanent、非 pinned/protected/anchor，按遗忘权重；第 1 条固定最高分，其余从 top20 打散。
  - 联想浮现：从本次命中的 anchor/普通记忆沿 memory_edges 多跳扩散，扩散分数会参考 `memory_nodes.sqlite` 中的节点 salience，并用当前 query 的 facets 计算轻量共振；返回只保留短摘要和背景提醒。
  - 空 query 浮现不 touch，不刷新 last_active。
有 query：返回 === 直接命中记忆 === 和可选的 === 联想浮现 ===；直命中按 bucket 渲染，短桶返回原文，长桶返回命中片段 + 原文窗口，高价值桶或细节 query 返回脱水胶囊。默认 `retrieval_mode="graph"` 会以 moment 为单位召回和扩散，bucket 级 memory_edges 会桥接到代表 moment；`retrieval_mode="bucket"` 保留接近 main 的桶召回味道，不刷新 moment graph，不返回联想浮现。
domain="feel"：返回 === 你留下的 feel ===，按 created 倒序列出 feel。
domain="whisper"：返回 === 你留下的 whisper ===，只列 whisper 标签的 feel。
is_session_start=true 或 mode="handoff"：无 query/domain 时返回 Persona、用户画像、关系画像、近期连续性和极少量必要锚点；不跑普通动态召回、联想扩散、随机旧记忆浮现，也不刷新 last_active。具体事件仍用 `breath(query="...")` 查。
夜梦：如果本次语境、情绪坐标或有 query 的新会话语境命中潜伏梦，会追加 ===== 梦境 ===== 块。不保证梦一定浮现。
无命中：返回 “权重池平静，没有需要处理的记忆。” 或 “未找到相关记忆。”。
```

示例：

```text
breath(max_results=5, include_core=false)
breath(is_session_start=true)
breath(query="少女暴君", max_results=5, include_related=true)
breath(query="少女暴君", retrieval_mode="bucket")
breath(domain="whisper", max_tokens=1200)
```

典型返回：

```text
=== 长期锚点 ===
⚓ [长期锚点] [bucket_id:abc123] ...

=== 直接命中记忆 ===
[bucket_id:def456] ...

=== 联想浮现 ===
- [bucket_id:xyz789] 一句短摘要。（背景联想，不代表当前事实。）
```

当前缺陷：

```text
1. `retrieval_mode="bucket"` 只作为可选对照模式；默认 graph 模式是当前 `main` 的 moment 扩散链。
2. 有 query 的 breath 默认不会随机带出 “--- 久未碰过 ---”。如果想恢复旧的随机回响，显式设置 `recall.query_resurface_enabled=true`，或者直接调用 `resurface()`。
3. 联想浮现来自 moment_edges 与 memory_edges 的桥接边；embedding 相似边主要用于候选检索，不等于手写关系。当前 moment_edges 是 deterministic 前后文/温度边，LLM/embedding 增量建边留给后续 CLI worker。
```

#### `inspect_diffusion(...) -> dict`

只读诊断某个 query 为什么点亮这些联想记忆。不创建 bucket，不 touch 记忆；会像 `breath(query=...)` 一样刷新 `memory_nodes.sqlite` 里的节点索引，方便查看当前 salience / facets。

输入：

```text
query: str
max_seeds: int = 3
max_hits: int = 5
edge_min_confidence: float = 0.55
```

返回：

```json
{
  "query_facets": {"affect": {}, "relation": {}, "scene": {}, "topic": {}},
  "seeds": [
    {"bucket_id": "...", "seed_score": 1.0, "salience": 1.08, "resonance": 1.0}
  ],
  "hits": [
    {
      "bucket_id": "...",
      "score": 0.42,
      "salience": 1.05,
      "resonance": 1.12,
      "path": "seed --supports:0.90--> target",
      "paths": []
    }
  ]
}
```

#### `inspect_moments(...) -> dict`

只读诊断 bucket 如何被解析成片段。不修改 bucket，不 touch 记忆；只刷新 `${state_dir}/memory_moments.sqlite`。

输入：

```text
bucket_id: str = ""   # 有值=只索引并返回这个 bucket；空=索引所有 active bucket 并返回 sample
limit: int = 20
```

结构化正文可写成：

```md
## moment
一句可扩散的短事实。

## original
当时的对话原文或关键原句。

## context
开头背景、命中词附近语境、结尾结果等。

## feeling
当时感受。

## assistant_reflection
Haven 的理解、确认、喜欢原因、以后怎么回应。

## followup
后续选择、承诺、待办。

### affect_anchor
> 和弦 -> 情绪移动

### 喜欢它的原因
为什么这条是 favorite。
```

旧格式正文没有这些标题时，会整体索引为 `body`；如果正文已有 `### moment / ### assistant_reflection / ### affect_anchor / ### 喜欢它的原因`，会单独拆成对应 moment。新写入路径会先做轻量标准化：无标题正文后面接 `### reflection` / `### affect_anchor`、且还没有 `### moment` 时，开头正文会包成 `### moment`；旧桶迁移 dry-run 仍默认跳过纯正文老桶。`assistant_reflection` 会作为 reflection/context moment，不应直接当作用户画像事实；`affect_anchor` 只承载和弦、温度、诗性标记，不承载事实。`metadata.comments` 会索引为 `comment`，保留年轮作者、kind、valence/arousal 等元信息。`haven_favorite / flavor_* / anchor / pinned` 等仍作为 bucket 级温度标记写进 moment metadata，不会降级成普通文本。

索引同时生成 deterministic moment edges：

```text
ordinal n -> n+1              next_context       0.85
ordinal n+1 -> n              previous_context   0.75
comment/affect/favorite -> 主片段 emotional_echo    0.90
```

后续本地 CLI/worker 可以在这个基础上用 LLM、embedding、BM25 增量补跨桶 moment 边；MCP 查询路径只读图。

#### `resurface(...) -> str`

输入：

```text
max_results: int = 1
include_archive: bool = True
max_tokens: int = 800
```

返回：纯文本 `=== 久未触碰的旧记忆 ===`，包含 bucket id、标题、状态和正文片段。只读，不 touch，不刷新 `last_active`。

#### `read_bucket(bucket_id) -> dict`

输入：

```text
bucket_id: str
```

返回：

```json
{
  "id": "bucket id",
  "metadata": {"name": "...", "tags": [], "comments": []},
  "content": "去掉 wikilink 后的正文",
  "score": 12.34
}
```

错误时返回 `{"error": "invalid bucket_id"}` 或 `{"error": "not found", "id": "..."}`。读取不 touch。

#### `comment_bucket(...) -> dict`

输入：

```text
bucket_id: str
content: str
kind: str = "comment"
valence: float = -1
arousal: float = -1
```

返回：

```json
{
  "status": "commented",
  "id": "源 bucket id",
  "comment": {"id": "comment id", "author": "<identity.ai_name>", "content": "..."},
  "embedding_refreshed": false,
  "embedding_queued": true,
  "metadata": {}
}
```

用途：给已有 bucket 追加年轮。MCP 调用不需要传作者，作者固定取 `identity.ai_name`。它会 `touch+1` 源 bucket，后台刷新源 bucket embedding，不改正文，不把源 bucket 标为 `digested`。`embedding_refreshed` 保留给旧客户端兼容；新逻辑看 `embedding_queued`。

这是现在推荐的年轮入口。新调用不要用 `hold(feel=True, source_bucket=...)` 写年轮；那只是旧兼容入口。

#### `hold(...) -> str`

输入：

```text
content: str
tags: str = ""                  # 逗号分隔，替换给自动 tags 合并
importance: int = 5             # 1~10
pinned: bool = False
feel: bool = False
whisper: bool = False
source_bucket: str = ""
valence: float = -1
arousal: float = -1
```

返回：纯文本状态。

```text
普通记忆：新建→<name> <domain>，并可能附带一条只读相关旧记忆。
pinned=True：📌钉选→<bucket_id> <domain>。
favorite：tags 里出现 haven_favorite 或 flavor_* 时，content 必须写明 “### 喜欢它的原因”，否则返回错误。
年轮：用 comment_bucket(bucket_id, content)，不要用 hold 写。
feel=True + source_bucket：仅旧兼容，会返回 年轮→<source_bucket>#<comment_id>；新调用不要使用。
feel=True 但无 source_bucket：兼容旧用法，转为 whisper；新调用请直接用 whisper=True。
whisper=True：🫧whisper→<bucket_id>。
错误：内容为空 / source_bucket 无效 / 源记忆不存在 / 年轮写入失败。
```

#### `grow(content) -> str`

输入：

```text
content: str
```

返回：纯文本状态。

```text
短内容（<30 字）：走 hold-like 快速路径，返回 “新建/合并 → <name> | <domain> Vx/Ay”。
长内容：由 LLM digest 成多条候选，返回 “N条|新X合Y” 加每条标题。
失败：返回 “长内容摘记失败: ...” 或 “内容为空或整理失败。”。
```

用途：只给已经筛过、包含多个长期记忆点的片段。一天结束或用户发来长日记/总结时，可以把值得长期记住的事件、偏好、承诺或项目状态摘出来交给 `grow`；整篇日记、一天流水、完整情绪过程不要原样 `grow`。

#### `trace(...) -> str`

输入：

```text
bucket_id: str
name: str = ""
domain: str = ""                # 逗号分隔；替换，不是追加
valence: float = -1
arousal: float = -1
importance: int = -1
tags: str = ""                  # 逗号分隔；替换，不是追加
resolved: int = -1              # 0/1
pinned: int = -1                # 0/1
anchor: int = -1                # 0/1
digested: int = -1              # 0/1
content: str = ""               # 替换完整正文
delete: bool = False            # 删除整个 bucket，写 tombstone
```

返回：纯文本状态，例如 `已修改记忆桶 <id>: tags=[...]`、`已遗忘记忆桶: <id>`、`未找到记忆桶: <id>`。
改正文前先 `read_bucket()`，因为 `content` 是完整替换。

`anchor=1` 受 `anchor.max_count` 和 `anchor.min_age_hours` 限制；默认最多 12 条，且 bucket 至少存在 24 小时后才能标记。

#### `pulse(include_archive=False) -> str`

输入：

```text
include_archive: bool = False
```

返回：纯文本系统状态和桶列表，包含 bucket id、主题、情绪、重要度、权重、标签。`include_archive=True` 才列归档桶。

#### `introspection() -> str`

输入：无。

返回：纯文本 `=== Introspection ===`，列出最近普通记忆，供 AI 清醒自省。
读后如果真的有沉淀，再用 `trace(resolved=1/digested=1)` 或 `comment_bucket(...)` 写年轮；不要把 introspection 输出原样写回。

#### `reflect(period="daily", force=False) -> dict`

输入：

```text
period: str = "daily"           # 目前推荐只用 "daily"
force: bool = False             # True 时重写同周期结果
```

返回：

```json
{
  "status": "created|updated|exists|empty|skipped|disabled",
  "period": "daily",
  "id": "reflection_daily_2026-05-23",
  "date": "2026-05-23",
  "diary": {"found": true, "diary_id": 37},
  "diary_memory": {"status": "created|skipped|not_applicable"},
  "materials": {"buckets": 3, "daily_impressions": 0, "persona_events": 5, "commitments": 1}
}
```

旧的 `period="weekly"` 路径默认返回 skipped，不作为常规能力使用。

## 年轮、whisper 与 Relationship Weather

- 年轮：再次读到旧记忆时留下的感受，挂到源 bucket 的 `metadata.comments`，不再作为单独 bucket 浮现。
- 旧 feel 迁移：已经能把一部分旧独立 feel 接到关联源记忆下面，并保留 `original_feel_id / original_feel_created`。
- 旧 feel 清理：确认已迁移后，用 `scripts/cleanup_migrated_feel_buckets.py` 清理旧独立 feel 桶，不删除源 bucket 下的 comments。
- whisper：无源碎碎念/悄悄话，不适合挂到某条源记忆时，用 `hold(whisper=True)` 独立保存；用 `breath(domain="whisper")` 单独读取。
- 日印象：`type=feel`，tags 包含 `relationship_weather` / `daily_impression`。
- Dashboard 的“日印象”页提供月历和单卡片详情：左侧按日期选 daily impression，右侧显示该日完整日印象；点小铅笔进入原 bucket 详情面板手动编辑。
- 不生成周印象；需要周视角时，优先做只读聚合视图，不把日印象压缩成周记。
- 日记原文留在外部日记系统，例如 [Yinglianchun/RiJi](https://github.com/Yinglianchun/RiJi)；不用日记系统时可以关闭 diary 摘记，Ombre 只在有长期价值时提取少量普通记忆。
- 日印象和重要高温记忆可带 `### affect_anchor`，但它只承载和弦、温度和诗性标记，不承载事实。
- 用户画像事实不要写进 `affect_anchor`，也不要从 `assistant_reflection` 直接推断；需要证据时用 `profile_fact(...)` 或 Dashboard 的 Profile Facts 确认流程。

## Supabase 同步

同步脚本默认 dry-run：

```bash
python scripts/sync_to_supabase.py
```

写入前先确认 Supabase 表结构和环境变量。删除使用 tombstone：

```text
buckets/.tombstones/<bucket_id>.json
source=deleted
```

当前同步字段包含 `confidence / period / date / comments / comment_count`。首次启用或升级旧表时，先在 Supabase SQL Editor 执行：

```sql
-- scripts/supabase_memory_rpc.sql
```

脚本会补齐字段并重建 `create_memory(...)` RPC。`comments` 用 `jsonb` 保存年轮数组，`comment_count` 方便列表页或外部客户端直接展示数量。

## 维护命令

这些脚本默认在仓库根目录运行。VPS/Linux 直接用 `bash`；Windows 本地测试可用 Git Bash。常用环境变量：

- `COMPOSE_FILE`：指定 compose 文件。`one_click.sh` 首次部署会生成 `compose.local.yml`；VPS 旧部署常用 `compose.hk.yml`。不填时会按 `compose.local.yml` → `compose.hk.yml` → `docker-compose.user.yml` → `docker-compose.yml` 自动找。后两个是旧形态 compose，不含新版 Gateway/state 完整能力；当前部署请优先显式设 `COMPOSE_FILE=compose.hk.yml` 或走 one-click 生成的 `compose.local.yml`。
- `OMBRE_SERVICE`：容器服务名，默认 `ombre-brain`。
- `GATEWAY_SERVICE`：Gateway 容器服务名，默认 `ombre-gateway`。
- `BATCH_SIZE`：embedding 每批处理数量，默认 `20`。
- `HEALTH_URL`：健康检查地址，不填时 `compose.hk.yml` 默认查 `http://127.0.0.1:18001/health`，用户版 compose 默认查 `http://127.0.0.1:8000/health`。
- `LOG_TAIL`：`doctor.sh` 查看最近日志的行数，默认 `160`。
- `YES=1`：跳过重建 embedding 的确认提示；清理孤儿 embedding 仍建议手动确认。

```bash
# 一键菜单：首次部署、更新、排障、备份、删除旧备份包、记忆桶格式转换、向量库、原版迁移
bash scripts/one_click.sh

# 同上，短入口
./ob

# 一键排障：检查 key、服务、端口、健康接口和最近错误日志
COMPOSE_FILE=compose.hk.yml bash scripts/doctor.sh

# 一键更新：拉代码、重建/更新容器、健康检查
COMPOSE_FILE=compose.hk.yml bash scripts/update_deploy.sh

# 服务状态
docker compose -f compose.hk.yml ps
docker compose -f compose.hk.yml logs --tail=120 ombre-brain
docker compose -f compose.hk.yml logs --tail=120 ombre-gateway

# 健康检查
curl -sS http://127.0.0.1:18001/health
curl -sS http://127.0.0.1:18002/health

# embedding 回填
docker compose -f compose.hk.yml exec -T ombre-brain python backfill_embeddings.py --batch-size 20

# 一键补缺失 embedding
COMPOSE_FILE=compose.hk.yml bash scripts/embedding_backfill.sh

# 一键重建所有 embedding（会消耗较多 embedding API 次数）
COMPOSE_FILE=compose.hk.yml bash scripts/embedding_rebuild.sh

# 一键检查孤儿 embedding，确认后清理
COMPOSE_FILE=compose.hk.yml bash scripts/embedding_cleanup_orphans.sh

# 导入重复桶清理/去重
# 不要直接删除全部 buckets；优先在 Dashboard -> 导入 -> 导入结果里删除/标为噪声。
# 如果必须批量手动删除 bucket 文件，先备份 buckets/state。
docker compose -f compose.hk.yml exec -T ombre-brain sh -lc 'mkdir -p /state/backups && tar -czf "/state/backups/before-import-dedupe-$(date +%Y%m%d_%H%M%S).tar.gz" /data /state'
# 扫描重复桶；会打印前两句话和相似度，默认不会自动删近似重复。
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/cleanup_duplicate_buckets.py
# 人工逐组确认：exact duplicate 可按组删；相似度 >=80% 的疑似重复按 y/1/2 选择。
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/cleanup_duplicate_buckets.py --interactive --near-threshold 80
# 一键删除只处理 exact duplicate 中安全的一份，并清对应 embedding。
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/cleanup_duplicate_buckets.py --delete --yes
# 如果你已经手动删除过 bucket 文件，再清没有对应 bucket 文件的 orphan embeddings。
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/cleanup_orphan_embeddings.py --delete --yes
# Python 直跑同理：
python scripts/cleanup_duplicate_buckets.py
python scripts/cleanup_duplicate_buckets.py --interactive --near-threshold 80
python scripts/cleanup_duplicate_buckets.py --delete --yes
python scripts/cleanup_orphan_embeddings.py --delete --yes

# Dashboard 桶列表也支持“批量选择 -> 全选当前筛选 -> 删除选中”。
# 它只删除普通 bucket，会跳过 protected / pinned / anchor / permanent，
# 并写 tombstone、清 embedding / moment / node / edge 索引；删除前需要输入 DELETE。

# enrich 补跑
# 正常情况下 reflection scheduler 会自动少量补跑；需要手动修复时可从 MCP 客户端调用 enrich_backfill(limit=20)。
# 只补关系边、不改 bucket metadata/正文时，用 edge_backfill(limit=10, bucket_id="", query="", dry_run=false)。

# 旧 bucket 正文结构迁移：把旧 affect_anchor 里的事实/反思移到 moment / assistant_reflection。
# 推荐走 ./ob -> 记忆桶格式转换。它会先 dry-run 输出审阅文件，apply 前强制备份。
# 当前生产数据已跑过这类迁移。
mkdir -p tmp
python scripts/migrate_affect_anchor_sections.py --scope all --include-archive --output tmp/affect_anchor_plan.json --output-md tmp/affect_anchor_plan.md
python scripts/migrate_affect_anchor_sections.py --from-plan tmp/affect_anchor_plan.json --apply --yes

# 旧 feel -> 年轮迁移，建议优先走 one_click.sh 的“从原版 Ombre-Brain 迁移”
docker compose -f compose.hk.yml exec -T ombre-brain sh -lc 'PYTHONIOENCODING=utf-8 python scripts/plan_feel_comment_backfill.py --mapping-template /state/feel_comment_backfill_mapping.json --review-markdown /state/feel_comment_backfill_review.md > /state/feel_comment_backfill_plan.json'
docker compose -f compose.hk.yml exec -T ombre-brain sh -lc 'PYTHONIOENCODING=utf-8 python scripts/review_feel_comment_backfill.py --plan /state/feel_comment_backfill_plan.json --mapping /state/feel_comment_backfill_mapping.json'
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/apply_feel_comment_backfill.py --mapping /state/feel_comment_backfill_mapping.json
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/apply_feel_comment_backfill.py --mapping /state/feel_comment_backfill_mapping.json --apply --archive-feel --refresh-embeddings
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/cleanup_migrated_feel_buckets.py
docker compose -f compose.hk.yml exec -T ombre-brain python scripts/cleanup_migrated_feel_buckets.py --apply
```

脚本用途：

- `scripts/one_click.sh`：新手入口。菜单包含首次部署、更新版本、错误排查、备份当前部署、删除旧备份包、记忆桶格式转换、向量库相关、从原版 Ombre-Brain 迁移。首次部署会先选择 `VPS / Windows / Python 直跑`，再选择 `只用 Ombre MCP 部分 / 部署全部`。只用 MCP 时只启动 MCP 工具和 Dashboard，不配置、不启动 Gateway；部署全部时才会继续填写 Gateway 上游、token 和 OpenAI-compatible 客户端地址。VPS 和 Windows 走 Docker 并生成本机专用的 `compose.local.yml`；Python 直跑适合手机 Termux、Linux、Windows 无 Docker，会生成 `start_local.sh` 和 `start_local.ps1`，同时保留 `start_mobile.sh` 兼容旧教程。模型配置和 key 会交互式填写，key 写入 `.env`，非密钥配置写入 `config.yaml`；生成的 config 已包含当前 main 的 memory diffusion、query planner、portrait、dream inject 默认值和自动写入门卫。最后生成 `connection_guide.txt`，除了 URL / token / header，也会写 handoff、Just Now、Darkroom、Dream Context 和 Dashboard 批量删除提示。
- `./ob`：短入口，等同于 `bash scripts/one_click.sh`。也可以在菜单里选“安装短命令 ob”，写入当前用户的 shell 配置；之后任意位置输入 `ob` 就能打开菜单。
- Windows 上运行 `.sh` 脚本建议打开 Git Bash 再执行；不要在 PowerShell 里直接输 `bash ...`，否则少数机器可能会调用到 WSL 的 `bash.exe`。
- `scripts/doctor.sh`：适合“更新后不能用、端口不通、怀疑 key 没配好”。它只读检查，不会重启服务、不改配置、不打印 key。会提示 `.env/config.yaml`、Docker Compose 状态、健康接口、容器内环境变量和最近错误日志；如果 compose 里没有启用 Gateway，会自动跳过 Gateway token 检查。
- `scripts/update_deploy.sh`：适合“我只想更新到最新版”。它会从当前分支或 `OMBRE_BRANCH` 指定分支拉取代码；能 fast-forward 就直接前进，遇到 2026-06-07 主线换轨这类分叉时，会在 tracked 文件干净的部署目录里先建本地备份分支再 reset 到新版远端。之后如果 compose 里是 `build:` 就重建镜像，否则先 pull 镜像，再启动容器；最后检查 Ombre-Brain 健康，如果 compose 里有 `ombre-gateway`，也会检查 Gateway 健康。
- 备份和清理旧备份：`one_click.sh` 的“备份当前部署”会打包 `buckets/data`、`state`、`config.yaml`、`.env`；“删除旧备份包”只列出并删除 `state/backups` 或容器 `/state/backups` 里的 `.tar.gz/.tgz/.zip`，需要输入序号和 `DELETE`。
- 记忆桶格式转换：`one_click.sh` 的“记忆桶格式转换”会先生成 `affect_anchor_plan.json` 和 Markdown 审阅文件，把旧 `affect_anchor` 里混入的事实/反思迁到 `moment` / `assistant_reflection`；应用前会强制备份当前部署。
- `scripts/embedding_backfill.sh`：只补缺失的 embedding，适合升级后发现部分记忆没有语义召回。
- `scripts/embedding_rebuild.sh`：重建全部 embedding，适合 embedding 模型、base_url 或 embedding 文本格式改过之后使用。它会消耗更多 API 次数。
- `scripts/embedding_cleanup_orphans.sh`：检查 `embeddings.db` 里已经没有对应 bucket 文件的记录，并要求输入确认后删除；确认已备份且要非交互执行时可追加 `--yes`。
- Python 直跑用户可以从 `scripts/one_click.sh` 的“向量库相关”菜单执行补向量、重建向量、清孤儿向量和导入重复桶清理，不需要 Docker Compose。
- 导入重复桶清理：不要直接删全部桶。优先在 Dashboard 的“导入 -> 导入结果”里删除/标为噪声；需要批量处理时先备份 `buckets/state`，再用 `scripts/cleanup_duplicate_buckets.py` 扫描。扫描结果会打印重复桶前两句话和相似度；`--interactive --near-threshold 80` 会逐组确认，疑似重复按 `y` 删除建议项、按 `1/2` 删除左/右；`--delete --yes` 只会一键删除 exact duplicate 中安全的一份并清对应 embedding。
- Dashboard 桶列表多选删除：适合按筛选结果批量删普通动态桶。入口是“批量选择 -> 全选当前筛选 -> 删除选中”，会要求输入 `DELETE`，后端会写 tombstone 并清理 embedding、moment、node、edge 索引；受保护、钉选、长期锚点和 permanent bucket 会被跳过。
- 原版迁移菜单：先检查旧部署、备份 buckets/state，再生成旧 `feel` 审阅表和 mapping。如果二改版目录和原版目录不同，可以选“备份指定原版目录”，手动填写原版仓库路径，脚本会只打包其中的 `buckets/`、`state/`、`config.yaml`、`.env`。可以逐条输入 `y` 接受候选源记忆，输入 `n` 自己填源记忆 bucket id，或输入 `w` 保留为 whisper/无源 feel。旧 `feel` 写入年轮前必须预演 mapping；清理旧独立 `feel` 前也会要求先看 dry-run。

`doctor.sh` 常见结论：

- `OMBRE_API_KEY 未配置`：导入抽取/脱水模型大概率不能调用。把 key 写进 `.env` 后重新 `docker compose up -d`。
- `OMBRE_EMBEDDING_API_KEY 未配置`：embedding 可能回退到脱水 key；如果你的 embedding 服务和脱水服务不是同一个站点，请单独配置。
- `服务没有运行`：先执行 `COMPOSE_FILE=compose.hk.yml bash scripts/update_deploy.sh`。
- `默认健康地址不通，但其它端口通`：客户端或反代地址可能写错，按脚本提示的可用端口改配置。
- `401/403`：通常是 key 或鉴权 token 错；`429` 是额度/频率限制；`connection refused/timeout` 多半是上游地址或网络问题。

`one_click.sh` 的 Gateway 上游配置支持：

- 单上游或多上游 provider。
- 每个 provider 可选单 key 或多 key，多 key 会写成 `api_key_envs`。
- 如果多个 provider 暴露了同名模型，脚本会自动把 Gateway 里显示的模型名改成 `provider/模型名`，同时保留 `upstream_model` 指向真实模型名，避免路由撞名。

`one_click.sh` 的客户端提示会按部署环境和功能范围给 URL：

- 只用 MCP：客户端只填 MCP 工具 URL，例如 `http://你的公网IP或域名:18001/mcp`；Dashboard 是 `http://你的公网IP或域名:18001/dashboard`。不会输出 Gateway Base URL。
- 部署全部：除了 MCP URL，还会输出 Gateway Base URL，例如 VPS 默认是 `http://你的公网IP或域名:18002/v1`。
- Windows：客户端在同一台电脑就填 `127.0.0.1`；手机连 Windows 时填 Windows 的局域网 IP，并允许防火墙通过脚本提示的端口。
- Python 直跑：同一台机器/手机填 `127.0.0.1`；其它设备连接时填运行 Ombre 的机器局域网 IP。Linux、Termux、Git Bash 用 `./start_local.sh`，Windows PowerShell 用 `powershell -ExecutionPolicy Bypass -File .\start_local.ps1`。

## 本地开发与测试

```powershell
C:\Python313\python.exe -m pytest -q
C:\Python313\python.exe -m py_compile gateway.py server.py reflection_engine.py
```

常用针对性测试：

```powershell
C:\Python313\python.exe -m pytest tests\test_gateway.py tests\test_memory_api.py tests\test_reflection_edges.py -q
```

## 还没完成的方向

- 完整 entity / 知识图谱。
- Memory Edge 同步到 Supabase：暂时不做；Supabase 目前只作为备用同步层。
- 召回候选过滤模型：如果 Query Planner / Word Map Lite 诊断显示短 query 补搜仍有噪音，再加严格 JSON 的 keep/drop 候选筛选。
- 通用化部署文案继续减少个性化示例；运行时 prompt 已优先读 `identity`。

## License

沿用仓库中的 `LICENSE`。
