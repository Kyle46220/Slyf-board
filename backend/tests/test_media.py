import shutil
import subprocess
import pytest
from pathlib import Path
from PIL import Image
from app.media import process_image, process_video, scrape_og

has_ffmpeg = shutil.which("ffmpeg") is not None

TMP = Path("/tmp/board_test_media")


@pytest.fixture(autouse=True)
def tmp_dir():
    TMP.mkdir(exist_ok=True)
    yield
    shutil.rmtree(TMP, ignore_errors=True)


def make_jpeg_with_exif(path: Path):
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    exif_bytes = img.getexif()
    exif_bytes[0x013B] = "Test Artist"
    img.save(path, "JPEG", exif=exif_bytes.tobytes())


def make_test_mp4(path: Path):
    """Create a minimal valid MP4 using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:size=64x64:duration=1",
         "-c:v", "libx264", "-t", "1", str(path)],
        capture_output=True, check=True
    )


def test_process_image_strips_exif_and_converts_to_webp(tmp_path):
    src = tmp_path / "input.jpg"
    make_jpeg_with_exif(src)
    out = process_image(src, TMP / "abc123")
    assert out is not None
    assert out.suffix == ".webp"
    result = Image.open(out)
    assert len(result.getexif()) == 0


def test_process_image_returns_none_on_corrupt_file(tmp_path):
    src = tmp_path / "bad.jpg"
    src.write_bytes(b"not an image")
    out = process_image(src, TMP / "def456")
    assert out is None


@pytest.mark.skipif(not has_ffmpeg, reason="ffmpeg not installed")
def test_process_video_re_encodes_to_mp4(tmp_path):
    """Requires ffmpeg installed."""
    src = tmp_path / "input.mp4"
    make_test_mp4(src)
    out = process_video(src, TMP / "vid123")
    assert out is not None
    assert out.suffix == ".mp4"
    assert out.exists()


def test_process_video_returns_none_on_corrupt_file(tmp_path):
    src = tmp_path / "bad.mp4"
    src.write_bytes(b"not a video")
    out = process_video(src, TMP / "vid456")
    assert out is None


def test_scrape_og_returns_none_on_network_error():
    result = scrape_og("http://10.255.255.1/")
    assert result is None
