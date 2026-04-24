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
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const baseDelay = 1000;

  es.onerror = () => {
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      const delay = Math.min(baseDelay * Math.pow(2, reconnectAttempts - 1), 30000);
      console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);

      es.close();
      setTimeout(() => {
        createEventSource();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
    }
  };

  es.onopen = () => {
    console.log('SSE connection established');
    reconnectAttempts = 0; // Reset counter on successful connection
  };

  return es;
}
