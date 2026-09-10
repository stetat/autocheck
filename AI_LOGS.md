# AI_LOGS.md — лог работы с ИИ-агентом

Проект выполнен в парадигме вайбкодинга: код пишет Claude Code (Opus 5),
человек выступает архитектором и постановщиком задач.

Формат записи: что было поставлено → что сделал ИИ → что пошло не так и как чинили.

---

## 0. Постановка и контроль до кода

**Промпт:**
> Hey, we're doing a test task, description is in TASK.md in root, git repo is
> already connected. Go over task file, present a plan to me. Tech stack is
> fastapi/react. As you present a brief plan to me, write a system prompt to
> follow further, install necessary skills for high quality completion.

**Что сделал ИИ:**
1. Разобрал TASK.md, выделил 6 обязательных пунктов + бонус (upsert по VIN).
2. Нашёл и установил 4 профильных скилла из реестра skills.sh, отфильтровав по
   репутации источника и числу установок: `fastapi/fastapi@fastapi` (официальный),
   `vercel-labs@vercel-react-best-practices` (701K), `github/awesome-copilot@multi-stage-dockerfile`,
   `github/awesome-copilot@pytest-coverage`.
3. Написал `CLAUDE.md` — системный промпт проекта: зафиксированный стек,
   архитектурные правила, явный список out-of-scope, протокол ведения этого лога.
4. Предложил план из 6 фаз.

**Проблемы и правки:**
- `npx skills add -g` упал с `PromptScript does not support global skill installation`.
  Переустановили на уровень проекта — в итоге даже лучше: скиллы поедут вместе с репозиторием.
- **Правка от человека:** в плане прозвучало «парсер без доступа к БД», что
  противоречило формулировке ТЗ («сервис загружает файл, парсит и сохраняет в БД»).
  Уточнено: правило касается слоёв, а не отсутствия БД. Запись в SQLite делает
  `services/ingest.py`; чистый парсер — это middle step, вынесенный ради
  юнит-тестируемости (тест парсера не требует БД, тест upsert не требует файла).
- **Правка от ИИ:** официальный скилл FastAPI рекомендует SQLModel вместо чистого
  SQLAlchemy. Стек в `CLAUDE.md` обновлён до SQLModel.

---

## 1. Фаза 0 — каркас и Docker

**Промпт:**
> now start implementing the plan. report to me after each phase, with things to
> check. be concise

**Что сделал ИИ:**
- Backend: `pyproject.toml`, `config.py` (все настройки через env, префикс
  `AUTOCHECK_`), `db.py` (engine + `init_db`), `models.py` (`Vehicle` с
  `UNIQUE` по `vin`, `IngestRun` для аудита), `main.py` с `/api/health`.
- Frontend: Vite + React + TS, dev-прокси `/api` → backend.
- Docker: два multi-stage Dockerfile (venv-билдер → slim-рантайм под non-root
  пользователем; node-билдер → nginx), `docker-compose.yml`, healthcheck'и,
  `.dockerignore`.

**Проверено (не «на глаз»):**
- `TestClient` → `/api/health` = 200 `{"status":"ok"}`.
- `sqlite3 .schema vehicles` → присутствует `CREATE UNIQUE INDEX ix_vehicles_vin`.
  Это фундамент бонусного upsert: уникальность обеспечивает БД, а не память приложения.
- `npm run build` → бандл собран без ошибок TypeScript.
- Живой сквозной запрос: `curl localhost:5173/api/health` через Vite-прокси вернул
  ответ бэкенда.
- `docker compose config` → валиден.

**Проблемы:**
- Docker daemon на машине не запущен, поэтому образы пока не собирались —
  проверка `docker compose up` отложена до фазы 5.
