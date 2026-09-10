import { memo } from "react";
import { formatDateTime, TRIGGER_LABELS, type IngestRun } from "../api";

interface Props {
  run: IngestRun | null;
  vehicles: number;
  dealers: number;
}

/** The last ingest run, read like a dashboard indicator cluster.
 *  Without this the page is a car list and the integration itself is invisible. */
function RunPanelImpl({ run, vehicles, dealers }: Props) {
  if (!run) {
    return (
      <section className="run" aria-label="Последняя загрузка">
        <div className="run__head">
          <div>
            <p className="eyebrow">Последняя загрузка</p>
            <p className="run__source">Загрузок ещё не было</p>
          </div>
          <div className="lamps">
            <span className="lamp lamp--idle">
              <span className="lamp__label">Ожидание выгрузки</span>
            </span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="run" aria-label="Последняя загрузка">
      <div className="run__head">
        <div>
          <p className="eyebrow">
            Последняя загрузка · {TRIGGER_LABELS[run.trigger] ?? run.trigger}
          </p>
          <p className="run__source">{run.source_file ?? "каталог выгрузок"}</p>
          <p className="run__when">
            {formatDateTime(run.started_at)} · {run.rows_total} строк за {run.duration_ms} мс
            {" · "}в базе {vehicles} авто из {dealers} салонов
          </p>
        </div>

        <div className="lamps">
          <span className="lamp lamp--created">
            <b className="lamp__value">{run.created}</b>
            <span className="lamp__label">добавлено</span>
          </span>
          <span className="lamp lamp--updated">
            <b className="lamp__value">{run.updated}</b>
            <span className="lamp__label">обновлено</span>
          </span>
          <span className={run.skipped > 0 ? "lamp lamp--skipped" : "lamp lamp--idle"}>
            <b className="lamp__value">{run.skipped}</b>
            <span className="lamp__label">отклонено</span>
          </span>
        </div>
      </div>

      {run.errors.length > 0 ? (
        <details className="run__rejects">
          <summary>Показать отклонённые строки ({run.errors.length})</summary>
          <ul className="reject-list">
            {run.errors.map((error) => (
              <li key={`${error.line}-${error.vin ?? ""}`}>
                <span className="reject-list__line">стр. {error.line}</span>
                <span>{error.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

export const RunPanel = memo(RunPanelImpl);
