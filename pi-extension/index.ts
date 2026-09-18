import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI, type ExtensionContext } from "@earendil-works/pi-coding-agent";

const baseUrl = process.env.SCHOLAR_HARNESS_URL ?? "http://127.0.0.1:8765";

async function callPythonTool(name: string, input: unknown, provenance: Record<string, string> = {}): Promise<unknown> {
  const response = await fetch(`${baseUrl}/internal/tools/${name}`, {
    method: "POST",
    headers: { "content-type": "application/json", ...provenance },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`ScholarHarness tool ${name} failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

function executionHeaders(toolCallId: string, ctx: ExtensionContext): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Scholar-Runtime-Type": "pi",
    "X-Scholar-Session-Id": ctx.sessionManager.getSessionId(),
    "X-Scholar-Tool-Call-Id": toolCallId,
  };
  const leafId = ctx.sessionManager.getLeafId();
  if (leafId) headers["X-Scholar-Entry-Id"] = leafId;
  return headers;
}

export default function scholarHarnessBridge(pi: ExtensionAPI) {
  pi.registerTool(defineTool({
    name: "search_papers",
    label: "Search Papers",
    description: "Search the user's paper collection and return citable passages.",
    parameters: Type.Object({
      query: Type.String({ minLength: 1 }),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 50, default: 5 })),
      mode: Type.Optional(Type.Union([
        Type.Literal("lexical"),
        Type.Literal("hybrid"),
      ], { default: "hybrid" })),
    }),
    async execute(_toolCallId, params) {
      const result = await callPythonTool("search_papers", params);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details: result,
      };
    },
  }));

  pi.registerTool(defineTool({
    name: "validate_citation",
    label: "Validate Citation",
    description: "Verify that a direct quote occurs at an exact paper coordinate.",
    parameters: Type.Object({
      paper_id: Type.String(),
      passage_id: Type.String(),
      quote: Type.String(),
    }),
    async execute(_toolCallId, params) {
      const result = await callPythonTool("validate_citation", params);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details: result,
      };
    },
  }));

  pi.registerTool(defineTool({
    name: "read_passage",
    label: "Read Passage",
    description: "Read one exact passage by paper and passage id.",
    parameters: Type.Object({
      paper_id: Type.String(),
      passage_id: Type.String(),
    }),
    async execute(_toolCallId, params) {
      const result = await callPythonTool("read_passage", params);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details: result,
      };
    },
  }));

  pi.registerTool(defineTool({
    name: "save_memory",
    label: "Save Memory Candidate",
    description: "Save an evidence-backed memory candidate for later human confirmation.",
    parameters: Type.Object({
      content: Type.String({ minLength: 1, maxLength: 8000 }),
      kind: Type.Optional(Type.Union([
        Type.Literal("semantic"),
        Type.Literal("episodic"),
        Type.Literal("procedural"),
      ], { default: "semantic" })),
      scope: Type.Optional(Type.Union([
        Type.Literal("global"),
        Type.Literal("session"),
        Type.Literal("branch"),
      ], { default: "global" })),
      confidence: Type.Optional(Type.Number({ minimum: 0, maximum: 1, default: 0.5 })),
      evidence: Type.Array(Type.Object({
        paper_id: Type.String({ minLength: 1 }),
        passage_id: Type.String({ minLength: 1 }),
        quote: Type.String({ minLength: 1 }),
      }), { minItems: 1, maxItems: 20 }),
    }),
    async execute(toolCallId, params, _signal, _onUpdate, ctx) {
      const result = await callPythonTool("save_memory", params, executionHeaders(toolCallId, ctx));
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details: result,
      };
    },
  }));

  pi.registerTool(defineTool({
    name: "recall_memory",
    label: "Recall Memory",
    description: "Search confirmed long-term memories; candidates are excluded.",
    parameters: Type.Object({
      query: Type.String({ minLength: 1 }),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 50, default: 5 })),
    }),
    async execute(_toolCallId, params) {
      const result = await callPythonTool("recall_memory", params);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details: result,
      };
    },
  }));

  pi.registerCommand("scholar-health", {
    description: "Check the ScholarHarness Python tool service",
    handler: async (_args, ctx) => {
      try {
        const response = await fetch(`${baseUrl}/health`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        ctx.ui.notify("ScholarHarness Python service is healthy", "info");
      } catch (error) {
        ctx.ui.notify(`ScholarHarness service unavailable: ${String(error)}`, "error");
      }
    },
  });
}
