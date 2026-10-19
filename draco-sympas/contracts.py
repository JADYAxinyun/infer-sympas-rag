"""Return-value contracts consumed by the narrow unchecked-return rule.

A contract is evidence, not a guess: callers must provide its source.  The
current Infer/SymPas JSON only contains slice findings, so the bundled
contracts are explicitly marked ``manual`` until a checker emits summaries.
"""

DEFAULT_RETURN_CONTRACTS = {
    name: {"kind": "status", "checks_required": True, "source": "manual", "evidence": "demo policy"}
    for name in (
        "connect_db", "flush_cache", "load_config", "open_config", "open_file",
        "open_log", "open_socket", "parse_file", "read_header", "save_record",
        "send_packet", "start_worker", "validate_user", "write_file",
    )
}


def merge_return_contracts(extra_contracts=None):
    """Merge explicit request/checker contracts over the documented demo policy."""
    contracts = {name: dict(value) for name, value in DEFAULT_RETURN_CONTRACTS.items()}
    for name, value in (extra_contracts or {}).items():
        if not isinstance(value, dict):
            continue
        contract = dict(value)
        contract.setdefault("source", "request")
        contracts[name] = contract
    return contracts


def infer_candidate_contracts(candidates):
    """Convert only medium-confidence Infer candidates into review evidence.

    They remain ``status_candidate`` contracts: review findings are deliberately
    low severity and require human confirmation.
    """
    contracts = {}
    for candidate in candidates or []:
        if not isinstance(candidate, dict) or candidate.get("confidence") != "medium":
            continue
        callee = candidate.get("callee")
        if not callee:
            continue
        contracts[callee] = {
            "kind": "status_candidate",
            "checks_required": True,
            "source": "infer_candidate",
            "confidence": "medium",
            "evidence": candidate.get("evidence", ""),
        }
    return contracts
