// Maquette en mémoire de tout le contrat d'API (activée par VITE_MOCK=1, cf. `pnpm dev:mock`).
// Elle remplace `fetch` : mêmes routes, mêmes codes HTTP, flux SSE simulé.
// Les textes de loi ci-dessous sont des extraits abrégés, destinés uniquement à tester l'interface.

import type {
  Conversation,
  DocRef,
  EnfantNoeud,
  Fournisseur,
  LigneRecherche,
  Message,
  Miette,
  ModeleActive,
  ModeleChoix,
  ModeleDistant,
  Part,
  Reglages,
  Renvoi,
  TexteCorpus,
  ThinkingSupport,
  VueArticle,
  VueNoeud,
} from "./types";

// ─── Utilitaires ─────────────────────────────────────────────────────────────

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const today = () => new Date().toISOString().slice(0, 10);
let seq = 100;
const newId = (prefix: string) => `${prefix}-${(seq++).toString(36)}${Math.random().toString(36).slice(2, 6)}`;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
const noContent = () => new Response(null, { status: 204 });
const notFound = (what = "Introuvable") => json({ detail: what }, 404);

// ─── Corpus factice ──────────────────────────────────────────────────────────

const CGI = "LEGITEXT000006069577";
const LPF = "LEGITEXT000006069583";

type NoeudMock = {
  id: string;
  kind: "texte" | "section";
  titre: string;
  texte_cid: string;
  parent: string | null;
  enfants: string[]; // ids de sections ou d'articles
};

const noeuds: Record<string, NoeudMock> = {};
function noeud(id: string, kind: "texte" | "section", titre: string, texte_cid: string, parent: string | null) {
  noeuds[id] = { id, kind, titre, texte_cid, parent, enfants: [] };
  if (parent) noeuds[parent]?.enfants.push(id);
}

// CGI
noeud(CGI, "texte", "Code général des impôts", CGI, null);
noeud("LEGISCTA000006089697", "section", "Livre premier : Assiette et liquidation de l'impôt", CGI, CGI);
noeud("LEGISCTA000006089698", "section", "Première Partie : Impôts d'État", CGI, "LEGISCTA000006089697");
noeud("LEGISCTA000006089699", "section", "Titre premier : Impôts directs et taxes assimilées", CGI, "LEGISCTA000006089698");
noeud("LEGISCTA000006089700", "section", "Chapitre premier : Impôt sur le revenu", CGI, "LEGISCTA000006089699");
noeud("LEGISCTA000006162626", "section", "Section I : Définition du revenu imposable", CGI, "LEGISCTA000006089700");
noeud("LEGISCTA000006162627", "section", "Section II : Revenus imposables", CGI, "LEGISCTA000006089700");
noeud(
  "LEGISCTA000006179573",
  "section",
  "1re Sous-section : Détermination des bénéfices ou revenus nets des diverses catégories de revenus",
  CGI,
  "LEGISCTA000006162627",
);
noeud(
  "LEGISCTA000006191597",
  "section",
  "VI bis : Plus-values de cession à titre onéreux de biens ou de droits de toute nature",
  CGI,
  "LEGISCTA000006179573",
);
noeud(
  "LEGISCTA000006191598",
  "section",
  "1 : Plus-values de cession de valeurs mobilières, de droits sociaux et de titres assimilés",
  CGI,
  "LEGISCTA000006191597",
);
noeud("LEGISCTA000006191599", "section", "2 : Plus-values de cession de biens meubles ou immeubles", CGI, "LEGISCTA000006191597");
noeud("LEGISCTA000006089727", "section", "Titre II : Taxes sur le chiffre d'affaires et taxes assimilées", CGI, "LEGISCTA000006089698");
noeud("LEGISCTA000006089790", "section", "Livre deuxième : Recouvrement de l'impôt", CGI, CGI);
// LPF
noeud(LPF, "texte", "Livre des procédures fiscales", LPF, null);
noeud("LEGISCTA000006148523", "section", "Première partie : Partie législative", LPF, LPF);
noeud("LEGISCTA000006148524", "section", "Titre II : Le contrôle de l'impôt", LPF, "LEGISCTA000006148523");
noeud("LEGISCTA000006165424", "section", "Chapitre premier : Le droit de contrôle de l'administration", LPF, "LEGISCTA000006148524");
noeud("LEGISCTA000006165515", "section", "Section V : Procédure de l'abus de droit fiscal", LPF, "LEGISCTA000006165424");

type ArticleMock = {
  id: string;
  num: string;
  texte_cid: string;
  section: string;
  html: string;
  nota_html: string | null;
  versions: { id: string; etat: string; date_debut: string; date_fin: string }[];
  renvois_sortants: Renvoi[];
};

const A_150_0_A = "LEGIARTI000047291741";
const A_150_0_B = "LEGIARTI000036428001";
const A_150_0_B_TER = "LEGIARTI000048811467";
const A_150_0_D = "LEGIARTI000048811542";
const A_L64 = "LEGIARTI000036428155";

const articles: Record<string, ArticleMock> = {};
function article(a: ArticleMock) {
  articles[a.id] = a;
  noeuds[a.section]?.enfants.push(a.id);
}

const renvoiLegi = (id: string, num: string, texte_titre: string, libelle: string, typelien = "CITATION"): Renvoi => ({
  id,
  cle: `${texte_titre === "Code général des impôts" ? "CGI" : "LPF"}:${num}`,
  num,
  texte_titre,
  typelien,
  origine: "legi",
  libelle,
});

