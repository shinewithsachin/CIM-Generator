import tempfile
from pathlib import Path

from document_processor import DocumentProcessor


def test_process_txt_file() -> None:
    processor = DocumentProcessor()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        f.write("Acme Corp is a mid-market SaaS company. " * 50)
        path = f.name

    try:
        docs = processor.process_file(path)
        assert len(docs) >= 1
        assert "Acme Corp" in docs[0].page_content
    finally:
        Path(path).unlink(missing_ok=True)


def test_process_docx_file() -> None:
    docx = __import__("docx")
    document = docx.Document()
    document.add_paragraph("Confidential Information Memorandum for Acme Corp.")
    document.add_paragraph("Revenue grew 22% year over year.")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = f.name
    document.save(path)

    try:
        docs = DocumentProcessor().process_file(path)
        assert len(docs) >= 1
        joined = " ".join(d.page_content for d in docs)
        assert "Acme Corp" in joined
    finally:
        Path(path).unlink(missing_ok=True)


def test_unsupported_extension_not_in_supported_set() -> None:
    assert ".exe" not in DocumentProcessor.SUPPORTED_EXTENSIONS
    assert ".pdf" in DocumentProcessor.SUPPORTED_EXTENSIONS
