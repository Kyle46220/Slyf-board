import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Error handling
window.addEventListener('error', (e) => {
  console.error('Global error:', e.error);
  document.body.innerHTML = `<div style="color: white; padding: 20px; font-family: monospace;">
    <h2>Application Error</h2>
    <pre>${e.error?.message || 'Unknown error'}</pre>
  </div>`;
});

window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise rejection:', e.reason);
});

const rootElement = document.getElementById("root");
if (!rootElement) {
  console.error('Root element not found');
} else {
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
