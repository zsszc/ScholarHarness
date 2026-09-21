# ScholarHarness 简历项目描述

## 完整版

### ScholarHarness —— 基于 Pi 的个人文献知识库与研究 Agent Harness

**技术栈：** Python、FastAPI、Pi SDK、TypeScript、SQLite/FTS5、WebSocket、
Pydantic、OpenAI-Compatible API、RAG、RRF、Pytest

**项目介绍：** 面向论文阅读与 Agent 工程学习的本地优先文献研究系统。
以 Pi 作为主要 Agent Runtime 接入方向，通过 JSONL RPC 和 TypeScript Bridge
将会话与 Tool Calling 接入 Python 服务；在 Runtime 外统一实现文献混合检索、
引用校验、可信 Memory、Trace 和自动化 Evaluation。额外实现轻量级 Python
Reference Runtime，用于显式学习 Agent Loop、离线测试和行为契约验证。

**个人职责：**

- 独立完成需求拆解、SDD 规格、架构设计、核心开发、评测与项目文档，
  按可验证里程碑管理 Git 提交。
- 实现 Pi JSONL RPC Client 与 TypeScript 工具桥，将 Pi 事件流和工具调用映射到
  Python ToolRegistry，并绑定可信 session、entry、run 和 tool-call 来源。
- 设计文献、Memory、Trace、Evaluation 与会话持久化等领域模块，使其与
  具体模型供应商和 Runtime 解耦。
- 建立无模型 Key 也能运行的测试、Pi Smoke、检索消融、Trace Evaluation 和
  CI 证据链，避免只以模型回答截图证明效果。

**技术亮点：**

- **Pi 与 Python 领域能力解耦：** 通过统一 Runtime/Event 契约接入 Pi RPC，
  文献、Memory、ToolRegistry、Trace 与 Evaluation 保持 Python 单一实现；MiniPy
  仅作为透明参考实现和确定性测试运行时，不宣称为第二套生产系统。
- **文献 RAG 与量化消融：** 实现 PDF 按页解析、重叠分块、FTS5/BM25、
  256 维 Hashing Vector 与 RRF 融合，并保留 paper/page/passage 引用坐标。
  构建 20 条标注查询的受控离线回归集，Hybrid 相比 BM25 将
  **Recall@5 从 50% 提升至 95%（+45.0pp）**、**MRR@5 从 50% 提升至
  79.3%（+29.3pp）**。
- **可信 Memory：** 设计 `candidate → confirmed → rejected/superseded` 生命周期，
  Agent 只能提出候选记忆；引用证据校验与人工确认后才可自动注入，
  避免模型直接写入长期可信上下文。
- **Trace / Evaluation / CI：** 统一记录模型事件、工具调用、Memory 注入、
  耗时和终态，并对敏感字段递归脱敏；实现 Case/Suite 确定性检查、
  回归对比和 JSON/JUnit 质量门禁。
- **会话与工程可靠性：** 使用 Append-only Session Tree 表示分支与活跃路径，
  支持中止、重试、压缩、恢复和原子 checkpoint；SQLite 启用 WAL、外键、
  busy timeout 和事务回滚，当前 **172 项自动化测试通过**。

## 一页简历精简版

### ScholarHarness —— 基于 Pi 的文献研究 Agent Harness

**技术栈：** Python、FastAPI、Pi SDK、TypeScript、SQLite/FTS5、WebSocket、
Pydantic、RAG、RRF、Pytest

- 通过 JSONL RPC 与 TypeScript Bridge 将 Pi 会话事件和 Tool Calling 接入 Python
  ToolRegistry，将 Runtime 与文献、Memory、Trace 和 Evaluation 领域能力解耦；
  自研 Python Reference Runtime 用于 Agent Loop 学习和确定性测试。
- 实现 PDF 分块、FTS5/BM25、Hashing Vector 和 RRF 混合检索，支持精确
  Passage 引用验证；在 20 条标注查询的受控离线消融中，将
  **Recall@5 从 50% 提升至 95%（+45.0pp）**、MRR@5 提升至 79.3%。
- 设计证据驱动的 Memory 信任链，Agent 只能生成 candidate，经 quote/passage
  校验和人工确认后才可召回；可信 provenance 由 Runtime 注入，不接受模型伪造。
- 建立脱敏 Trace、确定性 Evaluation Suite 与 JSON/JUnit CI Gate，覆盖工具、
  引用、终态与 Memory Context 回归；结合 SQLite WAL/事务、会话恢复与
  **172 项自动化测试**保证本地系统可复现性。

## 指标的安全说法

上述检索结果来自小规模受控离线回归集，不是公开论文检索基准。评测中
Hybrid 与 Vector-only 的三项质量指标相同，因此面试时应说“加入 hashing 向量
召回改善了词形变化查询”，不应说“RRF 单独带来 45pp 提升”。
