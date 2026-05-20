import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

  // Helper to extract external URL from body
  const getExternalUrl = () => {
    if (!post.body) return "#";
    const urlRegex = /(https?:\/\/[^\s]+)/;
    const match = post.body.match(urlRegex);
    return match ? match[0] : post.body;
  };
  const externalUrl = getExternalUrl();
  
  const getDomain = (urlStr: string) => {
    try {
      return new URL(urlStr).hostname;
    } catch {
      return urlStr;
    }
  };
  const domain = getDomain(externalUrl);

  const isDirectImageLink = post.content_type === "link" && post.og_image_path && !post.og_title && !post.og_description;

  // Link posts
  if (post.content_type === "link") {
    const isOnlyUrl = post.body ? post.body.trim() === externalUrl : false;

    return (
      <div
        className={cardBase}
        style={cardStyle}
        onClick={() => navigate(`/post/${post.hash}`)}
      >
        {post.og_image_path && (
          <a
            href={externalUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="block overflow-hidden rounded mb-3 group/img relative"
          >
            <LazyImage
              src={post.og_image_path.startsWith('http') ? post.og_image_path : `/media/${post.hash}/og.webp`}
              alt="link preview"
            />
            <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center">
              <span className="bg-white/95 text-black text-xs font-semibold px-2 py-1 rounded shadow-sm flex items-center gap-1">
                {isDirectImageLink ? "Open Image" : "Visit Site"} <span className="text-zinc-500">↗</span>
              </span>
            </div>
          </a>
        )}

        {!isDirectImageLink && (
          <div className="space-y-1">
            {post.og_title && (
              <h3 className="font-semibold text-sm text-zinc-900 leading-snug hover:text-blue-600 transition-colors">
                <a
                  href={externalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  {post.og_title}
                </a>
              </h3>
            )}
            {post.og_description && (
              <p className="text-xs text-zinc-500 mt-1 line-clamp-2 leading-relaxed">
                {post.og_description}
              </p>
            )}
          </div>
        )}

        {/* Display inline body message if it exists and is more than just the raw URL */}
        {post.body && !isOnlyUrl && (
          <div className="prose prose-sm text-zinc-800 max-w-none mt-2 border-t border-zinc-100 pt-2 prose-p:my-1 prose-a:text-blue-600 prose-a:underline break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ node, ...props }) => (
                  <a
                    {...props}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-blue-600 underline hover:text-blue-800"
                  />
                )
              }}
            >
              {post.body}
            </ReactMarkdown>
          </div>
        )}

        {/* Clickable domain path badge */}
        <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-2 text-[11px] text-zinc-400">
          <a
            href={externalUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 font-medium text-blue-600 hover:text-blue-800 transition-colors bg-blue-50/50 hover:bg-blue-50 px-2 py-1 rounded border border-blue-100/50 hover:border-blue-100"
          >
            <span>{domain}</span>
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>
    );
  }

  // Image / video / text posts
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
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ node, ...props }) => (
                <a
                  {...props}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-blue-600 underline hover:text-blue-800"
                />
              )
            }}
          >
            {post.body}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
