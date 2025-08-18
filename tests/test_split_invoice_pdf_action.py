import os
import sys
from pathlib import Path

from PyPDF2 import PdfWriter

# Ensure project root is on the path for test execution environments
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyzap.plugins.split_invoice_pdf import SplitInvoicePdfAction
from pyzap.utils import safe_filename


def _create_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as fh:
        writer.write(fh)


def _count_open_files() -> int:
    """Return the number of file descriptors open for this process."""
    return len(os.listdir("/proc/self/fd"))


def test_pdf_split_closes_input_file(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    _create_pdf(pdf_path, pages=2)
    output_dir = tmp_path / "out"

    action = SplitInvoicePdfAction(params={"output_dir": str(output_dir)})

    before = _count_open_files()
    result = action.execute({"pdf_path": str(pdf_path)})
    after = _count_open_files()

    # ensure the action produced an output file and no file descriptors leaked
    assert result["files"], "Expected at least one output file"
    assert after == before


def test_pdf_split_sanitizes_filename(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    _create_pdf(pdf_path, pages=1)
    output_dir = tmp_path / "out"

    template = "  inv*alid?{index}" + "x" * 150 + ".pdf  "
    action = SplitInvoicePdfAction(params={"output_dir": str(output_dir), "name_template": template})
    result = action.execute({"pdf_path": str(pdf_path)})

    expected = safe_filename(template.format(index=1))
    assert len(expected) <= 100
    assert os.path.basename(result["files"][0]) == expected

