"""Shared strict boundary validation and identifier helpers."""
from datetime import datetime, timezone
import json
import re
from uuid import uuid4
from .bootstrap import ROOT

class ApiError(Exception):
    def __init__(self, status, code, message, fields=None):
        self.status, self.code, self.message, self.fields = status, code, message, fields


def require(condition, status, code, message):
    if not condition:
        raise ApiError(status, code, message)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return prefix + '-' + uuid4().hex


def load(relative):
    return json.loads((ROOT / relative).read_text())


def shape(body, required, optional=()):
    require(isinstance(body, dict) and set(required) <= set(body) and set(body) <= set(required) | set(optional),
            422, 'invalid_input', 'Supply the required fields only: ' + ', '.join(required))


def integer(value):
    return type(value) is int and value >= 0


def opaque_ref(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,159}', value),
            422, 'invalid_reference', 'Saved references must be nonempty opaque identifiers')
    return value


def request_id(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value),
            422, 'invalid_request_id', 'Request ID must contain 1–80 letters, digits, dots, underscores or hyphens')
    return value


