"""Load the supplied, unchanged sibling Agent 2 implementation."""
import sys
import re
from pathlib import Path

AGENT2 = Path(__file__).resolve().parents[2] / 'agent2'
if not (AGENT2 / 'rental_agent').is_dir():
    raise ImportError('Keep agent1/ and agent2/ side by side in the project root.')
sys.path.insert(0, str(AGENT2))

from rental_agent.validation import validate_profile as _validate_profile, ValidationError  # noqa: E402
from rental_agent.contracts import validator, validate_contract as _validate_contract  # noqa: E402
from rental_agent.engine import evaluate as _evaluate, fingerprint  # noqa: E402
from rental_agent.report import compare_reports as _compare_reports  # noqa: E402


def compare_reports(before, after):
    if before['search_id'] != after['search_id']:
        raise ValueError('Cannot compare reports from different searches.')
    if any(before[k] != after[k] for k in ('dataset_fingerprint', 'as_of', 'scoring_version', 'data_mode')):
        raise ValueError('Cannot compare different data snapshots, assessment times or scoring versions.')
    return _compare_reports(before, after)


def english_validation_error(exc):
    """Present upstream validation failures in English without editing Agent2."""
    message = str(exc)
    if not re.search(r'[\u3400-\u9fff]', message):
        return message
    match = re.match(r'^([A-Za-z0-9_.$\[\]-]+):', message)
    field = match.group(1) if match else 'Agent2'
    guidance = {
        'budget.maximum': 'The maximum budget must not be lower than the preferred budget.',
        'commute.maximum_minutes': 'The maximum commute duration must not be lower than the preferred duration.',
        'move_in_window': 'The start date must not be later than the end date.',
        'soft_preferences': 'Check facility names and weights. A hard facility must not also be scored as a soft preference.',
        'weights': 'All four weights must be valid. Their effective total must be positive; housing is ignored when no soft facilities are weighted.',
    }
    detail = guidance.get(field, 'Agent2 rejected this field. Check its type, allowed values, required evidence and the interface specification.')
    return f'{field}: {detail}'


def validate_profile(profile):
    try:
        return _validate_profile(profile)
    except ValidationError as exc:
        raise ValidationError(english_validation_error(exc)) from None


def validate_contract(name, value):
    try:
        return _validate_contract(name, value)
    except ValidationError as exc:
        raise ValidationError(english_validation_error(exc)) from None


def evaluate(profile, dataset):
    try:
        return _evaluate(profile, dataset)
    except ValidationError as exc:
        raise ValidationError(english_validation_error(exc)) from None
