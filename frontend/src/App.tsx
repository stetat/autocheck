import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
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
import {
  LANGS,
  readStoredLang,
  storeLang,
  translator,
  type Lang,
} from "./i18n";

const PAGE_SIZE = 25;

/** How often to re-read stats. The scheduled trigger is the half of the
 *  requirement a user cannot see; polling is what makes it observable. */
const POLL_MS = 10_000;

type Toast = { text: string; kind: "ok" | "error" } | null;

export default function App() {
  // Lazy initialiser: reading localStorage on every render would be wasteful,
  // and the read can throw when site data is blocked.
  const [lang, setLang] = useState<Lang>(readStoredLang);
  const t = useMemo(() => translator(lang), [lang]);

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
        setError(cause instanceof Error ? cause.message : "unknown");
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

  // Keep the document language in step so screen readers and hyphenation
  // follow the chosen language.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = t("docTitle");
    storeLang(lang);
  }, [lang, t]);

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
          text: t("ingestDone", {
            created: run.created,
            updated: run.updated,
            skipped: run.skipped,
          }),
        });
        setOffset(0);
        reload();
      } catch (cause) {
        setToast({
          kind: "error",
          text: cause instanceof Error ? cause.message : t("ingestFailed"),
        });
      } finally {
        setBusy(false);
      }
    },
    [reload, t],
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
          <p className="eyebrow">{t("eyebrow")}</p>
          <h1 className="masthead__title">{t("title")}</h1>
        </div>

        <div className="masthead__side">
          <div className="langswitch" role="group" aria-label={t("languageLabel")}>
            {LANGS.map((entry) => (
              <button
                key={entry.code}
                type="button"
                className={entry.code === lang ? "langswitch__btn is-active" : "langswitch__btn"}
                aria-pressed={entry.code === lang}
                lang={entry.code}
                onClick={() => setLang(entry.code)}
              >
                {entry.label}
              </button>
            ))}
          </div>
          <p className="masthead__meta">
            <span className={lastRunAt ? "pulse" : "pulse pulse--stale"} aria-hidden="true" />
            {lastRunAt
              ? t("updatedAt", { when: formatDateTime(lastRunAt) })
              : t("noData")}
          </p>
        </div>
      </header>

      <RunPanel
        run={stats?.last_run ?? null}
        vehicles={stats?.vehicles ?? 0}
        dealers={stats?.dealers ?? 0}
        t={t}
        lang={lang}
      />

      <div className="controls">
        <label className="field field--search">
          <span className="field__icon" aria-hidden="true">⌕</span>
          <span className="visually-hidden">{t("searchLabel")}</span>
          <input
            type="search"
            placeholder={t("searchPlaceholder")}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </label>

        <label className="field">
          <span className="visually-hidden">{t("brandLabel")}</span>
          <select
            value={brand}
            onChange={(event) => {
              setBrand(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("allBrands")}</option>
            {brands.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <button className="btn" onClick={() => void runIngest()} disabled={busy}>
          {busy ? t("ingesting") : t("ingestNow")}
        </button>

        <button
          className="btn btn--ghost"
          onClick={() => fileInput.current?.click()}
          disabled={busy}
        >
          {t("uploadFile")}
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
        error={error === "unknown" ? t("unknownError") : error}
        sort={sort}
        order={order}
        onSort={handleSort}
        t={t}
      />

      <div className="pager">
        <p className="pager__count">
          {total === 0
            ? t("countEmpty")
            : t("countRange", {
                from: offset + 1,
                to: Math.min(offset + PAGE_SIZE, total),
                total,
              })}
          {pages > 1 ? t("pageOf", { page, pages }) : ""}
        </p>
        <div className="pager__buttons">
          <button
            className="btn btn--ghost"
            onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
            disabled={offset === 0}
          >
            {t("prev")}
          </button>
          <button
            className="btn btn--ghost"
            onClick={() => setOffset((value) => value + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
          >
            {t("next")}
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
