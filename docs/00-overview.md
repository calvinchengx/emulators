# 00 — Overview

Emulators that make an AI coding agent viable as the builder of Azure-shaped
applications and data products.

The problem is not that agents cannot write the code. It is that they cannot
*prove* it. Proving an Azure-shaped system means a tenant: a paid subscription,
minutes per round trip, state that does not reset, and a blast radius that
makes an agent's normal behaviour (try it, look, try again) expensive and
frightening. So the agent writes plausible code and a person spends weeks
finding out where it was wrong.

These emulators remove the tenant from the loop. Everything an agent needs to
observe is local, deterministic, free, and resettable in seconds. The agent
builds, runs, reads the actual response, and corrects itself, hundreds of times
before a person looks. When it is done, the same code points at the real
service by changing environment variables.

## Two fronts, one argument

**AI-driven application development.** Any Azure-shaped application or
automation needs identity, authorization, secrets and often a gateway before it
does anything interesting. Those four are precisely the parts you cannot stub
honestly: a fake token issuer teaches an agent nothing about audience
mismatches, and a permissive secret store teaches it nothing about RBAC. The
family gives an agent the real substrate locally:

- [entra-emulator](https://calvinchengx.github.io/entra-emulator/) issues real
  OIDC tokens that MSAL accepts.
- [arm-emulator](https://calvinchengx.github.io/arm-emulator/) enforces
  `Microsoft.Authorization` role assignments, so "no assignment means no
  access" is something the agent discovers rather than something it is told.
- [azure-keyvault-emulator](https://calvinchengx.github.io/azure-keyvault-emulator/)
  validates those tokens against that RBAC, with real cryptography behind the
  secrets, keys and certificates.
- [azure-apim-emulator](https://calvinchengx.github.io/azure-apim-emulator/)
  runs the management plane, the gateway and the policy engine.

**AI-driven data product development.** The same acceleration applied to the
data estate.
[fabric-emulator](https://calvinchengx.github.io/fabric-emulator/),
[databricks-emulator](https://calvinchengx.github.io/databricks-emulator/) and
[snowflake-emulator](https://github.com/calvinchengx/snowflake-emulator) let an
agent build a full medallion data product, with real Spark and real SQL behind
it, and check the numbers. Then one flag points the same product at the real
platform.

The measurable claim: the Contoso data product runs on Fabric, Databricks and
Snowflake. Porting a data product across engines is normally a project. It was
affordable here because each attempt cost seconds instead of a tenant round
trip. See [The data product matrix](03-the-data-product-matrix.md).

## Why fidelity is the whole point

An agent that iterates fast against a bad emulator converges fast on the wrong
answer. Speed without fidelity is worse than slowness, because it produces
confident code that fails on first contact with Azure.

So everything else in this ecosystem exists to make the acceleration
trustworthy:

- **Clean-room construction**, from published specification and observed
  protocol behaviour, never from decompiled product code.
- **Real trust between separate origins.** The emulators are separate
  processes on separate ports validating each other's tokens over HTTP,
  because that *is* the production relationship. Collapsing them into one
  process invites short-circuits that quietly stop resembling Azure.
- **Graded parity ledgers with enforced witnesses.** Every claim of "this
  works" names the test that proves it, most of them Microsoft's own SDKs or
  packaged third-party clients running in CI. See
  [Why these emulators](05-why-these-emulators.md).
- **A pinned, chain-tested family.** The combination is certified, not just
  the parts.

## Who this is for

- Someone pointing an AI agent at a data product and wanting the loop to close
  locally instead of in a tenant.
- A team whose agents need Entra, ARM, Key Vault or APIM available on a laptop
  and in CI, with no subscription and no shared-tenant contention.
- Anyone comparing analytics engines who wants the comparison to be about the
  engines rather than about who wrote the fixtures.

Read [the map](01-the-map.md) next for the full inventory and how the pieces
connect.
