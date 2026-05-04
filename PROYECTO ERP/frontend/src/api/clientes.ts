import { apiClient } from "./client";
import type { Cliente, CondicionIva, MovimientoCaja, Paginated } from "@/lib/types";

export interface ClientesQuery {
  q?: string;
  page?: number;
  per_page?: number;
}

export interface ClientePayload {
  codigo: string;
  razon_social: string;
  cuit?: string | null;
  condicion_iva?: CondicionIva;
  condicion_iva_receptor_id?: number | null;
  telefono?: string | null;
  email?: string | null;
  direccion?: string | null;
  cuenta_corriente?: boolean;
  limite_cuenta_corriente?: string | number;
  activo?: boolean;
}

export type ClienteUpdatePayload = Partial<ClientePayload>;

export async function listClientes(
  params: ClientesQuery = {},
): Promise<Paginated<Cliente>> {
  const { data } = await apiClient.get<Paginated<Cliente>>("/clientes", {
    params,
  });
  return data;
}

export async function getCliente(id: number): Promise<Cliente> {
  const { data } = await apiClient.get<Cliente>(`/clientes/${id}`);
  return data;
}

export async function createCliente(payload: ClientePayload): Promise<Cliente> {
  const { data } = await apiClient.post<Cliente>("/clientes", payload);
  return data;
}

export async function updateCliente(
  id: number,
  payload: ClienteUpdatePayload,
): Promise<Cliente> {
  const { data } = await apiClient.patch<Cliente>(`/clientes/${id}`, payload);
  return data;
}

export async function deactivateCliente(id: number): Promise<void> {
  await apiClient.delete(`/clientes/${id}`);
}

/**
 * Movimientos del ledger universal. El backend filtra por sucursal/tipo/fecha.
 * Para acotar a un cliente, filtramos client-side por `cliente_id`.
 */
export async function listMovimientosCliente(
  clienteId: number,
  perPage = 100,
): Promise<MovimientoCaja[]> {
  const { data } = await apiClient.get<Paginated<MovimientoCaja>>(
    "/movimientos",
    { params: { per_page: perPage } },
  );
  return (data.items ?? []).filter((m) => m.cliente_id === clienteId);
}
