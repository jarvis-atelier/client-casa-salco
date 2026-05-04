import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { bootstrapTheme } from "./hooks/use-theme";
import { startSyncDaemon } from "./lib/offline/sync-daemon";
import "./styles/globals.css";

bootstrapTheme();

// Daemon que vacía la cola offline cuando vuelve la conexión.
// Idempotente: corre una vez en el lifetime de la pestaña/app.
startSyncDaemon();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
