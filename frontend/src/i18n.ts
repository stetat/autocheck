/** Two-language UI: Russian and Kazakh.
 *
 *  Deliberately dependency-free — the string count is small and a runtime i18n
 *  library would cost more bundle than it saves. `t()` is typed against the
 *  Russian dictionary, so a key missing from Kazakh is a build error rather
 *  than a silent fallback in front of a user.
 */

export type Lang = "ru" | "kk";

export const LANGS: { code: Lang; label: string; locale: string }[] = [
  { code: "ru", label: "Рус", locale: "ru-RU" },
  { code: "kk", label: "Қаз", locale: "kk-KZ" },
];

const ru = {
  docTitle: "Autocheck — интеграция 1С",
  eyebrow: "Autocheck.kz · интеграция с 1С автосалонов",
  title: "Загруженные автомобили",
  updatedAt: "обновлено {when}",
  noData: "нет данных",

  lastRun: "Последняя загрузка",
  neverRun: "Загрузок ещё не было",
  awaitingFeed: "Ожидание выгрузки",
  feedDirectory: "каталог выгрузок",
  runSummary: "{rows} строк за {ms} мс · в базе {vehicles} авто из {dealers} салонов",

  created: "добавлено",
  updated: "обновлено",
  skipped: "отклонено",

  showRejected: "Показать отклонённые строки ({count})",
  line: "стр. {line}",

  searchPlaceholder: "VIN, марка или модель",
  searchLabel: "Поиск по VIN, марке или модели",
  allBrands: "Все марки",
  brandLabel: "Марка",
  ingestNow: "Загрузить сейчас",
  ingesting: "Загружаем…",
  uploadFile: "Загрузить файл",

  colVin: "VIN",
  colModel: "Марка и модель",
  colYear: "Год",
  colMileage: "Пробег, км",
  colPrice: "Цена, ₸",
  colSpec: "Характеристики",
  colDefects: "Дефекты",
  colDealer: "Салон",

  noDefects: "без дефектов",
  tableCaption: "Автомобили, загруженные из выгрузок 1С",

  loadFailed: "Не удалось загрузить список",
  emptyTitle: "Ничего не найдено",
  emptyHint: "Измените запрос или запустите загрузку выгрузки 1С.",
  unknownError: "Неизвестная ошибка",
  ingestFailed: "Загрузка не удалась",
  ingestDone: "Готово: добавлено {created}, обновлено {updated}, отклонено {skipped}",

  countRange: "{from}–{to} из {total}",
  countEmpty: "0 записей",
  pageOf: " · страница {page} из {pages}",
  prev: "Назад",
  next: "Вперёд",

  triggerScheduled: "по расписанию",
  triggerWebhook: "вручную",
  triggerUpload: "загрузка файла",

  languageLabel: "Язык интерфейса",

  // Rejection reasons, keyed by the backend's error codes.
  err_vin_empty: "поле «VIN» пустое",
  err_vin_length: "VIN должен быть 17 символов, получено {actual}: {value}",
  err_vin_charset: "VIN содержит недопустимые символы: {value}",
  err_field_empty: "обязательное поле «{field}» пустое",
  err_field_not_number: "поле «{field}» не число: {value}",
  err_year_out_of_range: "год выпуска вне допустимого диапазона: {year}",
  err_file_empty: "файл пуст",
  err_missing_columns: "в файле нет обязательных колонок: {columns}",
  err_unhandled: "необработанная ошибка: {error}",
} as const;

export type Key = keyof typeof ru;

