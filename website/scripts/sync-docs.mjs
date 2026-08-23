// Generates Starlight content from the canonical Markdown in /docs, keeping
// /docs as the single source of truth (its files stay pristine and their
// GitHub-relative links keep working). Run automatically before dev/build.
//
// For each docs/NN-name.md it: derives the title from the leading H1, injects
// Starlight frontmatter, drops the duplicate H1, and rewrites intra-doc
// `NN-name.md` links to site routes under the configured base.
import { readdirSync, readFileSync, writeFileSync, rmSync, mkdirSync, existsSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const REPO = join(here, '..', '..');
const DOCS_SRC = join(REPO, 'docs');
const OUT = join(here, '..', 'src', 'content', 'docs');
export const BASE = '/emulators/docs/';

// Docs are `NN-name.md` chapters.
const DOC_RE = /^\d{2}-.*\.md$/;

// Rewrite `](./|docs/ NN-slug.md#anchor)` → `](/emulators/NN-slug/#anchor)`.
const LINK_RE = /\]\((?:\.\/|docs\/)?(\d{2}-[a-z0-9-]+)\.md(#[^)]*)?\)/g;
// Repo-relative links (`../README.md`) are correct on GitHub, where /docs sits
// one level under the repo root, but they are dead on the site, whose pages
// are served from flat `/<base>/<slug>/` routes with nothing above them.
// Rewriting to an absolute GitHub URL keeps ONE source of truth working in
// both renderings. `tree` vs `blob` is decided from what the path actually is
// on disk, and a path that resolves to nothing is reported rather than
// silently linked into a 404.
const REPO_URL = 'https://github.com/calvinchengx/emulators';
const REPO_LINK_RE = /\]\(\.\.\/([^)#]+)(#[^)]*)?\)/g;
function rewriteRepoLinks(md, where) {
  return md.replace(REPO_LINK_RE, (_m, path, anchor) => {
    const clean = path.replace(/\/+$/, '');
    const target = join(REPO, clean);
    const exists = existsSync(target);
    if (!exists) {
      console.warn(`sync-docs: WARNING ${where}: ../${path} matches nothing in the repo`);
    }
    const kind = exists && statSync(target).isDirectory() ? 'tree' : 'blob';
    return `](${REPO_URL}/${kind}/main/${clean}${anchor ?? ''})`;
  });
}

function rewriteLinks(md, where = 'docs') {
  const sitewide = md.replace(LINK_RE, (_m, slug, anchor) => `](${BASE}${slug}/${anchor ?? ''})`);
  return rewriteRepoLinks(sitewide, where);
}

// "06 - Getting started" -> "Getting started".
function cleanTitle(h1) {
  return h1.replace(/^\d+[a-z]?\s*[—:-]\s*/i, '').trim();
}

// Backslashes must be escaped before quotes, or a title ending in one would
// escape the closing quote and produce unparseable frontmatter.
function yamlEscape(s) {
  return '"' + s.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
}

// The page's own meta description, taken from the first real paragraph.
//
// WHY. Starlight falls back to the SITE description when a page declares none,
// so every page of a site shipped the same `<meta name="description">` --
// checked on three pages of this site and they were byte-identical. Google
// discards duplicate descriptions and writes its own snippet, so 300+ pages
// across this family were competing with one sentence between them.
//
// FIRST PARAGRAPH, not a summary. It is the one sentence the author already
// wrote to introduce the page, and deriving it means it cannot go stale. Skips
// headings, code fences, tables, quotes, images, lists and HTML, which are all
// things that read badly as a search snippet.
//
// Absent rather than empty when nothing suitable is found: Starlight then falls
// back to the site description, which is the old behaviour and no worse.
function description(raw) {
  const lines = raw.split('\n');
  let inFence = false;
  const para = [];
  for (const line of lines) {
    const t = line.trim();
    if (/^(```|~~~)/.test(t)) { inFence = !inFence; continue; }
    if (inFence) continue;
    if (para.length === 0) {
      if (!t) continue;
      if (/^(#|>|\||-|\*|\d+\.|!\[|<)/.test(t)) continue;
      para.push(t);
    } else {
      if (!t || /^(#|>|\||```|~~~)/.test(t)) break;
      para.push(t);
    }
  }
  if (para.length === 0) return null;
  // Markdown emphasis, links and code marks read as noise in a snippet.
  let text = para
    .join(' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[`*_]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  // 25, not 40. "Seven services, one discipline." is 30 characters and is a
  // better description than the site-wide sentence it would otherwise inherit:
  // distinctive and short beats generic and long, for a snippet.
  if (text.length < 25) return null;
  // Search engines truncate around 160; cut on a sentence, else on a word.
  if (text.length > 160) {
    const stop = text.lastIndexOf('. ', 160);
    text = stop > 80 ? text.slice(0, stop + 1)
                     : text.slice(0, text.lastIndexOf(' ', 157)) + '\u2026';
  }
  return text;
}

// Strip the leading H1 (Starlight renders the frontmatter title) and rewrite
// intra-doc links.
function convertBody(raw, where = 'docs') {
  const lines = raw.split('\n');
  const h1Index = lines.findIndex((l) => /^#\s+/.test(l));
  if (h1Index >= 0) {
    lines.splice(h1Index, lines[h1Index + 1]?.trim() === '' ? 2 : 1);
  }
  return rewriteLinks(lines.join('\n').replace(/^\n+/, ''), where);
}

function convert(name) {
  const raw = readFileSync(join(DOCS_SRC, name), 'utf8');
  const h1 = raw.split('\n').find((l) => /^#\s+/.test(l));
  const title = h1 ? cleanTitle(h1.replace(/^#\s+/, '')) : name.replace(/\.md$/, '');
  const body = convertBody(raw, name);
  // Point "Edit this page" at the real source in /docs (the generated copy
  // under src/content/docs/ is git-ignored), not Starlight's default path.
  const editUrl = `${REPO_URL}/edit/main/docs/${name}`;
  const desc = description(raw);
  const frontmatter =
    `---\ntitle: ${yamlEscape(title)}\n` +
    (desc ? `description: ${yamlEscape(desc)}\n` : '') +
    `editUrl: ${yamlEscape(editUrl)}\n---\n\n`;
  return frontmatter + body;
}

function writeIndex() {
  const body = rewriteLinks(
    `Emulators that make an AI coding agent viable as the builder of ` +
      `Azure-shaped applications and data products. The agent builds and proves ` +
      `everything offline against local, clean-room emulators of the control ` +
      `planes nobody else emulates, then moves to the real tenant with no code ` +
      `changes. Tenant-speed iteration becomes machine-speed iteration.

` +
      `## Start here

` +
      `- [Overview](00-overview.md): the thesis, and who this is for
` +
      `- [The map](01-the-map.md): every repo, and how they relate
` +
      `- [The emulators](02-the-emulators.md): seven services, one discipline
` +
      `- [The data product matrix](03-the-data-product-matrix.md): one product, three engines
` +
      `- [Building with AI agents](04-building-with-ai-agents.md): the core value story
` +
      `- [Why these emulators](05-why-these-emulators.md): the comparison
` +
      `- [Getting started](06-getting-started.md): three doors in
` +
      `- [Mirrored images](10-mirrored-images.md): what the family pulls, and from where
` +
      `- [CI status](08-ci-status.md): is the whole ecosystem green
` +
      `- [Roadmap](07-roadmap.md): what earns a new emulator its place

` +
      `The [landing page](/emulators/) above these docs carries the argument, the ` +
      `evidence numbers and an honest status table, all generated from the same ` +
      `registry and ledgers these pages read.
`,
  );
  const frontmatter =
    `---
title: Emulators
description: "The emulator ecosystem: Entra ID, ARM, Key Vault, APIM, Fabric, Databricks and Snowflake emulators, plus a reference data product proven on three engines. Built to accelerate AI-driven development."
editUrl: false
---

`;
  writeFileSync(join(OUT, 'index.md'), frontmatter + body);
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
const names = readdirSync(DOCS_SRC).filter((n) => DOC_RE.test(n)).sort();
for (const name of names) {
  writeFileSync(join(OUT, name), convert(name));
}
writeIndex();
console.log(`sync-docs: wrote ${names.length} docs + index to src/content/docs/`);
