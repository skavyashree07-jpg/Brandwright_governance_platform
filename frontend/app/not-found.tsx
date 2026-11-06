import Link from "next/link";

export default function NotFound() {
  return <main className="not-found-page"><p className="section-tag">404</p><h1>We couldn’t find that page</h1><p>It may have moved, or you may not have access to it.</p><Link className="btn pr" href="/">Return to Brandwright</Link></main>;
}
