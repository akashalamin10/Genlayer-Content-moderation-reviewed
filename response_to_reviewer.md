Thank you for the detailed review — all four issues have been addressed and re-verified live on GenLayer Studio. Summary below, with on-chain transaction evidence for each.

**1. Appeals are now bound to the originally moderated content.**
`submit_content` now stores a SHA-256 hash of the moderated content (`content_hash`) in the decision record. `appeal` recomputes the hash of the supplied `content_text` and reverts if it doesn't match, so an appellant cannot substitute different content to get a favorable re-evaluation.
Verified: an appeal attempt with altered content_text was correctly reverted with `"content_text does not match the originally moderated content"`.
https://explorer-studio.genlayer.com/tx/0x8fe12fceef2502a2a74a43c93f72af14e7e174d3142458bc3900557c57560c4d

**2. Only the original submitter may consume the single appeal opportunity.**
`appeal` now asserts the caller matches the `submitter` address recorded at `submit_content` time, before any other logic runs. This prevents an unrelated address from calling `appeal` first and permanently locking out the intended appellant.
Verified: an appeal attempt from a non-submitter address was correctly reverted with `"only the original submitter may appeal"`.
https://explorer-studio.genlayer.com/tx/0xa17989de929e352a79736f797f7623c8c1bbadf249341375dc4f9b80f2b0eeff

**3. `coherence_confirmed` (renamed from `coherence_checked`) now reflects a real, independently-executed second consensus round.**
Previously this field was hardcoded `true`. It is now the output of a separate `gl.eq_principle.prompt_comparative` call that asks validators a fresh yes/no question — whether the agreed decision is actually justified by the content and the cited rule — independently of the first classification round. If validators cannot confirm coherence, the contract fails safe to `flag`.
This is independently verifiable on-chain: both the initial `submit_content` and the subsequent `appeal` transaction show two distinct entries under "Equivalence Principles Output" (Principle #0 for the classification, Principle #1 for the coherence confirmation), confirming two separate rounds actually executed rather than one hardcoded value.
Deploy: https://explorer-studio.genlayer.com/tx/0xe3757f7afba3d2f7ed9b79d6e3f081992e9e4ff4ae4e63524fa0abfa667bfeec
submit_content (two principles recorded): https://explorer-studio.genlayer.com/tx/0xeb6411da6bb1c40e02acc73ae1e2fdd355176be87b9650c38a481260ba72a01a
Successful appeal (two principles recorded again): https://explorer-studio.genlayer.com/tx/0x933b52fb8bd355b421ce88c762bd56eeb5a7e4061106c330ce407bc940a65f1c

**4. Non-approve decisions now enforce a valid cited rule or a canonical fallback.**
`_normalize_verdict` validates `matched_rule_id` against the policy's actual current rule set (with case/format normalization). If a non-approve decision arrives with an empty or non-existent rule id, the contract substitutes a canonical `unspecified_violation` id instead of storing an arbitrary or fabricated reference. This is implemented and covered in the updated source; the live tests above happened to trigger a valid rule match (`no_spam`) since that's what the test content genuinely violated, so the fallback path itself is verifiable by code review of `_normalize_verdict` in the updated contract.

Updated source, README, and full test log (including these transaction hashes) are pushed to the GitHub repository linked in this submission. Happy to provide any additional evidence if useful.
