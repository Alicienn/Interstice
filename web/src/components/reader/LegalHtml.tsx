import { useMemo, type MouseEvent } from "react";
import DOMPurify from "dompurify";

type Props = {
  html: string;
  className?: string;
  /** Clic sur un renvoi résolu `<a data-article="LEGIARTI…">`. */
  onArticle?: (id: string) => void;
};

// Niveaux d'alinéas usuels des codes : « I.- », « A.- », « 1. », « 1° », « a) ».
const NIVEAUX: [RegExp, string][] = [
  [/^([IVXLC]+(?:\s?(?:bis|ter|quater|quinquies|sexies|septies|octies))?\s?\.?\s?[-–—])/, "al-1"],
  [/^([A-H](?:\s?(?:bis|ter|quater))?\s?\.\s?[-–—])/, "al-2"],
  [/^(\d+(?:\s?(?:bis|ter|quater|quinquies|sexies))?\s?\.)\s/, "al-2"],
  [/^(\d+(?:\s?(?:bis|ter|quater|quinquies|sexies))?\s?°)/, "al-3"],
  [/^([a-z](?:\s?(?:bis|ter|quater))?\s?\))/, "al-4"],
];

const ALLOWED_ATTR_EXTRA = ["data-article", "colspan", "rowspan"];

/** Assainit le HTML LEGI puis l'enrichit : niveaux d'alinéas, liens internes, liens externes. */
export function prepareLegalHtml(html: string): string {
  const frag = DOMPurify.sanitize(html, {
    ADD_ATTR: ALLOWED_ATTR_EXTRA,
    FORBID_TAGS: ["style", "script", "iframe", "form", "input", "img"],
    FORBID_ATTR: ["style", "class", "id"],
    RETURN_DOM_FRAGMENT: true,
  });

  frag.querySelectorAll("p").forEach((p) => {
    const first = p.firstChild;
    if (!first || first.nodeType !== Node.TEXT_NODE) return;
    const text = first.textContent ?? "";
    const lead = text.replace(/^\s+/, "");
    for (const [re, cls] of NIVEAUX) {
      const m = re.exec(lead);
      if (!m || !m[1]) continue;
      p.classList.add("al", cls);
      const offset = text.length - lead.length;
      const span = document.createElement("span");
      span.className = "al-num";
      span.textContent = m[1];
      const rest = document.createTextNode(text.slice(offset + m[1].length));
      p.replaceChild(rest, first);
      p.insertBefore(span, rest);
      break;
    }
  });

  frag.querySelectorAll("a").forEach((a) => {
    if (a.hasAttribute("data-article")) {
      a.setAttribute("href", "#");
      a.classList.add("renvoi");
      a.setAttribute("title", "Ouvrir l'article cité");
    } else if (a.getAttribute("href")) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    }
  });

  frag.querySelectorAll("table").forEach((t) => {
    const wrap = document.createElement("div");
    wrap.className = "legal-table";
    t.replaceWith(wrap);
    wrap.appendChild(t);
  });

  const div = document.createElement("div");
  div.appendChild(frag);
  return div.innerHTML;
}

export function LegalHtml({ html, className, onArticle }: Props) {
  const clean = useMemo(() => prepareLegalHtml(html), [html]);
  const onClick = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    const a = target.closest<HTMLAnchorElement>("a[data-article]");
    if (a) {
      e.preventDefault();
      const id = a.getAttribute("data-article");
      if (id && onArticle) onArticle(id);
    }
  };
  return (
    <div
      className={`legal ${className ?? ""}`}
      onClick={onClick}
      // HTML assaini par DOMPurify ci-dessus.
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}
