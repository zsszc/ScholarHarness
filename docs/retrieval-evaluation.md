# Retrieval ablation report

本报告记录一次可复现的**受控离线**检索消融实验。它用于证明代码路径和回归趋势，
不是公开学术检索基准，也不能代表真实论文库、生产流量或通用语义检索质量。

## 复现

评测生成时的已提交 HEAD：`c3c622c`。实现提交后会重新生成该字段。

```bash
uv run scholar-harness retrieval-eval \
  --dataset benchmarks/retrieval-ablation-v1.json \
  --k 5 \
  --json-output docs/retrieval-evaluation.json
```

评测器使用临时 SQLite 数据库，不读取个人文献，也不需要模型或网络。数据集 SHA-256
为 `156b5c4af956c928fcdc2cd4170e3a988004ee0bea85952d58b7b9f9cb0208f2`；机器可读的
逐查询排名与延迟见 [`retrieval-evaluation.json`](retrieval-evaluation.json)。

## 数据集

- 15 个 Passage，内容覆盖 Agent Runtime、Tool Calling、Memory、RAG、Trace 与安全；
- 20 条人工标注查询，每条有明确的相关 Passage 坐标；
- 10 条 exact-token 查询和 10 条 related-word-form 查询；
- 另含缓存、网络流控和分类等干扰文档。

这个数据集刻意检验 FTS5 精确词项和 hashing 字符 n-gram 对词形变化的处理能力。
数据规模很小，而且由项目作者构造，不能用于宣称外部数据集上的泛化能力。

## 结果

环境：macOS 26.6.2 x86_64、Python 3.12.2、SQLite 3.45.2，`k=5`。

| 模式 | Recall@5 | MRR@5 | nDCG@5 | P50 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 / lexical | 50.0% | 50.0% | 50.0% | 0.255 ms | 0.762 ms |
| Hashing vector | 95.0% | 79.3% | 83.2% | 0.481 ms | 0.751 ms |
| RRF hybrid | 95.0% | 79.3% | 83.2% | 0.693 ms | 0.967 ms |

相对 BM25，Hybrid 的绝对变化为：

- Recall@5：**+45.0 个百分点**；
- MRR@5：**+29.3 个百分点**；
- nDCG@5：**+33.2 个百分点**。

分组结果揭示了提升来自哪里：三个模式在 exact-token 组均为 100%；BM25 在
related-word-form 组为 0%，Vector/Hybrid 的 Recall@5 为 90%、MRR@5 为 58.7%、
nDCG@5 为 66.5%。因此这里证明的是“加入字符 n-gram hashing 召回改善词形变化”，
不能把全部提升归因于 RRF。

## 诚实解释

本次 Hybrid 与 Vector-only 的三个质量指标完全相同，而 Hybrid 的观测延迟更高。
这说明当前受控集合没有证明 RRF 优于单独向量排序；RRF 的工程价值在于同时保留
词法与向量候选、避免直接混加不同量纲分数，并为换用更强 embedding 后的组合检索
提供稳定边界。未来应在真实论文查询上扩大标注集，再决定权重、重排器和 ANN 方案。

## 可用于简历的限定表述

> 构建包含 20 条标注查询的受控离线检索回归集，对 BM25、Hashing Vector 与 RRF
> Hybrid 进行消融；Hybrid 相比 BM25 将 Recall@5 从 50% 提升至 95%（+45.0pp），
> MRR@5 从 50% 提升至 79.3%（+29.3pp），并通过数据集哈希和逐查询排名保证结果
> 可复现。该指标是小规模工程回归证据，不代表公开论文检索基准成绩。
