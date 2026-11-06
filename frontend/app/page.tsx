import Link from "next/link";
import Image from "next/image";

const features = [
  { number: "01", title: "Evidence-led review", body: "Every finding points to the guideline or approved fact behind it. If the evidence is missing, Brandwright says it cannot verify the claim.", points: ["Source-linked findings", "Severity-ranked issues", "Intent-preserving suggestions"] },
  { number: "02", title: "Human decisions", body: "Creators can accept a suggestion or explain why a finding should be dismissed. Reviewers keep the final say on approval.", points: ["No silent edits", "Comments on specific passages", "Role-based approval"] },
  { number: "03", title: "A record you can inspect", body: "Content versions, reviewer actions and decisions are recorded so teams can trace what happened before publication.", points: ["Version history", "Audit trail", "Governance insights"] },
];

export default function Home() {
  return (
    <main className="marketing">
      <header className="marketing-nav">
        <Link href="/" className="wordmark">Brand<span>wright</span><i>.</i></Link>
        <nav aria-label="Main navigation">
          <a href="#platform">Platform</a><a href="#workflow">How it works</a><a href="#governance">Governance</a>
        </nav>
        <div className="nav-actions"><Link href="/login" className="nav-login">Sign in</Link><Link href="/login" className="button primary small">Open workspace <span>↗</span></Link></div>
      </header>

      <section className="hero-section">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-dot" /> PRE-PUBLICATION BRAND GOVERNANCE</div>
            <h1>Every claim checked against your brand’s <em>own rules.</em></h1>
            <p className="hero-lede">Brandwright reviews submitted content against your guidelines, cites the source behind each finding, and keeps a record of every decision.</p>
            <div className="hero-actions"><Link href="/login" className="button primary">Enter Brandwright <span>↗</span></Link><a href="#platform" className="button secondary">Explore the platform <span>↓</span></a></div>
            <div className="hero-proof"><span className="proof-check">✓</span><span>AI proposes. People decide.</span><span className="proof-divider" /><span>Evidence before approval.</span></div>
          </div>
          <div className="hero-visual hero-photo-wrap">
            <Image
              src="/images/ai-human-interface.jpeg"
              alt="Professional presenting an artificial intelligence interface with connected digital services"
              width={1279}
              height={720}
              priority
              className="hero-photo"
            />
            <div className="hero-photo-caption"><span className="hero-photo-dot" /> INTELLIGENT BRAND GOVERNANCE <span>AI + HUMAN OVERSIGHT</span></div>
          </div>
        </div>
        <div className="hero-bottom"><span>BUILT FOR TEAMS THAT CREATE AT SCALE</span><div><span>CREATORS</span><b>·</b><span>BRAND MANAGERS</span><b>·</b><span>REVIEWERS</span><b>·</b><span>GUIDELINE OWNERS</span></div></div>
      </section>

      <section className="intro-section" id="platform">
        <div className="section-tag">01 / THE PLATFORM</div>
        <div className="intro-grid"><h2>Not another grammar checker.<br/><em>A governance layer.</em></h2><p>As content volume grows, brand rules become harder to apply consistently. Brandwright brings the guideline, the evidence and the human decision into one review workflow.</p></div>
        <div className="platform-visual-row"><div><span className="section-tag">CONNECTED WORKFLOW</span><h3>One place for brand rules, evidence and decisions.</h3><p>Give every team a shared view of what is approved, what needs review and why a content decision was made.</p></div><Image src="/images/ai-platform-illustration.jpeg" alt="Illustration of an AI-powered connected digital workspace" width={1280} height={719} className="platform-illustration" /></div>
        <div className="feature-grid">{features.map((item) => <article className="feature-card" key={item.number}><span className="feature-number">{item.number}</span><h3>{item.title}</h3><p>{item.body}</p><ul>{item.points.map((point) => <li key={point}>{point}</li>)}</ul></article>)}</div>
      </section>

      <section className="workflow-section" id="workflow">
        <div className="section-tag">02 / HOW IT WORKS</div><div className="workflow-heading"><h2>From first draft to<br/><em>accountable approval.</em></h2><p>A clear path for creators, reviewers and the people who own the brand rules.</p></div>
        <div className="steps">
          {["Set up the knowledge base", "Submit content and intent", "Run evidence-led checks", "Review findings and suggestions", "Approve and record"].map((step, i) => <div className="step" key={step}><span>0{i+1}</span><strong>{step}</strong>{i < 4 && <i aria-hidden="true">→</i>}</div>)}
        </div>
      </section>

      <section className="governance-section" id="governance">
        <div className="governance-copy"><div className="section-tag">03 / RESPONSIBLE BY DESIGN</div><h2>AI explains and suggests.<br/><em>Humans decide.</em></h2><p>Brandwright is designed to make uncertainty visible, not hide it. Unsupported claims are escalated, suggestions do not silently rewrite content, and approval remains a human responsibility.</p><Link href="/login" className="text-link">Go to your workspace <span>↗</span></Link></div>
        <div className="governance-side"><Image src="/images/security-key-illustration.jpeg" alt="Illustration representing secure access and protection" width={740} height={740} className="security-illustration" /><div className="governance-list"><div><span>01</span><section><strong>Evidence first</strong><p>No finding should stand without a matched guideline, approved fact or a clear “cannot verify”.</p></section></div><div><span>02</span><section><strong>Intent stays with the creator</strong><p>Suggestions are presented for review. The creator chooses whether to accept or dismiss them.</p></section></div><div><span>03</span><section><strong>Human approval</strong><p>Reviewers inspect flagged claims, add comments and record the final decision.</p></section></div></div>
        </div>
      </section>

      <section className="closing-section"><div className="closing-kicker">BRANDWRIGHT / PRE-PUBLICATION GOVERNANCE</div><h2>Make every approval<br/> <em>traceable.</em></h2><p>Bring your guidelines, content reviews and human decisions into one workspace.</p><Link href="/login" className="button dark">Open Brandwright <span>↗</span></Link></section>
      <footer className="marketing-footer"><Link href="/" className="wordmark">Brand<span>wright</span><i>.</i></Link><span>AI explains and suggests. Humans decide.</span><span>© 2026 Brandwright · Team Nova-GPK</span></footer>
    </main>
  );
}
