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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sseConnected, setSseConnected] = useState(false);

  useEffect(() => {
    console.log("Board component mounted, starting initialization...");

    // Fetch initial posts
    fetchPosts()
      .then((data) => {
        console.log("Posts loaded successfully:", data);
        setPosts(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch posts:", err);
        setError("Failed to load posts");
        setLoading(false);
      });

    // Set up EventSource for real-time updates
    try {
      console.log("Attempting to connect to SSE...");
      const es = createEventSource();

      es.onopen = () => {
        console.log("SSE connection opened");
        setSseConnected(true);
      };

      es.onmessage = (e: MessageEvent<string>) => {
        console.log("SSE event received:", e.data);
        try {
          const event = JSON.parse(e.data) as SSEEvent;
          if (event.type === "new_post") {
            fetchPost(event.hash)
              .then((post) => setPosts((prev) => [post, ...prev]))
              .catch(console.error);
          } else if (event.type === "delete") {
            setPosts((prev) => prev.filter((p) => p.hash !== event.hash));
          }
        } catch (err) {
          console.error("Failed to parse SSE event:", err);
        }
      };

      es.onerror = (err) => {
        console.error("SSE error:", err);
        setError("Connection lost");
        setSseConnected(false);
        // Don't close the connection, let it retry automatically
      };

      return () => {
        console.log("Cleaning up SSE connection");
        es.close();
      };
    } catch (err) {
      console.error("Failed to create EventSource:", err);
      setError("Failed to establish connection");
      setLoading(false);
    }
  }, []);

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-white">
        <div className="text-center">
          <p className="text-xl mb-2">Loading board...</p>
          <p className="text-sm text-zinc-400">Please wait while we connect to the server</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-white">
        <div className="text-center max-w-md p-6 border border-zinc-700 rounded-lg">
          <h2 className="text-2xl font-bold mb-4 text-red-400">Connection Error</h2>
          <p className="text-zinc-300 mb-4">{error}</p>
          <div className="space-y-2 text-sm">
            <p className="text-zinc-400">
              <strong>Status:</strong> {sseConnected ? "Connected" : "Disconnected"}
            </p>
            <p className="text-zinc-400">
              <strong>API:</strong> <code className="bg-zinc-800 px-2 py-1 rounded">{window.location.origin}/api/posts</code>
            </p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded transition-colors"
          >
            Refresh Page
          </button>
        </div>
      </div>
    );
  }

  // Show empty state
  if (posts.length === 0) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-white">
        <div className="text-center">
          <h2 className="text-3xl font-bold mb-4">No posts yet</h2>
          <p className="text-zinc-400 mb-4">The board is empty</p>
          <div className="text-sm text-zinc-500">
            <p>Posts will appear here once users start posting via Signal</p>
            <p className="mt-2">Connection status: {sseConnected ? "✓ Connected" : "⚠ Disconnected"}</p>
          </div>
        </div>
      </div>
    );
  }

  // Show posts
  return (
    <div className="masonry p-4">
      {posts.map((post) => <PostCard key={post.hash} post={post} />)}
    </div>
  );
}
