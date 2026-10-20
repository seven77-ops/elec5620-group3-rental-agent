"""HTTP path/method registration; domain behavior lives in adapters."""
from .adapters.system import SystemAdapter
from .adapters.profiles import ProfilesAdapter
from .adapters.contracts import ContractsAdapter
from .adapters.aftercare import AftercareAdapter


def register_routes(app, services):
    system = SystemAdapter(services)
    app.get('/api/v1/health')(system.health)
    app.get('/api/v1/demo-config')(system.config)
    app.get('/api/v1/demo-agreements/{example_id}')(system.agreement)
    profiles = ProfilesAdapter(services)
    app.post('/api/v1/cases')(profiles.create_case)
    app.get('/api/v1/cases/{case_id}')(profiles.read_case)
    app.post('/api/v1/cases/{case_id}/profile-drafts')(profiles.draft)
    app.post('/api/v1/cases/{case_id}/profile-confirmations')(profiles.confirm)
    app.post('/api/v1/cases/{case_id}/evaluations')(profiles.evaluation)
    app.get('/api/v1/evaluations/{run_id}')(profiles.read_evaluation)
    app.get('/api/v1/evaluations/{run_id}/export')(profiles.export_evaluation)
    app.post('/api/v1/cases/{case_id}/selections')(profiles.select)
    app.get('/api/v1/cases/{case_id}/exports/selection')(profiles.export_selection)
    contracts = ContractsAdapter(services)
    app.post('/api/v1/cases/{case_id}/contract-consents')(contracts.consent)
    app.get('/api/v1/cases/{case_id}/contract-consents')(contracts.list_consents)
    app.post('/api/v1/cases/{case_id}/contract-reviews', openapi_extra={
        'requestBody': {'required': True, 'content': {
            'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}},
        'parameters': [{'in': 'header', 'name': key, 'required': True, 'schema': {'type': 'string'}}
                       for key in ('X-Consent-Id', 'X-Request-Id', 'X-Filename')],
    })(contracts.upload)
    app.get('/api/v1/contract-reviews/{review_id}')(contracts.read_review)
    app.get('/api/v1/contract-reviews/{review_id}/context')(contracts.review_context)
    app.get('/api/v1/contract-reviews/{review_id}/export')(contracts.export_review)
    app.get('/api/v1/contract-reviews/{review_id}/questions/export')(contracts.export_questions)
    app.get('/api/v1/contract-reviews/{review_id}/history')(contracts.review_history)
    app.post('/api/v1/contract-reviews/{review_id}/corrections')(contracts.correction)
    app.post('/api/v1/contract-reviews/{review_id}/decisions')(contracts.decision)
    app.post('/api/v1/contract-reviews/{review_id}/questions')(contracts.questions)
    aftercare = AftercareAdapter(services)
    app.get('/api/v1/aftercare/template-commands')(aftercare.command_templates)
    app.post('/api/v1/aftercare/commands')(aftercare.aftercare_command)
    app.get('/api/v1/aftercare/cases/{aftercare_id}')(aftercare.read_aftercare)
    app.get('/api/v1/aftercare/cases/{aftercare_id}/export')(aftercare.export_aftercare)

    from .ai.routes import register_ai_routes
    register_ai_routes(app, services, contracts)
