# 10 — Mirrored images

The family runs on images it builds and images it does not. The ones it does
not come from Docker Hub, from GHCR, and from **one vendor registry that is
neither**. That last one is the subject of this page.

```sh
./scripts/mirror_images.py              # every mirror against its record
./scripts/mirror_images.py --check      # exit 1 if one is missing or moved
./scripts/mirror_images.py --push       # copy upstream into GHCR (needs a login)
./scripts/mirror_images.py --self-test  # prove the checks can fail
```

The declaration is [`mirrors.json`](https://github.com/calvinchengx/emulators/blob/main/mirrors.json).

## The failure this exists to remove

OpenMetadata ships from `docker.getcollate.io`. Four repositories pull it:
`fabric-emulator`, `fabric-platform-notebook-pipelines`,
`databricks-platform-jobs` and `snowflake-platform-tasks`. Every one of them
runs a nightly cron, so when that registry is unavailable the family fails
**unattended, on a schedule**, and the failure reads as a broken governance step
rather than as somebody else's registry.

Measured on 2026-08-22, across seven acceptance runs dispatched within the same
second:

```
om-migrate Error Head "https://docker.getcollate.io/v2/openmetadata/server/manifests/1.13.2":
  net/http: TLS handshake timeout
```

and, on the rerun nineteen minutes later, the same pull with a different error:

```
openmetadata Error Get "https://docker.getcollate.io/v2/openmetadata/server/manifests/sha256:f5cdd8b6...":
  read tcp 10.1.0.45:40928->52.33.86.107:443: read: connection reset by peer
```

`fabric-emulator/e2e/governance/stack.py` already carries a bounded retry for
exactly this, and **it would not have saved either run**: two attempts nineteen
minutes apart both failed. A retry absorbs a hiccup. This was not one.

## Why not everything is mirrored

`opensearchproject/opensearch` is in the same governance stack and is
deliberately **not** here. It is on Docker Hub, which the family already trusts,
so mirroring it would add a copy to keep in step and buy no availability. The
rule is: mirror an image the family depends on and does not build, whose
registry is not one it already trusts.

## The two things that make this a check rather than a copy

**The index, not an image.** Both OpenMetadata images are multi-arch
(`linux/amd64` and `linux/arm64`). `docker pull` resolves a manifest index to
the puller's own architecture, so a mirror made with pull, tag and push holds
**one** arch — and since CI is amd64 and the laptops are arm64, that shape stays
green in every place anyone would look while breaking every place anyone
actually works. The copy therefore uses `docker buildx imagetools create`, which
copies the index itself, and `mirrors.json` records the platforms the index must
carry so the check fails rather than trusting this paragraph.

**A digest, computed rather than reported.** `mirrors.json` records the digest
of the mirror's index, and `--check` compares it against what the registry
serves today. The digest is `sha256` over exactly the manifest bytes the
registry returns, which is what an OCI digest *is* — no tool is asked to report
what another tool decided.

Upstream's digest is recorded too, and a tag that moves under us is **reported
and not adopted**: a vendor re-tagging is their business, and silently taking
the new bytes is the thing the record exists to prevent. Adopting it is
`--push`, which is a decision someone makes.

## Whether a consumer can actually pull it

Pushing a mirror and a consumer being able to use it are different questions,
and only the second one matters.

I expected the first push to create a **private** package, since making one
public needs `admin:packages` and no workflow token carries that. Measured on
[run 32551531685](https://github.com/calvinchengx/emulators/actions/runs/32551531685),
it did not: an anonymous GHCR token fetched the manifest, HTTP 200, from a
machine holding no `ghcr.io` credentials at all. Both packages were readable by
anyone the moment they existed. The prediction was wrong and nothing had to be
flipped.

That is a measurement and not a guarantee, so it is checked rather than
believed. The check job reads GHCR **with no login**, exactly as a laptop does,
and the push job reports each package's anonymous HTTP status into the run
summary. If a future mirror does land private, the symptom is a red check and a
`401` in the summary, with the settings URL beside it.

## What the copy proved

Both mirrored indexes carry `linux/amd64,linux/arm64`, and the mirror's index
digest is **identical to upstream's**:

| image | index digest |
|---|---|
| `openmetadata-server:1.13.2` | `sha256:f5cdd8b6…` |
| `openmetadata-postgresql:1.13.2` | `sha256:7c71755e…` |

Identical digests are the strong form of the claim. The index was copied byte
for byte, not rebuilt into something equivalent-looking, and the server digest
is the same one the failing pull named in the CI log this page opens with.
