from enum import Enum
from typing import Set

class ApplicationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    MATCHED = "MATCHED"
    QUALIFIED = "QUALIFIED"
    SKIPPED = "SKIPPED"
    DUPLICATE = "DUPLICATE"
    RESUME_READY = "RESUME_READY"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    FORM_FILLED = "FORM_FILLED"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMITTED = "SUBMITTED"
    CAPTCHA_WAITING = "CAPTCHA_WAITING"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"
    FAILED = "FAILED"

# Allowed valid transitions map
ALLOWED_TRANSITIONS = {
    ApplicationState.DISCOVERED: {ApplicationState.ANALYZED, ApplicationState.DUPLICATE, ApplicationState.FAILED},
    ApplicationState.ANALYZED: {ApplicationState.MATCHED, ApplicationState.QUALIFIED, ApplicationState.SKIPPED, ApplicationState.FAILED},
    ApplicationState.MATCHED: {ApplicationState.QUALIFIED, ApplicationState.SKIPPED, ApplicationState.FAILED},
    ApplicationState.QUALIFIED: {ApplicationState.RESUME_READY, ApplicationState.FAILED},
    ApplicationState.RESUME_READY: {ApplicationState.APPLICATION_STARTED, ApplicationState.MANUAL_ACTION_REQUIRED, ApplicationState.FAILED},
    ApplicationState.APPLICATION_STARTED: {ApplicationState.FORM_FILLED, ApplicationState.CAPTCHA_WAITING, ApplicationState.MANUAL_ACTION_REQUIRED, ApplicationState.FAILED},
    ApplicationState.CAPTCHA_WAITING: {ApplicationState.APPLICATION_STARTED, ApplicationState.FORM_FILLED, ApplicationState.MANUAL_ACTION_REQUIRED, ApplicationState.FAILED},
    ApplicationState.FORM_FILLED: {ApplicationState.READY_TO_SUBMIT, ApplicationState.SUBMITTED, ApplicationState.MANUAL_ACTION_REQUIRED, ApplicationState.FAILED},
    ApplicationState.READY_TO_SUBMIT: {ApplicationState.SUBMITTED, ApplicationState.FAILED},
    ApplicationState.MANUAL_ACTION_REQUIRED: {ApplicationState.RESUME_READY, ApplicationState.APPLICATION_STARTED, ApplicationState.FORM_FILLED, ApplicationState.READY_TO_SUBMIT, ApplicationState.FAILED},
    ApplicationState.SUBMITTED: set(),
    ApplicationState.SKIPPED: set(),
    ApplicationState.DUPLICATE: set(),
    ApplicationState.FAILED: set()
}

def validate_state_transition(current_state: str, new_state: str) -> bool:
    """Validates if transitioning from current_state to new_state is allowed."""
    try:
        curr_enum = ApplicationState(current_state)
        new_enum = ApplicationState(new_state)
        allowed = ALLOWED_TRANSITIONS.get(curr_enum, set())
        return new_enum in allowed
    except ValueError:
        return False
