#!/usr/bin/env python3
"""No family image is pulled from Docker Hub directly; mirror.gcr.io serves each one as Hub does.

    scripts/check_base_images.py                 # every member's published main
    scripts/check_base_images.py --member NAME   # one member
    scripts/check_base_images.py --local         # sibling checkouts' working trees
    scripts/check_base_images.py --no-digests    # skip the registry comparison
    scripts/check_base_images.py --self-test     # prove the checks can fail

WHY. Docker Hub's anonymous token endpoint resets connections under load, and
a job that pulls through it goes red for a reason that has nothing to do with
the change under test. On 2026-09-27 it failed two fabric-emulator jobs in one
morning (Dependabot #552 and the main run for #554), both at
`failed to fetch oauth token: Post "https://auth.docker.io/token" ... connection
reset by peer`, before a single test ran. data-agent-service hit the same wall
cutting v0.2.0 on 2026-08-23 and moved its base images to mirror.gcr.io.

WHY mirror.gcr.io AND NOT A COPY OF OUR OWN. It is Google's pull-through cache
of Docker Hub, so it follows every upstream rebuild with nothing here to keep
in step. Our own GHCR copies (mirrors.json `images`) remain for registries that
are neither Hub nor GHCR. Measured 2026-09-27 before switching: all 27 Hub
references in the family were served, every manifest byte-identical to Hub's.

TWO CHECKS.

  1. PROVENANCE. Every image reference in a member's Dockerfiles (FROM and
     COPY --from), compose files and workflow service containers resolves to
     an allowed registry. A bare `python:3.12-slim` is Docker Hub and fails.
     ENUMERATE GOOD, DEFAULT DENY: an unrecognised host fails too, printed as
     seen, rather than being assumed fine.

  2. FIDELITY. A cache that stopped following upstream would be a mirror that
     quietly stopped taking security rebuilds. For every mirror.gcr.io
     reference that names a concrete tag, the manifest index the cache serves
     must be byte-identical to Docker Hub's. A reference pinned by digest must
     be servable at that digest. Hub being unreachable is REPORTED, not
     failed: not depending on Hub being up is the point.

WHAT THIS DOES NOT SEE. `docker run IMAGE` inside scripts, Makefiles and
workflow `run:` steps. Those are shell, not declarations, and a regex over
shell is a guess.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGISTRY = HERE / "members.json"
MIRRORS = HERE / "mirrors.json"
OWNER = "calvinchengx"

MIRROR_HOST = "mirror.gcr.io"
HUB = "docker.io"


def policy() -> dict:
    return json.loads(MIRRORS.read_text(encoding="utf-8"))["docker_hub"]


def members() -> list[str]:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [m["name"] for m in doc["members"] if m.get("status") == "built"]


# --- finding the files -------------------------------------------------------

def is_candidate(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name.startswith("Dockerfile") or name.endswith(".Dockerfile"):
        return True
    if re.fullmatch(r"(docker-)?compose[\w.-]*\.ya?ml", name):
        return True
    return path.startswith(".github/workflows/") and name.endswith((".yml", ".yaml"))


def gh(path: str) -> str | None:
    got = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return got.stdout if got.returncode == 0 else None


def published_files(repo: str) -> list[tuple[str, str]] | None:
    tree = gh(f"repos/{OWNER}/{repo}/git/trees/main?recursive=1")
    if tree is None:
        return None
    out = []
    for entry in json.loads(tree).get("tree", []):
        if entry["type"] != "blob" or not is_candidate(entry["path"]):
            continue
        blob = gh(f"repos/{OWNER}/{repo}/git/blobs/{entry['sha']}")
        if blob is None:
            return None
        text = base64.b64decode(json.loads(blob)["content"]).decode("utf-8", "replace")
        out.append((entry["path"], text))
    return out


def local_files(repo: str) -> list[tuple[str, str]] | None:
    return tree_files(HERE.parent / repo)


def tree_files(root: Path) -> list[tuple[str, str]] | None:
    got = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True)
    if got.returncode != 0:
        return None
    return [(p, (root / p).read_text(errors="replace"))
            for p in got.stdout.splitlines() if is_candidate(p) and (root / p).is_file()]


# --- finding the references --------------------------------------------------

VAR = re.compile(r"\$\{(\w+)(?:(:?[-?])([^}]*))?\}|\$(\w+)")


def expand(ref: str, defaults: dict[str, str]) -> str:
    """Substitute what a declaration itself says a variable defaults to.

    A Dockerfile ARG default fills `${X}`; `${X:-d}` and `${X-d}` take `d`.
    `${X:?msg}` has no default by construction and stays as written, and the
    caller decides what an unresolved host means.
    """
    def sub(m: re.Match) -> str:
        name = m.group(1) or m.group(4)
        if name in defaults:
            return defaults[name]
        if m.group(2) in (":-", "-"):
            return m.group(3)
        return m.group(0)
    return VAR.sub(sub, ref)


def is_stage(ref: str, stages: set[str]) -> bool:
    """A name an earlier `FROM ... AS` defined, variables matched as wildcards.

    `FROM builder-${TARGETARCH}` selects `builder-amd64` or `builder-arm64`,
    which are stages, not images; nothing is pulled.
    """
    if "$" not in ref:
        return ref.lower() in stages
    pattern = re.sub(r"\\\$\\\{[^}]*\\\}|\\\$\w+", ".+", re.escape(ref.lower()))
    return any(re.fullmatch(pattern, st) for st in stages)


def dockerfile_refs(text: str) -> list[str]:
    defaults, stages, refs = {}, {"scratch"}, []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"ARG\s+(\w+)=(\S+)", s, re.I)
        if m:
            defaults.setdefault(m.group(1), m.group(2).strip("\"'"))
            continue
        m = re.match(r"FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", s, re.I)
        if m:
            ref = expand(m.group(1), defaults)
            if not is_stage(ref, stages):
                refs.append(ref)
            if m.group(2):
                stages.add(m.group(2).lower())
            continue
        for m in re.finditer(r"--from=(\S+)", s):
            ref = expand(m.group(1), defaults)
            if is_stage(ref, stages) or ref.isdigit():
                continue
            refs.append(ref)
    return refs


def compose_refs(text: str) -> list[str]:
    """`image:` values, plus workflow `container:` given as a bare string.

    A compose service that also has `build:` names its OWN output with
    `image:`, which is not a pull. Detected textually: an `image:` whose
    service block (same indentation run) contains `build:`.
    """
    refs = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(?:-\s+)?(image|container):\s*[\"']?([^\"'\s#]+)", line)
        if not m or m.group(3) in ("|", ">", "!reset", "null", "${{"):
            continue
        if m.group(2) == "container" and m.group(3).endswith(":"):
            continue
        ref = expand(m.group(3), {})
        if ref.startswith("${{"):
            continue
        indent = len(m.group(1))
        block = []
        for j in range(i - 1, -1, -1):
            if lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) < indent:
                break
            block.append(lines[j])
        for j in range(i + 1, len(lines)):
            if lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) < indent:
                break
            block.append(lines[j])
        if any(re.match(r"\s*build:", b) for b in block):
            continue
        refs.append(ref)
    return refs


def refs_in(path: str, text: str) -> list[str]:
    name = path.rsplit("/", 1)[-1]
    if name.startswith("Dockerfile") or name.endswith(".Dockerfile"):
        return dockerfile_refs(text)
    return compose_refs(text)


def host_of(ref: str) -> str:
    """The registry a reference pulls from, by Docker's own rule.

    The first path component is a registry only if it contains `.` or `:` or
    is `localhost`; otherwise the reference is Docker Hub's.
    """
    first = ref.split("/", 1)[0]
    if "/" in ref and ("." in first or ":" in first or first == "localhost"):
        return first
    if first.startswith("$"):
        return "?"
    return HUB


# --- judging -----------------------------------------------------------------

def judge(repo: str, path: str, ref: str, pol: dict) -> str | None:
    """None if the reference is acceptable, else why not."""
    if any(re.fullmatch(e["pattern"], ref) for e in pol.get("exempt", [])):
        return None
    host = host_of(ref)
    if host == HUB:
        return (f"{repo}/{path}: `{ref}` pulls from Docker Hub directly; "
                f"use {MIRROR_HOST}/{hub_path(ref)}")
    if host in pol["allowed_hosts"]:
        return None
    return (f"{repo}/{path}: `{ref}` pulls from {host!r}, which is not an allowed "
            f"registry (allowed: {', '.join(pol['allowed_hosts'])})")


def hub_path(ref: str) -> str:
    return ref if "/" in ref.split(":", 1)[0].split("@", 1)[0] else f"library/{ref}"


def raw_manifest(ref: str) -> bytes | None:
    got = subprocess.run(["docker", "buildx", "imagetools", "inspect", "--raw", ref],
                         capture_output=True)
    return got.stdout if got.returncode == 0 else None


def fidelity(ref: str) -> tuple[str | None, str | None]:
    """(complaint, note) for one mirror.gcr.io reference."""
    if "$" in ref:
        return None, f"`{ref}`: carries an unresolved variable, so not compared"
    rest = ref.split("/", 1)[1]
    if "@sha256:" in rest:
        if raw_manifest(ref) is None:
            return f"`{ref}`: {MIRROR_HOST} does not serve this digest", None
        return None, None
    if ":" not in rest.rsplit("/", 1)[-1]:
        rest += ":latest"
    mirror = raw_manifest(f"{MIRROR_HOST}/{rest}")
    if mirror is None:
        return f"`{ref}`: {MIRROR_HOST} does not serve it", None
    hub = raw_manifest(f"{HUB}/{rest}")
    if hub is None:
        return None, f"`{ref}`: Docker Hub unreachable, fidelity not compared"
    if hashlib.sha256(mirror).digest() != hashlib.sha256(hub).digest():
        return (f"`{ref}`: {MIRROR_HOST} serves sha256:{hashlib.sha256(mirror).hexdigest()[:12]}, "
                f"Docker Hub serves sha256:{hashlib.sha256(hub).hexdigest()[:12]}: the cache "
                f"is not following upstream"), None
    return None, None


def audit(repo: str, files: list[tuple[str, str]], pol: dict) -> tuple[list[str], set[str]]:
    bad, mirrored = [], set()
    for path, text in files:
        for ref in refs_in(path, text):
            why = judge(repo, path, ref, pol)
            if why:
                bad.append(why)
            elif host_of(ref) == MIRROR_HOST:
                mirrored.add(ref)
    return bad, mirrored


# --- self-test ---------------------------------------------------------------

def self_test() -> int:
    pol = {"allowed_hosts": ["mirror.gcr.io", "ghcr.io"],
           "exempt": [{"pattern": r"app:\w+", "reason": "built locally"}]}
    cases = [
        ("a bare official image", "FROM python:3.12-slim\n", 1),
        ("a namespaced Hub image", "FROM apache/kafka:3.9.1\n", 1),
        ("an explicit docker.io", "FROM docker.io/library/golang:1.27\n", 1),
        ("the mirror", "FROM mirror.gcr.io/library/golang:1.27\n", 0),
        ("an ARG default that is the mirror",
         "ARG R=mirror.gcr.io/library\nFROM ${R}/python:3.12-slim\n", 0),
        ("an ARG default that is Hub", "ARG V=3.12\nFROM python:${V}-slim\n", 1),
        ("a later stage by name", "FROM ghcr.io/x/y:1 AS build\nFROM build\n", 0),
        ("COPY --from a Hub image",
         "FROM ghcr.io/x/y:1\nCOPY --from=node:22-slim /a /b\n", 1),
        ("COPY --from a stage", "FROM ghcr.io/x/y:1 AS b\nFROM ghcr.io/x/z:1\nCOPY --from=b /a /b\n", 0),
        ("an unknown registry", "FROM quay.io/x/y:1\n", 1),
        ("a stage chosen by a variable",
         "FROM ghcr.io/x/y:1 AS builder-amd64\nFROM ghcr.io/x/y:1 AS builder-arm64\n"
         "FROM builder-${TARGETARCH}\n", 0),
        ("a variable that is not a stage", "FROM ghcr.io/x/y:1 AS b\nFROM python:${V}\n", 1),
    ]
    compose = [
        ("a Hub service", "services:\n  db:\n    image: postgres:16.4\n", 1),
        ("a variable tag on Hub",
         "services:\n  db:\n    image: postgres:${V:?see versions.env}\n", 1),
        ("a service that builds its own image",
         "services:\n  app:\n    build: .\n    image: app:dev\n", 0),
        ("a declared local image", "services:\n  app:\n    image: app:coverage\n", 0),
        ("the mirror in compose",
         "services:\n  db:\n    image: mirror.gcr.io/library/postgres:16.4\n", 0),
    ]
    failures = 0
    for name, text, want in cases:
        got = len(audit("r", [("Dockerfile", text)], pol)[0])
        ok = (got > 0) == (want > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got} complaint(s)")
        failures += not ok
    for name, text, want in compose:
        got = len(audit("r", [("docker-compose.yml", text)], pol)[0])
        ok = (got > 0) == (want > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got} complaint(s)")
        failures += not ok
    for ref, want in (("postgres:16.4", HUB), ("mirror.gcr.io/library/x:1", MIRROR_HOST),
                      ("localhost:5000/x", "localhost:5000"), ("apache/kafka:1", HUB)):
        ok = host_of(ref) == want
        print(f"  {'ok  ' if ok else 'FAIL'} host_of({ref}) = {host_of(ref)}")
        failures += not ok
    print("self-test FAILED" if failures else "self-test passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--member")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--path", help="audit one working tree, named by --member")
    ap.add_argument("--no-digests", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    pol = policy()
    names = [args.member] if args.member else members()
    bad, notes, mirrored = [], [], set()
    for repo in names:
        if args.path:
            files = tree_files(Path(args.path))
        else:
            files = local_files(repo) if args.local else published_files(repo)
        if files is None:
            bad.append(f"{repo}: could not read its files, so nothing about it is known")
            continue
        b, m = audit(repo, files, pol)
        bad += b
        mirrored |= m
        print(f"{repo:<48} {len(files):>3} files  {len(b):>3} direct-Hub/unknown")

    if not args.no_digests:
        for ref in sorted(mirrored):
            complaint, note = fidelity(ref)
            if complaint:
                bad.append(complaint)
            if note:
                notes.append(note)
        print(f"\ncompared {len(mirrored)} {MIRROR_HOST} reference(s) against Docker Hub")
    for n in notes:
        print(f"  note: {n}")
    sys.stdout.flush()
    if bad:
        print(f"\ncheck_base_images FAILED ({len(bad)})", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("\nevery image comes from an allowed registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
