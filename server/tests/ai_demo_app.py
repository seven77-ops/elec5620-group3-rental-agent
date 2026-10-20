"""Isolated browser-test ASGI app. All simulated calls are labeled test_stub."""
import os
from server.app.main import create_app
from server.tests.ai_fixtures import TestProvider
app=create_app(runtime_dir=os.environ['RENTAL_AI_TEST_RUNTIME'],operator_key='qa-local-key',ai_provider=TestProvider())
