# 02 — The emulators

Seven services, one discipline.

## Shared construction

Every emulator in this ecosystem is built the same way, and the choices are
deliberate.

**Clean room.** Built from published specifications, public documentation and
observed protocol behaviour. Nothing is derived from decompiled product code.
When capture and reflection cannot answer a question, what comes back is a
protocol fact, never vendor code.

**One static Go binary on `distroless/static-debian12`.** The images share a
base layer and each costs a few tens of megabytes of resident memory. Starting
the whole family costs less than most single-service alternatives.

**Separate processes, real trust.** keyvault and arm validating entra's tokens
over HTTP against a separate origin *is* the production trust relationship.
Bundling them into one process would save almost nothing and would invite
short-circuits, shared memory or direct key access, that quietly stop
resembling Azure. Separate containers also keep release cadences independent
and isolate failures behind per-service healthchecks.

**State that persists, and a deliberate reset.** Each service writes SQLite to
a named volume. `up`, `down`, `up` keeps your data; `down -v` is the reset. An
empty data directory selects in-memory for a throwaway stack.

**Graded parity with enforced witnesses.** Each emulator keeps a `docs/parity.md`
ledger and a `docs/witnesses.json` manifest, and CI refuses a green row that
does not name a resolvable witness. See
[Why these emulators](05-why-these-emulators.md) for what the witness tiers
mean and the current numbers.

## The family

Six of the seven compose as a family, pinned and chain-tested by
[azure-emulators](https://calvinchengx.github.io/azure-emulators/). Ports below
are the family compose defaults.

### entra-emulator: port 8443

Microsoft Entra ID: MSAL-compatible OIDC and OAuth2 v2.0, a minimal read-only
Graph, and an admin REST surface for seeding.

**The root of trust.** It issues every token in the family and publishes the
JWKS the others validate against. It is also the emulator most useful on its
own: any application that authenticates users or services against Entra can
develop against it without a tenant.

[Docs](https://calvinchengx.github.io/entra-emulator/) ·
[repo](https://github.com/calvinchengx/entra-emulator)

### arm-emulator: port 8445

The Azure Resource Manager control plane at `management.azure.com`, plus
`Microsoft.Authorization` RBAC, scoped to what its sibling data planes need.

This is the one that teaches authorization honestly. Role assignments decide
who may do what, and no assignment means no access. A data-plane call that
returns 403 rather than 404 tells you the token was valid but the grant never
arrived, which is a distinction most mocks erase.

[Docs](https://calvinchengx.github.io/arm-emulator/) ·
[repo](https://github.com/calvinchengx/arm-emulator)

### azure-keyvault-emulator: port 8444

The Key Vault data plane: secrets, keys with real RSA and EC cryptography, and
X.509 certificates. It is governed by arm, so a vault in the family stack
denies by default until a role assignment reaches it, exactly as a real vault
does.

[Docs](https://calvinchengx.github.io/azure-keyvault-emulator/) ·
[repo](https://github.com/calvinchengx/azure-keyvault-emulator)

### azure-apim-emulator: port 8446

API Management: the management plane, the gateway, and the policy engine. It
serves its own `Microsoft.ApiManagement` ARM surface rather than calling arm,
so it consumes entra alone.

The policy engine is the interesting part. Real APIM policies are saturated
with C# expressions, and an emulator that cannot evaluate them cannot host a
realistic policy at all.

[Docs](https://calvinchengx.github.io/azure-apim-emulator/) ·
[repo](https://github.com/calvinchengx/azure-apim-emulator)

### fabric-emulator: port 9443

Microsoft Fabric: the control plane (workspaces, items, RBAC, git integration,
long-running operations, MCP) and OneLake, with a real Spark engine behind it
rather than a stub.

It is a **consumer** of the three services above, which is why it sits behind a
`fabric` profile in the family compose. ARM-created
`Microsoft.Fabric/capacities` resources appear on its capacities endpoint.

[Docs](https://calvinchengx.github.io/fabric-emulator/) ·
[repo](https://github.com/calvinchengx/fabric-emulator)

### databricks-emulator: port 8447

An Azure Databricks workspace REST surface, a peer of fabric-emulator. Identity
is Databricks-native, a seeded admin personal access token plus its own OIDC,
with entra as an **optional** federated issuer. That optionality is faithful:
Azure Databricks really does accept both.

[Docs](https://calvinchengx.github.io/databricks-emulator/) ·
[repo](https://github.com/calvinchengx/databricks-emulator)

## The adjacent one

### snowflake-emulator

A Snowflake account emulator. SQL runs on DuckDB, and the dialect is reported
honestly as `duckdb` rather than pretending otherwise. Time Travel, Streams and
Cortex are enumerated as not implemented rather than silently missing.

It keeps the same discipline as the family: a graded ledger, a witness
manifest, a checker enforcing both. It is **not** in the Azure family compose,
because Snowflake is not an Azure service.

The line is bill-of-materials membership, not whether Azure touches the
product. Azure and Fabric integrate with Snowflake through mirroring,
shortcuts and Data Factory connectors. databricks-emulator is family because it
emulates *Azure* Databricks, down to the well-known first-party application ID
and federated Entra tokens. Whether snowflake should join the family is a
release-coordination question: it would have to enter the compose and the chain
test.

[Repo](https://github.com/calvinchengx/snowflake-emulator)

## Using one on its own

Nothing requires you to run the whole family. Each emulator ships its own
image, its own quickstart and its own docs site, and the common single-service
cases are real:

- **entra-emulator alone** as a local STS for any application that
  authenticates against Entra. This is the highest-value single emulator,
  because identity is the first thing that blocks local development.
- **arm-emulator alone** when the thing under test is authorization semantics:
  role assignments, scopes, inheritance, revocation.
- **azure-apim-emulator alone** for policy development, where the loop against
  a real APIM instance is measured in minutes per edit.

The family exists for when the *interaction* between services is what matters.
See [Getting started](06-getting-started.md).
