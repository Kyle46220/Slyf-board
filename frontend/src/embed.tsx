import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Routes, Route, Link } from "react-router-dom";
import { Board } from "./components/Board";
import { SinglePost } from "./components/SinglePost";
import { BoardContext } from "./BoardContext";
import boardStyles from "./index.css?inline";
import embedStyles from "./embed.css?inline";

// A classic script can locate its own insertion point, even with async/defer.
const script = document.currentScript as HTMLScriptElement | null;
if (script?.src) {
  if (!customElements.get("slyf-board")) {
    customElements.define(
      "slyf-board",
      class extends HTMLElement {
        private root?: Root;
        connectedCallback() {
          if (this.root) return;
          const shadow = this.shadowRoot ?? this.attachShadow({ mode: "open" });
          const style = document.createElement("style");
          style.textContent = boardStyles + "\n" + embedStyles;
          const container = document.createElement("div");
          container.className = "slyf-embed";
          shadow.replaceChildren(style, container);
          this.root = createRoot(container);
          this.root.render(
            <BoardContext.Provider
              value={{ origin: this.dataset.boardOrigin!, embedded: true }}
            >
              <MemoryRouter
                future={{
                  v7_startTransition: true,
                  v7_relativeSplatPath: true,
                }}
              >
                <Routes>
                  <Route path="/" element={<Board />} />
                  <Route
                    path="/post/:hash"
                    element={
                      <>
                        <Link to="/" className="embed-back">
                          ← Back to board
                        </Link>
                        <SinglePost />
                      </>
                    }
                  />
                </Routes>
              </MemoryRouter>
            </BoardContext.Provider>,
          );
        }
        disconnectedCallback() {
          this.root?.unmount();
          this.root = undefined;
        }
      },
    );
  }
  const host = document.createElement("slyf-board");
  // Set config before connecting the element. No host-page API or credentials.
  host.dataset.boardOrigin = new URL(script.src).origin;
  script.insertAdjacentElement("afterend", host);
}
