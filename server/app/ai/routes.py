"""Additive browser endpoints for optional AI sidecars."""
from .service import AiService
from .contracts import apply_candidates


def register_ai_routes(app,services,contracts):
    service=AiService(services,contracts)
    app.get('/api/v1/ai/config')(service.config)
    def recommend(run_id: str, body: dict):
        return service.generate('recommendation',run_id,body)
    def recommendation_latest(run_id: str):
        return service.latest('recommendation',run_id)
    def contract(review_id: str, body: dict):
        return service.generate('contract',review_id,body)
    def contract_latest(review_id: str):
        return service.latest('contract',review_id)
    def apply(review_id: str, analysis_id: str, body: dict):
        return apply_candidates(service,review_id,analysis_id,body)
    app.post('/api/v1/evaluations/{run_id}/ai-explanations')(recommend)
    app.get('/api/v1/evaluations/{run_id}/ai-explanations/latest')(recommendation_latest)
    app.post('/api/v1/contract-reviews/{review_id}/ai-analyses')(contract)
    app.get('/api/v1/contract-reviews/{review_id}/ai-analyses/latest')(contract_latest)
    app.post('/api/v1/contract-reviews/{review_id}/ai-analyses/{analysis_id}/apply')(apply)
