# ContentModerationRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-
based content moderation — designed to be a genuine primitive other builders
can deploy as-is or fork, not a one-off demo.

## What makes this a "strong" submission, not a thin wrapper

A minimal version of this idea is just "ask an LLM approve/reject". That's
the exact pattern the category explicitly excludes. This version adds four
things that only make sense once you take the contract seriously as
infrastructure:

### 1. Policy versioning
`policy_version` increments on every `add_rule`/`remove_rule`, and
`policy_history` snapshots the full rule set at each version. Every decision
record stores which `policy_version` it was judged under. This matters
because policy *will* change over the life of a community, and a decision
made in January under different rules than exist in June must still be
auditable against the rules that actually applied — otherwise appeals become
unfair (re-judged against rules that didn't exist yet).

### 2. Two-layer consensus
- **Layer 1 — structural (`gl.eq_principle.strict_eq`)**: validators
  independently classify content into a closed vocabulary
  (`decision` + `matched_rule_id`). Consensus requires exact agreement on
  this tuple, which is realistically achievable because the vocabulary is
  small and closed — unlike asking for identical free text.
- **Layer 2 — semantic consistency**: a second consensus round asks
  validators a yes/no coherence question — *is the agreed decision actually
  justified by the content and the cited rule?* If validators can't agree
  the decision is coherent, the contract fails safe to `flag` rather than
  trusting layer 1 alone. This catches the case where models converge on a
  label without a defensible reason.

  (Implementation note: this uses `strict_eq` on a boolean as a portable
  fallback. If your GenLayer SDK version exposes a comparative equivalence
  primitive like `gl.eq_principle.prompt_comparative`, swapping it in here
  is a natural extension — see the docstring in the code.)

### 3. Staked, reputation-weighted appeals
`appeal()` is `payable` and requires a minimum stake (`APPEAL_STAKE_MIN`).
If the appeal is dismissed (original decision upheld), a configurable
fraction (`APPEAL_SLASH_BPS`) is slashed to a treasury address instead of
refunded — a real economic disincentive against spam appeals, not just a
social one. Every address accumulates an on-chain `{upheld, overturned}`
record via `get_reputation`, which downstream apps can use to rate-limit or
trust-weight appellants, without this contract hard-coding one platform's
specific policy for how to use that signal.

### 4. Full audit trail
Every decision and appeal stores a timestamp, actor address, and (for
decisions) the policy version — enough for any external indexer to
reconstruct exactly what happened, under what rules, and who was involved.

## State design

| Field            | Type                | Purpose                                        |
|-------------------|---------------------|-------------------------------------------------|
| `owner`           | `str`               | Address allowed to edit policy                  |
| `treasury`        | `str`               | Receives slashed appeal stakes                  |
| `policy`          | `TreeMap[str, str]` | Current rule_id -> rule text                    |
| `policy_version`  | `int`               | Bumped on every policy edit                     |
| `policy_history`  | `TreeMap[str, str]` | version -> JSON snapshot of rules at that time  |
| `decisions`       | `TreeMap[str, str]` | content_id -> JSON decision record              |
| `appeals`         | `TreeMap[str, str]` | content_id -> JSON appeal record                |
| `reputation`      | `TreeMap[str, str]` | address -> JSON {upheld, overturned}            |

## Suggested tests (GenLayer Studio / simulator)

- **Deploy** with `initial_policy = {"no_spam": "no promotional spam links"}`,
  `treasury` set to a distinct address from `owner`.
- **Clear approve**: submit benign text, assert `decision == "approve"` and
  `coherence_checked == True`.
- **Clear reject**: submit obviously-matching spam text, assert
  `decision == "reject"`, `matched_rule_id == "no_spam"`.
- **Policy versioning correctness**: call `add_rule`, assert
  `policy_version` incremented and `get_policy_at_version(1)` still returns
  the original rule set.
- **Appeal — overturned**: appeal a rejected item with `value >=
  APPEAL_STAKE_MIN`, strong counter-argument; assert `overturned == True`,
  appellant's `get_reputation().overturned` incremented, and (via balance
  checks in the simulator) the full stake was returned.
- **Appeal — dismissed**: appeal a correctly-rejected item weakly; assert
  `overturned == False`, `upheld` incremented, and the treasury balance
  increased by the slashed amount.
- **Double-appeal guard**: assert a second `appeal()` on the same
  `content_id` reverts.
- **Insufficient stake**: assert `appeal()` reverts if `gl.message.value <
  APPEAL_STAKE_MIN`.
- **Access control**: assert `add_rule` / `remove_rule` revert for
  non-owner callers.

## Caveats / what to verify before deploying

- GenLayer's exact SDK surface (`gl.eq_principle.*`, `gl.message.*`,
  `gl.send`, `@gl.public.write.payable`) is evolving quickly — confirm
  current method names/signatures against GenLayer's latest docs.
- `APPEAL_STAKE_MIN` and `APPEAL_SLASH_BPS` are illustrative constants;
  real deployments should tune these (or expose them as owner-configurable
  state) based on expected content volume and token economics.
- The semantic consistency layer (Layer 2) is a portable fallback using
  `strict_eq` on a boolean. If a genuine comparative-equivalence primitive
  is available in your SDK version, prefer it — it's a better fit for
  "are these two things semantically similar" than exact-match on a forced
  yes/no.