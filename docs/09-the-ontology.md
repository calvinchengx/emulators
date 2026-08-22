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

**An `engine` emulator also declares which engine it serves**, so `targets` is
a join on a field rather than a match on a name prefix. `fabric-emulator`
begins with `fabric` today and that is a coincidence the ontology should not
rest on. This was found by writing the map generator against this page: it
reached for the emulator's `engine` and there was none.

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
| `targets` | platform → emulator | **derived**: joins the platform's `engine` to the emulator's |
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
| 3 | `kind` appears on `emulator` members and nowhere else, and `engine` on an emulator means `kind: engine` | `check_ontology.py` |
| 4 | exactly one member per (engine, orchestrator, tier) — no duplicate cells | `check_ontology.py` |
| 5 | every declared value is in the closed set for its field | `members.schema.json` |
| 6 | `bom: true` matches what `azure-emulators` pins | `check_ontology.py --bom` |
| 7 | the committed map matches the registry | `render_map.py --check` |
| 8 | the committed tables match the registry | `render_tables.py --check` |
| 9 | no ecosystem repo is missing from the registry, and none is phantom | `check_registry.py` |
| 10 | `ports` appears on `platform` members and nowhere else, and no host port is published by two members | `check_ontology.py` |
| 11 | every platform's `ports` equals the host ports its published compose maps | `check_ontology.py --ports` |
| 12 | every built member answers its tier's verb floor, read from its published Makefile | `check_verbs.py` |
| 13 | a leaf is `contoso-data-product-<engine>-<orchestrator>`, a platform is `<engine>-platform-<orchestrator>`, an emulator is `<service>-emulator`; `azure-keyvault-emulator` and `azure-apim-emulator` are grandfathered by name | `check_ontology.py` |

## Names

Three patterns, one per runnable tier, and a name that breaks its pattern is
a gate failure rather than a style remark:

| tier | name |
|---|---|
| leaf | `contoso-data-product-<engine>-<orchestrator>` |
| platform | `<engine>-platform-<orchestrator>` |
| emulator | `<service>-emulator` |

Leaf and platform names are **derived** from the member's `engine` and
`orchestrator`, so the check is not "does this look right" but "does this
repository's name agree with the cell it declares". A leaf named for Fabric
and declared as Snowflake is the kind of mistake prose never catches.

**Two emulators keep a prefix the rule does not have.** `azure-keyvault-emulator`
and `azure-apim-emulator` were named before the pattern existed; their five
siblings are `entra-`, `arm-`, `fabric-`, `databricks-` and
`snowflake-emulator`. They are grandfathered **by name**, listed in the
checker, and the reason is a cost the family has measured elsewhere: renaming
a published image touches every pin, every compose, every link and every
memory of it, and buys a reader nothing, since the registry's `tier` already
says what each is. The exception is closed: a new emulator gets the
unprefixed name, and the gate says so.

## `ports`: declared, then checked twice

A platform's compose publishes host ports, and that is the one fact a reader
needs before `make up` that no README states reliably. `ports` carries them
by service name. It is declared rather than derived because deriving it
would mean every reader of the registry fetching seven compose files; it is
**checked** against those files on published main so the declaration cannot
go stale, and checked **across members** so two stacks cannot claim one port.
The second check is the one a single compose file can never make: it does
not know what its siblings publish, and the registry is the only place that
sees all seven at once.

## The verb contract

"Run the medallion and tell me whether it worked" was spelled four ways
across seven platforms, two emulators answered no `up` at all, and leaves
ranged from a full `up/down/run` to no Makefile. The contract is a **floor**
per tier. A repository may answer more, and the rest of its Makefile is its
own business; the floor is what a reader who has learned one member may
assume of every other.

| tier | answers |
|---|---|
| emulator | `up` `down` `logs` `doctor` `test` |
| platform | `up` `down` `logs` `doctor` `test` `witness` |
| leaf, sources | `test` |

Two words are load-bearing. **`up`** means the published image, not a
checkout: it is what a platform pins and what a newcomer means by "start
it". **`witness`** takes no arguments and exits non-zero when the cell did
not produce what it claims. It is the family's word because a witness is the
family's unit of evidence, and because a platform that needs to be told which
DAG must **derive** it from the product it was pointed at: a platform that
names a product has stopped being a platform, and a test in each says so.

`check_verbs.py` reads each member's Makefile from published main, the way
every other gate here reads published state. `--local` reads the sibling
checkouts for a pre-merge answer, and says which it read.

## What this does not model

A cell's **witnesses**, and it should not. How much of an emulator's claimed
surface a third party has proved is a per-repository ledger with its own
checker, assembled by `family_parity.py`. Restating any of it here would
create a second copy that drifts, and the interesting number is not a
structural fact about the family: it is a measurement of one repository
against its own claims.
