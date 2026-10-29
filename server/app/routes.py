"""HTTP path/method registration; domain behavior lives in adapters."""
from .adapters.system import SystemAdapter
from .adapters.profiles import ProfilesAdapter
from .adapters.real_agent2 import RealProfilesAdapter
from .adapters.contracts import ContractsAdapter
from .adapters.aftercare import AftercareAdapter


def register_routes(app, services):
    system = SystemAdapter(services)
    app.get('/api/v1/health')(system.health)
    app.get('/api/v1/demo-config')(system.config)
    app.get('/api/v1/demo-agreements/{example_id}')(system.agreement)
    profiles = RealProfilesAdapter(services) if services.settings.catalog is not None else ProfilesAdapter(services)
    app.post('/api/v1/cases')(profiles.create_case)
    app.get('/api/v1/cases/{case_id}')(profiles.read_case)
    app.post('/api/v1/cases/{case_id}/profile-drafts')(profiles.draft)
    app.post('/api/v1/cases/{case_id}/profile-confirmations')(profiles.confirm)
    if services.settings.catalog is not None:
        app.get('/api/v1/cases/{case_id}/recommendation-context')(profiles.recommendation_context)
        from .adapters.favorites import FavoritesAdapter
        favorites = FavoritesAdapter(services)
        app.get('/api/v1/cases/{case_id}/favorites')(favorites.read)
        app.post('/api/v1/cases/{case_id}/favorites')(favorites.save)
        app.post('/api/v1/cases/{case_id}/followup-selection')(favorites.select)
        from .assistant.followup_start import FollowupStart
        from .assistant.requirements import RequirementsService
        app.post('/api/v1/cases/{case_id}/followup-preview')(FollowupStart(services).preview)
        app.post('/api/v1/cases/{case_id}/followup-start')(FollowupStart(services).start)
        app.post('/api/v1/cases/{case_id}/assistant/conversations/{conversation_id}/requirements')(RequirementsService(services).save)
    app.post('/api/v1/cases/{case_id}/evaluations')(profiles.evaluation)
    app.get('/api/v1/evaluations/{run_id}')(profiles.read_evaluation)
    app.get('/api/v1/evaluations/{run_id}/export')(profiles.export_evaluation)
    app.post('/api/v1/cases/{case_id}/selections')(profiles.select)
    app.get('/api/v1/cases/{case_id}/exports/selection')(profiles.export_selection)
    from .adapters.candidate_followup import CandidateFollowupAdapter
    followup = CandidateFollowupAdapter(services)
    app.get('/api/v1/cases/{case_id}/candidate-followup')(followup.read)
    app.post('/api/v1/cases/{case_id}/candidate-followup')(followup.save)
    app.get('/api/v1/cases/{case_id}/candidate-followup/questions')(followup.questions)
    from .lease_drafts.service import LeaseDraftService
    from .lease_drafts.ai import LeaseDraftAI
    from .lease_drafts.addresses import LeaseAddresses
    app.get('/api/v1/lease-addresses')(LeaseAddresses(services).search)
    from .lease_drafts.localities import search_localities
    app.get('/api/v1/lease-localities')(search_localities)
    drafts = LeaseDraftService(services)
    draft_base = '/api/v1/cases/{case_id}/lease-drafts'
    app.get(draft_base+'/context')(drafts.context)
    app.get(draft_base)(drafts.list)
    app.post(draft_base)(drafts.save)
    app.post(draft_base+'/proposals')(LeaseDraftAI(drafts).propose)
    app.get(draft_base+'/{draft_id}')(drafts.read)
    app.get(draft_base+'/{draft_id}/pdf')(drafts.pdf)
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
    from .adapters.aftercare_assist import AftercareAssist
    assist = AftercareAssist(services)
    app.get('/api/v1/cases/{case_id}/aftercare/tenancy-prefill')(assist.tenancy_prefill)
    app.post('/api/v1/cases/{case_id}/aftercare/deduction-extract')(assist.extract_deductions)
    from .adapters.progress import ProgressAdapter
    app.get('/api/v1/cases/{case_id}/progress')(ProgressAdapter(services).progress)

    from .living.service import LivingService
    living = LivingService(services)
    app.get('/api/v1/living-providers')(living.directory)
    living_base = '/api/v1/cases/{case_id}/living-services'
    app.get(living_base)(living.read)
    from .living.tenancy import LivingTenancy
    tenancy = LivingTenancy(services)
    app.get(living_base+'/tenancy-source')(tenancy.preview)
    app.post(living_base+'/tenancy-import')(tenancy.apply)
    app.post(living_base+'/profile')(living.profile)
    app.post(living_base+'/repairs')(living.repair)
    from .living.email_ai import RepairEmailAI
    app.post(living_base+'/repair-email/polish')(RepairEmailAI(services).polish)
    app.post(living_base+'/repairs/{repair_id}')(living.update_repair)
    app.post(living_base+'/bookings')(living.booking)
    app.post(living_base+'/proposals/{proposal_id}/apply')(living.apply)
    from .living.attachments import LivingAttachments
    attachments = LivingAttachments(services)
    app.get(living_base+'/attachments')(attachments.list)
    app.post(living_base+'/attachments',openapi_extra={
        'requestBody':{'required':True,'content':{'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}}})(attachments.upload)
    app.get(living_base+'/attachments/{attachment_id}')(attachments.download)

    from .ai.routes import register_ai_routes
    register_ai_routes(app, services, contracts)
    from .real_data.routes import register_real_data_routes
    register_real_data_routes(app, services)
    from .real_data.catalog import register_catalog_routes
    register_catalog_routes(app, services)
    from .assistant.routes import register_assistant_routes
    register_assistant_routes(app, services)
