import io

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from app.core.config import Settings
from app.models.domain import PreparedAIInput
from app.prompts.catalog import pdf_summary_prompt


class PdfProcessingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def prepare(self, file: UploadFile) -> PreparedAIInput:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="请上传 PDF 文件")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传文件为空")
        if len(content) > self.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="文件不能超过 20MB")
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [(page.extract_text() or "") for page in reader.pages[:8]]
            text = "\n".join(pages).strip()[:12000]
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败：{exc}") from exc
        if not text:
            raise HTTPException(status_code=400, detail="PDF 中没有可提取的文字")
        return PreparedAIInput(
            prompt=pdf_summary_prompt(text),
            input_preview=file.filename or "PDF",
            metadata={"bytes": len(content)},
        )
