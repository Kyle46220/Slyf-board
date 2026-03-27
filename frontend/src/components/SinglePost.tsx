import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { type Post } from "../types";
import { fetchPost } from "../api";
import { PostCard } from "./PostCard";

export function SinglePost() {
  const { hash } = useParams<{ hash: string }>();
  const [post, setPost] = useState<Post | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!hash) return;
    fetchPost(hash)
      .then(setPost)
      .catch(() => setNotFound(true));
  }, [hash]);

  if (notFound) return <div className="p-8 text-white">Post not found.</div>;
  if (!post) return <div className="p-8 text-white">Loading...</div>;

  return (
    <div className="max-w-xl mx-auto p-8">
      <PostCard post={post} />
    </div>
  );
}
