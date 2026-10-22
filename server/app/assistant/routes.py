"""Thin HTTP registration for the shared assistant."""
from .service import AssistantService
from .workspace import AssistantWorkspace


def register_assistant_routes(app,services):
    assistant=AssistantService(services)
    base='/api/v1/cases/{case_id}/assistant'
    app.get(base+'/conversations')(assistant.list)
    app.post(base+'/conversations')(assistant.create)
    app.get(base+'/conversations/{conversation_id}')(assistant.read)
    app.post(base+'/conversations/{conversation_id}/messages')(assistant.send)
    app.post(base+'/proposals/{proposal_id}/apply')(assistant.apply)
    workspace=AssistantWorkspace(services)
    app.post(base+'/conversations/{conversation_id}/proposals')(workspace.prepare)
    app.post(base+'/conversations/{conversation_id}/selections')(workspace.select)
