() => {
  // Collect every character the page can show: text nodes (hidden ones too,
  // since menus and dialogs open later), text-transform results, ::before and
  // ::after content, placeholders, alt/title/aria-label and form values.
  const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "HEAD", "TITLE"]);
  const parts = [];

  function transform(text, style) {
    const t = style.textTransform;
    const out = [];
    if (t === "uppercase") out.push(text.toUpperCase());
    else if (t === "lowercase") out.push(text.toLowerCase());
    else if (t === "capitalize") out.push(text, text.toUpperCase());
    else out.push(text);
    const caps = style.fontVariantCaps || "";
    if (caps && caps !== "normal") out.push(text.toUpperCase());
    return out.join("");
  }

  function cssStrings(value, el) {
    // Computed content, e.g. "\"-> \"" or counter(item) or attr(data-x).
    if (!value || value === "none" || value === "normal") return "";
    let out = "";
    const re = /"((?:[^"\\]|\\.)*)"|attr\(\s*([\w-]+)\s*\)|(counters?\()|(open-quote|close-quote)/g;
    let m;
    while ((m = re.exec(value)) !== null) {
      if (m[1] !== undefined) out += m[1].replace(/\\(.)/g, "$1");
      else if (m[2]) out += el.getAttribute(m[2]) || "";
      else if (m[3]) out += "0123456789.-";
      else if (m[4]) out += "\u201c\u201d\u2018\u2019\u00ab\u00bb\"'";
    }
    return out;
  }

  function walk(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let node = walker.currentNode;
    while (node) {
      if (node.nodeType === Node.TEXT_NODE) {
        const parent = node.parentElement;
        if (parent && !SKIP.has(parent.tagName) && !parent.closest("head")) {
          parts.push(transform(node.data, getComputedStyle(parent)));
        }
      } else if (node.nodeType === Node.ELEMENT_NODE && !SKIP.has(node.tagName)) {
        const el = node;
        const style = getComputedStyle(el);
        for (const pseudo of ["::before", "::after", "::marker"]) {
          const ps = getComputedStyle(el, pseudo);
          const text = cssStrings(ps.content, el);
          if (text) parts.push(transform(text, ps));
        }
        if (style.display === "list-item" && !/^(none|disc|circle|square)$/.test(style.listStyleType)) {
          parts.push("0123456789.");
        }
        for (const name of ["alt", "title", "aria-label", "placeholder"]) {
          const v = el.getAttribute(name);
          if (v) parts.push(transform(v, style));
        }
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
          const type = (el.getAttribute("type") || "").toLowerCase();
          if (type !== "password" && type !== "hidden" && el.value) parts.push(transform(el.value, style));
        }
        if (el.shadowRoot) walk(el.shadowRoot);
      }
      node = walker.nextNode();
    }
  }

  if (document.body) walk(document.body);
  const alternates = [];
  for (const link of document.querySelectorAll('link[rel~="alternate"][hreflang][href]')) {
    alternates.push({hreflang: link.getAttribute("hreflang"), href: link.href});
  }
  return {text: parts.join(""), lang: document.documentElement.lang || "", alternates};
}
