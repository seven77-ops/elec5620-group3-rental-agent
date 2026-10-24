"""Thin HTTP registration for the shared assistant."""
from .service import AssistantService
from .workspace import AssistantWorkspace
from .lease_bridge import LeaseChatBridge
from .commute import latest
from .areas import latest as area_latest


def register_assistant_routes(app,services):
    assistant=AssistantService(services)
    base='/api/v1/cases/{case_id}/assistant'
    app.get(base+'/conversations')(assistant.list)
    def commute_latest(case_id: str):return latest(services,case_id)
    app.get(base+'/commute-recommendation')(commute_latest)
    def areas_latest(case_id: str):return area_latest(services,case_id)
    app.get(base+'/area-advice')(areas_latest)
    app.post(base+'/conversations')(assistant.create)
    app.get(base+'/conversations/{conversation_id}')(assistant.read)
    app.post(base+'/conversations/{conversation_id}/messages')(assistant.send)
    app.post(base+'/proposals/{proposal_id}/apply')(assistant.apply)
    app.post(base+'/conversations/{conversation_id}/lease-proposals/{proposal_id}/apply')(LeaseChatBridge(services).apply)
    workspace=AssistantWorkspace(services)
    app.post(base+'/conversations/{conversation_id}/proposals')(workspace.prepare)
    app.post(base+'/conversations/{conversation_id}/selections')(workspace.select)
