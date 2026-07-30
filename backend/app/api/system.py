from fastapi import APIRouter, Request


router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "database": request.app.state.settings.database_path.name,
    }