/** Typed as Record<Key, string>, so omitting a key fails the build. */
const kk: Record<Key, string> = {
  docTitle: "Autocheck — 1С интеграциясы",
  eyebrow: "Autocheck.kz · автосалондардың 1С интеграциясы",
  title: "Жүктелген автомобильдер",
  updatedAt: "жаңартылды {when}",
  noData: "дерек жоқ",

  lastRun: "Соңғы жүктеу",
  neverRun: "Жүктеу әлі болған жоқ",
  awaitingFeed: "Түсірілім күтілуде",
  feedDirectory: "түсірілім қалтасы",
  runSummary: "{rows} жол {ms} мс ішінде · базада {dealers} салоннан {vehicles} көлік",

  created: "қосылды",
  updated: "жаңартылды",
  skipped: "қабылданбады",

  showRejected: "Қабылданбаған жолдарды көрсету ({count})",
  line: "{line}-жол",

  searchPlaceholder: "VIN, марка немесе үлгі",
  searchLabel: "VIN, марка немесе үлгі бойынша іздеу",
  allBrands: "Барлық маркалар",
  brandLabel: "Марка",
  ingestNow: "Қазір жүктеу",
  ingesting: "Жүктелуде…",
  uploadFile: "Файл жүктеу",

  colVin: "VIN",
  colModel: "Марка және үлгі",
  colYear: "Жылы",
  colMileage: "Жүрісі, км",
  colPrice: "Бағасы, ₸",
  colSpec: "Сипаттамалары",
  colDefects: "Ақаулары",
  colDealer: "Салон",

  noDefects: "ақауы жоқ",
  tableCaption: "1С түсірілімдерінен жүктелген автомобильдер",

  loadFailed: "Тізімді жүктеу мүмкін болмады",
  emptyTitle: "Ештеңе табылмады",
  emptyHint: "Сұранысты өзгертіңіз немесе 1С түсірілімін жүктеңіз.",
  unknownError: "Белгісіз қате",
  ingestFailed: "Жүктеу сәтсіз аяқталды",
  ingestDone: "Дайын: {created} қосылды, {updated} жаңартылды, {skipped} қабылданбады",

  countRange: "{total} ішінен {from}–{to}",
  countEmpty: "0 жазба",
  pageOf: " · {pages} беттің {page}-беті",
  prev: "Артқа",
  next: "Алға",

  triggerScheduled: "кесте бойынша",
  triggerWebhook: "қолмен",
  triggerUpload: "файл жүктеу",

  languageLabel: "Интерфейс тілі",

  err_vin_empty: "«VIN» өрісі бос",
  err_vin_length: "VIN 17 таңбадан тұруы керек, келгені {actual}: {value}",
  err_vin_charset: "VIN-де жарамсыз таңбалар бар: {value}",
  err_field_empty: "«{field}» міндетті өрісі бос",
  err_field_not_number: "«{field}» өрісі сан емес: {value}",
  err_year_out_of_range: "шығарылған жылы рұқсат етілген аралықтан тыс: {year}",
  err_file_empty: "файл бос",
  err_missing_columns: "файлда міндетті бағандар жоқ: {columns}",
  err_unhandled: "өңделмеген қате: {error}",
};

const DICTIONARIES: Record<Lang, Record<Key, string>> = { ru, kk };

const STORAGE_KEY = "autocheck.lang";

export function readStoredLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "ru" || stored === "kk") return stored;
    // Fall back to the browser's preference before defaulting.
    if (navigator.language?.toLowerCase().startsWith("kk")) return "kk";
  } catch {
    // Private browsing and blocked site data both throw on access.
  }
  return "ru";
}

export function storeLang(lang: Lang): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Persisting the choice is a convenience, never a requirement.
  }
}

export type Translate = (key: Key, params?: Record<string, string | number>) => string;

export function translator(lang: Lang): Translate {
  const dictionary = DICTIONARIES[lang];
  return (key, params) => {
    const template = dictionary[key];
    if (!params) return template;
    return template.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in params ? String(params[name]) : match,
    );
  };
}

/** Renders a backend rejection in the reader's language, falling back to the
 *  server's Russian prose if the code is one this build does not know. */
export function translateRejection(
  t: Translate,
  lang: Lang,
  error: { code: string; params: Record<string, string>; reason: string },
): string {
  const key = `err_${error.code}` as Key;
  if (!(key in DICTIONARIES[lang])) return error.reason;
  return t(key, error.params);
}

export const localeOf = (lang: Lang): string =>
  LANGS.find((entry) => entry.code === lang)?.locale ?? "ru-RU";
