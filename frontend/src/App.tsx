import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Board } from "./components/Board";
import { SinglePost } from "./components/SinglePost";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-zinc-950">
        <Routes>
          <Route path="/" element={<Board />} />
          <Route path="/post/:hash" element={<SinglePost />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
