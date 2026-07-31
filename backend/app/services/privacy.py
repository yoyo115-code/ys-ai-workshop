from fastapi import HTTPException

from app.models.domain import PublicUser
from app.repositories.career import CareerRepository
from app.repositories.resume import ResumeRepository
from app.repositories.resume_export import ResumeExportRepository
from app.repositories.workshop import WorkshopRepository
from app.services.storage import StorageProvider
from app.core.security import verify_password


class PrivacyService:
    def __init__(
        self,
        workshop_repository: WorkshopRepository,
        career_repository: CareerRepository,
        resume_repository: ResumeRepository,
        export_repository: ResumeExportRepository,
        storage: StorageProvider,
    ) -> None:
        self.workshop_repository = workshop_repository
        self.career_repository = career_repository
        self.resume_repository = resume_repository
        self.export_repository = export_repository
        self.storage = storage

    def delete_application(self, user: PublicUser, application_id: int) -> None:
        application = self.career_repository.get_application(application_id, user["id"])
        if application is None:
            raise HTTPException(status_code=404, detail="申请记录不存在")
        objects = self.export_repository.list_object_keys_for_application(
            user["id"], application_id
        )
        self._delete_objects(objects)
        if not self.career_repository.delete_application(application_id, user["id"]):
            raise HTTPException(status_code=409, detail="申请记录状态已变化")

    def delete_resume(self, user: PublicUser, resume_id: int) -> None:
        objects = self.export_repository.list_object_keys_for_resume(
            user["id"], resume_id
        )
        self._delete_objects(objects)
        if not self.resume_repository.delete_resume(resume_id, user["id"]):
            raise HTTPException(status_code=404, detail="简历不存在")

    def delete_account(self, user: PublicUser, password: str) -> None:
        row = self.workshop_repository.find_user_by_id(user["id"])
        if row is None:
            raise HTTPException(status_code=404, detail="账号不存在")
        if not verify_password(password, row["salt"], row["password_hash"]):
            raise HTTPException(status_code=403, detail="密码不正确，未删除账号")
        objects = self.export_repository.list_object_keys_for_user(user["id"])
        self._delete_objects(objects)
        if not self.workshop_repository.delete_user(user["id"]):
            raise HTTPException(status_code=409, detail="账号状态已变化")

    def _delete_objects(self, objects: list[dict]) -> None:
        try:
            for item in objects:
                self.storage.delete(item["user_id"], item["object_key"])
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "data_deletion_incomplete",
                    "message": "文件删除未完成，数据库记录已保留，请稍后重试",
                },
            ) from exc
