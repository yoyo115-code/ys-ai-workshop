from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TemplateKey = Literal["professional", "minimal_ats"]
ExportFormat = Literal["docx", "pdf"]
PaperSize = Literal["a4", "letter"]
ExportLanguage = Literal["zh", "en", "bilingual"]
ExportStatus = Literal["pending", "generating", "ready", "failed", "deleted"]


class ResumeBasics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=240)
    links: list[str] = Field(default_factory=list, max_length=12)
    summary: str = Field(default="", max_length=8000)


class ResumeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization: str = Field(default="", max_length=300)
    title: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=240)
    start_date: str = Field(default="", max_length=80)
    end_date: str = Field(default="", max_length=80)
    bullet_points: list[str] = Field(default_factory=list, max_length=80)


class StructuredResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str = Field(min_length=1, max_length=200_000)
    basics: ResumeBasics = Field(default_factory=ResumeBasics)
    education: list[ResumeEntry] = Field(default_factory=list, max_length=30)
    experience: list[ResumeEntry] = Field(default_factory=list, max_length=60)
    projects: list[ResumeEntry] = Field(default_factory=list, max_length=60)
    skills: list[str] = Field(default_factory=list, max_length=200)
    certifications: list[str] = Field(default_factory=list, max_length=100)
    awards: list[str] = Field(default_factory=list, max_length=100)
    additional_information: list[str] = Field(default_factory=list, max_length=200)


class ResumePreviewResponse(BaseModel):
    version_id: int
    resume_id: int
    version_number: int
    company_name: str
    job_title: str
    source_content_hash: str
    parse_status: Literal["structured", "needs_review"]
    parse_warnings: list[str]
    resume: StructuredResume


class CreateResumeExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: TemplateKey = "professional"
    format: ExportFormat
    paper_size: PaperSize = "a4"
    language: ExportLanguage = "bilingual"
    resume: StructuredResume | None = None


class ResumeExportResponse(BaseModel):
    id: int
    resume_id: int
    resume_version_id: int
    version_number: int
    company_name: str
    job_title: str
    template_key: TemplateKey
    format: ExportFormat
    paper_size: PaperSize
    language: ExportLanguage
    status: ExportStatus
    filename: str
    source_content_hash: str
    content_hash: str | None
    error_code: str | None
    created_at: str
    updated_at: str
    expires_at: str | None
    download_url: str | None
