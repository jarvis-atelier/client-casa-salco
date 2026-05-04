import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface ItemDraft {
  descripcion: string;
  cantidad: string;
  unidad: string;
  precio_unitario: string;
  iva_porc: string;
  articulo_id: number | null;
  crear_articulo_si_falta: boolean;
}

interface ItemsEditorProps {
  items: ItemDraft[];
  onChange: (idx: number, patch: Partial<ItemDraft>) => void;
  onRemove: (idx: number) => void;
}

const UNIDADES = ["unidad", "kg", "gr", "lt", "ml"] as const;

function calcSubtotal(it: ItemDraft): number {
  const c = parseFloat(it.cantidad || "0");
  const p = parseFloat(it.precio_unitario || "0");
  const iva = parseFloat(it.iva_porc || "0");
  if (!Number.isFinite(c) || !Number.isFinite(p)) return 0;
  return c * p * (1 + iva / 100);
}

export function ItemsEditor({ items, onChange, onRemove }: ItemsEditorProps) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[36%]">Descripción</TableHead>
            <TableHead className="w-[10%]">Cantidad</TableHead>
            <TableHead className="w-[10%]">Unidad</TableHead>
            <TableHead className="w-[14%]">Precio</TableHead>
            <TableHead className="w-[8%]">IVA %</TableHead>
            <TableHead className="w-[14%] text-right">Total línea</TableHead>
            <TableHead className="w-[8%]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={7}
                className="text-center text-sm text-muted-foreground py-8"
              >
                Sin ítems. Agregá al menos uno.
              </TableCell>
            </TableRow>
          )}
          {items.map((it, idx) => (
            <TableRow key={idx}>
              <TableCell>
                <Input
                  value={it.descripcion}
                  onChange={(e) =>
                    onChange(idx, { descripcion: e.target.value })
                  }
                  className="h-9"
                />
                {it.articulo_id ? (
                  <div className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-1">
                    Matcheado con artículo #{it.articulo_id}
                  </div>
                ) : (
                  <div className="text-[10px] text-amber-600 dark:text-amber-400 mt-1">
                    Se creará nuevo artículo al confirmar
                  </div>
                )}
              </TableCell>
              <TableCell>
                <Input
                  value={it.cantidad}
                  onChange={(e) => onChange(idx, { cantidad: e.target.value })}
                  className="h-9"
                  inputMode="decimal"
                />
              </TableCell>
              <TableCell>
                <select
                  value={it.unidad}
                  onChange={(e) => onChange(idx, { unidad: e.target.value })}
                  className="h-9 w-full rounded-[8px] border border-input bg-background px-2 text-sm"
                >
                  {UNIDADES.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </TableCell>
              <TableCell>
                <Input
                  value={it.precio_unitario}
                  onChange={(e) =>
                    onChange(idx, { precio_unitario: e.target.value })
                  }
                  className="h-9"
                  inputMode="decimal"
                />
              </TableCell>
              <TableCell>
                <Input
                  value={it.iva_porc}
                  onChange={(e) => onChange(idx, { iva_porc: e.target.value })}
                  className="h-9"
                  inputMode="decimal"
                />
              </TableCell>
              <TableCell className="text-right text-sm font-medium tabular-nums">
                {calcSubtotal(it).toLocaleString("es-AR", {
                  style: "currency",
                  currency: "ARS",
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </TableCell>
              <TableCell>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  onClick={() => onRemove(idx)}
                  aria-label="Quitar ítem"
                >
                  <Trash2 className="h-4 w-4" strokeWidth={1.5} />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
