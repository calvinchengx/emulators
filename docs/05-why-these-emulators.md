# 05 — Why these emulators

There are other Azure emulators, and some of them are good. This page is about
what is actually different here, stated so you can check it.

## The landscape, honestly

**Microsoft's own emulators are per-service and few.**
[Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite)
covers Storage, and there are official emulators for
[Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/emulator),
[Event Hubs](https://learn.microsoft.com/azure/event-hubs/test-locally-with-event-hub-emulator)
and Service Bus. They are solid within their boundaries and they are the right
answer when your problem is inside one of those boundaries. There is no
official emulator for Entra ID, ARM, API Management, Fabric or Databricks.

**Community and commercial projects cover breadth.**
[Topaz](https://github.com/TheCloudTheory/Topaz) is an Apache-2.0 single-binary
emulator spanning eighteen-plus Azure services including Storage, Key Vault,
Service Bus, Cosmos DB, SQL, RBAC, Entra ID identity flows and the APIM control
plane. [LocalStack for Azure](https://www.localstack.cloud/localstack-for-azure)
is a commercial product, in preview at the time of writing, bringing
LocalStack's AWS approach to Azure.
[Entra Local](https://github.com/cmaneu/entra-local) is a focused
MSAL-compatible Entra ID emulator that describes itself as a small fixed slice.
For Snowflake, [fakesnow](https://github.com/tekumara/fakesnow) takes the same
DuckDB-backed approach that snowflake-emulator does.

If you want one binary that answers to as much of the Azure control plane as
possible, Topaz or LocalStack is the shorter path, and you should take it.

## Five differences

### 1. Built for the AI loop, and the whole design follows from it

Every choice here traces back to one question: how many times can an AI coding
agent go round build, run, observe, correct before a person has to intervene?
That is why the stack comes up in one command, resets in one command, runs in
CI, costs nothing and has no blast radius. See
[Building with AI agents](04-building-with-ai-agents.md).

Others make this argument too, and LocalStack markets to agents explicitly. The
difference is not the claim, it is what the claim is allowed to cost. An
emulator optimised for the agent loop is worthless if the agent converges
quickly on something Azure rejects, so the rest of this list is about the
fidelity that makes the speed safe.

### 2. The analytics plane, which nothing else emulates

This is the clearest gap in everything else available.

- **[fabric-emulator](https://calvinchengx.github.io/fabric-emulator/)**: the
  Fabric control plane, workspaces, items, RBAC, git integration, long-running
  operations, plus OneLake and a real Spark engine. Microsoft ships no Fabric
  emulator; the documented local-development path for Fabric assumes a real
  Entra app and a real tenant.
- **[databricks-emulator](https://calvinchengx.github.io/databricks-emulator/)**:
  an Azure Databricks workspace REST surface. The official answer for local
  Databricks work is Databricks Connect, which is a bridge *to* a real
  workspace rather than a local substitute for one.
- **[snowflake-emulator](https://github.com/calvinchengx/snowflake-emulator)**:
  a Snowflake account emulator, adjacent to the Azure family.

If your work is data engineering rather than application development, this is
the difference that matters, because the analytics plane is exactly where the
tenant round trip is slowest and the capacity is most expensive.

### 3. A family with real trust, not one process with many faces

The breadth-first emulators are a single binary fronting many services. That is
a legitimate design and it makes installation trivial. It also means the
services cannot have a real relationship with each other: inside one process,
token validation between components is a function call at best and skipped at
worst.

Here the emulators are **separate processes on separate ports validating each
other's tokens over HTTP**, because that is the production trust relationship.
keyvault genuinely fetches entra's JWKS from a different origin. arm genuinely
decides, by role assignment, whether a caller may read a secret, and the vault
genuinely honours that decision. The two failures that dominate real Azure
integration work, issuer misalignment and audience mismatch, are reproducible
here rather than papered over.

That relationship is then **certified as a set**.
[azure-emulators](https://calvinchengx.github.io/azure-emulators/) pins a bill
of materials (the newest combination of released images proven to work
together) and runs a chain test that no single emulator's CI can run: entra
mints a token per audience, arm accepts it and performs a real write, keyvault
authorizes it on a real data-plane call returning 404 rather than 403 so a
broken grant cannot pass as success, apim accepts the ARM-audience token, and a
foreign-issuer token is refused so the earlier steps passed because the trust
chain holds rather than because validation is missing.

The cost of this design is honest: more containers, and a version-coordination
problem that the BOM exists to solve. The benefit is that the trust chain is
real enough to fail on.

### 4. Graded parity with CI-enforced witnesses

Most emulators tell you what they support in a README table. These publish a
per-capability ledger where every green row must name a **witness**, a specific
test that proves it, and CI refuses a green row whose witness does not resolve.
Witnesses are ranked by how independent they are:

| tier | meaning |
|---|---|
| `ci:` | a packaged external client, run in CI |
| `sdk:` | Microsoft's own SDK, linked in process |
| `go:` / `py:` | our own client on both ends of the wire |

The last of those is the weak one, because it only proves our client agrees
with our server. So the headline number is the share of claims proved by
something that is **not us**:

<!-- BEGIN evidence (generated by scripts/render_evidence.py) -->

| emulator | green claims | ci: external | sdk: only | own tests only | independently evidenced |
|---|---:|---:|---:|---:|---:|
| fabric | 113 | 107 | 0 | 6 | **107/113 (95%)** |
| entra | 55 | 52 | 0 | 3 | **52/55 (95%)** |
| keyvault | 49 | 38 | 9 | 2 | **47/49 (96%)** |
| apim | 35 | 27 | 3 | 5 | **30/35 (86%)** |
| arm | 29 | 19 | 9 | 1 | **28/29 (97%)** |
| databricks | 30 | 30 | 0 | 0 | **30/30 (100%)** |

Generated by `scripts/render_evidence.py` from azure-emulators'
`family_parity.py`, which derives each count using that repo's own
checker rules. The numbers move whenever a witness lands, so run it
yourself rather than trusting this snapshot:

```sh
git clone https://github.com/calvinchengx/azure-emulators
cd azure-emulators && ./scripts/family_parity.py --evidence
```

<!-- END evidence -->

Two caveats, stated because they are the ways these numbers get misread. **A
high score is not breadth**: arm reads near the top of that table, and its
ledger is scoped by its own boundary to the authorization slice rather than all
of ARM. And **none of this
is differential evidence against Azure**: green means witnessed locally against
real clients, never diffed against a live tenant.

We have not found another Azure emulator publishing a machine-checked witness
manifest of this kind. If one exists, that comparison should be made properly.

### 5. A reference data product on top, proven on three engines

Emulators are infrastructure. What most people actually want to know is whether
something real can be built on them.

The [Contoso data product](03-the-data-product-matrix.md) is that answer: four
vendor source systems through a full medallion into gold, with data contracts
and an expected-numbers oracle, running on Fabric, on Databricks and on
Snowflake from **one shared core**. The platforms that run it are, with one
exception, separate repos containing no product logic, so you can point one at
your own data product with `PRODUCT=<path>`.

No other Azure emulator project ships a worked data product across multiple
analytics engines, because most of them are not aimed at the data estate at
all.

## Comparison at a glance

| | this ecosystem | Azurite / Cosmos DB / Event Hubs | Topaz | LocalStack for Azure |
|---|---|---|---|---|
| Scope | identity, ARM+RBAC, Key Vault, APIM, Fabric, Databricks, Snowflake | one service each | 18+ Azure services, breadth-first | broad, AWS-style |
| Analytics plane (Fabric / Databricks) | yes | no | no | no |
| Process model | separate services, real cross-service trust | single service | single binary | single stack |
| Certified multi-service set | yes, a BOM plus a chain test | not applicable | not stated | not stated |
| Per-capability witness manifest | yes, CI-enforced | no | coverage docs, not witness-bound | no |
| Reference data product | yes, three engines | no | no | no |
| License | Apache-2.0 | Microsoft, per-service terms | Apache-2.0 | commercial |

Rows marked "not stated" mean we did not find the claim in their public
documentation, not that the capability is absent.

## When to use something else

- **Storage, Cosmos DB, Event Hubs or Service Bus alone.** Use Microsoft's
  official emulator. It is the reference implementation and this ecosystem does
  not emulate those services.
- **Breadth across many Azure resource providers with minimal setup.** Use
  Topaz or LocalStack. Eighteen services in one binary is a real advantage that
  a six-container family does not have.
- **A quick Entra stand-in for one application.** Entra Local is smaller and
  faster to adopt. Choose entra-emulator when you need it to hold a real trust
  relationship with other services, or when the emulator's own behaviour has to
  be evidenced.

Use this ecosystem when the thing you are building spans services, when your
work is on the Fabric or Databricks side, or when you want an AI agent doing
the building and need its fast loop to be an honest one.
