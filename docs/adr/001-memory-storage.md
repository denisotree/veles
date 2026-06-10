# ADR-001: Storage backend для проектной памяти Veles

- **Status**: Accepted
- **Date**: 2026-05-25
- **Supersedes**: —
- **Related**: `VISION.md` §4, §5.1, §9

---

## Context

VISION.md §5.1 описывает проектную память Veles как структурированный артефакт с пятью видами сущностей и связей между ними:

- лог общения (sessions / turns / tool_calls);
- правила и инсайты (с tags, источниками, decay);
- карта структуры проекта (file tree + смысловые кластеры);
- реестры tools и skills с телеметрией (use_count, success_rate, last_used);
- наследование skills и tools (skill→base_skill, tool→base_tool), references skill→tools с аргументами.

Это требует более богатой модели данных, чем текущая реализация. Сейчас в `<cwd>/.veles/memory.db` живут только 5 таблиц (sessions, turns, turns_fts, jobs, job_runs); телеметрия skills — в YAML frontmatter SKILL.md; tools телеметрии нет вообще; embeddings — в отдельном JSON-кэше `skill_embeddings.json`; recursive CTE не используется.

Шкала через 1–2 года активного использования на одного пользователя: **десятки тысяч записей**. ~50k сессий, ~5k skills+tools, ~100k инсайтов/правил, ~50k+ embeddings. На embeddings брутфорс numpy cosine при таких объёмах занимает 5–10 сек на запрос — это блокирует UX "найти похожий инсайт".

Архитектурный коридор от VISION:

- §4 — **local-first**, всё локально, embedded; cloud-зависимости только через opt-in модули.
- §4 — **минимальное ядро**; не вводить лишних зависимостей.
- §9 — **portable**, full export = bit-for-bit бандл `<cwd>/.veles/`.
- §11 — Apache-совместимые зависимости.

Возникает вопрос: достаточно ли SQLite, или нужна графовая БД / document store / hybrid?

## Decision

**Расширить текущий SQLite до полноценного embedded знания: `SQLite + JSON1 + FTS5 + sqlite-vec`.** Не вводить второй движок, не вводить графовую БД, не вводить DuckDB в core. Pure-Python numpy для embeddings — только как safety net при невозможности загрузить sqlite-vec на экзотической платформе.

Это покрывает все пять видов сущностей из §5.1 в одном файле `memory.db`, сохраняет local-first и portable, не ломает существующие 2300 тестов, и даёт явные триггеры для пересмотра.

## Что уже есть (factual baseline)

| Слой | Где живёт | Статус |
|---|---|---|
| Лог общения (sessions, turns) | `memory.db` + FTS5 | ✅ Реализовано (M0–M40) |
| Jobs / job_runs | `memory.db` | ✅ Реализовано (M75) |
| Skills телеметрия | YAML frontmatter в `SKILL.md` | ⚠️ Не в SQL — нет быстрой агрегации |
| Tools телеметрия | — (только in-memory `ToolEntry`) | ❌ Не персистентна |
| Правила и инсайты | wiki-страницы в FS (`wiki/insights/*.md`) | ⚠️ Не индексировано в SQL |
| Карта структуры проекта | — | ❌ Нет; ad-hoc walk при каждом запросе |
| Skill / tool наследование | `extends:` в YAML frontmatter | ⚠️ Граф не материализован, нет recursive queries |
| Embeddings | `<project>/.veles/skill_embeddings.json` | ⚠️ Отдельный артефакт; numpy brute force |
| Foreign keys / graph | `turns.session_id`, `sessions.parent_session_id`, `job_runs.job_id` | shallow, 1 уровень |
| Recursive CTE | — | ❌ Не используется |
| SQL JSON1 | — | ❌ tool_calls_json парсится в Python |

Главные gap'ы: tools без персистентной телеметрии; правила/инсайты не запросишь SQL; нет tree-cache; embeddings фрагментированы.

## Природа данных Veles

Данные **не graph-shaped в core**. Это смесь:

- **Append-only лог** (sessions, turns, tool_calls, telemetry events) — 90% объёма, write-once, read-many.
- **Документы с метаданными** (skills, tools, rules, insights) — markdown в FS, метаданные структурированы.
- **Shallow hierarchy** (parent_session, parent_skill, parent_tool, parent_project) — depth обычно 1–2, редко 3. Recursive CTE справляется до 1k узлов за миллисекунды.
- **Cross-references** (skill→tools, insight→wiki-page) — много-к-многим через ID, classic relational модель.
- **Semantic similarity** (поиск похожих skills, insights, conversation turns) — k-NN по embeddings.
- **Full-text search** (по turns, по insights, по правилам).

Граф у Veles — звезда + дерево, не сеть. Сложных pattern-matching типа "найди все skills, чьи tools используются вместе с инсайтами категории X в сессиях с negative feedback" — нет. Если такое и понадобится, это OLAP-запрос, не graph traversal.

