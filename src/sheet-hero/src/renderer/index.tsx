import "@/renderer/index.css";
import App from "@/renderer/app/App";
import { createRoot } from "react-dom/client";
import { StrictMode } from "react";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
