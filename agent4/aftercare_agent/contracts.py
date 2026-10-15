"""Strict JSON and versioned local input contracts."""
from datetime import date, datetime, timezone
from pathlib import Path
import json
from jsonschema import Draft202012Validator, FormatChecker
from .errors import AftercareError, require

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AftercareError('invalid_input', 'Only finite JSON values are supported') from exc


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'invalid_input', f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def constant(value):
        raise AftercareError('invalid_input', f'Non-finite JSON number: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def validate(name, value):
    canonical(value)
    schema = load_json(ROOT / 'schemas' / f'{name}.schema.json')
    error = next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), None)
    if error:
        location = '.'.join(map(str, error.absolute_path)) or '$'
        raise AftercareError('invalid_input', f'{location}: {error.message}')


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(result.tzinfo is not None, 'invalid_input', 'An explicit timezone is required')
        return result.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError) as exc:
        raise AftercareError('invalid_input', 'Invalid timezone-aware timestamp') from exc


def day(value):
    try:
        result = date.fromisoformat(value)
        require(result.isoformat() == value and 2000 <= result.year <= 2100,
                'invalid_input', 'Dates must be YYYY-MM-DD within 2000..2100')
        return result
    except (ValueError, TypeError) as exc:
        raise AftercareError('invalid_input', 'Invalid calendar date') from exc
