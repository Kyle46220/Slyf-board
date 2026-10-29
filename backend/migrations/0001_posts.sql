-- Compatible with the previous D1 posts table: no data is dropped or rewritten.
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hash TEXT UNIQUE,
  content_type TEXT,
  body TEXT,
  media_path TEXT,
  og_title TEXT,
  og_description TEXT,
  og_image_path TEXT,
  deleted INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS posts_visible_id ON posts(deleted, id DESC);
