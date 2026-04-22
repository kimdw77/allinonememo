"""
file_parser.py — 업로드 파일에서 텍스트 추출 (txt/md/pdf/docx)
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(filename: str, content: bytes) -> str:
    """
    파일 확장자별 텍스트 추출.
    실패 시 빈 문자열 반환.
    """
    ext = Path(filename).suffix.lower()

    try:
        if ext in (".txt", ".md", ".text"):
            return _from_text(content)
        elif ext == ".pdf":
            return _from_pdf(content)
        elif ext in (".docx", ".doc"):
            return _from_docx(content)
        else:
            # 지원하지 않는 형식은 UTF-8로 시도
            return content.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.error("파일 텍스트 추출 실패 (%s): %s", filename, e)
        return ""


def _from_text(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "euc-kr", "cp949"):
        try:
            return content.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace").strip()


def _from_pdf(content: bytes) -> str:
    import io
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text.strip())
    return "\n\n".join(text_parts)


def _from_docx(content: bytes) -> str:
    import io
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
