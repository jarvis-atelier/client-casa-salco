import { io, Socket } from "socket.io-client";
import { getAccessToken } from "@/store/auth";

/**
 * Cliente Socket.IO singleton para el namespace `/prices`.
 *
 * El handshake manda el JWT como `auth.token`. El backend valida con
 * `flask_jwt_extended.decode_token` y rechaza si falla.
 *
 * Estrategia de reconexión por defecto de socket.io (infinite retry con
 * backoff exponencial). Si el token caducó, el servidor rechazará el
 * handshake y seguirá reintentando — en ese caso conviene llamar a
 * `reconnectPricesSocket()` después de refrescar el token.
 */
let socket: Socket | null = null;

export function connectPricesSocket(): Socket | null {
  const token = getAccessToken();
  if (!token) return null;
  if (socket && socket.connected) return socket;
  if (socket) {
    // instancia existente pero desconectada: actualizamos auth y reconectamos
    // (el namespace reutiliza el mismo manager Engine.IO)
    socket.auth = { token };
    socket.connect();
    return socket;
  }

  socket = io("/prices", {
    auth: { token },
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1_000,
    reconnectionDelayMax: 5_000,
  });

  return socket;
}

export function disconnectPricesSocket(): void {
  if (socket) {
    socket.removeAllListeners();
    socket.disconnect();
    socket = null;
  }
}

export function reconnectPricesSocket(): Socket | null {
  disconnectPricesSocket();
  return connectPricesSocket();
}

export function getPricesSocket(): Socket | null {
  return socket;
}
