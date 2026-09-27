import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ChevronRight,
  FileText,
  FolderTree,
  History,
  Library,
  Lightbulb,
  Link2,
  ListTree,
  ScrollText,
  Search,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { DocKind, DocRef, Part, ToolPart } from "../../api/types";
import { resumeArguments } from "../../lib/format";
import { dureeLisible, libelleOutil } from "../../lib/journal";
import { sameDoc, targetFromDoc, type ReaderTarget } from "../../lib/reader";
import { Markdown } from "./Markdown";

type Nav = { activeTarget: ReaderTarget | null; onOpenTarget: (t: ReaderTarget) => void };

const ICONE_OUTIL: Record<string, LucideIcon> = {
  sommaire: ListTree,
  lister_textes: Library,
  lire_article: FileText,
  historique_article: History,
  comparer_versions: History,
  renvois: Link2,
  rechercher: Search,
  modifications: History,
  bofip_plan: ScrollText,
  bofip_lire: ScrollText,
  bofip_rechercher: ScrollText,
  bofip_pour_article: ScrollText,
};

const ICONE_DOC: Record<DocKind, LucideIcon> = {
  article: FileText,
  section: FolderTree,
  texte: Library,
  recherche: Search,
  bofip: ScrollText,
};

/** Ligne d'étape repliable : chevron + icône + libellé ; le corps se déplie en douceur. */
function Etape({
  icon,
  label,
  live,
  erreur,
  onLabel,
  labelTitle,
  children,
}: {
  icon: ReactNode;
  label: ReactNode;
  live: boolean;
  erreur?: boolean;
  /** Action du libellé (ouvrir le document principal) ; à défaut, le libellé déplie la ligne. */
  onLabel?: () => void;
  labelTitle?: string;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((o) => !o);
  const hasBody = children !== undefined && children !== null && children !== false;
  return (
    <div className={`step ${open ? "open" : ""} ${live ? "live" : ""} ${erreur ? "err" : ""}`}>
      <div className="step-line">
        <button
          className="step-chev"
          onClick={toggle}
          aria-expanded={open}
          aria-label={open ? "Replier" : "Déplier"}
          disabled={!hasBody}
        >
          <ChevronRight size={13} />
        </button>
        <span className="step-icon" aria-hidden>
          {icon}
        </span>
        <button className="step-label" onClick={onLabel ?? toggle} title={labelTitle}>
          <span className={live ? "shimmer" : undefined}>{label}</span>
        </button>
      </div>
      {hasBody && (
        <div className="step-body" aria-hidden={!open}>
          <div className="step-body-inner">{children}</div>
        </div>
      )}
    </div>
  );
}

export function EtapeReflexion({ text, live }: { text: string; live: boolean }) {
  const mots = text.trim() ? text.trim().split(/\s+/).length : 0;
  return (
    <Etape
      icon={<Lightbulb size={14} />}
      live={live}
      label={
        <>
          {live ? "Réfléchit…" : "Réflexion"}
          {mots > 0 && <span className="step-res"> · {mots} mots</span>}
        </>
      }
    >
      {text.trim() ? <div className="step-thinking">{text}</div> : null}
    </Etape>
  );
}

export function EtapeOutil({ part, live, activeTarget, onOpenTarget }: { part: ToolPart; live: boolean } & Nav) {
  const lib = libelleOutil(part);
  const Icon = part.status === "error" ? AlertTriangle : (ICONE_OUTIL[part.name] ?? Wrench);
  const principal = part.documents[0];
  const args = resumeArguments(part.arguments, 6);
  return (
    <Etape
      icon={<Icon size={14} />}
      live={live || part.status === "running"}
      erreur={part.status === "error"}
      onLabel={principal ? () => onOpenTarget(targetFromDoc(principal)) : undefined}
      labelTitle={principal ? `Ouvrir : ${principal.titre}` : undefined}
      label={
        <>
          <span className="step-action">{lib.action}</span>
          {lib.objet && <span className="step-objet"> · {lib.objet}</span>}
          {lib.resultat && <span className="step-res"> — {lib.resultat}</span>}
        </>
      }
    >
      {args.length > 0 && (
        <div className="step-args mono">
          {args.map(([k, v]) => (
            <span key={k}>
              <span className="k">{k}</span>=<span className="v">{v}</span>
            </span>
          ))}
        </div>
      )}
      {part.documents.length > 0 && (
        <div className="doc-chips">
          {part.documents.map((d, i) => (
            <DocChip key={`${d.kind}:${d.id}:${i}`} doc={d} active={sameDoc(activeTarget, d)} onOpen={() => onOpenTarget(targetFromDoc(d))} />
          ))}
        </div>
      )}
    </Etape>
  );
}

function DocChip({ doc, active, onOpen }: { doc: DocRef; active: boolean; onOpen: () => void }) {
  const Icon = ICONE_DOC[doc.kind] ?? FileText;
  const bofip = doc.kind === "bofip" && doc.sous_titre !== "";
  const titre = bofip ? doc.sous_titre : doc.titre;
  const sous = bofip ? doc.titre : doc.sous_titre;
  return (
    <button className={`doc-chip ${active ? "active" : ""}`} onClick={onOpen} title={`Ouvrir : ${titre}${sous ? ` — ${sous}` : ""}`}>
      <Icon size={13} aria-hidden />
      <span className="doc-chip-t">{titre}</span>
      {sous && <span className={`doc-chip-s ${bofip ? "mono" : ""}`}>{sous}</span>}
    </button>
  );
}

/** Rend une suite de parts en journal : étapes repliables, texte intermédiaire en petit. */
export function Etapes({
  parts,
  liveIndex,
  intermediaire,
  ...nav
}: { parts: Part[]; liveIndex: number; intermediaire: "petit" | "normal" } & Nav) {
  return (
    <>
      {parts.map((p, i) => {
        const live = i === liveIndex;
        if (p.type === "thinking") return <EtapeReflexion key={i} text={p.text} live={live} />;
        if (p.type === "tool") return <EtapeOutil key={p.call_id} part={p} live={live} {...nav} />;
        return (
          <div key={i} className={intermediaire === "petit" ? "step-text" : live ? "text-live" : "text-block"}>
            <Markdown text={p.text} />
          </div>
        );
      })}
    </>
  );
}

/** Compteur « Travaille depuis 23 s », rafraîchi chaque seconde. */
export function Chrono({ depuis }: { depuis: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="work-live" aria-live="off">
      <span className="work-dot" aria-hidden />
      <span className="shimmer">Travaille depuis {dureeLisible(Math.max(0, now - depuis))}</span>
    </div>
  );
}

/** Ligne « A travaillé pendant … » qui replie tout le journal d'un message terminé. */
export function Travail({
  journal,
  dureeMs,
  interrompu,
  ...nav
}: { journal: Part[]; dureeMs: number | null; interrompu: boolean } & Nav) {
  const [open, setOpen] = useState(false);
  const outils = journal.filter((p) => p.type === "tool").length;
  const duree = dureeMs != null ? dureeLisible(dureeMs) : null;
  const titre = interrompu
    ? duree
      ? `Interrompu après ${duree}`
      : "Interrompu"
    : duree
      ? `A travaillé pendant ${duree}`
      : "Étapes de travail";
  return (
    <div className={`work ${open ? "open" : ""} ${interrompu ? "err" : ""}`}>
      <button className="work-line" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <ChevronRight size={13} className="work-chev" aria-hidden />
        <span className="work-title">{titre}</span>
        {journal.length > 0 && (
          <span className="work-meta">
            {outils > 0 ? `${outils} étape${outils > 1 ? "s" : ""}` : "réflexion"}
          </span>
        )}
      </button>
      {journal.length > 0 && (
        <div className="work-body" aria-hidden={!open}>
          <div className="work-body-inner">
            <Etapes parts={journal} liveIndex={-1} intermediaire="petit" {...nav} />
          </div>
        </div>
      )}
    </div>
  );
}
