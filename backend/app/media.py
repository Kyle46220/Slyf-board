import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import mimetypes

import httpx
import logging
from PIL import Image
from bs4 import BeautifulSoup
import aioboto3
from app.config import settings
from app.validators import (
    validate_image_size,
    validate_video_size,
    validate_text_length,
    validate_og_image_size,
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
)

logger = logging.getLogger(__name__)

# Regex to detect direct image URLs by extension
_IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|bmp|tiff?)(?:\?.*)?$", re.IGNORECASE)


def _ensure_dir(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


def safe_path(path: Path, base_dir: Path) -> bool:
    """Ensure path is within allowed directory to prevent path traversal."""
    try:
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()
        resolved_path.relative_to(resolved_base)
        return True
    except ValueError:
        return False


async def upload_to_s3(file_path: Path, s3_key: str, content_type: str) -> Optional[str]:
    """Upload a file to S3 and return the public URL, or None if S3 is not configured/fails."""
    if not settings.aws_bucket_name or not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return None

    try:
        session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        async with session.client("s3", endpoint_url=settings.aws_endpoint_url) as s3:
            with open(file_path, "rb") as f:
                await s3.upload_fileobj(
                    f,
                    settings.aws_bucket_name,
                    s3_key,
                    ExtraArgs={"ContentType": content_type}
                )
        
        # Construct public URL based on endpoint or standard S3 URL
        if settings.aws_public_url:
            return f"{settings.aws_public_url.rstrip('/')}/{s3_key}"
        elif settings.aws_endpoint_url:
            url = f"{settings.aws_endpoint_url}/{settings.aws_bucket_name}/{s3_key}"
            return url
        else:
            return f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        return None


async def process_image(src: Path, dest_dir: Path, post_hash: str) -> Optional[str]:
    """Strip EXIF, resize max 1920x1920, and convert to WebP. Returns S3 URL or local path on failure."""
    try:
        # Validate destination will be in allowed directory
        if not safe_path(dest_dir, Path(settings.media_dir)):
            raise ValueError("Invalid destination file path")

        # Validate file size
        file_size = src.stat().st_size
        if not validate_image_size(file_size):
            raise ValueError(f"Image size {file_size} exceeds limit {MAX_IMAGE_SIZE}")

        _ensure_dir(dest_dir)
        img = Image.open(src)
        out = dest_dir / "media.webp"
        
        if getattr(img, "is_animated", False):
            # For animated GIFs, we don't resize to avoid breaking animation or exploding memory, 
            # just save it as animated WebP.
            img.save(out, "WEBP", save_all=True)
        else:
            img_clean = img.copy()  # drops EXIF
            # Resize logic: max dimension 1920
            img_clean.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            img_clean.save(out, "WEBP")
            
        s3_url = await upload_to_s3(out, f"{post_hash}/media.webp", "image/webp")
        if s3_url:
            return s3_url
            
        return str(out)
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        return None


async def process_video(src: Path, dest_dir: Path, post_hash: str) -> Optional[str]:
    """Strip metadata and re-encode to MP4. Returns S3 URL or local path on failure."""
    try:
        # Validate destination will be in allowed directory
        if not safe_path(dest_dir, Path(settings.media_dir)):
            raise ValueError("Invalid destination file path")

        # Validate file size
        file_size = src.stat().st_size
        if not validate_video_size(file_size):
            raise ValueError(f"Video size {file_size} exceeds limit {MAX_VIDEO_SIZE}")

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
            
        s3_url = await upload_to_s3(out, f"{post_hash}/media.mp4", "video/mp4")
        if s3_url:
            return s3_url
            
        return str(out)
    except Exception:
        return None


class OGResult:
    def __init__(self, title, description, image_path):
        self.title = title
        self.description = description
        self.image_path = image_path


async def scrape_og(url: str, dest_dir: Optional[Path] = None, post_hash: str = "") -> Optional[OGResult]:
    """Fetch OG tags from URL. Downloads and strips EXIF from OG image if dest_dir given.
    If the URL itself points directly to an image, use it as the thumbnail.
    """
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            content_type = resp.headers.get("content-type", "")

            # Check if this URL is itself an image (direct image link)
            is_direct_image = (
                content_type.startswith("image/")
                or bool(_IMAGE_EXT_RE.search(url.split("?")[0]))
            )

            image_url = None
            title = None
            description = None

            if is_direct_image:
                # The URL IS the image — use it directly as the thumbnail
                image_url = url
                logger.info(f"URL is a direct image ({content_type}): {url[:80]}")
            else:
                # Parse as HTML and extract OG tags
                if len(resp.content) > 10 * 1024 * 1024:
                    logger.warning(f"Page too large to scrape: {url[:80]}")
                    return None
                soup = BeautifulSoup(resp.text, "html.parser")

                def og(prop):
                    tag = soup.find("meta", property=f"og:{prop}")
                    return tag["content"] if tag and tag.get("content") else None

                title = og("title") or (soup.title.string if soup.title else None)
                description = og("description")
                image_url = og("image")
                logger.info(f"Scraped OG for {url[:80]}: title={title!r}, image={image_url!r}")

            image_path = None
            if image_url and dest_dir and post_hash:
                img_resp = await client.get(image_url)
                # Validate OG image size
                if not validate_og_image_size(len(img_resp.content)):
                    logger.warning(f"OG image too large ({len(img_resp.content)} bytes): {image_url[:80]}")
                    return OGResult(title=title, description=description, image_path=None)

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    raw = Path(tmp.name)
                raw.write_bytes(img_resp.content)
                processed_path_or_url = await process_image(raw, dest_dir, f"{post_hash}_og")
                raw.unlink(missing_ok=True)
                
                if processed_path_or_url:
                    # Rename the local file if it's a local file (to og.webp)
                    if not processed_path_or_url.startswith("http"):
                        og_path = Path(processed_path_or_url).parent / "og.webp"
                        Path(processed_path_or_url).rename(og_path)
                        image_path = str(og_path)
                    else:
                        # process_image uploads to {post_hash}_og/media.webp
                        # That's fine, we return the S3 URL
                        image_path = processed_path_or_url
                else:
                    logger.warning(f"Failed to process OG image from {image_url[:80]}")

            return OGResult(title=title, description=description, image_path=image_path)
    except Exception as e:
        logger.error(f"scrape_og failed for {url[:80]}: {e}")
        return None
