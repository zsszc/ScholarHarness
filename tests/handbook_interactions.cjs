const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(
  path.resolve(__dirname, "../docs/scholar-harness-deep-dive.html"),
  "utf8",
);
const script = html.split("<script>")[1]?.split("</script>")[0];
assert.ok(script, "inline interaction script exists");

function element(dataset = {}, textContent = "") {
  const listeners = new Map();
  const classes = new Set();
  return {
    dataset,
    textContent,
    value: "",
    hidden: false,
    children: [],
    attributes: {},
    classList: {
      toggle(name, active) {
        if (active) classes.add(name);
        else classes.delete(name);
      },
      contains(name) { return classes.has(name); },
    },
    addEventListener(name, callback) { listeners.set(name, callback); },
    setAttribute(name, value) { this.attributes[name] = value; },
    replaceChildren() { this.children = []; },
    append(...children) { this.children.push(...children); },
    fire(name) { listeners.get(name)?.(); },
  };
}

const steps = Array.from({ length: 6 }, (_, index) => element({ step: String(index) }));
const nodes = Array.from({ length: 6 }, () => element());
const filters = ["all", "project", "agent", "rag", "memory", "backend", "eval"]
  .map((filter) => element({ filter }));
const questions = [
  element({ tags: "project agent" }, "Pi 与 MiniPy Runtime"),
  element({ tags: "rag" }, "RAG 和 RRF 检索"),
];
const output = element();
const search = element();
const count = element();
const document = {
  querySelectorAll(selector) {
    return {
      ".step-btn": steps,
      ".flow-node": nodes,
      "[data-filter]": filters,
      ".qa": questions,
    }[selector] || [];
  },
  getElementById(id) {
    return { "step-output": output, "qa-search": search, "qa-count": count }[id];
  },
  createElement() { return element(); },
  createTextNode(text) { return { textContent: text }; },
};

vm.runInNewContext(script, { document });
assert.equal(count.textContent, "显示 2 / 2 题");
steps[2].fire("click");
assert.equal(steps[2].attributes["aria-pressed"], "true");
assert.ok(nodes[2].classList.contains("active"));
assert.ok(output.children[0].textContent.includes("模型请求"));
filters[1].fire("click");
assert.equal(questions[0].hidden, false);
assert.equal(questions[1].hidden, true);
search.value = "RRF";
search.fire("input");
assert.equal(count.textContent, "显示 0 / 2 题");
filters[0].fire("click");
assert.equal(count.textContent, "显示 1 / 2 题");
console.log("Handbook stepper and question filter passed");