article({
  id: A_150_0_A,
  num: "150-0 A",
  texte_cid: CGI,
  section: "LEGISCTA000006191598",
  html: `<p>I.-1. Sous réserve des dispositions propres aux bénéfices industriels et commerciaux, aux bénéfices non commerciaux et aux bénéfices agricoles ainsi que des articles <a data-article="${A_150_0_D}">150-0 D</a> et 150 UB, les gains nets retirés des cessions à titre onéreux, effectuées directement, par personne interposée ou par l'intermédiaire d'une fiducie, de valeurs mobilières, de droits sociaux, de titres mentionnés au 1° de l'article 118 et aux 6° et 7° de l'article 120, de droits portant sur ces valeurs, droits ou titres ou de titres représentatifs des mêmes valeurs, droits ou titres, sont soumis à l'impôt sur le revenu.</p>
<p>2. Le complément de prix reçu par le cédant en exécution de la clause du contrat de cession de valeurs mobilières ou de droits sociaux par laquelle le cessionnaire s'engage à verser au cédant un complément de prix exclusivement déterminé en fonction d'une indexation en relation directe avec l'activité de la société dont les titres sont l'objet du contrat, est imposable au titre de l'année au cours de laquelle il est reçu.</p>
<p>II.-Les dispositions du I sont applicables :</p>
<p>1. Au gain net retiré des cessions de titres ou droits effectuées dans le cadre d'un plan d'épargne en actions défini à l'article 163 quinquies D […] ;</p>
<p>2. Au gain net réalisé depuis l'ouverture d'un plan d'épargne en actions défini à l'article 163 quinquies D en cas de retrait de titres ou de liquidités ou de rachat avant l'expiration de la cinquième année […].</p>`,
  nota_html: null,
  versions: [
    { id: "LEGIARTI000036428112", etat: "MODIFIE", date_debut: "2018-01-01", date_fin: "2023-04-01" },
    { id: A_150_0_A, etat: "VIGUEUR", date_debut: "2023-04-01", date_fin: "2999-01-01" },
  ],
  renvois_sortants: [
    renvoiLegi(A_150_0_D, "150-0 D", "Code général des impôts", "articles 150-0 D et 150 UB"),
    { id: null, cle: null, num: "163 quinquies D", texte_titre: "Code général des impôts", typelien: "CITATION", origine: "texte", libelle: "article 163 quinquies D (non résolu)" },
  ],
});

article({
  id: A_150_0_B,
  num: "150-0 B",
  texte_cid: CGI,
  section: "LEGISCTA000006191598",
  html: `<p>Les dispositions de l'article <a data-article="${A_150_0_A}">150-0 A</a> ne sont pas applicables, au titre de l'année de l'échange des titres, aux plus-values réalisées dans le cadre d'une opération d'offre publique, de fusion, de scission, d'absorption d'un fonds commun de placement par une société d'investissement à capital variable, de conversion, de division, ou de regroupement, réalisée conformément à la réglementation en vigueur ou d'un apport de titres à une société soumise à l'impôt sur les sociétés.</p>
<p>Ces dispositions ne sont pas applicables aux opérations d'apport de titres à une société soumise à l'impôt sur les sociétés contrôlée par l'apporteur, qui relèvent de l'article <a data-article="${A_150_0_B_TER}">150-0 B ter</a>.</p>`,
  nota_html: null,
  versions: [{ id: A_150_0_B, etat: "VIGUEUR", date_debut: "2017-01-01", date_fin: "2999-01-01" }],
  renvois_sortants: [
    renvoiLegi(A_150_0_A, "150-0 A", "Code général des impôts", "article 150-0 A"),
    renvoiLegi(A_150_0_B_TER, "150-0 B ter", "Code général des impôts", "article 150-0 B ter"),
  ],
});

const HTML_150_0_B_TER = `<p>I.-L'imposition de la plus-value réalisée, directement ou par personne interposée, dans le cadre d'une opération d'échange ou d'apport de valeurs mobilières, de droits sociaux, de titres ou de droits s'y rapportant tels que définis à l'article <a data-article="${A_150_0_A}">150-0 A</a> à une société soumise à l'impôt sur les sociétés ou à un impôt équivalent est reportée si les conditions prévues au III du présent article sont remplies. Le contribuable mentionne le montant de la plus-value dans la déclaration prévue à l'article 170.</p>
<p>Il est mis fin au report d'imposition à l'occasion :</p>
<p>1° De la cession à titre onéreux, du rachat, du remboursement ou de l'annulation des titres reçus en rémunération de l'apport ;</p>
<p>2° De la cession à titre onéreux, du rachat, du remboursement ou de l'annulation des titres apportés, si cet événement intervient dans un délai de trois ans à compter de l'apport des titres. Toutefois, il n'est pas mis fin au report d'imposition lorsque la société bénéficiaire de l'apport cède les titres dans un délai de trois ans à compter de la date de l'apport et prend l'engagement d'investir le produit de leur cession, dans un délai de deux ans à compter de la date de la cession et à hauteur d'au moins 60 % du montant de ce produit :</p>
<p>a) Dans le financement de moyens permanents d'exploitation affectés à son activité commerciale, industrielle, artisanale, libérale, agricole ou financière, à l'exception de la gestion de son propre patrimoine mobilier ou immobilier ;</p>
<p>b) Dans l'acquisition d'une fraction du capital d'une ou de plusieurs sociétés exerçant une activité mentionnée au a […] ;</p>
<p>[…]</p>
<p>II.-Le report d'imposition est maintenu en cas d'échange de titres résultant d'une fusion ou d'une scission […].</p>
<p>III.-Le report d'imposition est subordonné aux conditions suivantes :</p>
<p>1° L'apport de titres est réalisé en France ou dans un État membre de l'Union européenne ou dans un État ou territoire ayant conclu avec la France une convention d'assistance administrative […] ;</p>
<p>2° La société bénéficiaire de l'apport est contrôlée par le contribuable. Cette condition est appréciée à la date de l'apport, en tenant compte des droits détenus par le contribuable à l'issue de celui-ci.</p>
<p>Pour l'application du présent 2°, un contribuable est considéré comme contrôlant une société :</p>
<table><thead><tr><th>Cas</th><th>Critère</th></tr></thead><tbody>
<tr><td>a)</td><td>Lorsque la majorité des droits de vote ou des droits dans les bénéfices sociaux de la société est détenue, directement ou indirectement, par le contribuable ou par l'intermédiaire de son conjoint ou de leurs ascendants ou descendants […] ;</td></tr>
<tr><td>b)</td><td>Lorsqu'il dispose seul de la majorité des droits de vote […] ;</td></tr>
<tr><td>c)</td><td>Lorsqu'il y exerce en fait le pouvoir de décision.</td></tr>
</tbody></table>
<p>Voir aussi l'article L. 64 du livre des procédures fiscales (<a data-article="${A_L64}">abus de droit</a>).</p>`;

