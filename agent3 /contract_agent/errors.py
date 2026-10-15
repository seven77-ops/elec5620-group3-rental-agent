class ContractError(ValueError):
    """A rejected input or an invalid review-state transition."""

    code = "invalid_request"


class ResubmissionRequired(ContractError):
    """The document cannot be read reliably; ask for a clearer copy."""

    code = "resubmission_required"


class SelectionError(ContractError):
    """The Agent 2 handoff packet is missing or inconsistent."""

    code = "invalid_selection"


class DuplicateRequestConflict(ContractError):
    """One request ID was reused with different input."""

    code = "duplicate_request_conflict"
