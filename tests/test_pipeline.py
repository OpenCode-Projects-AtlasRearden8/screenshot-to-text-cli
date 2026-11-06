"""End-to-end pipeline tests using a fake OCR engine (no model, fast)."""

from pathlib import Path

import pytest
from PIL import Image

from screenshot_to_text import manifest
from screenshot_to_text.clean import clean_ocr_text
from screenshot_to_text.ocr import OcrEngine
from screenshot_to_text.pipeline import blank_row, process_folder, scan_images


class FakeEngine(OcrEngine):
    """Deterministic stand-in for a real OCR backend."""

    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    def ensure_loaded(self) -> str:
        return "fake"

    def extract_text(self, image_path: Path) -> str:
        self.calls.append(str(image_path.name))
        return clean_ocr_text(
            f"TEXT FROM {image_path.name.strip('.png').upper() or 'IMAGE'}\n"
        )


def make_image(path: Path, color=(200, 200, 200)) -> None:
    img = Image.new("RGB", (50, 50), color)
    img.save(path)


@pytest.fixture()
def shots(tmp_path: Path) -> Path:
    folder = tmp_path / "shots"
    folder.mkdir()
    make_image(folder / "receipt1.png", (255, 255, 255))
    make_image(folder / "receipt2.png", (10, 10, 10))
    (folder / "notes.txt").write_text("not an image", encoding="utf-8")
    return folder


def test_scan_images_skips_non_images_and_sorts_naturally(shots: Path):
    names = [p.name for p in scan_images(shots)]
    assert names == ["receipt1.png", "receipt2.png"]


def test_process_folder_writes_text_and_manifest(shots, tmp_path: Path):
    out_dir = tmp_path / "out"
    manifest_path = tmp_path / "manifest.csv"
    result = process_folder(
        input_dir=shots,
        out_dir=out_dir,
        manifest_path=manifest_path,
        engine=FakeEngine(),
    )

    text_files = sorted(p.name for p in out_dir.glob("*.txt"))
    assert text_files == ["receipt1.txt", "receipt2.txt"]
    assert (out_dir / "receipt1.txt").read_text(encoding="utf-8") == "TEXT FROM RECEIPT1"

    rows = result["rows"]
    assert all(r["status"] == "ok" for r in rows)
    assert all(r["engine"] == "fake" for r in rows)
    assert rows[0]["sha256"] and rows[0]["sha256"] != rows[1]["sha256"]

    persisted = manifest.read_manifest(manifest_path)
    assert [r["image_file"] for r in persisted] == [
        str(shots / "receipt1.png"),
        str(shots / "receipt2.png"),
    ]


def test_rerun_dedupes_against_manifest(shots, tmp_path: Path):
    out_dir = tmp_path / "out"
    manifest_path = tmp_path / "manifest.csv"
    fake = FakeEngine()
    process_folder(shots, out_dir, manifest_path, engine=fake)
    assert len(fake.calls) == 2

    result = process_folder(shots, out_dir, manifest_path, engine=fake)
    # No images were re-OCR'd on the second pass; hashes matched the manifest.
    assert len(fake.calls) == 2
    assert all(r["status"] == "duplicate" for r in result["rows"])
    assert all(r["duplicate_of"] for r in result["rows"])
    # Duplicates still get their own text file (copied from the original).
    text_files = sorted(p.name for p in out_dir.glob("*.txt"))
    assert text_files == ["receipt1.2.txt", "receipt1.txt", "receipt2.2.txt", "receipt2.txt"]


def test_duplicate_screenshot_within_one_run(tmp_path: Path):
    folder = tmp_path / "shots"
    folder.mkdir()
    make_image(folder / "a.png", (128, 128, 128))
    make_image(folder / "copy.png", (128, 128, 128))  # same bytes

    out_dir = tmp_path / "out"
    result = process_folder(folder, out_dir, tmp_path / "manifest.csv", engine=FakeEngine())

    statuses = {Path(r["image_file"]).name: r["status"] for r in result["rows"]}
    assert statuses == {"a.png": "ok", "copy.png": "duplicate"}
    assert result["rows"][1]["duplicate_of"] == str(folder / "a.png")
    assert (out_dir / "copy.txt").read_text(encoding="utf-8") == (out_dir / "a.txt").read_text(encoding="utf-8")


def test_force_reprocesses(shots, tmp_path: Path):
    out_dir = tmp_path / "out"
    manifest_path = tmp_path / "manifest.csv"
    fake = FakeEngine()
    process_folder(shots, out_dir, manifest_path, engine=fake)
    process_folder(shots, out_dir, manifest_path, engine=fake, force=True)
    assert len(fake.calls) == 4


def test_unreadable_file_becomes_error_row(shots, tmp_path: Path):
    bad = shots / "broken.png"
    bad.write_bytes(b"")  # empty: fine for MD5 but a real OCR engine would choke

    class FailEngine(FakeEngine):
        def extract_text(self, image_path: Path) -> str:
            if image_path.name == "broken.png":
                raise ValueError("no pixels")
            return super().extract_text(image_path)

    result = process_folder(shots, out_dir=tmp_path / "out", manifest_path=tmp_path / "m.csv", engine=FailEngine())
    rows = {Path(r["image_file"]).name: r for r in result["rows"]}
    assert rows["broken.png"]["status"] == "error"
    assert "no pixels" in rows["broken.png"]["error"]
    # Other images still processed.
    assert rows["receipt1.png"]["status"] == "ok"


def test_blank_row_defaults(tmp_path: Path):
    p = tmp_path / "whatever.png"
    p.write_bytes(b"x")
    row = blank_row(p, "somehash")
    for field in manifest.MANIFEST_FIELDS:
        assert field in row
    assert row["sha256"] == "somehash"
    assert row["status"] == ""
