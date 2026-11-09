import { type Post } from './types';
import { boardUrl } from './BoardContext';

export async function fetchPosts(signal?: AbortSignal, before?: string, origin = ''): Promise<Post[]> {
  const query = before ? `?before=${encodeURIComponent(before)}` : '';
  const response = await fetch(boardUrl(`/api/posts${query}`, origin), { signal, credentials: 'omit', cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to fetch posts');
  return response.json() as Promise<Post[]>;
}

export async function fetchPost(hash: string, origin = ''): Promise<Post> {
  const response = await fetch(boardUrl(`/api/posts/${encodeURIComponent(hash)}`, origin), { credentials: 'omit', cache: 'no-store' });
  if (response.status === 404) throw new Error('Not found');
  if (!response.ok) throw new Error('Failed to fetch post');
  return response.json() as Promise<Post>;
}
