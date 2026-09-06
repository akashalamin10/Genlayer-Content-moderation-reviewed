# ContentModerationRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-based
content moderation — designed as genuine infrastructure other builders can
deploy or fork, with real safeguards against evidence tampering and
appeal-slot griefing.

**Deployed contract (GenLayer Studio):** `0xf7...19C2`
**Network:** GenLayer Studio (studionet)

## What makes this a strong primitive

### 1. Policy versioning
`policy_version` increments on every `add_rule` / `remove_rule`, and
`policy_history` snapshots the full rule set at each version. Every decision
record stores the `policy_version` it was judged under, so a decision remains
auditable against the exact rules that applied at the time — even after the
policy changes later.

### 2. Two independent, verifiable consensus rounds
- **Round 1 — structural classification** (`gl.eq_principle.prompt_comparative`):
  validators independently classify content into a closed vocabulary
  (`decision` + `matched_rule_id`). The equivalence principle requires the
  decision to match exactly, with limited tolerance on `matched_rule_id`
  wording.
- **Round 2 — independent coherence confirmation** (`gl.eq_principle.prompt_comparative`
  on a fresh yes/no question): a second, separately-seeded round asks
  validators whether the agreed decision is actually justified by the content
  and the cited rule. If validators cannot confirm coherence, the contract
  fails safe to `flag` rather than trusting round 1 alone.

  This is not a cosmetic flag — every transaction's on-chain **Equivalence
  Principles Output** shows two distinct entries (`Equivalence Principle #0`
  and `Equivalence Principle #1`), which is direct, verifiable proof that two
  separate consensus rounds actually executed. See the verified test evidence
  below.

### 3. Evidence-bound appeals
`submit_content` stores a SHA-256 hash of the moderated content
(`content_hash`) alongside the decision. `appeal` recomputes the hash of the
`content_text` argument the caller supplies and reverts if it doesn't match
the original — so an appeal cannot be used to swap in different content and
have the contract render a decision on evidence that was never actually
reviewed the first time.

### 4. Appeal access control
Only the original submitter (recorded at `submit_content` time) may call
`appeal` on their content. Since each content item allows exactly one appeal,
this prevents an unrelated caller from consuming that single appeal
opportunity and locking the real submitter out of ever appealing.

### 5. Validated rule citations
For any non-`approve` decision, `matched_rule_id` is validated against the
policy's actual rule set (case/format-normalized). If the model returns an
empty or non-existent rule id for a reject/flag decision, the contract falls
back to a canonical `unspecified_violation` id rather than silently storing
an invalid or fabricated rule reference.

## State design

| Field           | Type                | Purpose                                             |
|------------------|---------------------|--------------------------------------------------------|
| `owner`          | `str`               | Address allowed to edit policy                        |
| `policy`         | `TreeMap[str, str]` | Current rule_id -> rule text                          |
| `policy_version` | `u256`              | Bumped on every policy edit                            |
| `policy_history` | `TreeMap[str, str]` | version -> JSON snapshot of rules at that time         |
| `decisions`      | `TreeMap[str, str]` | content_id -> JSON decision record (includes `content_hash`, `submitter`, `coherence_confirmed`) |
| `appeals`        | `TreeMap[str, str]` | content_id -> JSON appeal record                       |
| `reputation`     | `TreeMap[str, str]` | address -> JSON {upheld, overturned}                   |

## How consensus is used

1. `submit_content` builds a prompt from the current policy and the content,
   then calls `gl.eq_principle.prompt_comparative` to get validator agreement
   on a structured `(decision, matched_rule_id)` pair.
2. If the decision is not `approve`, a second, independently-seeded
   `gl.eq_principle.prompt_comparative` call asks validators a yes/no
   coherence question about that specific decision and rule.
3. Both rounds' outputs are visible on-chain as separate Equivalence
   Principles — auditable proof the two-layer design is real, not just a
   named field.
4. `appeal` repeats the same two-round pattern with the appellant's
   counter-argument injected, after verifying the caller is the original
   submitter and the supplied content matches the stored hash.

## Verified on-chain test evidence

All transactions below were executed live on GenLayer Studio.

| Test | Tx | Result |
|---|---|---|
| Deploy | [`0xe3757f7a...`](https://explorer-studio.genlayer.com/tx/0xe3757f7afba3d2f7ed9b79d6e3f081992e9e4ff4ae4e63524fa0abfa667bfeec) | SUCCESS |
| `submit_content` — reject case, two Equivalence Principles recorded | [`0xeb6411da...`](https://explorer-studio.genlayer.com/tx/0xeb6411da6bb1c40e02acc73ae1e2fdd355176be87b9650c38a481260ba72a01a) | SUCCESS |
| `appeal` from a non-submitter address — correctly reverted | [`0xa17989de...`](https://explorer-studio.genlayer.com/tx/0xa17989de929e352a79736f797f7623c8c1bbadf249341375dc4f9b80f2b0eeff) | ERROR: `only the original submitter may appeal` |
| `appeal` with mismatched content_text — correctly reverted | [`0x8fe12fce...`](https://explorer-studio.genlayer.com/tx/0x8fe12fceef2502a2a74a43c93f72af14e7e174d3142458bc3900557c57560c4d) | ERROR: `content_text does not match the originally moderated content` |
| `appeal` from the real submitter with matching content — accepted, two Equivalence Principles recorded again | [`0x933b52fb...`](https://explorer-studio.genlayer.com/tx/0x933b52fb8bd355b421ce88c762bd56eeb5a7e4061106c330ce407bc940a65f1c) | SUCCESS |

### What this demonstrates

- The evidence-binding check (`content_hash`) genuinely blocks a caller from
  substituting different content during an appeal.
- The submitter-only access control genuinely blocks an unrelated caller from
  consuming the single appeal opportunity.
- Both the initial decision and the appeal show two separate Equivalence
  Principle entries on-chain, confirming the coherence-check round is a real,
  independently-executed second consensus round, not a hardcoded flag.

## Suggested tests to reproduce (GenLayer Studio)

- Deploy with a small policy, e.g. `{"no_spam": "no promotional spam links"}`.
- `submit_content` with clearly spammy text — confirm `decision: "reject"`,
  `matched_rule_id` is a real policy key, `coherence_confirmed: true`, and
  `content_hash` is populated.
- Attempt `appeal` from a different address — confirm it reverts with
  `only the original submitter may appeal`.
- Attempt `appeal` from the correct address but with different `content_text`
  — confirm it reverts with `content_text does not match...`.
- Attempt `appeal` from the correct address with the exact original
  `content_text` — confirm it succeeds and updates `status` to `"appealed"`.
- Confirm `add_rule` / `remove_rule` revert for non-owner callers.

## Caveats

- GenLayer's exact SDK surface (`gl.eq_principle.*`, `gl.message.*`) is
  evolving — verify current method names/signatures against GenLayer's latest
  docs before deploying elsewhere.
- The coherence-check round adds an extra round-trip of validator LLM calls;
  under Studio's simulated multi-validator load this can occasionally result
  in individual validator timeouts, though consensus still finalizes once
  quorum is met.
- `content_hash` uses SHA-256 over the raw `content_text` string; this assumes
  the caller submits the content as plain text rather than a reference to
  external content that could change after submission.
