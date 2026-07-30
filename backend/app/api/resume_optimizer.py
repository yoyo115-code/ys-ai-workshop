from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_user
from app.models.domain import PublicUser
from app.schemas.resume_optimizer import (
    GenerateSuggestionsRequest,
    ResumeVersionResponse,
    ResumeWorkspaceResponse,
    SuggestionResponse,
    UndoResponse,
    UpdateSuggestionRequest,
    VersionDiffResponse,
)


router = APIRouter(tags=["resume-optimizer"])


@router.post(
    "/career/applications/{application_id}/resume-suggestions/generate",
    response_model=ResumeWorkspaceResponse,
)
def generate_resume_suggestions(
    application_id: int,
    request: Request,
    data: GenerateSuggestionsRequest | None = None,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.generate_suggestions(
        user, application_id, retry=data.retry if data else False
    )


@router.get(
    "/career/applications/{application_id}/resume-suggestions",
    response_model=ResumeWorkspaceResponse,
)
def get_resume_suggestions(
    application_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.get_workspace(
        user, application_id
    )


@router.patch(
    "/career/resume-suggestions/{suggestion_id}",
    response_model=SuggestionResponse,
)
def update_resume_suggestion(
    suggestion_id: int,
    data: UpdateSuggestionRequest,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.update_suggestion(
        user, suggestion_id, data
    )


@router.post(
    "/career/resume-suggestions/{suggestion_id}/regenerate",
    response_model=SuggestionResponse,
)
def regenerate_resume_suggestion(
    suggestion_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.regenerate_suggestion(
        user, suggestion_id
    )


@router.post(
    "/career/resume-suggestions/{suggestion_id}/undo",
    response_model=UndoResponse,
)
def undo_resume_suggestion(
    suggestion_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.undo_suggestion(
        user, suggestion_id
    )


@router.post(
    "/career/applications/{application_id}/resume-versions",
    response_model=ResumeVersionResponse,
)
def create_resume_version(
    application_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.create_version(
        user, application_id
    )


@router.get(
    "/career/resumes/{resume_id}/versions",
    response_model=list[ResumeVersionResponse],
)
def list_resume_versions(
    resume_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> list[dict]:
    return request.app.state.resume_optimizer_service.list_versions(
        user, resume_id
    )


@router.get(
    "/career/resume-versions/{version_id}",
    response_model=ResumeVersionResponse,
)
def get_resume_version(
    version_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.get_version(user, version_id)


@router.get(
    "/career/resume-versions/{version_id}/compare/{other_version_id}",
    response_model=VersionDiffResponse,
)
def compare_resume_versions(
    version_id: int,
    other_version_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.compare_versions(
        user, version_id, other_version_id
    )


@router.post(
    "/career/resume-versions/{version_id}/restore",
    response_model=ResumeVersionResponse,
)
def restore_resume_version(
    version_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_optimizer_service.restore_version(
        user, version_id
    )
