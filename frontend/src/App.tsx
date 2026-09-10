import { useCallback, useDeferredValue, useEffect, useRef, useState } from "react";
import {
  fetchBrands,
  fetchStats,
  fetchVehicles,
  formatDateTime,
  triggerIngest,
  type SortField,
  type SortOrder,
  type Stats,
  type Vehicle,
} from "./api";
import { RunPanel } from "./components/RunPanel";
import { VehicleTable } from "./components/VehicleTable";

const PAGE_SIZE = 25;

/** How often to re-read stats. The scheduled trigger is the half of the
 *  requirement a user cannot see; polling is what makes it observable. */
const POLL_MS = 10_000;

type Toast = { text: string; kind: "ok" | "error" } | null;

export default function App() {
  const [search, setSearch] = useState("");
  const [brand, setBrand] = useState("");
  const [sort, setSort] = useState<SortField>("last_seen_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [offset, setOffset] = useState(0);

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [total, setTotal] = useState(0);
  const [brands, setBrands] = useState<string[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // Deferred so typing stays responsive while the table re-renders behind it.
  const deferredSearch = useDeferredValue(search);
  const fileInput = useRef<HTMLInputElement>(null);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  // --- vehicles -------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    fetchVehicles(
      { search: deferredSearch, brand, sort, order, limit: PAGE_SIZE, offset },
      controller.signal,
    )
      .then((page) => {
        setVehicles(page.items);
        setTotal(page.total);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Неизвестная ошибка");
        setVehicles([]);
        setTotal(0);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [deferredSearch, brand, sort, order, offset, reloadKey]);

  // --- stats, polled so a scheduled ingest shows up on its own ---------------
  useEffect(() => {
    const controller = new AbortController();

    const read = () => {
      fetchStats(controller.signal)
        .then(setStats)
        .catch(() => undefined); // a failed poll is not worth surfacing
    };

    read();
    const timer = window.setInterval(read, POLL_MS);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [reloadKey]);

  // --- brand list -----------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();
    fetchBrands(controller.signal)
      .then(setBrands)
      .catch(() => undefined);
    return () => controller.abort();
  }, [reloadKey]);

  // --- toast auto-dismiss ---------------------------------------------------
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const runIngest = useCallback(
    async (file?: File) => {
      setBusy(true);
      try {
        const run = await triggerIngest(file);
        setToast({
          kind: "ok",
          text: `Готово: добавлено ${run.created}, обновлено ${run.updated}, отклонено ${run.skipped}`,
        });
        setOffset(0);
        reload();
      } catch (cause) {
        setToast({
          kind: "error",
          text: cause instanceof Error ? cause.message : "Загрузка не удалась",
        });
      } finally {
        setBusy(false);
      }
    },
    [reload],
  );

  const handleSort = useCallback((field: SortField) => {
    setOffset(0);
    setSort((current) => {
      if (current === field) {
        setOrder((direction) => (direction === "asc" ? "desc" : "asc"));
        return current;
      }
      setOrder(field === "brand" || field === "vin" ? "asc" : "desc");
      return field;
    });
  }, []);

  const lastRunAt = stats?.last_run?.started_at ?? null;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">Autocheck.kz · интеграция с 1С автосалонов</p>
          <h1 className="masthead__title">Загруженные автомобили</h1>
        </div>
        <p className="masthead__meta">
          <span className={lastRunAt ? "pulse" : "pulse pulse--stale"} aria-hidden="true" />
          {lastRunAt ? `обновлено ${formatDateTime(lastRunAt)}` : "нет данных"}
        </p>
      </header>

      <RunPanel
        run={stats?.last_run ?? null}
        vehicles={stats?.vehicles ?? 0}
        dealers={stats?.dealers ?? 0}
      />

      <div className="controls">
        <label className="field field--search">
          <span className="field__icon" aria-hidden="true">⌕</span>
          <span className="visually-hidden">Поиск по VIN, марке или модели</span>
          <input
            type="search"
            placeholder="VIN, марка или модель"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </label>

        <label className="field">
          <span className="visually-hidden">Марка</span>
          <select
            value={brand}
            onChange={(event) => {
              setBrand(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Все марки</option>
            {brands.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <button className="btn" onClick={() => void runIngest()} disabled={busy}>
          {busy ? "Загружаем…" : "Загрузить сейчас"}
        </button>

        <button
          className="btn btn--ghost"
          onClick={() => fileInput.current?.click()}
          disabled={busy}
        >
          Загрузить файл
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".csv"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void runIngest(file);
            event.target.value = "";
          }}
        />
      </div>

      <VehicleTable
        vehicles={vehicles}
        loading={loading}
        error={error}
        sort={sort}
        order={order}
        onSort={handleSort}
      />

      <div className="pager">
        <p className="pager__count">
          {total === 0 ? "0 записей" : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} из ${total}`}
          {pages > 1 ? ` · страница ${page} из ${pages}` : ""}
        </p>
        <div className="pager__buttons">
          <button
            className="btn btn--ghost"
            onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
            disabled={offset === 0}
          >
            Назад
          </button>
          <button
            className="btn btn--ghost"
            onClick={() => setOffset((value) => value + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
          >
            Вперёд
          </button>
        </div>
      </div>

      {toast ? (
        <div className={toast.kind === "error" ? "toast toast--error" : "toast"} role="status">
          {toast.text}
        </div>
      ) : null}
    </div>
  );
}
