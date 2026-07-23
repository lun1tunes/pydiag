/**
 * Shadow-DOM-safe hit test for outside-click dismiss.
 *
 * Streamlit bidi components run in an open ShadowRoot. Document-capture
 * listeners see a retargeted host as event.target, so node.contains(target)
 * is false even when the real click was inside the menu — which closes the
 * menu before the item click handler runs.
 */
export function eventPathIncludes(event, node) {
  if (!node) {
    return false;
  }
  if (typeof event.composedPath === "function") {
    const path = event.composedPath();
    if (Array.isArray(path) && path.includes(node)) {
      return true;
    }
  }
  const target = event.target;
  if (target && typeof node.contains === "function" && node.contains(target)) {
    return true;
  }
  return false;
}
