import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { Board } from "./components/Board";
import { SinglePost } from "./components/SinglePost";

function LegacyPostLink() {
  const { pathname, hash } = useLocation();
  const legacy = hash.match(/^#\/post\/([a-f0-9]{64})$/);
  return pathname === "/" && legacy ? (
    <Navigate to={`/post/${legacy[1]}`} replace />
  ) : null;
}

export default function App() {
  return (
    <BrowserRouter>
      <LegacyPostLink />
      <div className="min-h-screen bg-zinc-950">
        <Routes>
          <Route path="/" element={<Board />} />
          <Route path="/post/:hash" element={<SinglePost />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
