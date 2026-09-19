# ScholarHarness 中文使用指南

## 启动

```bash
uv sync --extra dev
cp .env.example .env
# 在 .env 中填入你的 API Key
uv run --env-file .env scholar-harness api
```

打开 `http://127.0.0.1:8765/workbench`。`.env` 已被 Git 忽略，不要把真实
Key 填进 `.env.example`、README、源码或提交记录。

## 推荐学习路线

1. **文献库**：先通过 OpenAPI 的 `POST /papers/import/pdf` 导入一篇可选中
   文字的 PDF，然后在页面中用混合或关键词模式检索。每个命中都保留
   paper / passage / page 坐标。
2. **Agent 对话**：新建 MiniPy Runtime 会话，让 Agent 检索文献、验证引用并
   总结。右侧会实时显示 Memory 上下文注入、Tool Calling 和 Runtime 事件。
   上方“研究会话图”可点击历史回合查看对应路径；仅点击不会改变模型上下文。
   要沿旧答案另开方向，点击“从此继续”后发送消息；要从该问题重新回答，
   点击“重试此轮”后发送消息。旧回答保留在检查区，不进入重试上下文。
3. **运行追踪**：查看每个 Run 的时间线、工具入参、返回值、耗时与错误。这是
   理解 Agent 行为和面试展示的核心页面。
4. **记忆审核**：`save_memory` 只能生成 candidate（候选记忆）。你核对证据并确认
   后，它才会成为 confirmed（可信记忆）并参与后续上下文召回。
5. **评测实验室**：用 Case 定义 Prompt 和确定性预期，例如必须使用某工具、必须
   验证引用、不得超过最大调用数。用 Suite 按顺序组合 Case，形成可重复的回归测试。

注意：当前网页会话图使用 MiniPy（教学用 Python Runtime），并非 PiX 的 Pi
原生会话、独立并行分支或多列聊天。Pi RPC 和扩展桥接是现有的另一条运行路径。

## 一个可直接尝试的 Prompt

```text
检索文献库中与 Agent Memory 有关的内容，使用原文证据总结两条结论。
引用前请调用 validate_citation 验证，并将最有价值的结论保存为候选记忆。
```

## DeepSeek 配置

ScholarHarness 走 OpenAI-compatible Chat Completions 边界。DeepSeek 的官方配置是：

```dotenv
OPENAI_MODEL=deepseek-flash
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=your-key
```

这些变量由 API 服务端读取，浏览器不会接收或保存 API Key。
