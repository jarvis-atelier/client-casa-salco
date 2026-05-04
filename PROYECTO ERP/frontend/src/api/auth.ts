import { apiClient } from "./client";
import type { LoginResponse, User } from "@/lib/types";

export async function login(email: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", {
    email,
    password,
  });
  return data;
}

export async function me(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}
