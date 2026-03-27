import { useEffect, useState } from "react";
import { type Post } from "../types";
import { fetchPosts, fetchPost, createEventSource } from "../api";
import { PostCard } from "./PostCard";

interface SSEEvent {
  type: "new_post" | "delete";
  hash: string;
}

export function Board() {
  const [posts, setPosts] = useState<Post[]>([]);

  useEffect(() => {
    fetchPosts().then(setPosts).catch(console.error);

    const es = createEventSource();
    es.onmessage = (e: MessageEvent<string>) => {
      const event = JSON.parse(e.data) as SSEEvent;
      if (event.type === "new_post") {
        fetchPost(event.hash)
          .then((post) => setPosts((prev) => [post, ...prev]))
          .catch(console.error);
      } else if (event.type === "delete") {
        setPosts((prev) => prev.filter((p) => p.hash !== event.hash));
      }
    };

    return () => es.close();
  }, []);

  return (
    <div className="masonry p-4">
      {posts.map((post) => (
        <PostCard key={post.hash} post={post} />
      ))}
    </div>
  );
}
