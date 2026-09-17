import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Registering the worker is what lets a judge add CALIPER to a phone home
// screen and open it without browser chrome. It is strictly an enhancement:
// the worker is unavailable outside a secure context, so on a plain http LAN
// address this quietly does nothing and every screen still works. Registration
// is deferred to load so it never competes with the first paint.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // A failed registration must never surface to the user. There is nothing
      // they could do about it and nothing about the product depends on it.
    });
  });
}

