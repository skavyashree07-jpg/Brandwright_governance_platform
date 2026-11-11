"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { api, Brand, errText } from "@/lib/api";
import { Button, Input, Textarea } from "@/components/ui";
import { BrandLogo } from "./BrandLogo";

type BrandFields = {
  name: string;
  description: string;
  industry: string;
  website_url: string;
  primary_colour: string;
  secondary_colour: string;
  voice: string;
  target_audience: string;
  mission: string;
  vision: string;
  guidelines: string;
};

const emptyFields: BrandFields = {
  name: "", description: "", industry: "", website_url: "",
  primary_colour: "", secondary_colour: "", voice: "",
  target_audience: "", mission: "", vision: "", guidelines: "",
};

export function BrandEditor({
  initial,
  onSaved,
}: {
  initial?: Brand;
  onSaved: (brand: Brand) => void;
}) {
  const [fields, setFields] = useState<BrandFields>(() => initial ? {
    name: initial.name,
    description: initial.description ?? "",
    industry: initial.industry ?? "",
    website_url: initial.website_url ?? "",
    primary_colour: initial.primary_colour ?? "",
    secondary_colour: initial.secondary_colour ?? "",
    voice: initial.voice ?? "",
    target_audience: initial.target_audience ?? "",
    mission: initial.mission ?? "",
    vision: initial.vision ?? "",
    guidelines: initial.guidelines ?? "",
  } : emptyFields);
  const [logo, setLogo] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [logoError, setLogoError] = useState("");
  const [created, setCreated] = useState<Brand | null>(null);

  function update<K extends keyof BrandFields>(key: K, value: BrandFields[K]) {
    setFields(current => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLogoError("");
    if (logo && logo.size > 2 * 1024 * 1024) {
      setError("Logo file must be 2 MB or smaller.");
      return;
    }
    const payload = {
      name: fields.name.trim(),
      description: fields.description.trim() || null,
      industry: fields.industry.trim() || null,
      website_url: fields.website_url.trim() || null,
      primary_colour: fields.primary_colour || null,
      secondary_colour: fields.secondary_colour || null,
      voice: fields.voice.trim() || null,
      target_audience: fields.target_audience.trim() || null,
      mission: fields.mission.trim() || null,
      vision: fields.vision.trim() || null,
      guidelines: fields.guidelines.trim() || null,
    };
    if (!payload.name) {
      setError("Brand name is required.");
      return;
    }
    setSaving(true);
    try {
      const saved = initial
        ? await api.updateBrand(initial.id, payload)
        : await api.createBrand(payload);
      setCreated(saved);
      if (logo) {
        try {
          const withLogo = await api.uploadBrandLogo(saved.id, logo);
          onSaved(withLogo);
          return;
        } catch (cause) {
          setLogoError(`The brand details were saved, but the logo could not be uploaded: ${errText(cause)}`);
          if (initial) onSaved(saved);
          return;
        }
      }
      onSaved(saved);
    } catch (cause) {
      setError(errText(cause));
    } finally {
      setSaving(false);
    }
  }

  if (created && logoError && !initial) {
    return <section className="brand-form-state">
      <p className="alert error" role="alert">{logoError}</p>
      <Link className="btn pr" href={`/brands/${created.id}/edit`}>Continue to brand</Link>
    </section>;
  }

  return <form className="brand-editor" onSubmit={submit} noValidate>
    {error && <p className="alert error" role="alert">{error}</p>}
    {logoError && <p className="alert error" role="alert">{logoError}</p>}
    <section className="brand-form-section">
      <h2>Brand profile</h2>
      <div className="brand-form-grid">
        <Input label="Brand name *" required maxLength={160} value={fields.name} onChange={event => update("name", event.target.value)} />
        <Input label="Industry" maxLength={120} value={fields.industry} onChange={event => update("industry", event.target.value)} placeholder="For example, education" />
        <Input label="Website URL" type="url" maxLength={2048} value={fields.website_url} onChange={event => update("website_url", event.target.value)} placeholder="https://example.com" />
        <Input label="Brand voice" maxLength={120} value={fields.voice} onChange={event => update("voice", event.target.value)} placeholder="Professional, friendly, premium…" />
        <Input label="Primary brand colour" type="color" value={fields.primary_colour || "#244B3D"} onChange={event => update("primary_colour", event.target.value)} />
        <Input label="Secondary brand colour" type="color" value={fields.secondary_colour || "#D5E4D9"} onChange={event => update("secondary_colour", event.target.value)} />
      </div>
      <Textarea label="Brand description" rows={3} maxLength={5000} value={fields.description} onChange={event => update("description", event.target.value)} />
      <Input
        label="Brand logo"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        hint={initial?.logo_url ? "Uploading a new logo replaces the current logo." : "PNG, JPEG, or WebP; maximum 2 MB."}
        onChange={event => setLogo(event.target.files?.[0] ?? null)}
      />
      {initial?.logo_url && <BrandLogo brand={initial} className="brand-logo-preview" />}
    </section>
    <section className="brand-form-section">
      <h2>Audience and purpose</h2>
      <Textarea label="Target audience" rows={3} maxLength={5000} value={fields.target_audience} onChange={event => update("target_audience", event.target.value)} />
      <div className="brand-form-grid">
        <Textarea label="Mission" rows={3} maxLength={5000} value={fields.mission} onChange={event => update("mission", event.target.value)} />
        <Textarea label="Vision" rows={3} maxLength={5000} value={fields.vision} onChange={event => update("vision", event.target.value)} />
      </div>
    </section>
    <section className="brand-form-section">
      <h2>Brand guidelines</h2>
      <Textarea label="Guidelines" rows={6} maxLength={20000} hint="Add concise tone, messaging, and identity guidance. Approved rules, facts, and terms can be managed separately in Brand knowledge." value={fields.guidelines} onChange={event => update("guidelines", event.target.value)} />
    </section>
    <div className="brand-form-actions">
      <Link className="btn" href={initial ? `/brands/${initial.id}` : "/brands"}>Cancel</Link>
      <Button variant="primary" type="submit" loading={saving}>{initial ? "Save changes" : "Create brand"}</Button>
    </div>
  </form>;
}
