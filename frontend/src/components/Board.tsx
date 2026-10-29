import { useEffect, useState } from 'react';
import { type Post } from '../types';
import { fetchPosts } from '../api';
import { PostCard } from './PostCard';

export function Board() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [before, setBefore] = useState<string>();
  const [history, setHistory] = useState<(string | undefined)[]>([]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    let running = false;
    setLoading(true);
    const refresh = async () => {
      if (running) return;
      running = true;
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 15000);
      try {
        const data = await fetchPosts(controller.signal, before);
        if (active) { setPosts(data); setError(null); }
      } catch {
        if (active) setError('Unable to refresh the board. Retrying automatically.');
      } finally {
        clearTimeout(timeout);
        running = false;
        if (active) {
          setLoading(false);
          timer = setTimeout(() => { if (!document.hidden) void refresh(); }, 30000);
        }
      }
    };
    const onVisible = () => {
      if (!document.hidden) { clearTimeout(timer); void refresh(); }
    };
    document.addEventListener('visibilitychange', onVisible);
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [before]);

  if (loading) return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div aria-label="Loading posts" className="animate-spin h-6 w-6 border-2 border-black border-t-transparent rounded-full" />
    </div>
  );

  return (
    <div className="min-h-screen bg-white">
      {error && <p role="status" className="text-sm text-zinc-500 p-6">{error}</p>}
      {posts.length === 0 && !error && (
        <div className="flex items-center justify-center min-h-[70vh]">
          <h2 className="text-lg font-medium text-zinc-400">Board Empty</h2>
        </div>
      )}
      <div className="masonry p-6">
        {posts.map(post => <PostCard key={post.hash} post={post} />)}
      </div>
      <nav aria-label="Gallery pages" className="flex justify-center gap-6 p-6 text-sm text-zinc-500">
        {history.length > 0 && <button className="underline" onClick={() => {
          setBefore(history[history.length - 1]); setHistory(history.slice(0, -1));
        }}>Newer posts</button>}
        {posts.length === 100 && <button className="underline" onClick={() => {
          setHistory([...history, before]); setBefore(posts[posts.length - 1].hash);
        }}>Older posts</button>}
      </nav>
    </div>
  );
}
