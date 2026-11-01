"""Explicit historical synthetic fixtures for regression tests; never used by startup."""
from functools import wraps
from server.app.main import create_app as real_app
from server.app.common import load


@wraps(real_app)
def create_app(**kwargs):
    return real_app(dataset=load('agent2/data/demo/listings.json'), **kwargs)
