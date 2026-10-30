"""Local, self-contained JSON Schema contracts; no remote resolution or I/O writes."""

from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .validation import ValidationError


SCHEMAS = {
    'RentalProfile': 'rental-profile.schema.json',
    'RecommendationReport': 'recommendation-report.schema.json',
    'SelectedListingEvidence': 'selected-listing-evidence.schema.json',
}


@lru_cache(maxsize=3)
def validator(name):
    if not isinstance(name, str) or name not in SCHEMAS:
        raise ValidationError('contract: Unknown data contract name')
    path = Path(__file__).resolve().parents[1] / 'schemas' / SCHEMAS[name]
    schema = json.loads(path.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contract(name, value):
    """Validate structure and formats, not authenticity, user identity or business intent."""
    if not isinstance(name, str):
        raise ValidationError('contract: Unknown data contract name')
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'{name}: Must be serializable JSON without NaN or Infinity') from exc
    error = next(validator(name).iter_errors(value), None)
    if error is not None:
        field = '.'.join(str(part) for part in error.absolute_path) or '$'
        raise ValidationError(f'{name}.{field}: {error.message}')
