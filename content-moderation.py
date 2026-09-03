# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import time


DECISIONS = ("approve", "flag", "reject")


class ContentModerationRegistry(gl.Contract):
    owner: str
    policy: TreeMap[str, str]
    policy_version: u256
    policy_history: TreeMap[str, str]
    decisions: TreeMap[str, str]
    appeals: TreeMap[str, str]
    reputation: TreeMap[str, str]

    def __init__(self, owner: str, initial_policy: dict[str, str]):
        self.owner = owner
        self.policy = TreeMap()
        for rule_id, rule_text in initial_policy.items():
            self.policy[rule_id] = rule_text
        self.policy_version = u256(1)
        self.policy_history = TreeMap()
        self.policy_history[str(self.policy_version)] = json.dumps(dict(initial_policy))
        self.decisions = TreeMap()
        self.appeals = TreeMap()
        self.reputation = TreeMap()

    def _now(self) -> int:
        return int(time.time())

    def _sender(self) -> str:
        return str(gl.message.sender_address)

    def _snapshot_policy(self) -> None:
        self.policy_version += u256(1)
        self.policy_history[str(self.policy_version)] = json.dumps(dict(self.policy.items()))

    @gl.public.write
    def add_rule(self, rule_id: str, rule_text: str) -> None:
        assert self._sender() == self.owner, "only owner"
        self.policy[rule_id] = rule_text
        self._snapshot_policy()

    @gl.public.write
    def remove_rule(self, rule_id: str) -> None:
        assert self._sender() == self.owner, "only owner"
        if rule_id in self.policy:
            del self.policy[rule_id]
            self._snapshot_policy()

    @gl.public.view
    def get_policy(self) -> dict:
        return {"version": int(self.policy_version), "rules": dict(self.policy.items())}

    @gl.public.view
    def get_policy_at_version(self, version: int) -> dict:
        key = str(version)
        assert key in self.policy_history, "no such policy version"
        return json.loads(self.policy_history[key])

    def _policy_block(self, rules: dict[str, str]) -> str:
        lines = [f"- [{rid}] {text}" for rid, text in rules.items()]
        return "\n".join(lines) if lines else "- (no rules configured)"

    def _normalize_rule_id(self, raw_id: str, rules: dict[str, str]) -> str:
        rid = str(raw_id or "").strip()
        if rid in rules:
            return rid
        lowered = rid.lower().replace("-", "_").replace(" ", "_")
        for key in rules.keys():
            if key.lower() == lowered:
                return key
        return ""

    def _normalize_verdict(self, parsed: dict, rules: dict[str, str]) -> dict:
        decision = str(parsed.get("decision", "")).strip().lower()
        if decision not in DECISIONS:
            decision = "flag"
        matched = self._normalize_rule_id(str(parsed.get("matched_rule_id", "")), rules)
        if decision == "approve":
            matched = ""
        return {"decision": decision, "matched_rule_id": matched}

    def _decision_prompt(self, content_text: str, rules: dict[str, str], extra: str = "") -> str:
        return f"""
You are a content moderation reviewer. Evaluate CONTENT against POLICY RULES.
Return ONLY JSON with exactly these keys:
{{"decision":"approve","matched_rule_id":"","reasoning":"short reason"}}

decision must be one of: approve, flag, reject
matched_rule_id must be an exact rule id from the list, or empty string
approve = no rule violated
flag = unclear / borderline
reject = clear violation

POLICY RULES:
{self._policy_block(rules)}

{extra}

CONTENT:
\"\"\"{content_text}\"\"\"
""".strip()

    def _agree_verdict(self, prompt: str, rules: dict[str, str]) -> dict:
        def get_verdict() -> str:
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            normalized = self._normalize_verdict(raw, rules)
            return json.dumps(normalized, sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "decision must be exactly the same. "
                "matched_rule_id may differ only if both are empty "
                "or both name the same policy rule."
            ),
        )
        return json.loads(agreed_raw)

    @gl.public.write
    def submit_content(self, content_id: str, content_text: str) -> None:
        assert content_id not in self.decisions, "already moderated"
        rules = dict(self.policy.items())
        prompt = self._decision_prompt(content_text, rules)
        agreed = self._agree_verdict(prompt, rules)

        record = {
            "decision": agreed["decision"],
            "matched_rule_id": agreed["matched_rule_id"],
            "coherence_checked": True,
            "policy_version": int(self.policy_version),
            "timestamp": self._now(),
            "submitter": self._sender(),
            "status": "final",
        }
        self.decisions[content_id] = json.dumps(record)

    @gl.public.view
    def get_decision(self, content_id: str) -> dict:
        assert content_id in self.decisions, "no decision recorded"
        return json.loads(self.decisions[content_id])

    @gl.public.view
    def debug_has_decision(self, content_id: str) -> bool:
        return content_id in self.decisions

    @gl.public.view
    def debug_get_decision_raw(self, content_id: str) -> str:
        if content_id in self.decisions:
            return self.decisions[content_id]
        return "NOT_FOUND"

    def _get_reputation(self, address: str) -> dict:
        if address in self.reputation:
            return json.loads(self.reputation[address])
        return {"upheld": 0, "overturned": 0}

    @gl.public.view
    def get_reputation(self, address: str) -> dict:
        return self._get_reputation(address)

    @gl.public.write
    def appeal(self, content_id: str, content_text: str, appellant_argument: str) -> None:
        assert content_id in self.decisions, "no decision to appeal"
        prior = json.loads(self.decisions[content_id])
        assert prior["status"] != "appealed", "already appealed once"

        version_key = str(prior["policy_version"])
        if version_key in self.policy_history:
            rules = json.loads(self.policy_history[version_key])
        else:
            rules = dict(self.policy.items())

        extra = (
            f"A prior review reached decision '{prior['decision']}' "
            f"(matched rule: '{prior['matched_rule_id']}'). "
            f"The submitter disputes this and argues:\n{appellant_argument}\n"
            f"Re-evaluate independently; you are not bound by the prior decision."
        )
        prompt = self._decision_prompt(content_text, rules, extra)
        agreed = self._agree_verdict(prompt, rules)
        overturned = agreed["decision"] != prior["decision"]

        appellant = self._sender()
        rep = self._get_reputation(appellant)
        if overturned:
            rep["overturned"] += 1
        else:
            rep["upheld"] += 1
        self.reputation[appellant] = json.dumps(rep)

        record = {
            "decision": agreed["decision"],
            "matched_rule_id": agreed["matched_rule_id"],
            "policy_version": prior["policy_version"],
            "timestamp": self._now(),
            "submitter": prior.get("submitter", ""),
            "status": "appealed",
            "prior_decision": prior["decision"],
            "overturned": overturned,
        }
        self.decisions[content_id] = json.dumps(record)
        self.appeals[content_id] = json.dumps({
            "appellant": appellant,
            "argument": appellant_argument,
            "overturned": overturned,
            "resolved_at": self._now(),
        })

    @gl.public.view
    def get_appeal(self, content_id: str) -> dict:
        assert content_id in self.appeals, "no appeal recorded"
        return json.loads(self.appeals[content_id])