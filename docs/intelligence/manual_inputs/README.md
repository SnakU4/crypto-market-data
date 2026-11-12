# Optional manual ChatGPT research feedback (append-only)

ChatGPT runs the independent research **interactively** using GitHub and web.
After its independent source checks, it may write structured findings to
findings.jsonl, preserving existing lines and appending only new discoveries.
No scheduled paid LLM/API workers are involved. GitHub Actions ingests
these annotations at the NEXT snapshot build.

Each line must be valid JSON with:
- id: unique stable string (never reused)
- title: short description
- scope: GLOBAL, SECTOR, ASSET, MULTI_ASSET, or UNRESOLVED
- source_url: direct HTTPS URL to a source or primary documentation
- first_observed_utc: actual UTC moment the researcher first knew the content,
  e.g. 2026-11-12T07:30:00Z. Never invent an earlier timestamp.
- published_utc: actual publication time if known, else omit
- cmc_ids: only true official CMC IDs when scope ASSET or MULTI_ASSET;
  MULTI_ASSET requires at least two distinct IDs
- source_excerpt: a short source-attributed quote/context (bounded at 650 chars)
- verification_note: describe what was actually checked vs remaining ambiguity
- reviewer: e.g. chatgpt_manual
- themes: optional free-form list, never a fixed taxonomy

Example **not** automatically ingested (illustrative only):
{"id":"example-1","title":"Official project protocol notice",
 "scope":"SECTOR","themes":["network_security"],
 "source_url":"https://example.org/original-notice",
 "published_utc":"2026-11-12T07:00:00Z",
 "first_observed_utc":"2026-11-12T07:30:00Z",
 "source_excerpt":"Short attributed context describing the notice.",
 "verification_note":"Review primary document, verify timestamp, no price effect claimed.",
 "reviewer":"chatgpt_manual"}

The file is not a machine-verified feed: every entry is labelled
MANUAL_RESEARCH_SOURCE_ANNOTATION_RECHECK_REQUIRED. A model assertion
that it checked a link is not itself independent confirmation.
Incorrect or unknown coin IDs make the build FAIL CLOSED.
Post-cutoff findings are automatically excluded from historical packs.
Do NOT backdate findings. The original market archives remain immutable.

To add information, ask ChatGPT:
"Perform the GitHub manual research prompt, record defensible evidence
in an append-only findings.jsonl file, show exactly what you verified,
and commit the new lines to the connected GitHub repository."

This is a *feedback loop* for source quality, not a way to insert
retroactive forecasts or verified alpha claims.
