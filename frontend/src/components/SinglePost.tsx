import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type Post } from "../types";
import { fetchPost } from "../api";
import { PostCard } from "./PostCard";
import { useBoardContext } from "../BoardContext";

export function SinglePost() {
  const { origin } = useBoardContext();
  const { hash } = useParams<{ hash: string }>();
  const [post, setPost] = useState<Post | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!hash) return;
    fetchPost(hash, origin)
      .then(setPost)
      .catch(() => setNotFound(true));
  }, [hash, origin]);

  return (
    <div className="max-w-xl mx-auto p-8">
      <Link to="/" className="embed-back inline-block mb-4 text-blue-600 underline">← Back to board</Link>
      {notFound ? <p className="text-zinc-500">Post not found.</p>
        : post ? <PostCard post={post} /> : <p className="text-zinc-500">Loading...</p>}
    </div>
  );
}

