# 04 — Building with AI agents

This is the reason the ecosystem exists.

## The loop is the whole problem

An AI coding agent is good at writing code and bad at knowing whether the code
is right. It closes that gap the same way a person does: run it, read what came
back, correct, run again. The value of an agent is roughly the number of times
it can go round that loop before a human has to intervene.

Against a real Azure tenant, each turn of that loop costs:

- **Minutes**, not seconds. Provisioning is asynchronous, capacities take time
  to come up, and long-running operations are genuinely long.
- **Money**, per attempt, on a subscription somebody owns.
- **Irreversibility.** State does not reset. A half-created workspace, a
  mangled role assignment or a partially loaded lakehouse persists into the
  next attempt and corrupts the signal.
- **Contention.** A shared tenant means an agent's experiments collide with
  other people's work, so agents get run cautiously or not at all.
- **Blast radius.** Nobody grants an autonomous agent write access to a
  production tenant, and rightly so.

The result is that an agent gets a handful of loop turns per hour, each one
supervised. That is not enough to be economically interesting, so the human
ends up doing the work with the agent as an autocomplete.

Against the emulators each turn costs **seconds, nothing, and nothing
permanent**. The stack comes up in one command, resets with `down -v`, runs on
a laptop and in CI, and has no blast radius at all. An agent can take hundreds
of loop turns before a person looks, and it can afford to be wrong on most of
them.

That difference is the product.

## What makes the acceleration trustworthy

An agent iterating fast against a bad emulator converges fast on the wrong
answer, then fails on first contact with Azure. Speed alone would be worse than
useless, so everything else in this ecosystem exists to make the fast loop
*honest*:

**Real protocols, not stubs.** entra issues tokens MSAL accepts. arm enforces
role assignments. keyvault does real RSA and EC cryptography. fabric runs a
real Spark engine. An agent that gets a 403 here is learning something true
about Azure, not about a fixture someone wrote.

**Real trust between separate origins.** The services validate each other's
tokens over HTTP across process boundaries, which is the production
relationship. An agent discovers audience mismatches and issuer misalignment,
the two failures that dominate real Azure integration work, in the emulator
rather than in the tenant.

**Enumerated gaps.** Every emulator publishes a graded parity ledger where a
red row is a stated absence rather than a silence. An agent, and the person
reading its output, can tell the difference between "this is not implemented"
and "this is implemented and broken". Guessing that difference is one of the
most expensive things an agent does.

**Witnessed claims.** A green row must name the test that proves it, and CI
refuses rows that do not. Most green rows across the family are proved by
Microsoft's own SDKs or packaged third-party clients rather than by our own
code on both ends. See [Why these emulators](05-why-these-emulators.md).

**A certified combination.** The versions in the family compose are a bill of
materials that has been chain-tested together, so an agent is not left
resolving version skew between six independently released services.

## The same code goes to production

Nothing in a product built this way is emulator-specific. The switch is
configuration:

- Point the `*_ENTRA_ISSUER` variables at your real tenant instead of
  `https://entra-emulator:8443/<tenant>/v2.0`.
- Set the platform's target flag, for example `SNOWFLAKE_TARGET=real` or the
  equivalent Fabric target, to the real service.

That is the design constraint the platform repos exist to prove, and it is why
the emulators are a **development target** rather than a test double you throw
away before shipping. The artifact the agent produced is the artifact you
deploy.

## What this actually bought

The concrete result is the [data product
matrix](03-the-data-product-matrix.md): the same Contoso data product running
on Fabric, on Databricks and on Snowflake, with a shared set of vendor sources
and a shared expected-numbers oracle proving all three produce the same answer.

Porting a data product across analytics engines is normally a project with a
business case. It happened here because each attempt cost seconds instead of a
tenant round trip, and because `compare_products.py` could tell an agent it was
wrong without a human reading dataframes.

The fullest single demonstration is
[fabric-platform-notebook-pipelines](https://github.com/calvinchengx/fabric-platform-notebook-pipelines),
which describes what it cost to build in its own README: months of tenant-bound
trial and error, compressed into days by iterating offline first. It goes from
real source systems through a medallion lakehouse to a semantic model and Power
BI, with lineage in OpenMetadata, and it runs against a **published**
fabric-emulator release rather than a checkout. That last constraint matters
more than it looks: a consumer with no access to the emulator's source proves
the loop is reproducible by anyone, not just by whoever can rebuild both
sides.

## Working à la carte

The full family is for when the interaction between services is what matters.
Plenty of agent work needs only one piece:

- **Building an application that authenticates against Entra.** Run
  entra-emulator alone. Identity is the first thing that blocks local
  development, so this is the single highest-value emulator to adopt.
- **Getting authorization right.** Run entra plus arm. Role assignments,
  scopes, inheritance and revocation are semantics an agent cannot learn from
  documentation alone, and a permissive mock actively teaches the wrong thing.
- **Writing APIM policies.** Run apim-emulator. The loop against a real APIM
  instance is minutes per policy edit, which is exactly the cost structure that
  makes agent-driven policy work impractical.
- **Building anything on Fabric or Databricks.** Run that emulator with entra.

[Getting started](06-getting-started.md) has the commands.

## Practical notes for pointing an agent at this

- **Give the agent the reset.** `docker compose down -v` between attempts is
  what stops a corrupted run from poisoning the next twenty.
- **Give it the parity ledger.** When an agent hits a wall, the first question
  is whether the surface is implemented. The ledger answers that in the repo,
  and saves an hour of the agent theorising about its own code.
- **Let it read the chain test.** `e2e/chain/run.py` in azure-emulators is a
  worked example of the whole trust chain, in Python, in one file.
- **Keep the real-tenant switch in configuration from the start**, not as a
  port at the end. It costs nothing early and it is what makes the emulator a
  development target rather than a detour.
