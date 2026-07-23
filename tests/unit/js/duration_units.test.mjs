import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const js = readFileSync(
  path.join(root, "src/pydiag/rendering/flow_canvas_assets/flow_canvas.js"),
  "utf8",
);

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `missing ${name}`);
  let i = source.indexOf("{", start);
  let depth = 0;
  for (; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === "{") depth += 1;
    if (ch === "}") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start, i + 1);
      }
    }
  }
  throw new Error(`unterminated ${name}`);
}

const constsStart = js.indexOf("const DURATION_UNIT_OPTIONS = [");
const constsEnd = js.indexOf("];", constsStart) + 2;
const bundle = [
  js.slice(constsStart, constsEnd),
  extractFunction(js, "parseDurationParts"),
  extractFunction(js, "formatDurationValue"),
  "({ parseDurationParts, formatDurationValue, DURATION_UNIT_OPTIONS });",
].join("\n");

const api = vm.runInNewContext(bundle);

assert.deepEqual(api.parseDurationParts("16 hours"), { amount: "16", unit: "hours" });
assert.deepEqual(api.parseDurationParts("1 hour"), { amount: "1", unit: "hours" });
assert.deepEqual(api.parseDurationParts("40 minutes"), { amount: "40", unit: "minutes" });
assert.deepEqual(api.parseDurationParts("2 days"), { amount: "2", unit: "days" });
assert.deepEqual(api.parseDurationParts("3h"), { amount: "3", unit: "hours" });
assert.deepEqual(api.parseDurationParts(""), { amount: "", unit: "hours" });

assert.equal(api.formatDurationValue("16", "hours"), "16 hours");
assert.equal(api.formatDurationValue("1", "hours"), "1 hour");
assert.equal(api.formatDurationValue("40", "minutes"), "40 minutes");
assert.equal(api.formatDurationValue("1", "minutes"), "1 minute");
assert.equal(api.formatDurationValue("2", "days"), "2 days");
assert.equal(api.formatDurationValue("1", "days"), "1 day");
assert.equal(api.formatDurationValue("0", "hours"), "");
assert.equal(api.formatDurationValue("", "hours"), "");

assert.deepEqual(
  api.DURATION_UNIT_OPTIONS.map((item) => item.label),
  ["минут", "час", "день"],
);

console.log("duration_units: ok");
