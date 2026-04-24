import { type Post } from "./types";

const BASE = "/api";

export async function fetchPosts(): Promise<Post[]> {
  const res = await fetch(`${BASE}/posts`);
  if (!res.ok) throw new Error("Failed to fetch posts");
  return res.json() as Promise<Post[]>;
}

export async function fetchPost(hash: string): Promise<Post> {
  const res = await fetch(`${BASE}/posts/${hash}`);
  if (res.status === 404) throw new Error("Not found");
  if (!res.ok) throw new Error("Failed to fetch post");
  return res.json() as Promise<Post>;
}

export function createEventSource(): EventSource {
  const es = new EventSource(`${BASE}/stream`);

  // Auto-reconnect on error with exponential backoff
  es.onerror = () => {
    es.close();
    // Reconnect after 5 seconds
    setTimeout(() => {
      createEventSource();
    }, 5000);
  };

  return es;
}