article({
  id: A_150_0_B_TER,
  num: "150-0 B ter",
  texte_cid: CGI,
  section: "LEGISCTA000006191598",
  html: HTML_150_0_B_TER,
  nota_html: `<p>Conformément au B du II de l'article 106 de la loi n° 2018-1317 du 28 décembre 2018, ces dispositions s'appliquent aux cessions, rachats, remboursements ou annulations de titres intervenant à compter du 1er janvier 2019.</p><p>Conformément à l'article 8 de la loi n° 2023-1322 du 29 décembre 2023, les modifications s'appliquent aux apports réalisés à compter du 1er janvier 2024.</p>`,
  versions: [
    { id: "LEGIARTI000033817781", etat: "MODIFIE", date_debut: "2017-01-01", date_fin: "2018-01-01" },
    { id: "LEGIARTI000036428125", etat: "MODIFIE", date_debut: "2018-01-01", date_fin: "2019-01-01" },
    { id: "LEGIARTI000038612345", etat: "MODIFIE", date_debut: "2019-01-01", date_fin: "2024-01-01" },
    { id: A_150_0_B_TER, etat: "VIGUEUR", date_debut: "2024-01-01", date_fin: "2999-01-01" },
  ],
  renvois_sortants: [
    renvoiLegi(A_150_0_A, "150-0 A", "Code général des impôts", "article 150-0 A"),
    renvoiLegi(A_L64, "L64", "Livre des procédures fiscales", "article L. 64"),
    { id: null, cle: null, num: "170", texte_titre: "Code général des impôts", typelien: "CITATION", origine: "texte", libelle: "article 170" },
  ],
});

article({
  id: A_150_0_D,
  num: "150-0 D",
  texte_cid: CGI,
  section: "LEGISCTA000006191598",
  html: `<p>1. Les gains nets mentionnés au I de l'article <a data-article="${A_150_0_A}">150-0 A</a> sont constitués par la différence entre le prix effectif de cession des titres ou droits, net des frais et taxes acquittés par le cédant, et leur prix effectif d'acquisition par celui-ci diminué, le cas échéant, des réductions d'impôt effectivement obtenues […].</p><p>1 bis. […]</p>`,
  nota_html: null,
  versions: [
    { id: "LEGIARTI000036428143", etat: "MODIFIE", date_debut: "2018-01-01", date_fin: "2024-01-01" },
    { id: A_150_0_D, etat: "VIGUEUR", date_debut: "2024-01-01", date_fin: "2999-01-01" },
  ],
  renvois_sortants: [renvoiLegi(A_150_0_A, "150-0 A", "Code général des impôts", "article 150-0 A")],
});

article({
  id: A_L64,
  num: "L64",
  texte_cid: LPF,
  section: "LEGISCTA000006165515",
  html: `<p>Afin d'en restituer le véritable caractère, l'administration est en droit d'écarter, comme ne lui étant pas opposables, les actes constitutifs d'un abus de droit, soit que ces actes ont un caractère fictif, soit que, recherchant le bénéfice d'une application littérale des textes ou de décisions à l'encontre des objectifs poursuivis par leurs auteurs, ils n'ont pu être inspirés par aucun autre motif que celui d'éluder ou d'atténuer les charges fiscales que l'intéressé, si ces actes n'avaient pas été passés ou réalisés, aurait normalement supportées eu égard à sa situation ou à ses activités réelles.</p>
<p>En cas de désaccord sur les rectifications notifiées sur le fondement du présent article, le litige est soumis, à la demande du contribuable, à l'avis du comité de l'abus de droit fiscal. L'administration peut également soumettre le litige à l'avis du comité.</p>
<p>Si l'administration ne s'est pas conformée à l'avis du comité, elle doit apporter la preuve du bien-fondé de la rectification.</p>`,
  nota_html: null,
  versions: [
    { id: "LEGIARTI000006313176", etat: "MODIFIE", date_debut: "2009-01-01", date_fin: "2019-01-01" },
    { id: A_L64, etat: "VIGUEUR", date_debut: "2019-01-01", date_fin: "2999-01-01" },
  ],
  renvois_sortants: [],
});

// Index des versions : id de version → article porteur
const versionIndex: Record<string, { art: ArticleMock; v: ArticleMock["versions"][number] }> = {};
for (const art of Object.values(articles))
  for (const v of art.versions) versionIndex[v.id] = { art, v };

