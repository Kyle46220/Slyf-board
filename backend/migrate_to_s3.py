import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import SessionLocal
from app.models import Post
from sqlalchemy import select
from app.media import upload_to_s3
from app.config import settings

async def migrate_post(post: Post, session: AsyncSession):
    updated = False

    # Migrate main media
    if post.media_path and not post.media_path.startswith("http"):
        # The media path in DB is currently a relative path like /media/hash/media.webp 
        # Actually it's probably an absolute local path or just the string returned by process_image
        # Wait, the previous process_image returned `str(out)` which was something like `/var/board/media/<hash>/media.webp`
        local_path = Path(post.media_path)
        if local_path.exists():
            s3_key = f"{post.hash}/{local_path.name}"
            content_type = "video/mp4" if local_path.suffix == ".mp4" else "image/webp"
            print(f"Uploading {local_path} to {s3_key}...")
            s3_url = await upload_to_s3(local_path, s3_key, content_type)
            if s3_url:
                post.media_path = s3_url
                updated = True
                print(f"Successfully uploaded: {s3_url}")
            else:
                print(f"Failed to upload: {local_path}")

    # Migrate OG image
    if post.og_image_path and not post.og_image_path.startswith("http"):
        local_path = Path(post.og_image_path)
        if local_path.exists():
            # Usually og images are at <hash>_og/og.webp
            s3_key = f"{post.hash}_og/{local_path.name}"
            print(f"Uploading {local_path} to {s3_key}...")
            s3_url = await upload_to_s3(local_path, s3_key, "image/webp")
            if s3_url:
                post.og_image_path = s3_url
                updated = True
                print(f"Successfully uploaded OG image: {s3_url}")
            else:
                print(f"Failed to upload OG image: {local_path}")

    if updated:
        session.add(post)
        await session.commit()

async def main():
    if not settings.aws_access_key_id:
        print("S3 credentials not configured in environment.")
        return

    print("Starting migration to S3...")
    async with SessionLocal() as session:
        result = await session.execute(select(Post))
        posts = result.scalars().all()

        for post in posts:
            await migrate_post(post, session)
            
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
