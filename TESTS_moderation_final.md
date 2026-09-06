# Test Results — ContentModerationRegistry

All tests below were executed live on GenLayer Studio (not simulated locally).

**Deployed contract (fixed version):** `0xf7...19C2`
**Network:** GenLayer Studio (studionet)
**Test account (original submitter):** `0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48`

---

## Round 2 tests — verifying the 4 reviewer-requested fixes

### 1. Deploy (fixed contract)

- **Tx:** [`0xe3757f7afba3d2f7ed9b79d6e3f081992e9e4ff4ae4e63524fa0abfa667bfeec`](https://explorer-studio.genlayer.com/tx/0xe3757f7afba3d2f7ed9b79d6e3f081992e9e4ff4ae4e63524fa0abfa667bfeec)
- **Constructor args:** `owner = 0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48`, `initial_policy = {"no_spam": "no promotional spam links"}`
- **Result:** SUCCESS, FINALIZED

### 2. submit_content — reject case, with content_hash and coherence round

- **Tx:** [`0xeb6411da6bb1c40e02acc73ae1e2fdd355176be87b9650c38a481260ba72a01a`](https://explorer-studio.genlayer.com/tx/0xeb6411da6bb1c40e02acc73ae1e2fdd355176be87b9650c38a481260ba72a01a)
- **Input:** `content_id="c1"`, `content_text="Buy cheap followers now, click this link!!!"`
- **On-chain Equivalence Principles Output:**
  - Principle #0: `{"decision": "reject", "matched_rule_id": "no_spam"}`
  - Principle #1: `"yes"` (the independent coherence-confirmation round)
- **Result:** SUCCESS, FINALIZED

`get_decision("c1")`:
```json
{
  "coherence_confirmed": true,
  "content_hash": "580ae6f9c85ea6899cb9a17c49d246c9e243ecd3a50be3682d4fb8b9a74c3909",
  "decision": "reject",
  "matched_rule_id": "no_spam",
  "policy_version": 1,
  "status": "final",
  "submitter": "0x8F4F89D5fc40E3DB9ec5d52d5e181801FBcB4d48",
  "timestamp": 1788682490
}
```
The two Equivalence Principle entries recorded on-chain are direct, verifiable proof that the coherence check is a real second consensus round, not a hardcoded value — addressing the reviewer's Issue 3.

### 3. Fix verification — appeal from a non-submitter address (must revert)

- **Tx:** [`0xa17989de929e352a79736f797f7623c8c1bbadf249341375dc4f9b80f2b0eeff`](https://explorer-studio.genlayer.com/tx/0xa17989de929e352a79736f797f7623c8c1bbadf249341375dc4f9b80f2b0eeff)
- **Input:** `content_id="c1"`, same `content_text`, called from an address other than the original submitter
- **Result:** ERROR — `AssertionError: only the original submitter may appeal`

This confirms Issue 2 (appeal-slot griefing) is fixed: an unrelated caller cannot consume the single appeal opportunity.

### 4. Fix verification — appeal with mismatched content_text (must revert)

- **Tx:** [`0x8fe12fceef2502a2a74a43c93f72af14e7e174d3142458bc3900557c57560c4d`](https://explorer-studio.genlayer.com/tx/0x8fe12fceef2502a2a74a43c93f72af14e7e174d3142458bc3900557c57560c4d)
- **Input:** `content_id="c1"`, `content_text="This is completely different text"` (deliberately altered), called from the correct submitter address
- **Result:** ERROR — `AssertionError: content_text does not match the originally moderated content`

This confirms Issue 1 (evidence binding) is fixed: even the correct submitter cannot substitute different content into an appeal.

### 5. Successful appeal — correct submitter, correct content_text

- **Tx:** [`0x933b52fb8bd355b421ce88c762bd56eeb5a7e4061106c330ce407bc940a65f1c`](https://explorer-studio.genlayer.com/tx/0x933b52fb8bd355b421ce88c762bd56eeb5a7e4061106c330ce407bc940a65f1c)
- **Input:** `content_id="c1"`, exact original `content_text`, `appellant_argument="This is a legitimate business promotion, not spam"`
- **On-chain Equivalence Principles Output:**
  - Principle #0: `{"decision": "reject", "matched_rule_id": "no_spam"}`
  - Principle #1: `"yes"`
- **Result:** SUCCESS, FINALIZED — appeal dismissed (decision upheld as `reject`), demonstrating the appeal still runs a full independent two-round re-evaluation once the caller and content are validated.

### 6. Rule-fallback logic (Issue 4) — implemented, not independently triggered in this test run

`_normalize_verdict` validates `matched_rule_id` against the current policy's actual keys for any non-approve decision, substituting a canonical `unspecified_violation` id if the model returns an empty or invalid rule id. In the tests above, the model correctly cited the real `no_spam` rule, so the fallback path was not exercised live — it is verifiable by code review of `_normalize_verdict` in the updated contract source.

---

## Round 1 tests (original submission, prior contract version)

*(Preserved for continuity — these establish the baseline consensus, policy versioning, and reputation-tracking behavior; access-control and evidence-binding were not yet present in this version and were added in Round 2 above.)*

### Deploy
- **Tx:** `0x89684aa1cb97ffcbb24fee0bcdf8c111f4dd2638bef7526229e3c25089943dc6`
- **Result:** SUCCESS, FINALIZED

### submit_content — reject case
- **Tx:** `0x670a9b1a95a2014060f75785194cbbba4f9e1cf0a6eb85786841392c076344c4`
- One consensus round saw "Majority disagreement, rotating the leader" before validators converged — GenLayer's Optimistic Democracy leader-rotation mechanism observed live.
- `get_decision("t2")` returned `decision: "reject"`, `matched_rule_id: "no_spam"`.

### appeal — dismissed case
- **Tx:** `0x7cd5a31216cb6bb99f5e7304daea43706d62967191812d43a0f85d9c3a56fd7f`
- Appeal correctly re-ran consensus and upheld the original `reject` decision (`overturned: false`); reputation `upheld` counter incremented.

## Summary

| Behavior tested | Verified on-chain? |
|---|---|
| Structured two-round consensus (classification + independent coherence confirmation) | ✅ (visible as two Equivalence Principles per transaction) |
| Policy version locked into decision record | ✅ |
| Content hash stored and enforced on appeal (evidence binding) | ✅ |
| Appeal restricted to original submitter (access control) | ✅ |
| Appeal with altered evidence correctly reverts | ✅ |
| Appeal from unauthorized address correctly reverts | ✅ |
| Valid appeal (correct caller + content) still runs full re-evaluation | ✅ |
| Rule-id validation with canonical fallback | Implemented; verifiable by code review |
| Reputation counters update on appeal outcome | ✅ (Round 1 test) |
| Leader rotation under validator disagreement observed live | ✅ (Round 1 test) |

## Known limitations observed

- The coherence-check round adds an extra LLM round-trip per transaction; under Studio's simulated multi-validator load, individual validators can occasionally time out, though consensus still finalizes once quorum is met.
- One Studio RPC call (`gen_getContractSchemaForCode`) intermittently returned schema-related warnings mid-session in earlier testing; this did not affect any actual contract transaction.
