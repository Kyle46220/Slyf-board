"""Input validation constants and helpers."""

MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_TEXT_LENGTH = 50000  # 50,000 characters
MAX_OG_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_image_size(file_size: int) -> bool:
    """Validate image file size."""
    return file_size <= MAX_IMAGE_SIZE


def validate_video_size(file_size: int) -> bool:
    """Validate video file size."""
    return file_size <= MAX_VIDEO_SIZE


def validate_text_length(text: str | None) -> bool:
    """Validate text length."""
    if text is None:
        return True
    return len(text) <= MAX_TEXT_LENGTH


def validate_og_image_size(file_size: int) -> bool:
    """Validate OG image file size."""
    return file_size <= MAX_OG_IMAGE_SIZE
