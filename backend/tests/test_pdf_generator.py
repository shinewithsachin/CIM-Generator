import tempfile
from pathlib import Path

from pypdf import PdfReader

from pdf_generator import PDFGenerator


def test_generate_standalone_pdf_from_fake_sections() -> None:
    sections = {
        "executive_summary": {
            "content": "## Executive Summary\n\nAcme Corp is a profitable SaaS business.",
            "charts": [],
        },
        "financials": {
            "content": "## Financials\n\nRevenue grew from $10M to $22M over three years.",
            "charts": [],
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        output_path = str(Path(tmp) / "test_cim.pdf")
        PDFGenerator().generate(sections, output_path, "test-session-id")

        assert Path(output_path).exists()
        assert Path(output_path).stat().st_size > 1000  # non-trivial PDF, not an empty stub

        reader = PdfReader(output_path)
        assert len(reader.pages) >= 3  # cover + disclaimer + at least one section
