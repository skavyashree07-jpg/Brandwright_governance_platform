"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, Brand, errText } from "@/lib/api";
import { useBrand, useUser } from "@/components/Shell";
import { Badge, Button, EmptyState, Input, Skeleton } from "@/components/ui";
import { BrandLogo } from "./BrandLogo";

export default function BrandsPage() {
  const user = useUser();
  const { activeBrandId, setActiveBrand } = useBrand();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Brand | null>(null);
  const [busyId, setBusyId] = useState("");
  const [actionError, setActionError] = useState("");
  const query = useQuery({
    queryKey: ["brand-management", user.organisation_id, includeArchived],
    queryFn: () => api.brands("", includeArchived),
    enabled: user.role === "admin",
  });
  const searchTerm = search.trim().toLowerCase();
  const visibleBrands = (query.data ?? []).filter(brand =>
    [brand.name, brand.industry, brand.description, brand.website_url]
      .some(value => value?.toLowerCase().includes(searchTerm)),
  );

  async function archiveBrand(brand: Brand) {
    setBusyId(brand.id);
    setActionError("");
    try {
      await api.archiveBrand(brand.id);
      setArchiveTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["brand-management"] });
      await queryClient.invalidateQueries({ queryKey: ["brands"] });
      if (activeBrandId === brand.id) setActiveBrand(null);
    } catch (error) {
      setActionError(errText(error));
    } finally {
      setBusyId("");
    }
  }

  if (user.role !== "admin") {
    return <main className="product-page"><section className="access-denied"><h1>Brand management</h1><p>Only organisation admins can create, edit, or archive brands.</p></section></main>;
  }

  return <main className="product-page brand-management">
    <header className="page-heading product-heading">
      <div><h1>Brand management</h1><p className="mu">Create and maintain distinct brand workspaces for this organisation.</p></div>
      <Link className="btn pr" href="/brands/new">Create new brand</Link>
    </header>
    <section className="brand-management-toolbar" aria-label="Brand search and filters">
      <Input label="Search brands" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name, industry, or description" />
      <label className="brand-archived-filter"><input type="checkbox" checked={includeArchived} onChange={event => setIncludeArchived(event.target.checked)} /> Include archived brands</label>
    </section>
    {actionError && <p className="alert error" role="alert">{actionError}</p>}
    {archiveTarget && <section className="brand-archive-confirm" role="alertdialog" aria-labelledby="archive-title">
      <div><h2 id="archive-title">Archive {archiveTarget.name}?</h2><p>Its history is retained, but it can no longer be selected for new work.</p></div>
      <div className="brand-card-actions">
        <Button variant="ghost" onClick={() => setArchiveTarget(null)}>Cancel</Button>
        <Button variant="danger" loading={busyId === archiveTarget.id} onClick={() => void archiveBrand(archiveTarget)}>Archive brand</Button>
      </div>
    </section>}
    {query.isPending
      ? <div className="brand-grid" role="status" aria-label="Loading brands"><Skeleton /><Skeleton /><Skeleton /></div>
      : query.isError
        ? <p className="alert error" role="alert">{errText(query.error)}</p>
        : visibleBrands.length
          ? <ul className="brand-grid" aria-label="Brands">
              {visibleBrands.map(brand => <li className="brand-card" key={brand.id}>
              <div className="brand-card-heading">
                <BrandLogo brand={brand} />
                <div><h2>{brand.name}</h2><p>{brand.industry || "Industry not specified"}</p></div>
                {brand.status === "archived" && <Badge tone="neutral">Archived</Badge>}
              </div>
              <p className="brand-card-description">{brand.description || "No description has been added."}</p>
              <div className="brand-card-meta">
                {brand.website_url && <a href={brand.website_url} target="_blank" rel="noreferrer">{brand.website_url}</a>}
                <span>Created {new Date(brand.created_at).toLocaleDateString()}</span>
              </div>
              <div className="brand-card-actions">
                <Link className="btn" href={`/brands/${brand.id}`}>View brand</Link>
                {brand.status === "active" && <Link className="btn" href={`/brands/${brand.id}/edit`}>Edit</Link>}
                {brand.status === "active" && <Button variant="ghost" onClick={() => setActiveBrand(brand.id)}>Set active</Button>}
                {brand.status === "active" && <Button variant="danger" onClick={() => setArchiveTarget(brand)}>Archive</Button>}
              </div>
            </li>)}
          </ul>
          : <EmptyState title={search ? "No brands match this search" : "No brands yet"} description={search ? "Try a different name or industry." : "Create the first brand workspace. Existing organisation-wide knowledge will remain available as shared guidance."} action={!search && <Link className="btn pr" href="/brands/new">Create new brand</Link>} />}
  </main>;
}
