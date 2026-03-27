import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image
from bs4 import BeautifulSoup


def _ensure_dir(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


def process_image(src: Path, dest_dir: Path) -> Optional[Path]:
    """Strip EXIF and convert to WebP. Returns output path or None on failure."""
    try:
        _ensure_dir(dest_dir)
        img = Image.open(src)
        img_clean = img.copy()  # drops EXIF
        out = dest_dir / "media.webp"
        img_clean.save(out, "WEBP")
        return out
    except Exception:
        return None


def process_video(src: Path, dest_dir: Path) -> Optional[Path]:
    """Strip metadata and re-encode to MP4. Returns output path or None on failure."""
    try:
        _ensure_dir(dest_dir)
        out = dest_dir / "media.mp4"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-map_metadata", "-1",
                "-fflags", "+bitexact",
                "-c:v", "libx264",
                "-crf", "23",
                "-preset", "fast",
                "-c:a", "aac",
                str(out),
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            return None
        return out
    except Exception:
        return None


class OGResult:
    def __init__(self, title, description, image_path):
        self.title = title
        self.description = description
        self.image_path = image_path


def scrape_og(url: str, dest_dir: Optional[Path] = None) -> Optional[OGResult]:
    """Fetch OG tags from URL. Downloads and strips EXIF from OG image if dest_dir given."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        def og(prop):
            tag = soup.find("meta", property=f"og:{prop}")
            return tag["content"] if tag and tag.get("content") else None

        title = og("title") or (soup.title.string if soup.title else None)
        description = og("description")
        image_url = og("image")
        image_path = None

        if image_url and dest_dir:
            img_resp = httpx.get(image_url, timeout=10, follow_redirects=True)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                raw = Path(tmp.name)
            raw.write_bytes(img_resp.content)
            image_path = process_image(raw, dest_dir)
            if image_path:
                og_path = image_path.parent / "og.webp"
                (image_path.parent / "media.webp").rename(og_path)
                image_path = og_path

        return OGResult(title=title, description=description, image_path=image_path)
    except Exception:
        return None
