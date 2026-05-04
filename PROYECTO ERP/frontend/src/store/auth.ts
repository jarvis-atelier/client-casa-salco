import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isHydrated: boolean;
  setTokens: (access: string, refresh?: string) => void;
  setUser: (user: User | null) => void;
  login: (tokens: { access_token: string; refresh_token: string; user: User }) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isHydrated: false,
      setTokens: (access, refresh) =>
        set((s) => ({
          accessToken: access,
          refreshToken: refresh ?? s.refreshToken,
        })),
      setUser: (user) => set({ user }),
      login: ({ access_token, refresh_token, user }) =>
        set({
          accessToken: access_token,
          refreshToken: refresh_token,
          user,
        }),
      logout: () =>
        set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: "castulo.auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) state.isHydrated = true;
      },
    },
  ),
);

export function getAccessToken(): string | null {
  return useAuth.getState().accessToken;
}

export function getRefreshToken(): string | null {
  return useAuth.getState().refreshToken;
}
