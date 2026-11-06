"use client";

import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return <main className="not-found-page" role="alert"><p className="section-tag">Something went wrong</p><h1>This page could not load</h1><p>Try again. Your saved review decisions remain unchanged.</p><button className="btn pr" onClick={reset}>Try again</button></main>;
}
