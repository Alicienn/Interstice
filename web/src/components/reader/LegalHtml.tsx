import { forwardRef, useMemo, type MouseEvent } from "react";
import DOMPurify from "dompurify";

export type TocEntry = { id: string; level: 1 | 2 | 3; text: string };

type Variant = "legi" | "bofip";

type Props = {
  html: string;
  className?: string;
  variant?: Variant;
  /** Clic sur un renvoi résolu `<a data-article="LEGIARTI…">`. */
  onArticle?: (id: string) => void;
  /** Clic sur un lien vers un autre document BOFiP `<a data-bofip="NNN-PGP" data-ancre="…">`. */
  onBofip?: (id: string, ancre: string | null) => void;
};

// Niveaux d'alinéas usuels des codes : « I.- », « A.- », « 1. », « 1° », « a) ».
const NIVEAUX: [RegExp, string][] = [
  [/^([IVXLC]+(?:\s?(?:bis|ter|quater|quinquies|sexies|septies|octies))?\s?\.?\s?[-–—])/, "al-1"],
  [/^([A-H](?:\s?(?:bis|ter|quater))?\s?\.\s?[-–—])/, "al-2"],
  [/^(\d+(?:\s?(?:bis|ter|quater|quinquies|sexies))?\s?\.)\s/, "al-2"],
  [/^(\d+(?:\s?(?:bis|ter|quater|quinquies|sexies))?\s?°)/, "al-3"],
  [/^([a-z](?:\s?(?:bis|ter|quater))?\s?\))/, "al-4"],
];

/** Préfixe ajouté par DOMPurify (SANITIZE_NAMED_PROPS) aux `id` / `name` du document. */
export const ANCRE_PREFIX = "user-content-";

/** Assainit le HTML puis l'enrichit : niveaux d'alinéas, liens internes, pièces non servies, sommaire. */
export function prepareLegalHtml(html: string, variant: Variant = "legi"): { html: string; toc: TocEntry[] } {
  const bofip = variant === "bofip";
  const frag = DOMPurify.sanitize(html, {
    ADD_ATTR: ["data-article", "data-bofip", "data-ancre", "data-bofip-fichier", "data-bofip-image", "colspan", "rowspan"],
    FORBID_TAGS: ["style", "script", "iframe", "form", "input", "object", "embed", ...(bofip ? [] : ["img"])],
    FORBID_ATTR: ["style", "class", ...(bofip ? [] : ["id", "name"])],
    SANITIZE_NAMED_PROPS: true,
    RETURN_DOM_FRAGMENT: true,
  });

  frag.querySelectorAll("p").forEach((p) => {
    const first = p.firstChild;
    const whole = (p.textContent ?? "").trim();
    // BOFiP : numéro de paragraphe seul sur sa ligne (« 10 », « 110 »).
    if (bofip && /^\d{1,4}$/.test(whole)) {
      p.classList.add("para-num");
      return;
    }
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
    } else if (a.hasAttribute("data-bofip")) {
      a.setAttribute("href", "#");
      a.classList.add("renvoi", "renvoi-bofip");
      a.setAttribute("title", "Ouvrir le document BOFiP");
    } else if (a.hasAttribute("data-bofip-fichier")) {
      a.removeAttribute("href");
      a.classList.add("piece-absente");
      a.setAttribute("title", "Pièce jointe non disponible dans Interstice");
      const note = document.createElement("span");
      note.className = "piece-note";
      note.textContent = "pièce jointe non disponible";
      a.after(note);
    } else if (a.getAttribute("href")) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    }
  });

  // Images : jamais chargées (non servies par le backend) ; remplacées par une mention.
  frag.querySelectorAll("img").forEach((img) => {
    const span = document.createElement("span");
    span.className = "piece-absente image";
    const alt = (img.getAttribute("alt") ?? "").trim();
    span.textContent = alt && alt !== "image" ? `Image non disponible : ${alt}` : "Image non disponible";
    img.replaceWith(span);
  });

  frag.querySelectorAll("table").forEach((t) => {
    const wrap = document.createElement("div");
    wrap.className = "legal-table";
    t.replaceWith(wrap);
    wrap.appendChild(t);
  });

  const toc: TocEntry[] = [];
  if (bofip) {
    frag.querySelectorAll("h1, h2, h3").forEach((h, i) => {
      const text = (h.textContent ?? "").replace(/\s+/g, " ").trim();
      if (!text) return;
      const id = `toc-${i}`;
      h.setAttribute("data-toc", id);
      toc.push({ id, level: Number(h.tagName[1]) as 1 | 2 | 3, text });
    });
  }

  const div = document.createElement("div");
  div.appendChild(frag);
  return { html: div.innerHTML, toc };
}

export const LegalHtml = forwardRef<HTMLDivElement, Props & { prepared?: string }>(function LegalHtml(
  { html, className, variant = "legi", onArticle, onBofip, prepared },
  ref,
) {
  const clean = useMemo(() => prepared ?? prepareLegalHtml(html, variant).html, [html, variant, prepared]);
  const onClick = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    const art = target.closest<HTMLAnchorElement>("a[data-article]");
    if (art) {
      e.preventDefault();
      const id = art.getAttribute("data-article");
      if (id && onArticle) onArticle(id);
      return;
    }
    const bof = target.closest<HTMLAnchorElement>("a[data-bofip]");
    if (bof) {
      e.preventDefault();
      const id = bof.getAttribute("data-bofip");
      if (id && onBofip) onBofip(id, bof.getAttribute("data-ancre"));
      return;
    }
    if (target.closest("a.piece-absente")) e.preventDefault();
  };
  return (
    <div
      ref={ref}
      className={`legal ${className ?? ""}`}
      onClick={onClick}
      // HTML assaini par DOMPurify ci-dessus.
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
});