## Опции — сравнительная таблица

Оценка вёрстана под шкалу 50k сессий / 100k инсайтов / 50k embeddings и local-first ограничения.

| Опция | Граф shallow ≤3 | k-NN 50k | FTS 100k | OLAP агрегации | Embedded / portable | Apache-compat | Python ecosystem | Сложность миграции |
|---|---|---|---|---|---|---|---|---|
| **SQLite + JSON1 + FTS5 + sqlite-vec** | ✅ recursive CTE | ✅ C brute force ≤100ms | ✅ FTS5 BM25 | ⚠️ ok до 1M | ✅ один файл | ✅ public domain + MIT | ✅ stdlib | низкая |
| SQLite + numpy embeddings (pure-Python) | ✅ | ❌ 5–10s @ 50k | ✅ | ⚠️ | ✅ | ✅ | ✅ | низкая |
| SQLite + LanceDB (vector только) | ✅ для SQL | ✅ ANN, fast | через SQLite | ⚠️ | ⚠️ два корня | ✅ Apache 2.0 | хорошо | средняя |
| Kuzu embedded (заменить SQLite) | ✅✅ Cypher | ⚠️ нет встроенного vector | ❌ нет FTS5 | ⚠️ | ✅ | ✅ MIT | моложе | высокая |
| DuckDB embedded | ✅ | через VSS ext | ⚠️ слабее FTS5 | ✅✅ OLAP-first | ✅ один файл | ✅ MIT | хорошо | высокая, OLTP weak |
| PostgreSQL embedded | ✅ | ✅ pgvector | ✅ ts_vector | ✅ | ❌ не truly embedded | ✅ | хорошо | очень высокая |
| Knowledge graph (Oxigraph + SPARQL) | ✅✅✅ | ❌ | ❌ | ❌ | ✅ | ✅ Apache 2.0 | средне | overkill |
| TinyDB / document store | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | дёшево, но всё ломается |

Ключевые наблюдения:

- **Заменить SQLite на Kuzu или DuckDB** означает выбросить рабочий код, FTS5, 2300 тестов — и получить меньше FTS / меньше OLTP / меньше Python инструментов взамен. Не оправдано shallow-graph природой данных Veles.
- **PostgreSQL embedded** ломает local-first простоту (single-file backup из §9).
- **Pure-Python numpy** уязвим на k-NN при 50k+ векторов — это блокер для §5.1 "реестры с поиском похожих".
- **SQLite + LanceDB** — рабочий гибрид, но удваивает state и усложняет export/import.
- **SQLite + sqlite-vec** — единственный вариант, покрывающий все 4 столбца (граф / k-NN / FTS / portable) одним файлом, оставаясь в local-first границе.

## Детали решения

### Core stack

```
memory.db (один файл) =
    SQLite 3.45+              # stdlib, базовый OLTP
  + JSON1                     # встроен в SQLite ≥3.38, нативные JSON-функции
  + FTS5                      # встроен, поиск по turns / insights / rules
  + sqlite-vec v0.1+          # loadable C-extension, k-NN над embeddings
```

Расширения, **не** входящие в core (opt-in модули при возникновении конкретной нагрузки):

- **Kuzu** — если появятся graph queries 5+ hops.
- **DuckDB** — для analytical exports / отчётов по телеметрии через `ATTACH 'memory.db'`. Данные не дублируются.
- **LanceDB** — резерв, если шкала embeddings перевалит 500k–1M.

### Почему sqlite-vec, а не pure-Python numpy fallback навсегда

- **Шкала 50k+ векторов** делает pure-Python numpy brute force неприемлемым (5–10 сек/запрос). sqlite-vec даёт C brute force ≤100ms.
- **Pre-built wheels** доступны от `alexgarcia/sqlite-vec` под macOS (Intel + ARM), Linux (x86_64 + ARM64), Windows. `pip install sqlite-vec`. Нет требования к компилятору на машине пользователя.
- **Apache 2.0** лицензия — совместимо с Veles.
- **Один файл `memory.db`** — критично для §9 (full export как bit-for-bit бандл). LanceDB-фрагмент пришлось бы отдельно архивировать.
- **Изоляция риска**: модуль `veles.core.memory.vector` ловит `ImportError` / `OperationalError("not authorized")` при загрузке extension и переключается на pure-Python numpy. Деградация по скорости, не отказ функционала. На экзотической платформе всё работает, просто медленнее.

Альтернативное "только pure-Python" приемлемо лишь если UX где "найти похожий инсайт" занимает 5 секунд считается допустимым. На VISION §1 ("knowledge workers, опытные пользователи") это не пройдёт.

## Схема расширения (sketch, не имплементация)

