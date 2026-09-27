import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Search } from "lucide-react";

export type DropdownOption = {
  value: string;
  label: string;
  /** Regroupement (ex. fournisseur). Les options d'un même groupe doivent être contiguës. */
  group?: string;
  /** Texte secondaire à droite (ex. identifiant, niveau). */
  hint?: string;
};

type Props = {
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
  /** Icône affichée dans le déclencheur, avant la valeur. */
  icon?: ReactNode;
  placeholder?: string;
  /** Champ de recherche : `"auto"` (défaut) l'affiche au-delà de 8 options. */
  searchable?: boolean | "auto";
  searchPlaceholder?: string;
  /** `pill` : compact, pour la barre du compositeur ; `field` : champ de formulaire pleine largeur. */
  variant?: "pill" | "field";
  disabled?: boolean;
  title?: string;
  minPopoverWidth?: number;
};

const norm = (s: string) =>
  s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

type Pos = { left: number; width: number; maxHeight: number; top?: number; bottom?: number };

export function Dropdown({
  value,
  options,
  onChange,
  ariaLabel,
  icon,
  placeholder = "Choisir…",
  searchable = "auto",
  searchPlaceholder = "Rechercher…",
  variant = "pill",
  disabled,
  title,
  minPopoverWidth = 240,
}: Props) {
  const uid = useId();
  const listId = `${uid}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [pos, setPos] = useState<Pos | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const withSearch = searchable === "auto" ? options.length > 8 : searchable;
  const selected = options.find((o) => o.value === value) ?? null;

  const filtered = useMemo(() => {
    const words = norm(query).split(/\s+/).filter(Boolean);
    if (words.length === 0) return options;
    return options.filter((o) => {
      const hay = norm(`${o.label} ${o.group ?? ""} ${o.hint ?? ""} ${o.value}`);
      return words.every((w) => hay.includes(w));
    });
  }, [options, query]);

  const place = useCallback(() => {
    const t = triggerRef.current;
    if (!t) return;
    const r = t.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = Math.min(Math.max(r.width, minPopoverWidth), vw - 16);
    const left = Math.min(Math.max(8, r.left), vw - width - 8);
    const below = vh - r.bottom - 12;
    const above = r.top - 12;
    const wanted = 380;
    if (below >= Math.min(wanted, 260) || below >= above) {
      setPos({ left, width, top: r.bottom + 6, maxHeight: Math.min(wanted, below) });
    } else {
      setPos({ left, width, bottom: vh - r.top + 6, maxHeight: Math.min(wanted, above) });
    }
  }, [minPopoverWidth]);

  const openMenu = () => {
    if (disabled) return;
    setQuery("");
    const i = options.findIndex((o) => o.value === value);
    setActive(Math.max(0, i));
    place();
    setOpen(true);
  };

  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  };

  const choose = (o: DropdownOption | undefined) => {
    if (!o) return;
    onChange(o.value);
    close();
  };

  // Focus à l'ouverture
  useLayoutEffect(() => {
    if (!open) return;
    if (withSearch) inputRef.current?.focus();
    else listRef.current?.focus();
  }, [open, withSearch]);

  // Garde l'option active visible
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  // Réinitialise l'option active quand le filtre change
  useEffect(() => {
    if (!open) return;
    const i = filtered.findIndex((o) => o.value === value);
    setActive(query ? 0 : Math.max(0, i));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  // Fermeture au clic extérieur, repositionnement au défilement / redimensionnement
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (popRef.current?.contains(t) || triggerRef.current?.contains(t)) return;
      close(false);
    };
    const onScroll = (e: Event) => {
      if (popRef.current && e.target instanceof Node && popRef.current.contains(e.target)) return;
      place();
    };
    window.addEventListener("mousedown", onDown, true);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      window.removeEventListener("mousedown", onDown, true);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, place]);

  const onPopKey = (e: KeyboardEvent) => {
    const n = filtered.length;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (n) setActive((a) => (a + 1) % n);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (n) setActive((a) => (a - 1 + n) % n);
        break;
      case "Home":
        if (!withSearch) {
          e.preventDefault();
          setActive(0);
        }
        break;
      case "End":
        if (!withSearch) {
          e.preventDefault();
          setActive(Math.max(0, n - 1));
        }
        break;
      case "PageDown":
        e.preventDefault();
        setActive((a) => Math.min(n - 1, a + 8));
        break;
      case "PageUp":
        e.preventDefault();
        setActive((a) => Math.max(0, a - 8));
        break;
      case "Enter":
        e.preventDefault();
        choose(filtered[active]);
        break;
      case "Escape":
        e.preventDefault();
        e.stopPropagation();
        close();
        break;
      case "Tab":
        close(false);
        break;
      default:
        // Saisie directe sans champ de recherche : saute à la première option qui commence ainsi.
        if (!withSearch && e.key.length === 1 && /\S/.test(e.key)) {
          const k = norm(e.key);
          const start = active + 1;
          for (let j = 0; j < n; j++) {
            const idx = (start + j) % n;
            if (norm(filtered[idx]!.label).startsWith(k)) {
              setActive(idx);
              break;
            }
          }
        }
    }
  };

  const onTriggerKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) openMenu();
    }
  };

  const activeId = filtered[active] ? `${uid}-opt-${active}` : undefined;

  // Rendu des options avec en-têtes de groupe
  const rows: ReactNode[] = [];
  let lastGroup: string | undefined;
  filtered.forEach((o, i) => {
    if (o.group && o.group !== lastGroup) {
      rows.push(
        <div key={`g-${o.group}-${i}`} className="dd-group" role="presentation">
          {o.group}
        </div>,
      );
    }
    lastGroup = o.group;
    const isSel = o.value === value;
    rows.push(
      <div
        key={o.value}
        id={`${uid}-opt-${i}`}
        data-index={i}
        role="option"
        aria-selected={isSel}
        className={`dd-opt ${i === active ? "active" : ""} ${isSel ? "selected" : ""}`}
        onMouseMove={() => i !== active && setActive(i)}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => choose(o)}
      >
        <span className="dd-check" aria-hidden>
          {isSel && <Check size={14} />}
        </span>
        <span className="dd-label">{o.label}</span>
        {o.hint && <span className="dd-hint">{o.hint}</span>}
      </div>,
    );
  });

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`dd-trigger dd-${variant} ${open ? "open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={`${ariaLabel} : ${selected?.label ?? placeholder}`}
        title={title}
        disabled={disabled}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={onTriggerKey}
      >
        {icon && <span className="dd-icon" aria-hidden>{icon}</span>}
        <span className={`dd-value ${selected ? "" : "placeholder"}`}>{selected?.label ?? placeholder}</span>
        <ChevronDown size={14} className="dd-chev" aria-hidden />
      </button>
      {open &&
        pos &&
        createPortal(
          <div
            ref={popRef}
            className={`dd-pop ${pos.bottom !== undefined ? "up" : "down"}`}
            style={{ left: pos.left, width: pos.width, top: pos.top, bottom: pos.bottom, maxHeight: pos.maxHeight }}
            onKeyDown={onPopKey}
          >
            {withSearch && (
              <div className="dd-search">
                <Search size={14} aria-hidden />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={searchPlaceholder}
                  role="combobox"
                  aria-expanded
                  aria-controls={listId}
                  aria-activedescendant={activeId}
                  aria-autocomplete="list"
                  aria-label={`${ariaLabel} : rechercher`}
                  spellCheck={false}
                />
              </div>
            )}
            <div
              ref={listRef}
              id={listId}
              className="dd-list"
              role="listbox"
              aria-label={ariaLabel}
              tabIndex={-1}
              aria-activedescendant={withSearch ? undefined : activeId}
            >
              {rows.length ? rows : <div className="dd-empty">Aucun résultat pour « {query} »</div>}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
