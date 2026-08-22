#!/usr/bin/env python3
"""Copy the third-party images the family depends on into its own registry.

    scripts/mirror_images.py              # report every mirror against upstream
    scripts/mirror_images.py --check      # exit 1 if a mirror is missing or moved
    scripts/mirror_images.py --push       # copy upstream -> GHCR, record the digests
    scripts/mirror_images.py --self-test  # prove the checks can fail

WHY (G44). OpenMetadata ships from `docker.getcollate.io`, a vendor registry
backed by neither Docker Hub nor GHCR, and four repositories pull it on nightly
crons. On 2026-08-22 two of seven acceptance runs died at `make up` with a TLS
handshake timeout, and the rerun died again with `connection reset by peer` --
so this is not a hiccup a retry absorbs, and the bounded retry
`fabric-emulator/e2e/governance/stack.py` carries would not have saved either
run. A consumer that pulls from the registry the family already trusts has one
fewer way to go red for somebody else's reason.

`buildx imagetools create`, NEVER pull/tag/push. Both images carry a manifest
INDEX with linux/amd64 and linux/arm64 (and their attestations). `docker pull`
resolves the index to the puller's own architecture, so a mirror made that way
holds one arch: CI on amd64 would stay green while every arm64 laptop in the
family broke, which is the worst shape a defect can have. `imagetools create`
copies the index itself and never materialises a layer locally. The platform
list in mirrors.json exists so `--check` FAILS for this rather than trusting
this paragraph.

DIGESTS ARE COMPUTED FROM THE RAW MANIFEST BYTES, which is what an OCI digest
is: sha256 over exactly the bytes the registry serves for that reference. That
avoids asking one tool to report what another tool decided, and it is why
`--check` can compare a mirror to its record without pulling anything.

WHAT THIS DOES NOT DO. It cannot make a new GHCR package public: that needs
`admin:packages`, which no workflow token has. A first mirror lands PRIVATE and
someone with the account has to flip it, or every consumer needs a docker login
it does not have today.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REGISTRY_FILE = Path(__file__).resolve().parent.parent / "mirrors.json"


def load() -> dict:
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def save(doc: dict) -> None:
    REGISTRY_FILE.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def raw_manifest(ref: str) -> bytes | None:
    """The bytes the registry serves for `ref`, or None if it serves none.

    None means "not there or not reachable", and the caller must treat those as
    the same thing: both mean this reference cannot be relied on right now, and
    a mirror check that passed on an unreachable registry would be a check that
    passes when the network is down.
    """
    got = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", "--raw", ref],
        capture_output=True,
    )
    if got.returncode != 0:
        return None
    return got.stdout


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def platforms(raw: bytes) -> list[str]:
    """The os/arch pairs an index advertises, attestations excluded.

    Attestation manifests are recorded as platform `unknown/unknown`; they are
    copied with everything else and are not what a consumer selects on, so they
    are not part of the promise this checks.
    """
    doc = json.loads(raw)
    out = []
    for entry in doc.get("manifests", []):
        p = entry.get("platform") or {}
        pair = f"{p.get('os')}/{p.get('architecture')}"
        if "unknown" in pair:
            continue
        out.append(pair)
    return sorted(set(out))


def mirror_ref(doc: dict, image: dict) -> str:
    tag = image["upstream"].rsplit(":", 1)[1]
    return f"{doc['registry']}/{image['mirror']}:{tag}"


def inspect_all(doc: dict) -> list[dict]:
    rows = []
    for image in doc["images"]:
        up = raw_manifest(image["upstream"])
        mr = raw_manifest(mirror_ref(doc, image))
        rows.append({
            "image": image,
            "mirror_ref": mirror_ref(doc, image),
            "upstream_digest": digest(up) if up else None,
            "upstream_platforms": platforms(up) if up else [],
            "mirror_digest": digest(mr) if mr else None,
            "mirror_platforms": platforms(mr) if mr else [],
        })
    return rows


def complaints(doc: dict, rows: list[dict]) -> list[str]:
    """Everything wrong with the mirrors, as sentences.

    A LIST, so one run names every problem. And an ABSENT mirror is a
    complaint, never a skip: "we have not mirrored it yet" and "we mirrored it
    and it is fine" must not print the same thing.
    """
    bad = []
    for row in rows:
        image = row["image"]
        name = image["upstream"]
        want = sorted(image["platforms"])

        if row["mirror_digest"] is None:
            bad.append(
                f"{name}: no mirror at {row['mirror_ref']} -- either it was "
                f"never pushed, or the package is private and this token "
                f"cannot see it"
            )
            continue

        recorded = image.get("index")
        if not recorded:
            bad.append(
                f"{name}: the mirror exists but mirrors.json records no digest "
                f"for it, so nothing here can tell whether it moved"
            )
        elif recorded != row["mirror_digest"]:
            bad.append(
                f"{name}: {row['mirror_ref']} serves {row['mirror_digest']}, "
                f"mirrors.json records {recorded}"
            )

        if row["mirror_platforms"] != want:
            bad.append(
                f"{name}: the mirror carries {row['mirror_platforms'] or 'nothing'} "
                f"and must carry {want} -- an index collapsed to one architecture "
                f"is how CI stays green while every other machine breaks"
            )

        # UPSTREAM IS REPORTED, NOT ENFORCED. A vendor moving its own tag is
        # their business and not a defect here; adopting the move silently
        # would be. Unreachable upstream is likewise not a failure: the whole
        # point of the mirror is that the family no longer depends on it being
        # up.
        was = image.get("upstream_index")
        if row["upstream_digest"] and was and was != row["upstream_digest"]:
            bad.append(
                f"{name}: UPSTREAM TAG MOVED. mirrored from {was}, the vendor "
                f"now serves {row['upstream_digest']}. Re-run --push to adopt "
                f"it deliberately"
            )
    return bad


def push(doc: dict) -> int:
    for image in doc["images"]:
        target = mirror_ref(doc, image)
        print(f"==> {image['upstream']} -> {target}", flush=True)
        got = subprocess.run(
            ["docker", "buildx", "imagetools", "create", "--tag", target,
             image["upstream"]],
        )
        if got.returncode != 0:
            print(f"copy failed for {image['upstream']}", file=sys.stderr)
            return 1

    # RE-READ FROM THE REGISTRY rather than trusting what the copy said it did.
    # The recorded digest has to be the one a consumer will resolve, and the
    # only authority on that is the registry.
    rows = inspect_all(doc)
    for row in rows:
        row["image"]["index"] = row["mirror_digest"]
        row["image"]["upstream_index"] = row["upstream_digest"]
    save(doc)

    bad = complaints(doc, rows)
    report(rows)
    if bad:
        print("\nmirror_images FAILED after pushing:", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("\nmirrors.json updated")
    return 0


def report(rows: list[dict]) -> None:
    print(f"{'image':<52} {'mirror':<24} {'arch':<24} state")
    for row in rows:
        up = row["image"]["upstream"]
        state = "MISSING" if row["mirror_digest"] is None else (
            "ok" if row["mirror_digest"] == row["image"].get("index") else "moved")
        print(f"{up:<52} {row['image']['mirror']:<24} "
              f"{','.join(row['mirror_platforms']) or '-':<24} {state}")
        if row["mirror_digest"]:
            print(f"    {row['mirror_digest']}")


def self_test() -> int:
    """Prove the checks can fail, on data rather than on a live registry.

    A gate nobody has watched fail is a gate nobody knows the direction of.
    """
    doc = {"registry": "ghcr.io/example", "images": [{
        "upstream": "vendor.example/thing:1.0", "mirror": "thing",
        "index": "sha256:aaa", "upstream_index": "sha256:up",
        "platforms": ["linux/amd64", "linux/arm64"]}]}

    def row(**over):
        base = {"image": doc["images"][0], "mirror_ref": "ghcr.io/example/thing:1.0",
                "upstream_digest": "sha256:up", "upstream_platforms": [],
                "mirror_digest": "sha256:aaa",
                "mirror_platforms": ["linux/amd64", "linux/arm64"]}
        return {**base, **over}

    cases = [
        ("a healthy mirror", row(), 0),
        ("an absent mirror", row(mirror_digest=None, mirror_platforms=[]), 1),
        ("a mirror that moved", row(mirror_digest="sha256:bbb"), 1),
        ("an index collapsed to one arch",
         row(mirror_platforms=["linux/amd64"]), 1),
        ("upstream's tag moved", row(upstream_digest="sha256:elsewhere"), 1),
    ]
    failures = 0
    for name, r, want in cases:
        got = len(complaints(doc, [r]))
        ok = (got > 0) == (want > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got} complaint(s)")
        failures += 0 if ok else 1

    # And the one that is reported rather than failed: no recorded digest to
    # compare upstream against means no drift claim either way.
    quiet = dict(doc["images"][0], upstream_index=None)
    got = complaints({"registry": "x", "images": [quiet]},
                     [row(image=quiet, upstream_digest="sha256:elsewhere")])
    ok = not got
    print(f"  {'ok  ' if ok else 'FAIL'} an unrecorded upstream is not drift: {len(got)}")
    failures += 0 if ok else 1

    print("self-test FAILED" if failures else "self-test passed")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="exit 1 if a mirror is missing, moved or single-arch")
    p.add_argument("--push", action="store_true",
                   help="copy upstream into the mirror and record the digests")
    p.add_argument("--self-test", action="store_true",
                   help="prove the checks can fail")
    args = p.parse_args()

    if args.self_test:
        return self_test()

    doc = load()
    if args.push:
        return push(doc)

    rows = inspect_all(doc)
    report(rows)
    sys.stdout.flush()  # the table belongs ABOVE the complaints in a CI log
    bad = complaints(doc, rows)
    if bad:
        print("\nmirror_images FAILED", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1 if args.check else 0
    print("\nevery mirror matches its record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
