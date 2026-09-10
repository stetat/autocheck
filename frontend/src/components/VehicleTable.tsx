import { memo } from "react";
import { formatNumber, type SortField, type SortOrder, type Vehicle } from "../api";

interface Column {
  key: keyof Vehicle | "spec";
  label: string;
  sortAs?: SortField;
  numeric?: boolean;
}

const COLUMNS: Column[] = [
  { key: "vin", label: "VIN", sortAs: "vin" },
  { key: "brand", label: "Марка и модель", sortAs: "brand" },
  { key: "year", label: "Год", sortAs: "year", numeric: true },
  { key: "mileage_km", label: "Пробег, км", sortAs: "mileage_km", numeric: true },
  { key: "price_kzt", label: "Цена, ₸", sortAs: "price_kzt", numeric: true },
  { key: "spec", label: "Характеристики" },
  { key: "defects", label: "Дефекты" },
  { key: "dealer_name", label: "Салон" },
];

const SKELETON_ROWS = Array.from({ length: 8 }, (_, i) => i);

interface Props {
  vehicles: Vehicle[];
  loading: boolean;
  error: string | null;
  sort: SortField;
  order: SortOrder;
  onSort: (field: SortField) => void;
}

function VehicleTableImpl({ vehicles, loading, error, sort, order, onSort }: Props) {
  const showSkeleton = loading && vehicles.length === 0;

  return (
    <div className="tablewrap">
      <table>
        <caption className="visually-hidden">Автомобили, загруженные из выгрузок 1С</caption>
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
                  {column.label}
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
                    <span className="defects__text">{vehicle.defects ?? "без дефектов"}</span>
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
          <p className="state__title">Не удалось загрузить список</p>
          <p>{error}</p>
        </div>
      ) : null}

      {!showSkeleton && error === null && vehicles.length === 0 ? (
        <div className="state">
          <p className="state__title">Ничего не найдено</p>
          <p>Измените запрос или запустите загрузку выгрузки 1С.</p>
        </div>
      ) : null}
    </div>
  );
}

export const VehicleTable = memo(VehicleTableImpl);
