"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Brand, errText } from "@/lib/api";
import { useBrand, useUser } from "@/components/Shell";
import { Badge, Button, EmptyState, Skeleton } from "@/components/ui";
import { BrandEditor } from "../BrandEditor";
import { BrandLogo } from "../BrandLogo";

export function BrandDetails({ startEditing = false }: { startEditing?: boolean }) {
  const { id } = useParams<{ id: string }>();
  const user = useUser();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { activeBrandId, setActiveBrand } = useBrand();
  const [editing, setEditing] = useState(startEditing);
  const [archiveConfirm, setArchiveConfirm] = useState(false);
  const [actionError, setActionError] = useState("");
  const brandQuery = useQuery({ queryKey: ["brand", id], queryFn: () => api.brand(id), enabled: !!id });
  const rulesQuery = useQuery({ queryKey: ["brand-rules", id], queryFn: () => api.rules(id), enabled: !!id });
  const factsQuery = useQuery({ queryKey: ["brand-facts", id], queryFn: () => api.facts(id), enabled: !!id });
  const termsQuery = useQuery({ queryKey: ["brand-terms", id], queryFn: () => api.terms(id), enabled: !!id });

  async function archive() {
    setActionError("");
    try {
      await api.archiveBrand(id);
      await queryClient.invalidateQueries({ queryKey: ["brands"] });
      await queryClient.invalidateQueries({ queryKey: ["brand-management"] });
      if (activeBrandId === id) setActiveBrand(null);
      router.push("/brands");
    } catch (error) {
      setActionError(errText(error));
    }
  }

  if (brandQuery.isPending) return <main className="product-page"><Skeleton /><Skeleton /></main>;
  if (brandQuery.isError) return <main className="product-page"><p className="alert error" role="alert">{errText(brandQuery.error)}</p><Link className="btn" href="/brands">Back to brands</Link></main>;
  const brand = brandQuery.data;
  const isAdmin = user.role === "admin";

  if (editing && isAdmin && brand.status === "active") {
    return <main className="product-page">
      <header className="page-heading product-heading"><div><h1>Edit {brand.name}</h1><p className="mu">Update the brand identity and guidance shown to your team.</p></div><Link className="btn" href={`/brands/${id}`}>Cancel</Link></header>
      <BrandEditor
        initial={brand}
        onSaved={saved => {
          queryClient.setQueryData(["brand", id], saved);
          void queryClient.invalidateQueries({ queryKey: ["brands"] });
          void queryClient.invalidateQueries({ queryKey: ["brand-management"] });
          setEditing(false);
          router.replace(`/brands/${id}`);
        }}
      />
    </main>;
  }

  const kbLoading = rulesQuery.isPending || factsQuery.isPending || termsQuery.isPending;
  const kbError = rulesQuery.error || factsQuery.error || termsQuery.error;
  const sharedCount = [...(rulesQuery.data ?? []), ...(factsQuery.data ?? []), ...(termsQuery.data ?? [])]
    .filter(record => !record.brand_id).length;
  return <main className="product-page brand-details">
    <header className="page-heading product-heading">
      <div><p className="eyebrow">Brand workspace</p><h1>{brand.name}</h1><p className="mu">{brand.industry || "Industry not specified"}{brand.website_url ? ` · ${brand.website_url}` : ""}</p></div>
      <div className="brand-card-actions">
        <Button onClick={() => setActiveBrand(brand.id)} disabled={activeBrandId === brand.id}>{activeBrandId === brand.id ? "Active brand" : "Use this brand"}</Button>
        {isAdmin && brand.status === "active" && <Button variant="secondary" onClick={() => setEditing(true)}>Edit brand</Button>}
        {isAdmin && brand.status === "active" && <Button variant="danger" onClick={() => setArchiveConfirm(value => !value)}>Archive</Button>}
      </div>
    </header>
    {brand.status === "archived" && <p className="alert">This brand is archived. Its history and knowledge records are retained.</p>}
    {actionError && <p className="alert error" role="alert">{actionError}</p>}
    {archiveConfirm && <section className="brand-archive-confirm" role="alertdialog" aria-label="Confirm brand archive">
      <div><h2>Archive {brand.name}?</h2><p>The brand will no longer be selectable for new content or knowledge records.</p></div>
      <div className="brand-card-actions"><Button variant="ghost" onClick={() => setArchiveConfirm(false)}>Cancel</Button><Button variant="danger" onClick={() => void archive()}>Confirm archive</Button></div>
    </section>}
    <section className="brand-hero-panel">
      <BrandLogo brand={brand} className="brand-logo-large" />
      <div><h2>Overview</h2><p>{brand.description || "No brand description has been added."}</p>{brand.website_url && <a href={brand.website_url} target="_blank" rel="noreferrer">{brand.website_url}</a>}</div>
      <div className="brand-colours">
        <span><i style={{ backgroundColor: brand.primary_colour || "#e8edf0" }} />Primary {brand.primary_colour || "Not set"}</span>
        <span><i style={{ backgroundColor: brand.secondary_colour || "#e8edf0" }} />Secondary {brand.secondary_colour || "Not set"}</span>
      </div>
    </section>
    <div className="brand-details-grid">
      <section className="brand-info-panel"><h2>Voice and audience</h2><dl><div><dt>Brand voice</dt><dd>{brand.voice || "Not specified"}</dd></div><div><dt>Target audience</dt><dd>{brand.target_audience || "Not specified"}</dd></div></dl></section>
      <section className="brand-info-panel"><h2>Mission and vision</h2><dl><div><dt>Mission</dt><dd>{brand.mission || "Not specified"}</dd></div><div><dt>Vision</dt><dd>{brand.vision || "Not specified"}</dd></div></dl></section>
    </div>
    <section className="brand-info-panel"><h2>Brand guidelines</h2><p className="brand-guidelines-copy">{brand.guidelines || "No written brand guidelines have been added."}</p></section>
    <section className="brand-info-panel">
      <div className="brand-kb-heading"><div><h2>Related knowledge base</h2><p className="mu">Approved rules, facts, and terms available to this brand workspace.</p></div>{["admin", "manager"].includes(user.role) && <Link className="btn" href="/brand-knowledge">Open knowledge base</Link>}</div>
      {kbLoading ? <div role="status"><Skeleton /><Skeleton /></div>
        : kbError ? <p className="alert error" role="alert">{errText(kbError)}</p>
          : <div className="brand-kb-summary">
            <div><strong>{rulesQuery.data?.length ?? 0}</strong><span>rules</span></div>
            <div><strong>{factsQuery.data?.length ?? 0}</strong><span>facts</span></div>
            <div><strong>{termsQuery.data?.length ?? 0}</strong><span>terms</span></div>
            {sharedCount > 0 && <p>{sharedCount} records are organisation-wide shared guidance, retained from the existing knowledge base.</p>}
            {!rulesQuery.data?.length && !factsQuery.data?.length && !termsQuery.data?.length && <EmptyState title="No knowledge records yet" description="Add approved guidance, facts, or terminology in Brand knowledge." />}
          </div>}
      {!kbLoading && !kbError && <div className="brand-kb-records">
        {(rulesQuery.data ?? []).slice(0, 3).map(rule => <article key={rule.id}><Badge tone="neutral">{rule.brand_id ? "Brand-specific rule" : "Shared rule"}</Badge><p>{rule.clause_number}: {rule.text}</p></article>)}
        {(factsQuery.data ?? []).slice(0, 3).map(fact => <article key={fact.id}><Badge tone="neutral">{fact.brand_id ? "Brand-specific fact" : "Shared fact"}</Badge><p>{fact.text}</p></article>)}
      </div>}
    </section>
    <footer className="brand-details-footer"><span>Created {new Date(brand.created_at).toLocaleString()}</span><Link href="/brands">Back to brand management</Link></footer>
  </main>;
}
