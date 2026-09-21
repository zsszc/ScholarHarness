# ScholarHarness portfolio guide

## 一句话介绍

ScholarHarness 是一个 Python 文献研究 Agent harness：生产运行时可接 Pi，学习与
测试运行时使用透明的 MiniPy，两者共享工具、Memory、Trace、Evaluation 和
安全边界。项目重点不是再写一个聊天 UI，而是展示 Agent 系统如何被拆分、观测、
验证和演进。

## 三分钟验证路径

所有步骤都不需要模型 API Key：

```bash
uv sync --extra dev
uv run scholar-harness doctor
uv run scholar-harness pi-smoke
uv run scholar-harness benchmark \
  --papers 100 --passages-per-paper 4 \
  --queries 100 --trace-events 1000
uv run scholar-harness retrieval-eval \
  --dataset benchmarks/retrieval-ablation-v1.json --k 5
uv run pytest
```

然后启动本地界面：

```bash
uv run scholar-harness api
```

打开 `http://127.0.0.1:8765/workbench`，可查看文献检索、Memory 审核、Trace
时间线、Evaluation Case/Suite 和持久化 Chat。配置 `OPENAI_MODEL` 后可以运行
MiniPy Chat；Pi bridge 可以通过 `SCHOLAR_HARNESS_BRIDGE_TOKEN` 加固。

## 面试讲解主线

### 1. 为什么既使用 Pi，又实现 MiniPy？

Pi 是可复用的成熟 Agent runtime，负责真实会话、RPC 和工具调度；MiniPy 是约
400 行左右的透明 Python loop，用来学习并验证 tool calling、abort、branch、
compaction、context injection 和 session restore。二者实现同一个 `AgentRuntime`
接口，并通过持久化 trace parity 报告比较行为，而不是维护两套业务逻辑。

### 2. 系统边界如何划分？

- runtime 拥有模型循环和活跃会话；
- Python `ToolRegistry` 拥有文献、引用和 Memory 工具；
- SQLite 仓库拥有可恢复状态；
- `TracingRuntime` 负责横切观测，不侵入 runtime；
- Evaluation 只读取已落盘 trace，不再次调用模型；
- Pi TypeScript extension 只是 HTTP bridge，不包含检索或 Memory 业务规则。

### 3. Memory 为什么不能让 Agent 直接写入长期上下文？

`save_memory` 只创建 evidence-backed candidate。引用必须能在指定 passage 中逐字
验证，人工确认后才可 recall；旧记忆通过带 replacement id 的 supersession 保留
审计链。Session、entry、run 和 tool-call provenance 来自 runtime context，不接受
模型参数伪造。

### 4. 如何证明 Agent 没有悄悄退化？

每次运行产生规范化 event 和 tool execution。Evaluation Case 可以检查必需/禁止
工具、调用上限、终态、引用验证、答案片段和 Memory context；Suite 聚合多个
Case，`eval-gate` 输出 JSON/JUnit 并以退出码阻断 CI。Pi/MiniPy parity 进一步检查
生命周期和工具行为是否一致。

### 5. 哪些地方体现了生产意识？

- Trace 递归脱敏与大小限制；
- 运行时 provenance 使用 task-local `ContextVar` 隔离；
- Pi provenance bridge 支持共享密钥和常量时间校验；
- SQLite 统一 WAL、外键、busy timeout 和事务回滚；
- Browser session 原子 checkpoint、校验后延迟恢复；
- 错误使用稳定类别，配置错误与损坏数据隔离；
- SDD requirement id 与 verification evidence 同提交。

## 证据地图

