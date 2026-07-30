import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from fastapi import UploadFile
from pypdf import PdfReader

from app.core.config import Settings


@dataclass(frozen=True)
class ParsedResume:
    source_type: str
    original_filename: str | None
    extracted_text: str
    content_hash: str
    parse_status: str = "parsed"
    parse_error: str | None = None


class ResumeParseFailure(Exception):
    def __init__(self, code: str, message: str, source_type: str, filename: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.source_type = source_type
        self.filename = filename


class ResumeParsingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def from_text(self, text: str) -> ParsedResume:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("简历文本不能为空")
        return ParsedResume(
            source_type="text",
            original_filename=None,
            extracted_text=clean_text[:50000],
            content_hash=self._hash(clean_text.encode("utf-8")),
        )

    async def from_upload(self, file: UploadFile) -> ParsedResume:
        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.lower()
        if extension not in {".pdf", ".docx"}:
            raise ResumeParseFailure(
                "unsupported_resume_format",
                "仅支持 PDF 或 DOCX 简历",
                extension.removeprefix(".") or "unknown",
                filename,
            )
        content = await file.read()
        if not content:
            raise ResumeParseFailure(
                "empty_resume_file", "上传的简历文件为空", extension[1:], filename
            )
        if len(content) > self.settings.max_upload_bytes:
            raise ResumeParseFailure(
                "resume_file_too_large",
                "简历文件不能超过 20MB",
                extension[1:],
                filename,
            )

        try:
            text = (
                self._extract_pdf(content)
                if extension == ".pdf"
                else self._extract_docx(content)
            )
        except ResumeParseFailure:
            raise
        except Exception as exc:
            raise ResumeParseFailure(
                "resume_parse_failed",
                f"{extension[1:].upper()} 简历解析失败",
                extension[1:],
                filename,
            ) from exc

        if not text:
            message = (
                "PDF 中没有可提取文字；扫描版 PDF 暂不支持，请上传可复制文字的 PDF 或 DOCX"
                if extension == ".pdf"
                else "DOCX 中没有可提取的简历文字"
            )
            raise ResumeParseFailure(
                "no_extractable_resume_text", message, extension[1:], filename
            )
        return ParsedResume(
            source_type=extension[1:],
            original_filename=filename,
            extracted_text=text[:50000],
            content_hash=self._hash(content),
        )

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()

    @staticmethod
    def _extract_docx(content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > 10 * 1024 * 1024:
                raise ValueError("DOCX document.xml is too large")
            root = ElementTree.fromstring(archive.read(info))
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{namespace}p"):
            value = "".join(
                node.text or "" for node in paragraph.iter(f"{namespace}t")
            ).strip()
            if value:
                paragraphs.append(value)
        return "\n".join(paragraphs).strip()

    @staticmethod
    def _hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
