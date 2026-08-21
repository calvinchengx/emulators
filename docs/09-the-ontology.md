# 09 — The ontology

Twenty-five repositories, seven kinds of thing, and five relations between
them. This page is the controlled vocabulary: what a member can be, what can
be true of a pair of members, and which of those facts are **derived**,
**declared** or **checked against another system**.

It exists because the ecosystem had a vocabulary already and it lived in prose.
Six edges in the old README diagram carried six different phrasings — "issues
tokens for", "governs", "capacities", "pins + certifies", "by tag", "installed
via `PRODUCT=`" — and nothing could tell you which two meant the same kind of
thing, or check that any of them were still true.

## The rule this page keeps

**Derive what can be derived, declare only what cannot, and gate both.**

A field a human types is a field that goes stale. This repository has already
paid for that twice: two wrong statuses in its first commit, taken from README
prose over a tree that contradicted it, and — in a sibling repository — a
hand-written inventory field that was wrong 28 times in 70 rows before it was
derived. Everything below says which category it is in, and a fact with no
gate named against it is a fact nobody is checking.

## Entities

Every member has a `tier`. There are seven, and the set is closed.

| tier | what it is | how many |
|---|---|---|
| `emulator` | a service this family emulates | 7 |
| `composition` | the BOM: pins, family compose, chain test | 1 |
| `hub` | this repository: directory, docs site, CI sweep | 1 |
| `sources` | the vendor systems every cell pulls from | 1 |
| `core` | the data product defined once: SQL, contracts, numbers | 1 |
| `leaf` | one cell's product half | 7 |
| `platform` | one cell's infrastructure half | 7 |

### Two axes

`leaf` and `platform` members carry both. Nothing else carries either.

- **`engine`** — `fabric`, `databricks`, `snowflake`
- **`orchestrator`** — `airflow3`, `airflow-builtin`, `notebook-pipelines`, `jobs`, `tasks`

A **cell** is an (engine, orchestrator) pair. There are seven, and a cell is
always exactly two repositories.

### One distinction inside `emulator`

`kind` splits the emulators by what they are for, which the old `role` prose
could not be read for:

| kind | members |
|---|---|
| `engine` | fabric, databricks, snowflake |
| `identity` | entra |
| `control-plane` | arm |
| `secrets` | keyvault |
| `gateway` | apim |

`engine` is the load-bearing one: a platform `targets` exactly one engine
emulator, and every other emulator is cross-cutting, running in a stack
without being what the stack is named for.

### `bom`, and why it is not the same as `kind`

`bom: true` means the member is one of the six `azure-emulators` certifies:
pinned in the BOM, present in the family compose, covered by the chain test.
`snowflake-emulator` is `kind: engine` and `bom: false`, and that pair of
facts is the whole of its adjacency. It keeps the same discipline as the
certified six — graded ledger, witness manifest, checker enforcing both — and
is not in the set the pin gate and the chain test are built around.

**The line is BOM membership, not whether Azure touches the product.** Azure
and Fabric integrate with Snowflake, so "not an Azure service" invites an
objection it cannot answer. `databricks-emulator` is `bom: true` because it
emulates *Azure* Databricks, down to the first-party app id and federated
Entra tokens.

## Relations

Five, and the set is closed. Each one says where it comes from.

| relation | from → to | source |
|---|---|---|
| `pairs_with` | leaf ↔ platform | **derived** from equal (engine, orchestrator) |
| `targets` | platform → emulator | **derived** from engine |
| `pins_by_tag` | leaf → core | **invariant**: every leaf, no exceptions |
| `materialises_from` | platform → sources | **invariant**: every platform |
| `certifies` | composition → emulator | **declared** `bom`, **checked** against `azure-emulators` |

### Why `pairs_with` is derived rather than listed

Listing it would let a leaf name a platform that does not exist, or two leaves
claim one platform, and nothing would notice. Derived, the absence is the
error: a leaf whose (engine, orchestrator) has no platform is an **unpaired**
row, and so is a platform with no leaf. That distinction — reserved on
purpose versus missing by accident — is the same one `status` and `ci` exist
to draw, and it is the entry that earns the registry.

### Why `certifies` is declared and checked

Nothing in this repository can know what the BOM pins. `bom` is therefore a
declaration, and a declaration that nothing verifies is a claim. It is
compared against `azure-emulators`' published main, the way the parity report
already reads published state over HTTP rather than trusting a checkout.

### What is deliberately not a relation

**`authenticates`.** Every emulator validates tokens against `entra-emulator`,
which makes it true of six edges and therefore not worth drawing: an arrow
that is always present carries no information. It belongs in prose, and it is
in [02 — the emulators](02-the-emulators.md).

**Anything about a cell's health.** `status`, `ci` and the sweep already carry
that, they change hourly, and folding them into the structure would mean the
map goes stale every time a workflow runs.

## Invariants

These are the statements the gates enforce. Each names the gate.

| # | invariant | gate |
|---|---|---|
| 1 | every `leaf` has exactly one `platform` with the same (engine, orchestrator), and the reverse | `check_ontology.py` |
| 2 | `engine` and `orchestrator` appear on `leaf` and `platform` members and nowhere else | `check_ontology.py` |
| 3 | `kind` appears on `emulator` members and nowhere else | `check_ontology.py` |
| 4 | exactly one member per (engine, orchestrator, tier) — no duplicate cells | `check_ontology.py` |
| 5 | every declared value is in the closed set for its field | `members.schema.json` |
| 6 | `bom: true` matches what `azure-emulators` pins | `check_ontology.py --bom` |
| 7 | the committed map matches the registry | `render_map.py --check` |
| 8 | the committed tables match the registry | `render_tables.py --check` |
| 9 | no ecosystem repo is missing from the registry, and none is phantom | `check_registry.py` |

## What this does not model

A cell's **witnesses**, and it should not. How much of an emulator's claimed
surface a third party has proved is a per-repository ledger with its own
checker, assembled by `family_parity.py`. Restating any of it here would
create a second copy that drifts, and the interesting number is not a
structural fact about the family: it is a measurement of one repository
against its own claims.