const textes: TexteCorpus[] = [
  { cid: CGI, sigle: "CGI", titre: "Code général des impôts", nature: "CODE", fiscal: true, nb_articles_vigueur: 4127 },
  { cid: "LEGITEXT000006069568", sigle: "CGI ann. II", titre: "Code général des impôts, annexe 2", nature: "CODE", fiscal: true, nb_articles_vigueur: 1321 },
  { cid: "LEGITEXT000006069569", sigle: "CGI ann. III", titre: "Code général des impôts, annexe 3", nature: "CODE", fiscal: true, nb_articles_vigueur: 1784 },
  { cid: LPF, sigle: "LPF", titre: "Livre des procédures fiscales", nature: "CODE", fiscal: true, nb_articles_vigueur: 1212 },
  { cid: "LEGITEXT000044595989", sigle: "CIBS", titre: "Code des impositions sur les biens et services", nature: "CODE", fiscal: true, nb_articles_vigueur: 862 },
  { cid: "LEGITEXT000006071570", sigle: "C. douanes", titre: "Code des douanes", nature: "CODE", fiscal: true, nb_articles_vigueur: 690 },
  { cid: "LEGITEXT000006070721", sigle: "C. civ.", titre: "Code civil", nature: "CODE", fiscal: false, nb_articles_vigueur: 2861 },
  { cid: "LEGITEXT000005634379", sigle: "C. com.", titre: "Code de commerce", nature: "CODE", fiscal: false, nb_articles_vigueur: 5112 },
];

function sigleDe(cid: string): string | null {
  return textes.find((t) => t.cid === cid)?.sigle ?? null;
}
function titreTexte(cid: string): string {
  return noeuds[cid]?.titre ?? textes.find((t) => t.cid === cid)?.titre ?? cid;
}

function chemin(sectionId: string | null): Miette[] {
  const out: Miette[] = [];
  let cur = sectionId ? noeuds[sectionId] : undefined;
  while (cur) {
    out.unshift({ id: cur.id, kind: cur.kind, titre: cur.titre });
    cur = cur.parent ? noeuds[cur.parent] : undefined;
  }
  return out;
}

function compterArticles(id: string): number {
  const n = noeuds[id];
  if (!n) return articles[id] ? 1 : 0;
  return n.enfants.reduce((acc, e) => acc + compterArticles(e), 0);
}

function vueNoeud(id: string, date: string | null): VueNoeud | null {
  let n = noeuds[id];
  if (!n) {
    // Texte connu mais non détaillé dans la maquette : racine avec quelques parties vides.
    const t = textes.find((x) => x.cid === id);
    if (!t) return null;
    noeud(id, "texte", t.titre, id, null);
    noeud(`${id}-P1`, "section", "Partie législative", id, id);
    noeud(`${id}-P2`, "section", "Partie réglementaire", id, id);
    n = noeuds[id]!;
  }
  const enfants: EnfantNoeud[] = n.enfants.map((e) => {
    const sec = noeuds[e];
    if (sec) return { kind: "section", id: e, titre: sec.titre, etat: "VIGUEUR", nb_articles: compterArticles(e) };
    const art = articles[e]!;
    return { kind: "article", id: e, titre: `Article ${art.num}`, etat: "VIGUEUR" };
  });
  return {
    id: n.id,
    kind: n.kind,
    titre: n.titre,
    texte_cid: n.texte_cid,
    chemin: chemin(n.parent),
    date: date ?? today(),
    enfants,
  };
}

function vueArticle(id: string, date: string | null): VueArticle | null {
  let entry = versionIndex[id];
  if (!entry) return null;
  // Avec une date : version en vigueur à cette date (si connue).
  if (date) {
    const v = entry.art.versions.find((x) => x.date_debut <= date && date < x.date_fin);
    if (v) entry = { art: entry.art, v };
  }
  const { art, v } = entry;
  const isCurrent = v.id === art.id;
  const html = isCurrent
    ? art.html
    : `<p><em>Version du ${v.date_debut} au ${v.date_fin} (texte simplifié pour la maquette).</em></p>${art.html}`;
  const entrants: Renvoi[] = Object.values(articles)
    .filter((a) => a.id !== art.id && a.renvois_sortants.some((r) => r.id === art.id))
    .map((a) => ({
      id: a.id,
      cle: `${sigleDe(a.texte_cid)}:${a.num}`,
      num: a.num,
      texte_titre: titreTexte(a.texte_cid),
      typelien: "CITATION",
      origine: "legi" as const,
      libelle: `cité par l'article ${a.num}`,
    }));
  return {
    id: v.id,
    cle: `${sigleDe(art.texte_cid) ?? ""}:${art.num}`,
    num: art.num,
    texte_cid: art.texte_cid,
    texte_titre: titreTexte(art.texte_cid),
    sigle: sigleDe(art.texte_cid),
    etat: v.etat,
    date_debut: v.date_debut,
    date_fin: v.date_fin,
    chemin: chemin(art.section),
    html,
    nota_html: art.nota_html,
    url_legifrance: `https://www.legifrance.gouv.fr/codes/article_lc/${v.id}`,
    versions: art.versions,
    renvois_sortants: art.renvois_sortants,
    renvois_entrants: entrants,
  };
}

function strip(html: string): string {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}
function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

