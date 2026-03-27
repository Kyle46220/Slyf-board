# backend/app/schemas.py
from datetime import datetime
from pydantic import BaseModel

class PostOut(BaseModel):
    hash: str
    content_type: str
    body: str | None
    media_path: str | None
    og_title: str | None
    og_description: str | None
    og_image_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
