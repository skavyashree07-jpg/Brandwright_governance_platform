"use client";

import { useEffect, useState } from "react";
import { api, Brand } from "@/lib/api";

export function BrandLogo({ brand, className = "" }: { brand: Brand; className?: string }) {
  const [src, setSrc] = useState("");
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setSrc("");
    setLoadError(false);
    if (!brand.logo_url) {
      return;
    }
    api.brandLogo(brand.id).then(blob => {
      objectUrl = URL.createObjectURL(blob);
      if (active) setSrc(objectUrl);
      else URL.revokeObjectURL(objectUrl);
    }).catch(() => {
      if (active) setLoadError(true);
    });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [brand.id, brand.logo_url]);

  if (src) return <img className={`brand-logo ${className}`} src={src} alt={`${brand.name} logo`} />;
  if (loadError) {
    return <span className={`brand-logo-fallback brand-logo-error ${className}`} role="img" aria-label={`${brand.name} logo could not be loaded`} title="Logo could not be loaded">!</span>;
  }
  return <span className={`brand-logo-fallback ${className}`} aria-label={`${brand.name} logo placeholder`}>{brand.name.slice(0, 1).toUpperCase()}</span>;
}