function rechercher(q: string, texte: string | null): LigneRecherche[] {
  const mots = q
    .toLowerCase()
    .split(/\s+/)
    .filter((m) => m.length > 2);
  if (mots.length === 0) return [];
  const out: LigneRecherche[] = [];
  for (const art of Object.values(articles)) {
    if (texte && art.texte_cid !== texte) continue;
    const plain = strip(art.html);
    const low = plain.toLowerCase();
    const tous = mots.every((m) => low.includes(m));
    const hit = tous ? mots[0] : undefined;
    if (!tous && !art.num.toLowerCase().includes(q.toLowerCase())) continue;
    const pos = hit ? low.indexOf(hit) : 0;
    const from = Math.max(0, pos - 80);
    let extrait = escapeHtml(plain.slice(from, from + 240));
    for (const m of mots) extrait = extrait.replace(new RegExp(`(${m.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"), "<mark>$1</mark>");
    out.push({
      id: art.id,
      num: art.num,
      texte_titre: titreTexte(art.texte_cid),
      chemin: chemin(art.section)
        .slice(-2)
        .map((m) => m.titre)
        .join(" › "),
      extrait_html: `${from > 0 ? "… " : ""}${extrait} …`,
    });
  }
  return out;
}

// ─── Fournisseurs, modèles, réglages ─────────────────────────────────────────

const TH_OFF: ThinkingSupport = { supported: false, levels: [], source: "heuristique" };
const TH_OPENAI: ThinkingSupport = { supported: true, levels: ["low", "medium", "high"], source: "heuristique" };
const TH_CLAUDE: ThinkingSupport = { supported: true, levels: ["low", "medium", "high", "xhigh", "max"], source: "api" };

const providers: Fournisseur[] = [
  {
    id: "openrouter",
    name: "OpenRouter",
    type: "openai",
    base_url: "https://openrouter.ai/api/v1",
    api_key_set: true,
    models: [
      { id: "openai/gpt-5", label: "GPT-5", thinking: { ...TH_OPENAI, source: "api" }, context_length: 400000 },
      { id: "deepseek/deepseek-v3.2", thinking: TH_OFF, context_length: 128000 },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    type: "anthropic",
    base_url: "https://api.anthropic.com",
    api_key_set: true,
    models: [{ id: "claude-opus-4-5", label: "Claude Opus 4.5", thinking: TH_CLAUDE, context_length: 200000 }],
  },
];

let settings: Reglages = { default_model_key: "anthropic::claude-opus-4-5", default_thinking: "medium" };

function remoteCatalogue(p: Fournisseur): Omit<ModeleDistant, "enabled">[] {
  if (p.type === "anthropic") {
    return [
      { id: "claude-opus-4-5", owned_by: "anthropic", context_length: 200000, thinking: TH_CLAUDE },
      { id: "claude-sonnet-4-5", owned_by: "anthropic", context_length: 1000000, thinking: TH_CLAUDE },
      { id: "claude-haiku-4-5", owned_by: "anthropic", context_length: 200000, thinking: { ...TH_CLAUDE, levels: ["low", "medium", "high"] } },
      { id: "claude-3-5-haiku-latest", owned_by: "anthropic", context_length: 200000, thinking: { ...TH_OFF, source: "api" } },
    ];
  }
  const base: [string, string, number | null, ThinkingSupport][] = [
    ["openai/gpt-5", "openai", 400000, { ...TH_OPENAI, source: "api" }],
    ["openai/gpt-5-mini", "openai", 400000, { ...TH_OPENAI, source: "api" }],
    ["openai/gpt-5-nano", "openai", 400000, { ...TH_OPENAI, source: "api" }],
    ["openai/o3", "openai", 200000, { ...TH_OPENAI, source: "api" }],
    ["openai/o4-mini", "openai", 200000, { ...TH_OPENAI, source: "api" }],
    ["openai/gpt-4.1", "openai", 1047576, TH_OFF],
    ["openai/gpt-4.1-mini", "openai", 1047576, TH_OFF],
    ["openai/gpt-4o", "openai", 128000, TH_OFF],
    ["anthropic/claude-opus-4.5", "anthropic", 200000, { ...TH_CLAUDE, source: "api" }],
    ["anthropic/claude-sonnet-4.5", "anthropic", 1000000, { ...TH_CLAUDE, source: "api" }],
    ["anthropic/claude-haiku-4.5", "anthropic", 200000, TH_OPENAI],
    ["google/gemini-2.5-pro", "google", 1048576, TH_OPENAI],
    ["google/gemini-2.5-flash", "google", 1048576, TH_OPENAI],
    ["deepseek/deepseek-v3.2", "deepseek", 128000, TH_OFF],
    ["deepseek/deepseek-r1", "deepseek", 128000, { supported: true, levels: [], source: "heuristique" }],
    ["mistralai/mistral-large-2411", "mistralai", 128000, TH_OFF],
    ["mistralai/magistral-medium", "mistralai", 40000, { supported: true, levels: [], source: "heuristique" }],
    ["mistralai/mistral-small-3.2", "mistralai", 128000, TH_OFF],
    ["qwen/qwen3-235b-a22b", "qwen", 131072, { ...TH_OPENAI, levels: ["low", "high"] }],
    ["qwen/qwen3-coder", "qwen", 262144, TH_OFF],
    ["meta-llama/llama-4-maverick", "meta-llama", 1048576, TH_OFF],
    ["x-ai/grok-4", "x-ai", 256000, TH_OPENAI],
    ["moonshotai/kimi-k2", "moonshotai", 131072, TH_OFF],
    ["z-ai/glm-4.6", "z-ai", 200000, TH_OPENAI],
  ];
  return base.map(([id, owned_by, context_length, thinking]) => ({ id, owned_by, context_length, thinking }));
}

function modelesChoix(): ModeleChoix[] {
  return providers.flatMap((p) =>
    p.models.map((m) => ({
      key: `${p.id}::${m.id}`,
      provider_id: p.id,
      provider_name: p.name,
      model_id: m.id,
      label: m.label ?? m.id,
      thinking: m.thinking,
    })),
  );
}

// ─── Conversations ───────────────────────────────────────────────────────────

const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString();

const docArticle = (id: string, num: string, sous_titre: string, date: string | null = null): DocRef => ({
  kind: "article",
  id,
  titre: `CGI, art. ${num}`,
  sous_titre,
  date,
});

const conversations: Conversation[] = [
  {
    id: "conv-demo",
    title: "Apport-cession et remploi",
    updated_at: ago(42),
    messages: [
      {
        id: "m-demo-u",
        role: "user",
        parts: [{ type: "text", text: "Quel est le délai de remploi après un apport-cession en 150-0 B ter ?" }],
        created_at: ago(44),
      },
      {
        id: "m-demo-a",
        role: "assistant",
        created_at: ago(43),
        model_key: "anthropic::claude-opus-4-5",
        thinking_level: "medium",
        usage: { input_tokens: 18230, output_tokens: 412, cache_read_tokens: 15020 },
        parts: [
          { type: "thinking", text: "La question porte sur le 2° du I de l'article 150-0 B ter. Je lis l'article en vigueur." },
          {
            type: "tool",
            call_id: "demo-1",
            name: "lire_article",
            arguments: { texte: "CGI", num: "150-0 B ter" },
            status: "done",
            summary: "Article en vigueur depuis le 01/01/2024",
            documents: [docArticle(A_150_0_B_TER, "150-0 B ter", "En vigueur · depuis le 1er janvier 2024")],
          },
          {
            type: "text",
            text:
              "Lorsque la société bénéficiaire cède les titres apportés **dans les trois ans** de l'apport, le report est maintenu si elle s'engage à réinvestir **au moins 60 %** du produit de cession **dans un délai de deux ans** à compter de la cession (CGI, art. 150-0 B ter, I, 2°).\n\nLes investissements éligibles sont énumérés aux a) à d) du même 2°.",
          },
        ],
      },
    ],
  },
  { id: "conv-vide", title: "Abus de droit : critère du but exclusivement fiscal", updated_at: ago(60 * 26), messages: [] },
];

const running = new Map<string, { stopped: boolean }>();

function resume(c: Conversation) {
  return { id: c.id, title: c.title, updated_at: c.updated_at };
}

function titreDepuis(texte: string): string {
  const mots = texte.trim().split(/\s+/).slice(0, 8).join(" ");
  return mots.length > 60 ? `${mots.slice(0, 57)}…` : mots;
}

// ─── Flux SSE simulé ─────────────────────────────────────────────────────────

const REFLEXION = [
  "L'utilisateur interroge le régime d'apport-cession. ",
  "Je dois d'abord situer l'article 150-0 B ter dans le plan du CGI, ",
  "puis le lire en vigueur à la date du jour, ",
  "et vérifier l'articulation avec l'article 150-0 A (champ des gains imposables).\n\n",
  "Points à couvrir : condition de contrôle (III, 2°), délai de trois ans, ",
  "engagement de réinvestissement de 60 % sous deux ans, et risque d'abus de droit (L. 64 LPF).",
];

const REPONSE = `## Réponse courte

Le report d'imposition de l'article **150-0 B ter** s'applique automatiquement lorsque vous apportez des titres à une société soumise à l'IS **que vous contrôlez** (III, 2°). Le report prend fin notamment si la société bénéficiaire **cède les titres apportés dans les trois ans**, sauf réinvestissement.

## Conditions du maintien du report en cas de cession rapide

| Condition | Contenu | Source |
|---|---|---|
| Délai de cession | Cession dans les **3 ans** de l'apport | I, 2° |
| Quote-part réinvestie | **≥ 60 %** du produit de cession | I, 2° |
| Délai de réinvestissement | **2 ans** à compter de la cession | I, 2° |
| Emplois éligibles | Activité opérationnelle, prise de contrôle, fonds éligibles | I, 2°, a) à d) |

## Points de vigilance

1. La condition de **contrôle** s'apprécie à la date de l'apport, en tenant compte des droits détenus à l'issue de celui-ci.
2. Les gains relèvent du champ de l'article **150-0 A** ; l'assiette suit l'article 150-0 D.
3. Un montage dont le but serait *exclusivement* fiscal reste exposé à la procédure d'**abus de droit** (LPF, art. L. 64).

> Les références sont cliquables ci-dessus : ouvrez-les dans le panneau de lecture pour vérifier le texte exact et ses versions.
`;

function chunks(text: string, size: number): string[] {
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    const n = size + Math.floor(Math.random() * size);
    out.push(text.slice(i, i + n));
    i += n;
  }
  return out;
}

function streamReponse(conv: Conversation, content: string, model_key: string, thinking_level: string | null, signal?: AbortSignal | null): Response {
  const encoder = new TextEncoder();
  const state = { stopped: false };
  running.set(conv.id, state);
  let cancelled = false;

  const userMsg: Message = {
    id: newId("m"),
    role: "user",
    parts: [{ type: "text", text: content }],
    created_at: new Date().toISOString(),
  };
  conv.messages.push(userMsg);
  if (!conv.title) conv.title = titreDepuis(content);
  conv.updated_at = new Date().toISOString();

  const assistant: Message = {
    id: newId("m"),
    role: "assistant",
    parts: [],
    created_at: new Date().toISOString(),
    model_key,
    thinking_level,
  };
  const parts: Part[] = assistant.parts;
  const addDelta = (type: "thinking" | "text", text: string) => {
    const last = parts[parts.length - 1];
    if (last && last.type === type) last.text += text;
    else parts.push({ type, text });
  };

  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        if (cancelled) return;
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      };
      const alive = () => !cancelled && !state.stopped && !signal?.aborted;
      // Comme un vrai fetch : l'abandon côté client fait échouer la lecture du corps.
      signal?.addEventListener("abort", () => {
        if (cancelled) return;
        cancelled = true;
        state.stopped = true;
        controller.error(new DOMException("Lecture interrompue", "AbortError"));
      });

      send("user_message", userMsg);
      await sleep(250);
      conv.messages.push(assistant);
      send("message_start", { message_id: assistant.id, model_key, thinking_level });

      const erreur = /\berreur\b/i.test(content);
      const date = today();
      try {
        if (thinking_level) {
          for (const piece of REFLEXION.flatMap((r) => chunks(r, 12))) {
            if (!alive()) throw new Error("stop");
            addDelta("thinking", piece);
            send("thinking_delta", { text: piece });
            await sleep(35);
          }
        }
        // Outil 1 : sommaire
        const call1 = newId("call");
        const args1 = { id: "LEGISCTA000006191598", date };
        parts.push({ type: "tool", call_id: call1, name: "sommaire", arguments: args1, status: "running", documents: [] });
        send("tool_call", { call_id: call1, name: "sommaire", arguments: args1 });
        await sleep(900);
        if (!alive()) throw new Error("stop");
        const docs1: DocRef[] = [
          {
            kind: "section",
            id: "LEGISCTA000006191598",
            titre: "CGI › 1 : Plus-values de cession de valeurs mobilières…",
            sous_titre: `${compterArticles("LEGISCTA000006191598")} articles en vigueur`,
            date,
          },
        ];
        Object.assign(parts[parts.length - 1]!, { status: "done", summary: "4 articles", documents: docs1 });
        send("tool_result", { call_id: call1, status: "done", summary: "4 articles", documents: docs1 });

        if (erreur) {
          send("error", { message: "Le fournisseur a renvoyé une erreur 529 (surcharge). Réessayez dans un instant." });
          assistant.error = "Le fournisseur a renvoyé une erreur 529 (surcharge). Réessayez dans un instant.";
          throw new Error("erreur simulée");
        }

        // Outil 2 : lire_article (×2, en parallèle)
        const call2 = newId("call");
        const call3 = newId("call");
        const args2 = { texte: "CGI", num: "150-0 B ter", date };
        const args3 = { texte: "CGI", num: "150-0 A", date };
        parts.push({ type: "tool", call_id: call2, name: "lire_article", arguments: args2, status: "running", documents: [] });
        send("tool_call", { call_id: call2, name: "lire_article", arguments: args2 });
        parts.push({ type: "tool", call_id: call3, name: "lire_article", arguments: args3, status: "running", documents: [] });
        send("tool_call", { call_id: call3, name: "lire_article", arguments: args3 });
        await sleep(700);
        if (!alive()) throw new Error("stop");
        const docs2 = [docArticle(A_150_0_B_TER, "150-0 B ter", "En vigueur · depuis le 1er janvier 2024", date)];
        Object.assign(parts.find((p) => p.type === "tool" && p.call_id === call2)!, { status: "done", summary: "Version en vigueur (2024)", documents: docs2 });
        send("tool_result", { call_id: call2, status: "done", summary: "Version en vigueur (2024)", documents: docs2 });
        await sleep(300);
        const docs3 = [docArticle(A_150_0_A, "150-0 A", "En vigueur · depuis le 1er avril 2023", date)];
        Object.assign(parts.find((p) => p.type === "tool" && p.call_id === call3)!, { status: "done", summary: "Version en vigueur (2023)", documents: docs3 });
        send("tool_result", { call_id: call3, status: "done", summary: "Version en vigueur (2023)", documents: docs3 });

        // Outil 3 : rechercher (recherche plein texte)
        const call4 = newId("call");
        const args4 = { q: "abus de droit", texte: "LPF" };
        parts.push({ type: "tool", call_id: call4, name: "rechercher", arguments: args4, status: "running", documents: [] });
        send("tool_call", { call_id: call4, name: "rechercher", arguments: args4 });
        await sleep(600);
        if (!alive()) throw new Error("stop");
        const docs4: DocRef[] = [
          { kind: "recherche", id: "abus de droit", titre: "Recherche « abus de droit »", sous_titre: "1 résultat · LPF", date: null },
          { kind: "article", id: A_L64, titre: "LPF, art. L64", sous_titre: "En vigueur · procédure de l'abus de droit", date },
        ];
        Object.assign(parts[parts.length - 1]!, { status: "done", summary: "1 résultat", documents: docs4 });
        send("tool_result", { call_id: call4, status: "done", summary: "1 résultat", documents: docs4 });

        if (thinking_level) {
          const t = "\n\nLes textes confirment le délai de 3 ans et le réinvestissement de 60 % sous 2 ans. Je rédige.";
          for (const piece of chunks(t, 14)) {
            if (!alive()) throw new Error("stop");
            addDelta("thinking", piece);
            send("thinking_delta", { text: piece });
            await sleep(30);
          }
        }
        for (const piece of chunks(REPONSE, 6)) {
          if (!alive()) throw new Error("stop");
          addDelta("text", piece);
          send("text_delta", { text: piece });
          await sleep(18);
        }
      } catch {
        /* arrêt ou erreur simulée : on termine proprement */
      }
      const usage = { input_tokens: 21480, output_tokens: 1260, cache_read_tokens: 17950 };
      assistant.usage = usage;
      for (const p of parts) if (p.type === "tool" && p.status === "running") Object.assign(p, { status: "error", summary: "Interrompu" });
      send("message_end", { message_id: assistant.id, usage });
      conv.updated_at = new Date().toISOString();
      running.delete(conv.id);
      if (!cancelled) controller.close();
    },
    cancel() {
      cancelled = true;
      state.stopped = true;
    },
  });

  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

// ─── Routeur ─────────────────────────────────────────────────────────────────

async function readBody<T>(init?: RequestInit): Promise<T> {
  if (!init?.body || typeof init.body !== "string") return {} as T;
  return JSON.parse(init.body) as T;
}

export async function mockFetch(input: string, init?: RequestInit): Promise<Response> {
  const u = new URL(input, "http://maquette.local/");
  const path = u.pathname.replace(/^\/api/, "");
  const method = (init?.method ?? "GET").toUpperCase();
  const q = u.searchParams;
  const seg = path.split("/").filter(Boolean).map(decodeURIComponent);
  await sleep(120 + Math.random() * 180);

  // /providers
  if (seg[0] === "providers") {
    if (seg.length === 1 && method === "GET") return json(providers);
    if (seg.length === 1 && method === "POST") {
      const b = await readBody<{ name: string; type: "openai" | "anthropic"; base_url: string; api_key: string }>(init);
      if (!b.name?.trim()) return json({ detail: "Le nom est obligatoire" }, 422);
      const p: Fournisseur = {
        id: newId("prov"),
        name: b.name.trim(),
        type: b.type,
        base_url: b.base_url,
        api_key_set: !!b.api_key,
        models: [],
      };
      providers.push(p);
      return json(p);
    }
    const p = providers.find((x) => x.id === seg[1]);
    if (!p) return notFound("Fournisseur introuvable");
    if (seg.length === 2 && method === "PATCH") {
      const b = await readBody<{ name?: string; base_url?: string; api_key?: string }>(init);
      if (b.name !== undefined) p.name = b.name;
      if (b.base_url !== undefined) p.base_url = b.base_url;
      if (b.api_key !== undefined && b.api_key !== "") p.api_key_set = true;
      return json(p);
    }
    if (seg.length === 2 && method === "DELETE") {
      providers.splice(providers.indexOf(p), 1);
      if (settings.default_model_key?.startsWith(`${p.id}::`)) settings = { ...settings, default_model_key: null };
      return noContent();
    }
    if (seg[2] === "remote-models" && method === "GET") {
      await sleep(600);
      if (/erreur|invalid/i.test(p.base_url))
        return json({ detail: `Le fournisseur a répondu 401 Unauthorized sur ${p.base_url}/models` }, 502);
      const enabled = new Set(p.models.map((m) => m.id));
      return json(remoteCatalogue(p).map((m) => ({ ...m, enabled: enabled.has(m.id) })));
    }
    if (seg[2] === "models" && method === "PUT") {
      const b = await readBody<{ models: ModeleActive[] }>(init);
      p.models = b.models;
      return json(p);
    }
  }

  if (seg[0] === "models" && method === "GET") return json(modelesChoix());

  if (seg[0] === "settings") {
    if (method === "GET") return json(settings);
    if (method === "PUT") {
      settings = await readBody<Reglages>(init);
      return json(settings);
    }
  }

  // /conversations
  if (seg[0] === "conversations") {
    if (seg.length === 1 && method === "GET") {
      return json([...conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(resume));
    }
    if (seg.length === 1 && method === "POST") {
      const b = await readBody<{ title?: string }>(init);
      const c: Conversation = { id: newId("conv"), title: b.title ?? "", updated_at: new Date().toISOString(), messages: [] };
      conversations.push(c);
      return json(c);
    }
    const c = conversations.find((x) => x.id === seg[1]);
    if (!c) return notFound("Conversation introuvable");
    if (seg.length === 2 && method === "GET") return json(c);
    if (seg.length === 2 && method === "PATCH") {
      const b = await readBody<{ title: string }>(init);
      c.title = b.title;
      c.updated_at = new Date().toISOString();
      return json(resume(c));
    }
    if (seg.length === 2 && method === "DELETE") {
      conversations.splice(conversations.indexOf(c), 1);
      return noContent();
    }
    if (seg[2] === "stop" && method === "POST") {
      const r = running.get(c.id);
      if (r) r.stopped = true;
      return noContent();
    }
    if (seg[2] === "messages" && method === "POST") {
      const b = await readBody<{ content: string; model_key: string; thinking_level: string | null }>(init);
      if (!b.content?.trim()) return json({ detail: "Message vide" }, 422);
      if (!modelesChoix().some((m) => m.key === b.model_key))
        return json({ detail: `Modèle inconnu : ${b.model_key}` }, 400);
      return streamReponse(c, b.content, b.model_key, b.thinking_level, init?.signal);
    }
  }

  // /documents
  if (seg[0] === "documents") {
    const date = q.get("date");
    if (seg[1] === "article" && seg[2]) {
      const v = vueArticle(seg[2], date);
      return v ? json(v) : notFound("Article introuvable");
    }
    if ((seg[1] === "section" || seg[1] === "texte") && seg[2]) {
      const v = vueNoeud(seg[2], date);
      return v ? json(v) : notFound("Nœud introuvable");
    }
    if (seg[1] === "recherche") {
      const texteParam = q.get("texte");
      const cid = texteParam ? (textes.find((t) => t.cid === texteParam || t.sigle === texteParam)?.cid ?? texteParam) : null;
      return json({ resultats: rechercher(q.get("q") ?? "", cid) });
    }
  }

  if (seg[0] === "textes" && method === "GET") return json(textes);
  if (seg[0] === "health") return json({ ok: true, db: { articles: Object.keys(articles).length, derniere_ingestion: today() } });
  if (seg[0] === "tools") return json([]);

  return notFound(`Route inconnue (maquette) : ${method} ${path}`);
}
