from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import FileResponse

from app.api.dependencies import require_user
from app.models.domain import PublicUser
from app.schemas.resume_export import (
    CreateResumeExportRequest,
    ResumeExportResponse,
    ResumePreviewResponse,
)


router = APIRouter(tags=["resume-export"])


@router.get(
    "/career/resume-versions/{version_id}/preview",
    response_model=ResumePreviewResponse,
)
def preview_resume_version(
    version_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_export_service.preview(user, version_id)


@router.post(
    "/career/resume-versions/{version_id}/exports",
    response_model=ResumeExportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resume_export(
    version_id: int,
    data: CreateResumeExportRequest,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_export_service.create_export(user, version_id, data)


@router.get(
    "/career/resume-exports",
    response_model=list[ResumeExportResponse],
)
def list_resume_exports(
    request: Request,
    version_id: int | None = Query(default=None, ge=1),
    user: PublicUser = Depends(require_user),
) -> list[dict]:
    return request.app.state.resume_export_service.list_exports(user, version_id)


@router.get(
    "/career/resume-exports/{export_id}",
    response_model=ResumeExportResponse,
)
def get_resume_export(
    export_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict:
    return request.app.state.resume_export_service.get_export(user, export_id)


@router.get("/career/resume-exports/{export_id}/download")
def download_resume_export(
    export_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> FileResponse:
    path, row = request.app.state.resume_export_service.download(user, export_id)
    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if row["format"] == "docx"
        else "application/pdf"
    )
    return FileResponse(path=path, media_type=media_type, filename=row["filename"])


@router.delete(
    "/career/resume-exports/{export_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resume_export(
    export_id: int,
    request: Request,
    user: PublicUser = Depends(require_user),
) -> Response:
    request.app.state.resume_export_service.delete_export(user, export_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
