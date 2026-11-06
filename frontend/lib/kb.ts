"use client";
import { useCallback, useEffect, useState } from "react";
import { api, Finding } from "./api";

export function useSourceLabel() {
  const [labels, setLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    let active = true;
    Promise.allSettled([api.rules(), api.facts(), api.terms()]).then(([rules, facts, terms]) => {
      if (!active) return;
      const next: Record<string, string> = {};
      if (rules.status === "fulfilled") {
        rules.value.forEach((rule) => { next[rule.id] = `Guideline ${rule.clause_number}: ${rule.text}`; });
      }
      if (facts.status === "fulfilled") {
        facts.value.forEach((fact) => { next[fact.id] = `Approved fact: ${fact.text}`; });
      }
      if (terms.status === "fulfilled") {
        terms.value.forEach((term) => { next[term.id] = `Terminology rule: replace “${term.banned}” with “${term.preferred}”.`; });
      }
      setLabels(next);
    });
    return () => { active = false; };
  }, []);
  return useCallback((source: Finding["source"]): string | null => {
    if (!source) return null;
    if (source.id && labels[source.id]) return labels[source.id];
    if (source.type === "term") return "Approved terminology list";
    return source.id ? "Matched source is not available in the current knowledge-base response." : null;
  }, [labels]);
}
