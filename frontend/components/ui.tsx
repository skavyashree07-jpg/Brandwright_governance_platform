"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  DragEvent,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

export type ButtonVariant = "primary" | "secondary" | "tertiary" | "danger" | "ghost";
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  size?: "sm" | "md" | "lg";
};

export function Button({ variant = "secondary", size = "md", loading = false, disabled, children, ...props }: ButtonProps) {
  return <button {...props} className={`ds-button ds-button-${variant} ds-button-${size} ${props.className ?? ""}`} disabled={disabled || loading} aria-busy={loading || undefined}>
    {loading && <span className="ds-spinner" aria-hidden="true" />}
    {children}
  </button>;
}

type FieldProps = { label: string; error?: string; hint?: string; id?: string };
export function Input({ label, error, hint, id, ...props }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  return <div className="ds-field">
    <label htmlFor={controlId}>{label}</label>
    <input {...props} id={controlId} className={`ds-input ${error ? "ds-invalid" : ""} ${props.className ?? ""}`} aria-invalid={error ? true : undefined} aria-describedby={[hint ? `${controlId}-hint` : "", error ? `${controlId}-error` : ""].filter(Boolean).join(" ") || undefined} />
    {hint && <span className="ds-hint" id={`${controlId}-hint`}>{hint}</span>}
    {error && <span className="ds-error" id={`${controlId}-error`}>{error}</span>}
  </div>;
}

export function Textarea({ label, error, hint, id, ...props }: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  return <div className="ds-field">
    <label htmlFor={controlId}>{label}</label>
    <textarea {...props} id={controlId} className={`ds-textarea ${error ? "ds-invalid" : ""} ${props.className ?? ""}`} aria-invalid={error ? true : undefined} aria-describedby={[hint ? `${controlId}-hint` : "", error ? `${controlId}-error` : ""].filter(Boolean).join(" ") || undefined} />
    {hint && <span className="ds-hint" id={`${controlId}-hint`}>{hint}</span>}
    {error && <span className="ds-error" id={`${controlId}-error`}>{error}</span>}
  </div>;
}

type SelectOption = { value: string; label: string };
export function Select({ label, options, error, hint, id, ...props }: FieldProps & SelectHTMLAttributes<HTMLSelectElement> & { options: SelectOption[] }) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  return <div className="ds-field">
    <label htmlFor={controlId}>{label}</label>
    <select {...props} id={controlId} className={`ds-select ${error ? "ds-invalid" : ""} ${props.className ?? ""}`} aria-invalid={error ? true : undefined} aria-describedby={[hint ? `${controlId}-hint` : "", error ? `${controlId}-error` : ""].filter(Boolean).join(" ") || undefined}>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
    {hint && <span className="ds-hint" id={`${controlId}-hint`}>{hint}</span>}
    {error && <span className="ds-error" id={`${controlId}-error`}>{error}</span>}
  </div>;
}

export function Combobox({ label, options, hint, id, ...props }: FieldProps & InputHTMLAttributes<HTMLInputElement> & { options: string[] }) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const listId = `${controlId}-options`;
  return <div className="ds-field">
    <label htmlFor={controlId}>{label}</label>
    <input {...props} id={controlId} className={`ds-input ${props.className ?? ""}`} list={listId} aria-describedby={hint ? `${controlId}-hint` : undefined} />
    <datalist id={listId}>{options.map(option => <option key={option} value={option} />)}</datalist>
    {hint && <span className="ds-hint" id={`${controlId}-hint`}>{hint}</span>}
  </div>;
}

export function Checkbox({ label, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: string }) {
  const id = useId();
  return <label className="ds-check" htmlFor={id}><input {...props} id={id} type="checkbox" /><span>{label}</span></label>;
}

