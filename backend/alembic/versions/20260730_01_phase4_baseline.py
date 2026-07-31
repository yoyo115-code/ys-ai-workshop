"""Phase 4 application schema baseline.

Revision ID: 20260730_01
Revises: None
"""
from alembic import op
import sqlalchemy as sa


revision = "20260730_01"
down_revision = None
branch_labels = None
depends_on = None


def _id_column() -> sa.Column:
    return sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True)


def upgrade() -> None:
    op.create_table(
        "users",
        _id_column(),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("token", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "activity_logs",
        _id_column(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("input_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("output_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_activity_user_created", "activity_logs", ["user_id", sa.text("created_at DESC")])
    op.create_table(
        "job_applications",
        _id_column(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("job_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.Text(), nullable=False, server_default=""),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False, server_default="zh"),
        sa.Column("status", sa.Text(), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_job_applications_user_updated", "job_applications", ["user_id", sa.text("updated_at DESC")])
    op.create_table(
        "resume_sources",
        _id_column(),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text()),
        sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.Text(), nullable=False, server_default=""),
        sa.Column("parse_status", sa.Text(), nullable=False),
        sa.Column("parse_error", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "match_analyses",
        _id_column(),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_alignment", sa.Text()),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("limitations", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_match_analyses_application_created", "match_analyses", ["application_id", sa.text("created_at DESC")])
    op.create_index("idx_match_analyses_one_active", "match_analyses", ["application_id"], unique=True, postgresql_where=sa.text("status = 'analyzing'"), sqlite_where=sa.text("status = 'analyzing'"))
    op.create_table(
        "match_items",
        _id_column(),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("match_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("jd_requirement", sa.Text(), nullable=False),
        sa.Column("resume_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("confidence_level", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_match_items_analysis_category", "match_items", ["analysis_id", "category", "sort_order"])
    op.create_table(
        "resumes",
        _id_column(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_application_id", sa.Integer(), sa.ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_version_id", sa.Integer()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.Text()),
    )
    op.create_index("idx_resumes_user_updated", "resumes", ["user_id", sa.text("updated_at DESC")])
    op.create_table(
        "resume_versions",
        _id_column(),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_version_id", sa.Integer(), sa.ForeignKey("resume_versions.id", ondelete="SET NULL")),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("resume_id", "version_number"),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_resumes_current_version", "resumes", "resume_versions", ["current_version_id"], ["id"], ondelete="SET NULL")
    op.create_index("idx_resume_versions_resume_number", "resume_versions", ["resume_id", sa.text("version_number DESC")])
    op.create_table(
        "resume_suggestions",
        _id_column(),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_version_id", sa.Integer(), sa.ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("jd_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("resume_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("clarification_required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("generation_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.Text()),
    )
    op.create_index("idx_resume_suggestions_application_version", "resume_suggestions", ["application_id", "resume_version_id", "status", "id"])
    op.create_table(
        "resume_suggestion_events",
        _id_column(),
        sa.Column("suggestion_id", sa.Integer(), sa.ForeignKey("resume_suggestions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("new_value", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_resume_suggestion_events_suggestion", "resume_suggestion_events", ["suggestion_id", sa.text("id DESC")])
    op.create_table(
        "resume_exports",
        _id_column(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_version_id", sa.Integer(), sa.ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_key", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("paper_size", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text()),
        sa.Column("source_content_hash", sa.Text(), nullable=False),
        sa.Column("structured_content", sa.Text(), nullable=False),
        sa.Column("structure_hash", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text()),
        sa.Column("deleted_at", sa.Text()),
        sa.CheckConstraint("template_key IN ('professional', 'minimal_ats')"),
        sa.CheckConstraint("format IN ('docx', 'pdf')"),
        sa.CheckConstraint("paper_size IN ('a4', 'letter')"),
        sa.CheckConstraint("language IN ('zh', 'en', 'bilingual')"),
        sa.CheckConstraint("status IN ('pending', 'generating', 'ready', 'failed', 'deleted')"),
    )
    op.create_index("idx_resume_exports_user_created", "resume_exports", ["user_id", sa.text("created_at DESC"), sa.text("id DESC")])
    op.create_index("idx_resume_exports_version_created", "resume_exports", ["resume_version_id", sa.text("created_at DESC"), sa.text("id DESC")])


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_resumes_current_version", "resumes", type_="foreignkey")
    for table in (
        "resume_exports",
        "resume_suggestion_events",
        "resume_suggestions",
        "resume_versions",
        "resumes",
        "match_items",
        "match_analyses",
        "resume_sources",
        "job_applications",
        "activity_logs",
        "sessions",
        "users",
    ):
        op.drop_table(table)
