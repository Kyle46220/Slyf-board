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

    // Fetch initial posts with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
      setError("Connection timeout - server may be down");
      setLoading(false);
    }, 15000); // 15 second timeout

    fetchPosts()
      .then((data) => {
        clearTimeout(timeoutId);
        console.log("Posts loaded successfully:", data);
        setPosts(data);
        setLoading(false);
        setError(null); // Clear any previous errors
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
          console.error("Request timeout");
          setError("Connection timeout - server may be down");
        } else {
          console.error("Failed to fetch posts:", err);
          setError("Failed to load posts");
        }
        setLoading(false);
      });

    // Set up EventSource for real-time updates
    try {
      console.log("Attempting to connect to SSE...");
      const es = createEventSource();

      es.onopen = () => {
        console.log("SSE connection opened");
        setSseConnected(true);
        setError(null); // Clear connection errors on successful connect
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
        // Only set error on first connection failure, not during reconnection attempts
        if (sseConnected) {
          setError("Connection lost - will retry automatically");
        }
        setSseConnected(false);
        // Don't close the connection, let it retry automatically
      };

      return () => {
        console.log("Cleaning up SSE connection");
        clearTimeout(timeoutId);
        es.close();
      };
    } catch (err) {
      console.error("Failed to create EventSource:", err);
      setError("Failed to establish connection");
      setLoading(false);
      clearTimeout(timeoutId);
    }
  }, []);

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="animate-spin h-6 w-6 border-2 border-black border-t-transparent rounded-full"></div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center p-8 max-w-sm">
          <h2 className="text-lg font-medium mb-2">Connection Issue</h2>
          <p className="text-sm text-zinc-500 mb-6">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-sm font-medium underline underline-offset-4 hover:text-zinc-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show empty state
  if (posts.length === 0) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-lg font-medium text-zinc-400">Board Empty</h2>
        </div>
      </div>
    );
  }

  // Show posts
  return (
    <div className="min-h-screen bg-white">
      <div className="masonry p-6">
        {posts.map((post) => <PostCard key={post.hash} post={post} />)}
      </div>
    </div>
  );
}