| 能力 | 代码/文档证据 | 可执行证据 |
| --- | --- | --- |
| 双 runtime | `runtimes/pi_rpc.py`, `runtimes/mini_py.py` | `pi-smoke`, runtime tests |
| Tool calling | `tools/registry.py`, Pi extension | tool and MiniPy tests |
| 文献检索 | paper repository, embeddings, citation tool | throughput benchmark + labelled ablation |
| Memory trust | memory repository/context/tools | memory and context tests |
| 可观测性 | trace repository/runtime, Workbench | run APIs and trace tests |
| Evaluation | case/suite/service/reports | `eval-gate`, JSON/JUnit tests |
| Runtime parity | `traces/parity.py` | `scholar-harness parity` |
| 生产边界 | bridge auth, SQLite policy | auth/contention/live smoke |
| 开发过程 | `docs/specs/0001`–`0021` | 规格与验证记录 |

## 简历表述

中文版本：

- 独立设计并实现 Python 研究 Agent Harness，以统一 runtime contract 接入 Pi RPC
  与自研 MiniPy tool loop，支持分支、压缩、中止、会话恢复与行为 parity 验证。
- 构建 evidence-backed Memory 生命周期和文献 RAG：FTS5/离线向量混合检索、精确
  引用校验、可信 provenance、人工确认及可审计 supersession。
- 构建 20 条标注查询的受控离线检索回归集，对 BM25、Hashing Vector 和
  RRF Hybrid 做消融；Hybrid 相比 BM25 将 Recall@5 从 50% 提升至 95%
  （+45.0pp），MRR@5 从 50% 提升至 79.3%（+29.3pp）。
- 建立 runtime-neutral Trace/Evaluation/CI 体系，支持工具、终态、引用与 Memory
  context 回归检查，输出 JSON/JUnit；累计 171 项自动化测试通过。
- 加固本地生产边界：Pi bridge 共享密钥认证、Trace 脱敏、SQLite WAL/事务/锁等待、
  持久化浏览器会话和故障隔离。

English version:

- Designed and built a runtime-agnostic Python research-agent harness integrating Pi
  RPC with an inspectable MiniPy tool loop, including branching, compaction, abort,
  durable restore, and trace-based behavioral parity.
- Implemented evidence-backed memory and literature retrieval with FTS5/vector RRF,
  exact citation validation, runtime-owned provenance, human confirmation, and
  auditable supersession.
- Built a 20-query controlled offline relevance set and ablation harness; hybrid
  retrieval improved Recall@5 from 50% to 95% (+45.0pp) and MRR@5 from 50% to
  79.3% (+29.3pp) over the BM25 baseline on this regression fixture.
- Built trace-driven evaluations and CI gates for tool use, terminal status,
  citations, and memory context, with versioned JSON/JUnit evidence and 171
  passing automated tests.
- Hardened local operations with authenticated Pi provenance, recursive trace
  redaction, SQLite WAL/transactions/contention handling, and failure isolation.

## 已知限制与下一步

- 当前部署目标是可信本机单用户，不是公网多租户 SaaS；公网部署需要 TLS、用户
  鉴权、权限模型、CSRF/CORS 策略和 secret manager。
- PDF 只处理数字文本；扫描文档需要 OCR、版面分析和质量评分。
- 离线 hashing embedding 是可复现 baseline，语义质量不等同于专用 embedding；
  大规模语料还需要 ANN/vector database。
- SQLite 适合本地作品集与单机工具服务；多实例写入应迁移 PostgreSQL，并把事件
  和后台任务交给可靠队列。
- Evaluation 是确定性行为检查，不替代人工科研事实审核；模型文本仍有非确定性。
- Branch-scoped Memory 暂不自动注入，直到 branch identity 在所有 runtime 间具备
  同等持久语义。

## 深入阅读

- [Architecture](architecture.md)
- [Benchmark](benchmark.md)
- [Retrieval ablation](retrieval-evaluation.md)
- [CI workflow](ci.md)
- [Changelog](../CHANGELOG.md)
- [Release checklist](release.md)
- [SDD workflow](sdd/README.md)
- [Latest delivery specification](specs/0021-portfolio-delivery/spec.md)
