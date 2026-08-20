# 07 — Roadmap

What is coming, and what a new emulator has to earn.

## The bar for a new emulator

Adding a service is cheap. Adding a *trustworthy* service is not, so a new
emulator joins on the same terms as the existing ones:

1. **Its own repo, its own release cadence, its own image.** Emulators are
   independently useful and independently versioned. Bundling them into one
   release train would couple work that has no reason to be coupled.
2. **Clean-room construction.** From published specifications, public
   documentation and observed protocol behaviour. Nothing derived from
   decompiled product code, ever.
3. **A graded parity ledger from day one.** Not a README table. Green, partial
   and not-implemented rows, with the scope boundary stated explicitly so the
   denominator means something.
4. **A witness manifest with a CI gate.** A green row that cannot name a
   resolvable test is not green. This is the rule that keeps the ledger from
   becoming marketing.
5. **Real identity, not a bypass.** If the real service validates tokens, the
   emulator validates tokens, against a separate origin.

Only after all five does a **family** question arise, and family membership is
a separate and higher bar.

## Joining the family

Being an Azure emulator is not sufficient. The family is a *certified
combination*, so joining means:

- entering the [azure-emulators](https://calvinchengx.github.io/azure-emulators/)
  compose with a profile and a pinned version in the bill of materials;
- appearing in the chain test, with at least one assertion that proves the
  trust seam rather than the service in isolation;
- entering the pin gate, so consumer repos cannot certify against a different
  family than the BOM defines.

`snowflake-emulator` is the worked example of the distinction. It keeps every
part of the discipline, and it is deliberately outside the family because
Snowflake is not an Azure first-party service. The line is bill-of-materials
membership, not whether Azure touches the product: Azure and Fabric integrate
with Snowflake through mirroring, shortcuts and Data Factory connectors.
Whether snowflake should join is a release-coordination question, not a naming
one, and it would change what the word "family" means in the parity report.

## Open directions

**Filling the matrix.** Twelve of the fourteen repos carry code, six leaf
products and six platforms, and **every cell is now either complete or empty**:
no cell has one half built and the other reserved. The two that remain are the
Snowflake Airflow 3 pair, which is the last unstarted cell.

The verification gap that used to sit alongside this is closed. Every built
repo in the ecosystem now has CI, secret scanning and vulnerability scanning,
and the registry has no member declared as missing CI, so an unverified cell
can no longer quietly fail to settle the comparison the matrix exists to make.
See [CI status](08-ci-status.md) and [the matrix](03-the-data-product-matrix.md).

**Extracting the flagship's product.** `fabric-platform-notebook-pipelines`
predates the platform/product split and carries its product inline, which is
why it is the one platform that does not take `PRODUCT=`. Its leaf cell is now
built separately, so splitting the platform would make the fullest end-to-end
demonstration in the ecosystem also the clearest illustration of the
separation.

**Differential evidence against real Azure.** The strongest caveat on every
parity number today is that green means witnessed locally against real clients,
never diffed against a live tenant. A differential harness would run the same
client against the emulator and a real tenant and compare responses, turning
parity claims into measured agreement. This is the single biggest available
improvement to the evidence story and it is the one gap the ledgers cannot
close on their own.

**Deeper policy and expression fidelity in APIM.** Real APIM policies are
saturated with C# expressions, so expression evaluation is the capability that
compounds across everything else the gateway does.

**More of ARM.** The arm-emulator ledger is deliberately scoped to the
authorization slice. Broadening it is a question of which resource providers
the family's own consumers actually need, answered by demand rather than by
completeness for its own sake.

## Candidate emulators

No commitments, listed so the shape of the ecosystem is legible. The ordering
principle is the same one that produced the current set: emulate what blocks a
local development loop, starting with the services that have no local story at
all.

The strongest candidates are the services that sit next to the analytics plane
already covered, since that is where this ecosystem is genuinely alone, and the
Azure services whose absence forces a tenant round trip in an otherwise local
application stack.

If you want a service emulated, the useful thing to say is not "please add X"
but "here is the loop X is blocking". That framing is what decides ordering.
