//! Jarvis Core — Tauri 2.x desktop shell.
//!
//! Empaqueta el frontend React (Vite) en una ventana nativa Windows usando
//! WebView2. La lógica de negocio queda 100% en el frontend; este shell solo
//! provee la ventana, persistencia de estado de ventana, y acceso opcional al
//! agente local (`tauri-plugin-shell`).
//!
//! Comandos nativos: ninguno por ahora — toda la integración con backend
//! (:5000) y agente (:9123) se hace vía HTTP desde el frontend.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
