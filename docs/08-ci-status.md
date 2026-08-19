# 08 — CI status across the ecosystem

Twenty-five repos, each with its own CI. This page is how you answer "is
everything green?" without opening twenty-five Actions tabs.

```sh
git clone https://github.com/calvinchengx/emulators
cd emulators
./scripts/family_ci.py              # every member, one table
./scripts/family_ci.py --red-only   # just what needs attention
./scripts/family_ci.py entra-emulator   # one member, per workflow
```

[`.github/workflows/family-ci.yml`](https://github.com/calvinchengx/emulators/blob/main/.github/workflows/family-ci.yml)
runs the same sweep every thirty minutes and **fails the job when a member is
red**, so GitHub's own notifications do the alerting. There is no bespoke
notifier to keep working.

## Why it asks two questions instead of one

The obvious implementation reads each repo's head-commit check rollup. It is one
batched GraphQL query for all twenty-five, it costs a single point of the
5000-per-hour budget, and **on its own it is a false all-clear**.

Worked example, from the day this was written. `azure-emulators` reported
`statusCheckRollup = SUCCESS`. Its `Docs site` workflow was **absent from that
rollup entirely**: the head commit touched only `docker-compose.yml` and a
script, and the workflow is path-filtered to `docs/**` and `website/**`, so it
never ran. The rollup was green partly because things did not run.

So the tool asks two independent questions and reports both:

| question | how | what it catches |
|---|---|---|
| **A.** Is the tip of main green right now? | one batched GraphQL query | breakage on the newest commit, including runs still in flight |
| **B.** For each workflow, what did its most recent *completed* run on main conclude, and how long ago? | one REST call per repo, grouped by `workflow_id` | a workflow that has been broken for weeks because nobody touched its paths |

A member is green only when both agree. Question B is the one that finds real
problems, which is why the tool keeps working when A is unavailable: GraphQL
refuses unauthenticated callers, while the REST runs endpoint serves public
repos to anyone.

## What the columns mean

**`tip of main`** is question A. It reads `no checks on tip` when no workflow
ran on the head commit, which is information rather than an error, and is
exactly why it is never read alone.

**`oldest proof`** is the age of the stalest workflow's last completed run. A
green from nine days ago is a claim about last week, and this column is the
difference between knowing that and assuming otherwise. `azure-emulators` sits
at four days for precisely the path-filter reason above.

**The verdict** is one of five, and the middle three exist because collapsing
them into pass or fail would be a fabrication:

| | meaning |
|---|---|
| 🟢 | every workflow's last completed run passed, and none are stale |
| 🔴 | a workflow's last completed run failed or timed out |
| 🟡 | needs a look: something cancelled or skipped, a stale green, or substantive code with no CI at all |
| 🟠 | misdeclared: the registry and reality disagree, so one of them is wrong |
| ⚪ | unknown |

`cancelled` is neither pass nor fail. At the time of writing `entra-emulator`'s
`flutter-e2e.yml` is cancelled, green the four days before. Calling that green
hides a gap; calling it red invents a failure.

## The registry

[`members.json`](https://github.com/calvinchengx/emulators/blob/main/members.json)
lists every repo with its tier and, crucially, **whether CI is expected**:

- `required`: a red workflow here is a family-level failure.
- `missing`: substantive code with no workflow at all. A gap to close.
- `none`: nothing to verify yet, correct for a reserved repo.

That last distinction is what earns the file. Without a declared expectation, a
reserved repo with no CI and a repo whose CI was deleted print the same blank
row, and the second one is a problem.

Four repos currently sit at `missing`: `contoso-sources`, the
`fabric-airflow-builtin` leaf and platform, and `databricks-platform-airflow3`.
All four carry real code that nothing verifies. `contoso-sources` is the one
that matters most, since every platform generates its vendor stack from it.

The registry is also the source of truth for **status**, derived from what is on
main rather than from what a README claims. Several READMEs still say
"Reserved. It holds nothing but this file and a LICENSE" over a tree carrying
dozens of files, and trusting that prose put two wrong statuses into this
repository's first commit.

## Cost

One sweep is one GraphQL point plus twenty-five REST calls, against a
5000-per-hour authenticated limit. Polling every thirty minutes uses under one
percent of the budget, which is why the cadence is a choice rather than a
compromise.

## What this deliberately is not

**A badge wall.** Twenty-five repos times five workflows is more than a hundred
images, gives no aggregate answer, and inherits the same path-filter blindness
as the rollup.

**A push model.** Having all twenty-five repos fire `repository_dispatch` at the
hub means twenty-five workflows to add and keep in sync, in exchange for
freshness that a thirty-minute cadence already provides.

**A long-lived local watcher.** An earlier attempt at exactly that covered only
the emulators, missed the sixteen product and platform repos, and reported a
clean sweep having checked nothing, because in zsh `for r in $REPOS` iterates
once over the whole string. This tool is Python for that reason, and its own
`--self-test` asserts that an unresolvable repo fails loudly rather than being
skipped.
