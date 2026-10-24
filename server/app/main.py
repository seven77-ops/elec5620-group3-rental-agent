"""Application wiring for the loopback synthetic rental API."""
from fastapi import FastAPI
from .settings import Settings
from .adapters.services import Services
from .http import strict_route, install_error_handlers
from .routes import register_routes


def create_app(runtime_dir=None, operator_key=None, ai_provider=None, data_provider=None, dataset=None):
    services = Services(Settings(runtime_dir=runtime_dir, operator_key=operator_key, dataset=dataset), ai_provider=ai_provider, data_provider=data_provider)
    app = FastAPI(title='Rental journey · real Agent2 catalogue', version='1.1')
    app.router.route_class = strict_route(services.operator)
    app.state.repository = services.repo
    install_error_handlers(app, services)
    register_routes(app, services)
    return app


app = create_app()
