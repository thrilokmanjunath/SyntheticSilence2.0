type El = HTMLElementTagNameMap;

/** Tiny element builder. Children are appended as text nodes or nodes, never parsed as HTML. */
export function h<K extends keyof El>(
  tag: K,
  attrs: Record<string, string> = {},
  ...children: (Node | string | null)[]
): El[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  for (const c of children) if (c !== null) node.append(c);
  return node;
}

export function byId<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing element #${id}`);
  return node as T;
}
