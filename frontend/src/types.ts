export interface Post {
  hash: string;
  content_type: "text" | "image" | "video" | "link";
  body: string | null;
  media_path: string | null;
  og_title: string | null;
  og_description: string | null;
  og_image_path: string | null;
  created_at: string;
}