```sql
-- УЖЕ ЕСТЬ
sessions(id, created_at, last_activity_at, title, parent_session_id)
turns(id, session_id, seq, role, content, tool_calls_json, tool_call_id)
turns_fts(content)               -- FTS5
jobs(...), job_runs(...)

-- ДОБАВИТЬ

tools(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE, scope TEXT,    -- 'project' | 'user' | 'builtin'
  origin TEXT,                                              -- 'builtin' | 'agent-generated' | 'manual'
  base_tool_id INTEGER REFERENCES tools(id),
  manifest_json TEXT,                                       -- JSON1: args schema, risk_class, side_effects
  created_at, updated_at
)
tools_fts(name, description)     -- FTS5

tool_uses(
  id, tool_id REFERENCES tools(id), session_id, turn_id,
  invoked_at, ok BOOLEAN, latency_ms, error_kind
)
-- агрегаты use_count / success_rate / last_used → GROUP BY tool_id

skills(
  id, name UNIQUE, scope, base_skill_id REFERENCES skills(id),
  frontmatter_json,           -- JSON1: tags, description, body_hash
  file_path,                  -- проекция на FS-файл SKILL.md (источник истины — файл)
  ...
)
skills_fts(name, description)
skill_tool_refs(skill_id, tool_id, args_json)  -- §5.5: skill ссылается на tool с аргументами

rules(
  id, kind TEXT,              -- 'format' | 'do' | 'dont' | 'preference'
  body TEXT, source TEXT,     -- 'explicit-feedback' | 'extracted'
  created_at, last_applied_at, decay_score REAL
)
rules_fts(body)

insights(
  id, title, body, category, file_path,    -- проекция на wiki/insights/*.md
  created_at, last_referenced_at
)
insights_fts(title, body)
insight_refs(from_insight_id, to_insight_id)  -- cross-references

project_tree(                 -- §5.1: карта структуры проекта
  rel_path PRIMARY KEY, kind TEXT,     -- 'dir' | 'file' | 'subproject'
  parent_path REFERENCES project_tree(rel_path),
  semantic_tag TEXT, last_scanned_at
)

embeddings(                   -- sqlite-vec virtual table
  rowid INTEGER PRIMARY KEY,
  ref_kind TEXT,              -- 'skill' | 'tool' | 'insight' | 'rule' | 'turn'
  ref_id INTEGER,
  vec FLOAT[1536]             -- sqlite-vec: vec0 virtual table
)
-- k-NN: SELECT ref_kind, ref_id, distance FROM embeddings WHERE vec MATCH :q ORDER BY distance LIMIT 10
```

Граф queries для shallow hierarchies — стандартный recursive CTE:

```sql
WITH RECURSIVE skill_chain(id, base_skill_id, depth) AS (
  SELECT id, base_skill_id, 0 FROM skills WHERE name = :name
  UNION ALL
  SELECT s.id, s.base_skill_id, c.depth + 1
  FROM skills s JOIN skill_chain c ON s.id = c.base_skill_id
)
SELECT * FROM skill_chain;
```

При shallow depth (≤5) — <1ms даже на 5k skills.

## Когда пересмотреть решение (явные триггеры)

Решение не вечное. Триггеры для opt-in модуля или замены:

1. **Graph queries 5+ hops становятся частыми и медленными.** Симптом: recursive CTE > 100ms на типичном запросе, разработчик ловит себя на 4-уровневых JOIN'ах. Действие: добавить **Kuzu** как opt-in модуль `veles-graph`, ATTACH-стиль интеграция, SQLite остаётся для всего остального.

2. **Шкала embeddings > 500k векторов.** Симптом: sqlite-vec brute force на 500k+ векторов > 500ms. Действие: переход на **LanceDB** для vector layer, остальное в SQLite. Export бандлит оба корня.

3. **Heavy analytical workload по телеметрии.** Симптом: пользователь регулярно делает запросы типа "топ-50 skills за месяц, разбитые по success_rate, с rolling-window средним latency". Действие: добавить **DuckDB** через `duckdb.attach('memory.db')` как read-only OLAP view. Запись остаётся в SQLite.

4. **Multi-user concurrent writes** (если Veles переедет в shared mode). Симптом: SQLite write lock contention. Действие: рассмотреть **PostgreSQL** (отдельный server) — но это меняет local-first VISION и должно быть отдельным архитектурным решением.

Каждый триггер изолирован: добавляется как модуль, не ломает текущую memory.db. Это и есть смысл "минимального ядра + опциональных модулей" из VISION §4.

## Out of scope (для отдельных milestones / ADR)

- **Имплементация расширения схемы** (`tools` / `skills` / `rules` / `insights` / `project_tree` / `embeddings` таблиц + миграция с YAML frontmatter и `skill_embeddings.json`) — отдельный milestone "Memory v3: full §5.1 coverage".
- **Выбор embedding model и dimension** — отдельное решение (зависит от провайдера, бюджета на API, латентности).
- **UI команд** `veles memory show / dump / vacuum` — отдельный UX milestone.
- **Concurrent-writer pattern** (WAL tuning, write queue) — текущая нагрузка не требует.
