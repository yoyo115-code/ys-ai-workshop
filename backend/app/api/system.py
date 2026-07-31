from fastapi import APIRouter, Request, Response, status


router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    if settings.is_production:
        database_label = "postgresql"
    else:
        path = request.app.state.database.sqlite_path
        database_label = path.name if path is not None else "sqlite"
    return {"status": "ok", "database": database_label}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request, response: Response) -> dict[str, object]:
    configuration_ready = not bool(
        request.app.state.settings.production_configuration_errors()
    )
    database_ready = request.app.state.database.ping()
    storage_ready = request.app.state.storage_provider.healthcheck()
    ready = configuration_ready and database_ready and storage_ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "configuration": "ok" if configuration_ready else "invalid",
            "database": "ok" if database_ready else "unavailable",
            "storage": "ok" if storage_ready else "unavailable",
        },
    }


@router.get("/config/public")
def public_configuration(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    session_token = request.cookies.get(settings.session_cookie_name)
    session_active = (
        request.app.state.auth_service.current_user(session_token) is not None
        if session_token
        else False
    )
    return {
        "environment": settings.app_env,
        "private_beta": settings.is_production,
        "registration_mode": settings.registration_mode,
        "ai_labs_enabled": settings.ai_labs_enabled,
        "session_active": session_active,
        "export_retention_days": settings.export_retention_days,
        "privacy_document": "#privacy-notice",
    }
