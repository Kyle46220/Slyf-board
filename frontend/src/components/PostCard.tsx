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

  const mediaUrl = post.media_path
    ? post.media_path.startsWith('http') 
      ? post.media_path 
      : `/media/${post.hash}/${post.content_type === "video" ? "media.mp4" : "media.webp"}`
    : null;

  const RAINBOW_COLORS = [
    '#FF0000', // Red
    '#FF7F00', // Orange
    '#FFFF00', // Yellow
    '#00FF00', // Green
    '#0000FF', // Blue
    '#4B0082', // Indigo
    '#8B00FF', // Violet
  ];

  // Stable random color based on hash
  const colorIndex = Math.abs(post.hash.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)) % RAINBOW_COLORS.length;
  const rainbowColor = RAINBOW_COLORS[colorIndex];

  const cardBase =
    "break-inside-avoid mb-6 rounded-lg p-4 text-black cursor-pointer transition-all duration-200 hover:shadow-md border-[1.5px]";
  const cardStyle = {
    background: '#ffffff',
    borderColor: rainbowColor,
  };

  // Link posts: entire card is an external anchor
  if (post.content_type === "link") {
    return (
      <a
        href={post.body ?? "#"}
        target="_blank"
        rel="noopener noreferrer"
        className={`${cardBase} block`}
        style={cardStyle}
      >
        {post.og_image_path && (
          <LazyImage src={post.og_image_path.startsWith('http') ? post.og_image_path : `/media/${post.hash}/og.webp`} alt="link preview" />
        )}
        {post.og_title && <p className="font-semibold mt-3 text-sm">{post.og_title}</p>}
        {post.og_description && (
          <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{post.og_description}</p>
        )}
        {post.body && (
          <p className="text-[10px] text-zinc-400 mt-2 truncate">{post.body}</p>
        )}
      </a>
    );
  }

  // Image / video / text posts: click navigates to single-post view
  return (
    <div
      className={cardBase}
      style={cardStyle}
      onClick={() => navigate(`/post/${post.hash}`)}
    >
      {post.content_type === "image" && mediaUrl && (
        <LazyImage src={mediaUrl} alt="post image" />
      )}
      {post.content_type === "video" && mediaUrl && (
        <LazyVideo src={mediaUrl} />
      )}
      {post.body && (
        <div className="prose prose-sm text-zinc-800 max-w-none prose-p:my-1 prose-a:text-blue-600 prose-a:underline break-words">
          <ReactMarkdown>{post.body}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
