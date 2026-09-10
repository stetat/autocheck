/** Types mirror app/schemas.py. Kept hand-written and small rather than
 *  generated: the surface is five endpoints. */

export type SortField = "last_seen_at" | "price_kzt" | "mileage_km" | "year" | "brand" | "vin";
export type SortOrder = "asc" | "desc";

export interface Vehicle {
  id: number;
  vin: string;
  brand: string;
  model: string;
  year: number;
  mileage_km: number;
  price_kzt: number;
  color: string | null;
  body_type: string | null;
  transmission: string | null;
  engine_volume_l: number | null;
  defects: string | null;
  dealer_name: string;
  dealer_city: string | null;
  exported_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface VehiclePage {
  items: Vehicle[];
  total: number;
  limit: number;
  offset: number;
}

export interface RowError {
  line: number;
  vin: string | null;
  /** Machine-readable rejection code; the UI localises it. */
  code: string;
  params: Record<string, string>;
  /** Russian rendering from the server, used as a fallback. */
  reason: string;
}

export interface IngestRun {
  id: number | null;
  trigger: string;
  source_file: string | null;
  rows_total: number;
  created: number;
  updated: number;
  skipped: number;
  errors: RowError[];
  duration_ms: number;
  started_at: string;
  ok: boolean;
}

export interface Stats {
  vehicles: number;
  dealers: number;
  brands: number;
  last_run: IngestRun | null;
}

export interface VehicleQuery {
  search: string;
  brand: string;
  sort: SortField;
  order: SortOrder;
  limit: number;
  offset: number;
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export function fetchVehicles(query: VehicleQuery, signal?: AbortSignal): Promise<VehiclePage> {
  const params = new URLSearchParams({
    sort: query.sort,
    order: query.order,
    limit: String(query.limit),
    offset: String(query.offset),
  });
  if (query.search) params.set("search", query.search);
  if (query.brand) params.set("brand", query.brand);
  return get<VehiclePage>(`/api/vehicles?${params}`, signal);
}

export const fetchStats = (signal?: AbortSignal) => get<Stats>("/api/stats", signal);
export const fetchBrands = (signal?: AbortSignal) => get<string[]>("/api/brands", signal);

/** Forced trigger. With a file it ingests that upload; without one it sweeps
 *  the watched directory, which skips feeds it has already processed. */
export async function triggerIngest(file?: File): Promise<IngestRun> {
  const body = new FormData();
  if (file) body.append("file", file);

  const response = await fetch(file ? "/api/ingest" : "/api/ingest?force=true", {
    method: "POST",
    body: file ? body : undefined,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Загрузка не удалась (${response.status})`);
  }
  return response.json() as Promise<IngestRun>;
}

// --- formatting -------------------------------------------------------------
// Numbers and dates are pinned to one convention regardless of UI language.
// Chrome's "kk" data groups thousands with commas (1,300,000) and writes dates
// as 2026-09-10; Kazakhstan uses space grouping and DD.MM.YYYY in Kazakh just
// as in Russian. A price also should not change shape because the reader
// switched interface language. Hoisted to module level: building Intl objects
// per render is costly.

const DATA_LOCALE = "ru-RU";

const NUMBER = new Intl.NumberFormat(DATA_LOCALE, { maximumFractionDigits: 0 });
const DATE_TIME = new Intl.DateTimeFormat(DATA_LOCALE, {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});

export const formatNumber = (value: number) => NUMBER.format(value);

/** Backend timestamps are UTC but naive (no trailing Z), so they must be
 *  marked as UTC explicitly or the browser reads them as local time. */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const normalised = /[Z+]|-\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(normalised);
  return Number.isNaN(date.getTime()) ? "—" : DATE_TIME.format(date);
}
