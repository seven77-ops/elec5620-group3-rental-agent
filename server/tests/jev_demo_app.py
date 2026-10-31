"""Browser-only Decisions double. Never used by normal startup; no external calls."""
import json
import os

import httpx

from server.app.main import create_app
from server.app.routing.jev import JevProvider
from server.tests.assistant_demo_app import AssistantDemoProvider
from server.tests.test_jev_provider import envelope


def decision_response(request):
    state = json.loads(request.content)['state']
    # The state is structured JSON, as in the actual Decisions request.
    message = state['message']
    if 'fallback-test' in message:
        return httpx.Response(429)
    route = 'knowledge' if message == 'How do I request repairs?' else (
        'mixed' if message == 'Compare commute options, then review my lease.' else 'housing')
    return httpx.Response(200, json=envelope(route))


app = create_app(
    runtime_dir=os.environ['RENTAL_ASSISTANT_TEST_RUNTIME'],
    operator_key='test-only-local',
    ai_provider=AssistantDemoProvider(),
    decision_provider=JevProvider(
        {'OPENROUTER_API_KEY': 'test-only-not-a-real-key', 'RENTAL_JEV_MODE': 'active'},
        transport=httpx.MockTransport(decision_response),
    ),
)
