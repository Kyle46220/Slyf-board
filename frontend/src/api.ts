import { type Post } from './types';

export async function fetchPosts(signal?: AbortSignal, before?: string): Promise<Post[]> {
  const query = before ? `?before=${encodeURIComponent(before)}` : '';
  const response = await fetch(`/api/posts${query}`, { signal });
  if (!response.ok) throw new Error('Failed to fetch posts');
  return response.json() as Promise<Post[]>;
}

export async function fetchPost(hash: string): Promise<Post> {
  const response = await fetch(`/api/posts/${encodeURIComponent(hash)}`);
  if (response.status === 404) throw new Error('Not found');
  if (!response.ok) throw new Error('Failed to fetch post');
  return response.json() as Promise<Post>;
}
