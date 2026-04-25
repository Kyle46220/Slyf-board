import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import { type Post } from "../types";

interface Props {
  post: Post;
}

function LazyImage({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && ref.current) {
        ref.current.src = src;
        observer.disconnect();
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [src]);

  return <img ref={ref} alt={alt} className="w-full rounded" />;
}

function LazyVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && ref.current) {
        ref.current.src = src;
        observer.disconnect();
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [src]);

  return <video ref={ref} controls autoPlay={false} className="w-full rounded" />;
}

export function PostCard({ post }: Props) {
  const navigate = useNavigate();

  function viewPost() {
    navigate(`/post/${post.hash}`);
  }

  const mediaUrl = post.media_path
    ? `/media/${post.hash}/${post.content_type === "video" ? "media.mp4" : "media.webp"}`
    : null;

  return (
    <div className="break-inside-avoid mb-4 bg-zinc-900 rounded-lg p-3 text-white">
      {post.content_type === "image" && mediaUrl && (
        <LazyImage src={mediaUrl} alt="post image" />
      )}
      {post.content_type === "video" && mediaUrl && (
        <LazyVideo src={mediaUrl} />
      )}
      {post.content_type === "link" && (
        <a href={post.body ?? "#"} target="_blank" rel="noopener noreferrer"
           className="block border border-zinc-700 rounded p-2 hover:bg-zinc-800">
          {post.og_image_path && (
            <LazyImage src={`/media/${post.hash}/og.webp`} alt="link preview" />
          )}
          {post.og_title && <p className="font-bold mt-1">{post.og_title}</p>}
          {post.og_description && (
            <p className="text-sm text-zinc-400 mt-1">{post.og_description}</p>
          )}
          <p className="text-xs text-zinc-500 mt-1 truncate">{post.body}</p>
        </a>
      )}
      {post.body && post.content_type !== "link" && (
        <div className="prose prose-invert prose-sm mt-2">
          <ReactMarkdown>{post.body}</ReactMarkdown>
        </div>
      )}
      <button onClick={viewPost}
              className="mt-2 text-xs text-zinc-500 hover:text-zinc-300">
        View Post
      </button>
    </div>
  );
}
