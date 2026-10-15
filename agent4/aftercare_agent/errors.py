"""Public errors are safe to serialize at the CLI boundary."""

class AftercareError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code, message):
    if not condition:
        raise AftercareError(code, message)
