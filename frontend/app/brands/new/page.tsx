"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Brand } from "@/lib/api";
import { useUser } from "@/components/Shell";
import { BrandEditor } from "../BrandEditor";

export default function NewBrandPage() {
  const user = useUser();
  const router = useRouter();
  const queryClient = useQueryClient();

  if (user.role !== "admin") {
    return <main className="product-page"><section className="access-denied"><h1>Create a brand</h1><p>Only organisation admins can create brands.</p><Link className="btn" href="/brands">Return to brands</Link></section></main>;
  }

  function saved(brand: Brand) {
    void queryClient.invalidateQueries({ queryKey: ["brands"] });
    void queryClient.invalidateQueries({ queryKey: ["brand-management"] });
    router.push(`/brands/${brand.id}`);
  }

  return <main className="product-page">
    <header className="page-heading product-heading">
      <div><h1>Create a brand</h1><p className="mu">Set up a separate identity and knowledge workspace for your team.</p></div>
      <Link className="btn" href="/brands">Back to brand management</Link>
    </header>
    <BrandEditor onSaved={saved} />
  </main>;
}
