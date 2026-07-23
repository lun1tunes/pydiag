import assert from "node:assert/strict";
import { eventPathIncludes } from "../../../src/pydiag/rendering/flow_canvas_assets/flow_canvas_dom_utils.js";

function makeNode({ contains = false } = {}) {
  return {
    contains() {
      return contains;
    },
  };
}

// Regression: Shadow DOM retargets capture-phase target to the host.
// contains(host) is false; composedPath still lists the real menu.
{
  const menu = makeNode({ contains: false });
  const menuItem = {};
  const shadowHost = {};
  const event = {
    target: shadowHost,
    composedPath() {
      return [menuItem, menu, shadowHost, {}];
    },
  };
  assert.equal(
    eventPathIncludes(event, menu),
    true,
    "menu click must survive retargeted Shadow DOM target",
  );
  // Old buggy check that made the dropdown appear dead:
  assert.equal(menu.contains(event.target), false);
}

{
  const menu = makeNode({ contains: false });
  const outside = {};
  const shadowHost = {};
  const event = {
    target: shadowHost,
    composedPath() {
      return [outside, shadowHost, {}];
    },
  };
  assert.equal(eventPathIncludes(event, menu), false);
}

{
  const menu = makeNode({ contains: true });
  const event = { target: {} };
  assert.equal(eventPathIncludes(event, menu), true);
}

{
  assert.equal(eventPathIncludes({ target: {} }, null), false);
}

console.log("event_path_includes: ok");
