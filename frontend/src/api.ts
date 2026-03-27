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
  return new EventSource(`${BASE}/stream`);
}
