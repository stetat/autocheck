import { memo } from "react";
import { formatDateTime, type IngestRun } from "../api";
import { translateRejection, type Key, type Lang, type Translate } from "../i18n";

interface Props {
  run: IngestRun | null;
  vehicles: number;
  dealers: number;
  t: Translate;
  lang: Lang;
}

const TRIGGER_KEYS: Record<string, Key> = {
  scheduled: "triggerScheduled",
  webhook: "triggerWebhook",
  upload: "triggerUpload",
};

/** The last ingest run, read like a dashboard indicator cluster.
 *  Without this the page is a car list and the integration itself is invisible. */
function RunPanelImpl({ run, vehicles, dealers, t, lang }: Props) {
  if (!run) {
    return (
      <section className="run" aria-label={t("lastRun")}>
        <div className="run__head">
          <div>
            <p className="eyebrow">{t("lastRun")}</p>
            <p className="run__source">{t("neverRun")}</p>
          </div>
          <div className="lamps">
            <span className="lamp lamp--idle">
              <span className="lamp__label">{t("awaitingFeed")}</span>
            </span>
          </div>
        </div>
      </section>
    );
  }

  const triggerKey = TRIGGER_KEYS[run.trigger];

  return (
    <section className="run" aria-label={t("lastRun")}>
      <div className="run__head">
        <div>
          <p className="eyebrow">
            {t("lastRun")} · {triggerKey ? t(triggerKey) : run.trigger}
          </p>
          <p className="run__source">{run.source_file ?? t("feedDirectory")}</p>
          <p className="run__when">
            {formatDateTime(run.started_at)} ·{" "}
            {t("runSummary", {
              rows: run.rows_total,
              ms: run.duration_ms,
              vehicles,
              dealers,
            })}
          </p>
        </div>

        <div className="lamps">
          <span className="lamp lamp--created">
            <b className="lamp__value">{run.created}</b>
            <span className="lamp__label">{t("created")}</span>
          </span>
          <span className="lamp lamp--updated">
            <b className="lamp__value">{run.updated}</b>
            <span className="lamp__label">{t("updated")}</span>
          </span>
          <span className={run.skipped > 0 ? "lamp lamp--skipped" : "lamp lamp--idle"}>
            <b className="lamp__value">{run.skipped}</b>
            <span className="lamp__label">{t("skipped")}</span>
          </span>
        </div>
      </div>

      {run.errors.length > 0 ? (
        <details className="run__rejects">
          <summary>{t("showRejected", { count: run.errors.length })}</summary>
          <ul className="reject-list">
            {run.errors.map((error) => (
              <li key={`${error.line}-${error.vin ?? ""}`}>
                <span className="reject-list__line">{t("line", { line: error.line })}</span>
                <span>{translateRejection(t, lang, error)}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

export const RunPanel = memo(RunPanelImpl);
