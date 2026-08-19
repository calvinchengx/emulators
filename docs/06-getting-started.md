# 06 — Getting started

Three doors in. Pick by what you are building.

Each repo carries its own authoritative quickstart, so this page routes rather
than duplicates: a command copied here would drift from the repo that owns it.

## Door 1: the whole family

The certified set in one command. Start here if you are building an
application that needs identity, authorization or secrets.

```sh
git clone https://github.com/calvinchengx/azure-emulators
cd azure-emulators
docker compose up                        # entra + keyvault + arm
docker compose --profile fabric up       # ...and fabric
docker compose --profile apim up         # ...or apim
docker compose --profile databricks up   # ...or the Databricks workspace
```

The compose defaults are the bill of materials, a combination of released
images chain-tested together. A bare `docker compose up` runs exactly that set.

ARM governs the vault, as it does in Azure: role assignments decide who may do
what, and no assignment means no access. The stack seeds what the portal gives
you when you create a vault, so the quickstart works without hand-writing a
role assignment.

**State persists.** `up`, `down`, `up` keeps your data. `down -v` is the reset,
and it is the command to give an agent between attempts.

Full detail: [azure-emulators docs](https://calvinchengx.github.io/azure-emulators/).

## Door 2: one emulator

Nothing requires the family. Each emulator ships its own image and its own
quickstart, and the single-service cases are real:

| You are working on | Run |
|---|---|
| Sign-in, tokens, MSAL, protected APIs | [entra-emulator](https://calvinchengx.github.io/entra-emulator/) |
| Role assignments, scopes, revocation | [arm-emulator](https://calvinchengx.github.io/arm-emulator/) with entra |
| Secrets, keys, certificates | [azure-keyvault-emulator](https://calvinchengx.github.io/azure-keyvault-emulator/) |
| APIM policies and the gateway | [azure-apim-emulator](https://calvinchengx.github.io/azure-apim-emulator/) |
| Fabric workspaces, items, OneLake | [fabric-emulator](https://calvinchengx.github.io/fabric-emulator/) |
| Databricks jobs and workspace REST | [databricks-emulator](https://calvinchengx.github.io/databricks-emulator/) |
| Snowflake SQL and account objects | [snowflake-emulator](https://github.com/calvinchengx/snowflake-emulator) |

entra-emulator is the highest-value one to adopt first, because identity is
usually the first thing that blocks local development.

## Door 3: a working data product

Start from a built platform and swap the product for your own. Every platform
takes `PRODUCT=<path>` and contains no product logic of its own.

| Platform | What it demonstrates |
|---|---|
| [fabric-platform-notebook-pipelines](https://github.com/calvinchengx/fabric-platform-notebook-pipelines) | The fullest one: four vendors, full medallion, semantic model, Power BI, OpenMetadata lineage |
| [fabric-platform-airflow3](https://github.com/calvinchengx/fabric-platform-airflow3) | The platform reduced to essentials: Airflow 3 plus a pinnable Fabric target, no product inside it |
| [databricks-platform-jobs](https://github.com/calvinchengx/databricks-platform-jobs) | The same product on Databricks Jobs, with Unity Catalog |
| [snowflake-platform-tasks](https://github.com/calvinchengx/snowflake-platform-tasks) | Gold-only on Snowflake, switchable to a real account |

The pieces they compose:
[contoso-sources](https://github.com/calvinchengx/contoso-sources) for the
vendor systems and
[contoso-data-product](https://github.com/calvinchengx/contoso-data-product)
for the transforms, contracts and expected numbers. See
[the matrix](03-the-data-product-matrix.md).

## Pointing an AI agent at this

Give the agent four things and it will mostly look after itself:

1. **The stack and the reset.** `docker compose up` and `docker compose down -v`.
   The reset is what stops one corrupted run from poisoning the next twenty.
2. **The parity ledger** for whichever emulator it is working against
   (`docs/parity.md` in that repo). When it hits a wall, the first question is
   whether the surface exists, and the ledger answers that in seconds.
3. **The chain test**, `e2e/chain/run.py` in azure-emulators: a worked example
   of the whole trust chain in one readable Python file.
4. **The real-tenant switch in configuration from day one**, not as a port at
   the end.

More on this in [Building with AI agents](04-building-with-ai-agents.md).

## Moving to real Azure

By design, nothing you build is emulator-specific. Point the issuer variables
at your tenant instead of `https://entra-emulator:8443/<tenant>/v2.0`, set the
platform's target flag to the real service, and the rest is unchanged. That is
the constraint the platform repos exist to prove.
