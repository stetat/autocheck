import { memo } from "react";
import { formatNumber, type SortField, type SortOrder, type Vehicle } from "../api";
import type { Key, Translate } from "../i18n";

interface Column {
  key: keyof Vehicle | "spec";
  label: Key;
  sortAs?: SortField;
}

const COLUMNS: Column[] = [
  { key: "vin", label: "colVin", sortAs: "vin" },
  { key: "brand", label: "colModel", sortAs: "brand" },
  { key: "year", label: "colYear", sortAs: "year" },
  { key: "mileage_km", label: "colMileage", sortAs: "mileage_km" },
  { key: "price_kzt", label: "colPrice", sortAs: "price_kzt" },
  { key: "spec", label: "colSpec" },
  { key: "defects", label: "colDefects" },
  { key: "dealer_name", label: "colDealer" },
];

const SKELETON_ROWS = Array.from({ length: 8 }, (_, i) => i);

interface Props {
  vehicles: Vehicle[];
  loading: boolean;
  error: string | null;
  sort: SortField;
  order: SortOrder;
  onSort: (field: SortField) => void;
  t: Translate;
}

function VehicleTableImpl({ vehicles, loading, error, sort, order, onSort, t }: Props) {
  const showSkeleton = loading && vehicles.length === 0;

  return (
    <div className="tablewrap">
      <table>
        <caption className="visually-hidden">{t("tableCaption")}</caption>
        <colgroup>
          <col className="col-vin" />
          <col className="col-model" />
          <col className="col-year" />
          <col className="col-km" />
          <col className="col-price" />
          <col className="col-spec" />
          <col className="col-defect" />
          <col className="col-dealer" />
        </colgroup>
        <thead>
          <tr>
            {COLUMNS.map((column) => {
              const sortable = column.sortAs !== undefined;
              const active = column.sortAs === sort;
              return (
                <th
                  key={column.key}
                  className={[sortable ? "is-sortable" : "", active ? "is-sorted" : ""]
                    .filter(Boolean)
                    .join(" ")}
                  aria-sort={active ? (order === "asc" ? "ascending" : "descending") : undefined}
                  tabIndex={sortable ? 0 : undefined}
                  role={sortable ? "button" : undefined}
                  onClick={sortable ? () => onSort(column.sortAs!) : undefined}
                  onKeyDown={
                    sortable
                      ? (event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onSort(column.sortAs!);
                          }
                        }
                      : undefined
                  }
                >
                  {t(column.label)}
                  {active ? <span className="sortmark">{order === "asc" ? "▲" : "▼"}</span> : null}
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {showSkeleton
            ? SKELETON_ROWS.map((row) => (
                <tr key={row} className="skeleton-row">
                  {COLUMNS.map((column) => (
                    <td key={column.key}>
                      <div className="skeleton" />
                    </td>
                  ))}
                </tr>
              ))
            : vehicles.map((vehicle) => (
                <tr key={vehicle.id}>
                  <td>
                    <span className="vin">{vehicle.vin}</span>
                  </td>
                  <td className="model">
                    {vehicle.brand} {vehicle.model}
                    <span>
                      {[vehicle.body_type, vehicle.color].filter(Boolean).join(" · ") || "—"}
                    </span>
                  </td>
                  <td className="num">{vehicle.year}</td>
                  <td className="num">{formatNumber(vehicle.mileage_km)}</td>
                  <td className="num">{formatNumber(vehicle.price_kzt)}</td>
                  <td>
                    {[
                      vehicle.engine_volume_l ? `${vehicle.engine_volume_l} л` : null,
                      vehicle.transmission,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                  <td
                    className={vehicle.defects ? "defects" : "defects defects--none"}
                    title={vehicle.defects ?? undefined}
                  >
                    <span className="defects__text">{vehicle.defects ?? t("noDefects")}</span>
                  </td>
                  <td className="dealer">
                    {vehicle.dealer_name}
                    {vehicle.dealer_city ? `, ${vehicle.dealer_city}` : ""}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>

      {!showSkeleton && error !== null ? (
        <div className="state state--error">
          <p className="state__title">{t("loadFailed")}</p>
          <p>{error}</p>
        </div>
      ) : null}

      {!showSkeleton && error === null && vehicles.length === 0 ? (
        <div className="state">
          <p className="state__title">{t("emptyTitle")}</p>
          <p>{t("emptyHint")}</p>
        </div>
      ) : null}
    </div>
  );
}

export const VehicleTable = memo(VehicleTableImpl);
