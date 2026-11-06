"use client";

import { useState } from "react";
import {
  Avatar, Badge, Breadcrumbs, Button, Card, Checkbox, Combobox, Dialog, DiffViewer,
  DropdownMenu, EmptyState, FileDropzone, Input, Pagination, Progress, Radio, Select,
  Skeleton, StatCard, Switch, Table, TableColumn, Tabs, Textarea, Toast, Tooltip,
} from "@/components/ui";

type GuidelineRow = { rule: string; category: string; status: string };
const sampleRows: GuidelineRow[] = [
  { rule: "R1.1", category: "Messaging", status: "Approved" },
  { rule: "R2.4", category: "Claims", status: "Needs review" },
  { rule: "R3.2", category: "Accessibility", status: "Approved" },
];
const sampleColumns: TableColumn<GuidelineRow>[] = [
  { key: "rule", header: "Rule", sortable: true },
  { key: "category", header: "Category", sortable: true },
  { key: "status", header: "Status", sortable: true, render: (row: GuidelineRow) => <Badge tone={row.status === "Approved" ? "success" : "warning"}>{row.status}</Badge> },
];

export default function DesignSystemPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [fileName, setFileName] = useState("");
  const [page, setPage] = useState(2);
  const [toast, setToast] = useState("Your changes were saved.");

  return <div className="design-system-page">
    <header className="ds-page-heading">
      <div>
        <p className="section-tag">BRANDWRIGHT INTERFACE</p>
        <h1>Design system</h1>
        <p className="mu">Tokens, accessible components, and interaction states used throughout the workspace.</p>
      </div>
      <Badge tone="info">Keyboard-ready components</Badge>
    </header>

    <section className="ds-section" aria-labelledby="tokens-title">
      <h2 id="tokens-title">Design tokens</h2>
      <p className="mu">Theme modes follow the operating-system preference by default. Use the top-bar theme control to choose light, dark, or high contrast.</p>
      <div className="ds-token-group">
        <h3>Colour roles</h3>
        <div className="ds-swatch-grid">
          {[
            ["Navy", "navy-900", "#14283b"], ["Navy", "navy-700", "#263d56"],
            ["Lime", "lime-500", "#d9ef68"], ["Neutral", "neutral-0", "var(--ds-surface)"],
            ["Neutral", "neutral-100", "var(--ds-surface-muted)"], ["Neutral", "neutral-700", "var(--ds-text-muted)"],
            ["Success", "success-600", "#27633a"], ["Warning", "warning-700", "#815300"],
            ["Danger", "danger-700", "#9d3028"], ["Info", "info-700", "#245a91"],
          ].map(([group, name, color]) => <div className="ds-swatch" key={`${group}-${name}`}>
            <span style={{ background: color }} />
            <strong>{name}</strong><small>{group} · {color.startsWith("var") ? "theme token" : color}</small>
          </div>)}
        </div>
      </div>
      <div className="ds-token-grid">
        <div className="ds-token-group">
          <h3>Typography</h3>
          <p className="ds-type-display">Trustworthy by design</p>
          <p className="ds-type-heading">Display · fluid 2rem to 3.25rem</p>
          <p className="ds-type-body">Body · 1rem / 1.6. Readable sans-serif for product UI.</p>
          <p className="ds-type-small">Small · .75rem / 1.5. Use for supporting labels, never essential content.</p>
        </div>
        <div className="ds-token-group">
          <h3>Space, shape, elevation</h3>
          <div className="ds-token-rows">
            <p><code>space-1</code><span>4px</span><code>space-2</code><span>8px</span><code>space-4</code><span>16px</span><code>space-8</code><span>32px</span></p>
            <p><code>radius-sm</code><span>6px</span><code>radius-md</code><span>10px</span><code>radius-lg</code><span>16px</span></p>
            <p><code>shadow-sm</code><span>Control</span><code>shadow-md</code><span>Raised surface</span></p>
            <p><code>z-sidebar</code><span>20</span><code>z-overlay</code><span>40</span><code>z-dialog</code><span>60</span></p>
            <p><code>motion-fast</code><span>120ms</span><code>motion-standard</code><span>180ms</span><code>motion-slow</code><span>260ms</span></p>
          </div>
        </div>
      </div>
      <div className="ds-token-group">
        <h3>Theme modes</h3>
        <div className="ds-theme-preview-grid">
          <div className="ds-theme-preview"><strong>Light</strong><span>Bright surface, navy text, lime action</span></div>
          <div className="ds-theme-preview dark-preview"><strong>Dark</strong><span>Deep navy surface, clear text, preserved accent</span></div>
          <div className="ds-theme-preview contrast-preview"><strong>High contrast</strong><span>Hard borders and high-contrast control states</span></div>
        </div>
      </div>
    </section>

    <section className="ds-section" aria-labelledby="actions-title">
      <h2 id="actions-title">Actions and feedback</h2>
      <div className="ds-component-grid">
        <Card title="Button variants">
          <div className="ds-demo-row"><Button variant="primary">Primary</Button><Button variant="secondary">Secondary</Button><Button variant="tertiary">Tertiary</Button><Button variant="danger">Danger</Button><Button variant="ghost">Ghost</Button></div>
          <div className="ds-demo-row"><Button loading>Saving</Button><Button disabled>Disabled</Button><Button size="sm">Small</Button><Button size="lg">Large</Button></div>
        </Card>
        <Card title="Badges and status pills">
          <div className="ds-demo-row"><Badge>Draft</Badge><Badge tone="success">Approved</Badge><Badge tone="warning">Needs review</Badge><Badge tone="danger">Blocked</Badge><Badge tone="info">In progress</Badge></div>
        </Card>
        <Card title="Tooltip and dropdown menu">
          <div className="ds-demo-row"><Tooltip label="This action records a human decision."><Button>Focus or hover for help</Button></Tooltip>
            <DropdownMenu label="More actions"><button type="button">View details</button><button type="button">Copy link</button><button type="button" disabled>Unavailable action</button></DropdownMenu>
          </div>
        </Card>
        <Card title="Toast states">
          <div className="ds-demo-stack"><Toast message={toast} onDismiss={() => setToast("Notification dismissed.")} /><Toast message="A review needs your attention." tone="warning" /><Toast message="The request could not be completed." tone="danger" /><Toast message="A new guideline version is available." tone="info" /></div>
        </Card>
        <Card title="Progress and loading">
          <Progress value={62} label="Review progress" /><div className="ds-skeleton-row"><Skeleton label="Loading rule title" /><Skeleton label="Loading rule summary" /></div>
        </Card>
        <Card title="Empty state">
          <EmptyState title="No assets uploaded" description="Upload an approved logo or image to make it available in reviews." action={<Button variant="secondary">Browse assets</Button>} />
        </Card>
      </div>
    </section>

    <section className="ds-section" aria-labelledby="forms-title">
      <h2 id="forms-title">Forms and selection</h2>
      <div className="ds-component-grid">
        <Card title="Input states">
          <div className="ds-demo-stack"><Input label="Search term" defaultValue="Brandwright" hint="Searches approved rules and facts." /><Input label="Invalid input" defaultValue=" " error="Enter a valid product name." /><Input label="Disabled input" defaultValue="Read only value" disabled /></div>
        </Card>
        <Card title="Textarea states">
          <div className="ds-demo-stack"><Textarea label="Review note" defaultValue="The suggestion keeps the original intent." /><Textarea label="Validation error" error="Add a reason before dismissing this finding." /></div>
        </Card>
        <Card title="Select and combobox">
          <div className="ds-demo-stack"><Select label="Channel" defaultValue="website" options={[{ value: "website", label: "Website" }, { value: "email", label: "Email" }, { value: "press", label: "Press" }]} /><Combobox label="Organisation role" options={["Creator", "Reviewer", "Manager", "Admin"]} hint="Type to filter available choices." /><Select label="Invalid selection" error="Choose a channel." options={[{ value: "", label: "Select a channel" }]} /></div>
        </Card>
        <Card title="Checkbox, radio, and switch">
          <div className="ds-demo-stack">
            <Checkbox label="I reviewed the source" defaultChecked />
            <Checkbox label="Disabled checkbox" disabled />
            <fieldset className="ds-choice-group"><legend>Review action</legend><Radio name="review-action" label="Approve" defaultChecked /><Radio name="review-action" label="Request changes" /></fieldset>
            <Switch label="Email me about updates" checked={notifications} onChange={setNotifications} />
            <Switch label="Disabled switch" checked={false} onChange={() => {}} disabled />
          </div>
        </Card>
        <Card title="Tabs">
          <Tabs label="Sample settings" tabs={[
            { value: "profile", label: "Profile", content: <p>Profile settings are available to the signed-in user.</p> },
            { value: "access", label: "Access", content: <p>Roles control access to review and governance tasks.</p> },
            { value: "disabled", label: "Disabled", content: <p>This panel remains keyboard accessible.</p>, disabled: true },
          ]} />
        </Card>
        <Card title="File dropzone">
          <FileDropzone label={fileName || "Upload a guideline or brand asset"} accept=".pdf,.docx,.png,.jpg" onFile={file => setFileName(file?.name ?? "")} />
          {fileName && <p className="ds-hint">Selected file: {fileName}</p>}
        </Card>
      </div>
    </section>

    <section className="ds-section" aria-labelledby="data-title">
      <h2 id="data-title">Data and navigation</h2>
      <div className="ds-component-grid">
        <Card title="Sortable table">
          <Table<GuidelineRow> rows={sampleRows} columns={sampleColumns} caption="Example approved guidelines" rowKey="rule" />
        </Card>
        <Card title="Stat cards">
          <div className="ds-stat-grid"><StatCard label="Open findings" value="8" change="2 need attention" tone="warning" /><StatCard label="Approved facts" value="24" change="Current" tone="success" /></div>
        </Card>
        <Card title="Avatar">
          <div className="ds-demo-row"><Avatar name="Mina Patel" size="sm" /><Avatar name="Kavyashree S" /><Avatar name="Brand reviewer" size="lg" /><span>Initials provide a useful fallback when no profile image is available.</span></div>
        </Card>
        <Card title="Breadcrumbs">
          <Breadcrumbs items={[{ label: "Workspace", href: "/workspace" }, { label: "Governance", href: "/insights" }, { label: "Design system" }]} />
        </Card>
        <Card title="Pagination">
          <Pagination page={page} pages={5} onChange={setPage} />
        </Card>
        <Card title="Diff viewer">
          <DiffViewer before="Brandwright is the absolute best platform." after="Brandwright helps teams review brand-aligned content." />
        </Card>
        <Card title="Dialog, drawer, and command palette">
          <div className="ds-demo-row"><Button onClick={() => setDialogOpen(true)}>Open dialog</Button><Button onClick={() => setDrawerOpen(true)}>Open drawer</Button><Button onClick={() => setCommandOpen(true)}>Open command palette</Button></div>
        </Card>
      </div>
    </section>

    <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Review confirmation">
      <p>Dialogs keep keyboard focus inside the modal and close with Escape.</p>
      <div className="ds-demo-row"><Button variant="primary" onClick={() => setDialogOpen(false)}>Confirm</Button><Button onClick={() => setDialogOpen(false)}>Cancel</Button></div>
    </Dialog>
    <Dialog open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Navigation drawer">
      <p>Use a drawer for secondary navigation on smaller screens.</p>
      <Button onClick={() => setDrawerOpen(false)}>Close drawer</Button>
    </Dialog>
    <Dialog open={commandOpen} onClose={() => setCommandOpen(false)} title="Command palette">
      <Input label="Search actions" autoFocus placeholder="Search pages and actions" />
      <p className="ds-hint">Use Ctrl+K or Cmd+K from the application shell to open global search.</p>
    </Dialog>
  </div>;
}