export function Radio({ name, label, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { name: string; label: string }) {
  const id = useId();
  return <label className="ds-check" htmlFor={id}><input {...props} id={id} name={name} type="radio" /><span>{label}</span></label>;
}

export function Switch({ label, checked, onChange, disabled = false, id, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "checked" | "onChange"> & { label: string; checked: boolean; onChange: (checked: boolean) => void; id?: string }) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  return <label className={`ds-switch ${disabled ? "is-disabled" : ""}`} htmlFor={controlId}>
    <input {...props} id={controlId} type="checkbox" role="switch" checked={checked} disabled={disabled} onChange={event => onChange(event.target.checked)} />
    <span className="ds-switch-track" aria-hidden="true"><span /></span><span>{label}</span>
  </label>;
}

export function Tabs({ tabs, label = "Sections" }: { tabs: { value: string; label: string; content: ReactNode; disabled?: boolean }[]; label?: string }) {
  return <TabsPrimitive.Root className="ds-tabs" defaultValue={tabs[0]?.value}>
    <TabsPrimitive.List className="ds-tab-list" aria-label={label}>
      {tabs.map(tab => <TabsPrimitive.Trigger className="ds-tab-trigger" key={tab.value} value={tab.value} disabled={tab.disabled}>{tab.label}</TabsPrimitive.Trigger>)}
    </TabsPrimitive.List>
    {tabs.map(tab => <TabsPrimitive.Content className="ds-tab-panel" key={tab.value} value={tab.value}>{tab.content}</TabsPrimitive.Content>)}
  </TabsPrimitive.Root>;
}

export type TableColumn<Row> = { key: keyof Row & string; header: string; render?: (row: Row) => ReactNode; sortable?: boolean };
export function Table<Row extends Record<string, unknown>>({ rows, columns, caption, rowKey }: { rows: Row[]; columns: TableColumn<Row>[]; caption: string; rowKey: keyof Row & string }) {
  const [sortKey, setSortKey] = useState<keyof Row & string | null>(null);
  const [ascending, setAscending] = useState(true);
  const [hidden, setHidden] = useState<string[]>([]);
  const shownColumns = columns.filter(column => !hidden.includes(column.key));
  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? ""), undefined, { numeric: true }) * (ascending ? 1 : -1));
  }, [ascending, rows, sortKey]);
  function sort(column: TableColumn<Row>) {
    if (!column.sortable) return;
    if (sortKey === column.key) setAscending(value => !value);
    else { setSortKey(column.key); setAscending(true); }
  }
  function toggleColumn(key: string) {
    if (!hidden.includes(key) && shownColumns.length === 1) return;
    setHidden(current => current.includes(key) ? current.filter(item => item !== key) : [...current, key]);
  }
  return <div className="ds-table-region">
    <details className="ds-column-picker">
      <summary>Columns</summary>
      <div role="group" aria-label="Visible table columns">{columns.map(column => <Checkbox key={column.key} label={column.header} checked={!hidden.includes(column.key)} onChange={() => toggleColumn(column.key)} />)}</div>
    </details>
    <div className="ds-table-scroll" tabIndex={0} role="region" aria-label={`${caption} table`}>
      <table className="ds-table">
        <caption>{caption}</caption>
        <thead><tr>{shownColumns.map(column => <th key={column.key} scope="col" aria-sort={sortKey === column.key ? (ascending ? "ascending" : "descending") : undefined}>
          {column.sortable ? <button className="ds-sort-button" onClick={() => sort(column)}>{column.header}<span aria-hidden="true">{sortKey === column.key ? (ascending ? " ↑" : " ↓") : " ↕"}</span></button> : column.header}
        </th>)}</tr></thead>
        <tbody>{sortedRows.map(row => <tr key={String(row[rowKey])}>{shownColumns.map(column => <td key={column.key} data-label={column.header}>{column.render ? column.render(row) : String(row[column.key] ?? "")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  </div>;
}

export function Card({ children, title, action, className = "" }: { children: ReactNode; title?: string; action?: ReactNode; className?: string }) {
  return <section className={`ds-card ${className}`}>{(title || action) && <header className="ds-card-header">{title && <h3>{title}</h3>}{action}</header>}{children}</section>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger" | "info" }) {
  return <span className={`ds-badge ds-badge-${tone}`}>{children}</span>;
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return <span className="ds-tooltip-wrap" aria-describedby={id}>{children}<span id={id} className="ds-tooltip" role="tooltip">{label}</span></span>;
}

export function Dialog({ open, onClose, title, children, labelledBy, className = "" }: { open: boolean; onClose: () => void; title: string; children: ReactNode; labelledBy?: string; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return <dialog ref={ref} className={`ds-dialog ${className}`} aria-labelledby={labelledBy ?? titleId} onCancel={event => { event.preventDefault(); onClose(); }} onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); onClose(); } }} onClick={event => { if (event.target === ref.current) onClose(); }}>
    <header><h2 id={labelledBy ?? titleId}>{title}</h2><Button variant="ghost" aria-label="Close dialog" onClick={onClose}>Close</Button></header>
    <div>{children}</div>
  </dialog>;
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return <Dialog open={open} onClose={onClose} title={title} className="ds-drawer">{children}</Dialog>;
}

export function DropdownMenu({ label, children }: { label: string; children: ReactNode }) {
  return <details className="ds-dropdown"><summary>{label}</summary><div className="ds-dropdown-panel">{children}</div></details>;
}

export function Toast({ message, tone = "success", onDismiss }: { message: string; tone?: "success" | "warning" | "danger" | "info"; onDismiss?: () => void }) {
  return <div className={`ds-toast ds-toast-${tone}`} role={tone === "danger" ? "alert" : "status"} aria-live={tone === "danger" ? "assertive" : "polite"}>{message}{onDismiss && <Button variant="ghost" onClick={onDismiss} aria-label="Dismiss notification">Dismiss</Button>}</div>;
}

export function Skeleton({ label = "Loading", className = "" }: { label?: string; className?: string }) {
  return <span className={`ds-skeleton ${className}`} role="status"><span className="sr-only">{label}</span></span>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="ds-empty"><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export function StatCard({ label, value, change, tone = "neutral" }: { label: string; value: ReactNode; change?: string; tone?: "neutral" | "success" | "warning" | "danger" }) {
  return <article className="ds-stat"><span>{label}</span><strong>{value}</strong>{change && <small className={`ds-stat-${tone}`}>{change}</small>}</article>;
}

export function Progress({ value, label }: { value: number; label: string }) {
  const bounded = Math.max(0, Math.min(100, value));
  return <div className="ds-progress"><label>{label}<progress max={100} value={bounded}>{bounded}%</progress></label><span>{bounded}%</span></div>;
}

export function Avatar({ name, src, size = "md" }: { name: string; src?: string; size?: "sm" | "md" | "lg" }) {
  const initials = name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "?";
  return <span className={`ds-avatar ds-avatar-${size}`} role="img" aria-label={name}>{src ? <img src={src} alt="" /> : initials}</span>;
}

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return <nav className="ds-breadcrumbs" aria-label="Breadcrumb"><ol>{items.map((item, index) => <li key={`${item.label}-${index}`}>{item.href && index < items.length - 1 ? <a href={item.href}>{item.label}</a> : <span aria-current={index === items.length - 1 ? "page" : undefined}>{item.label}</span>}</li>)}</ol></nav>;
}

export function Pagination({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  return <nav className="ds-pagination" aria-label="Pagination">
    <Button disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
    <span aria-live="polite">Page {page} of {pages}</span>
    <Button disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</Button>
  </nav>;
}

export type CommandPaletteItem = {
  label: string;
  description?: string;
  keywords?: string;
  href?: string;
  group?: string;
  onSelect?: () => void | Promise<void>;
};

export function CommandPalette({ open, onClose, items, loading = false, error }: {
  open: boolean;
  onClose: () => void;
  items: CommandPaletteItem[];
  loading?: boolean;
  error?: string;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const filtered = useMemo(() => items.filter(item => `${item.label} ${item.description ?? ""} ${item.group ?? ""} ${item.keywords ?? ""}`.toLowerCase().includes(query.toLowerCase())), [items, query]);
  useEffect(() => {
    if (!open) { setQuery(""); setActionError(""); setActiveIndex(0); }
  }, [open]);
  useEffect(() => { setActiveIndex(0); }, [query]);
  async function activate(item: CommandPaletteItem) {
    if (item.onSelect) {
      setBusy(true);
      setActionError("");
      try { await item.onSelect(); onClose(); }
      catch (cause) { setActionError(cause instanceof Error ? cause.message : "The action could not be completed."); }
      finally { setBusy(false); }
    } else if (item.href) {
      router.push(item.href);
      onClose();
    }
  }
  function navigateResults(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && filtered.length) {
      event.preventDefault();
      setActiveIndex(index => (index + 1) % filtered.length);
    } else if (event.key === "ArrowUp" && filtered.length) {
      event.preventDefault();
      setActiveIndex(index => (index - 1 + filtered.length) % filtered.length);
    } else if (event.key === "Enter" && filtered[activeIndex]) {
      event.preventDefault();
      void activate(filtered[activeIndex]);
    }
  }
  return <Dialog open={open} onClose={onClose} title="Search Brandwright">
    <Input label="Search pages, submissions, rules, and facts" autoFocus value={query} onKeyDown={navigateResults} onChange={event => setQuery(event.target.value)} role="combobox" aria-expanded="true" aria-controls="command-results" aria-activedescendant={filtered[activeIndex] ? `command-result-${activeIndex}` : undefined} />
    {loading && <p role="status">Searching your organisation’s content…</p>}
    {error && <p className="alert error" role="alert">{error}</p>}
    {actionError && <p className="alert error" role="alert">{actionError}</p>}
    <ul className="ds-command-results" id="command-results" role="listbox" aria-label="Command results">{filtered.map((item, index) => <li key={`${item.group ?? ""}-${item.label}-${item.href ?? "action"}`} className={index === activeIndex ? "is-active" : ""}>
      {item.href
        ? <Link id={`command-result-${index}`} role="option" aria-selected={index === activeIndex} href={item.href} onClick={event => { if (item.onSelect) { event.preventDefault(); void activate(item); } else onClose(); }}><strong>{item.label}</strong>{item.description && <span>{item.description}</span>}</Link>
        : <button id={`command-result-${index}`} role="option" aria-selected={index === activeIndex} type="button" disabled={busy} onClick={() => void activate(item)}><strong>{busy ? "Working…" : item.label}</strong>{item.description && <span>{item.description}</span>}</button>}
    </li>)}</ul>
    {!loading && !filtered.length && <EmptyState title="No results" description="Try a different search term." />}
    <p className="ds-command-hint">Use ↑ and ↓ to move, Enter to open, Esc to close.</p>
  </Dialog>;
}

export function DiffViewer({ before, after }: { before: string; after: string }) {
  return <div className="ds-diff" aria-label="Text comparison"><section><h4>Original</h4><del>{before}</del></section><section><h4>Proposed</h4><ins>{after}</ins></section></div>;
}

export function FileDropzone({ label, accept, onFile }: { label: string; accept?: string; onFile: (file: File | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  function setFromEvent(event: ChangeEvent<HTMLInputElement>) { onFile(event.target.files?.[0] ?? null); }
  function drop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault(); setDragging(false);
    onFile(event.dataTransfer.files[0] ?? null);
  }
  return <label className={`ds-dropzone ${dragging ? "is-dragging" : ""}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
    <input ref={inputRef} type="file" accept={accept} onChange={setFromEvent} />
    <strong>{label}</strong><span>Choose a file or drag it here.</span>
  </label>;
}
