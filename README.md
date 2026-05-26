# Lead MVP

MVP backend для обробки заявок з лендінг-форми. POST → нормалізація → AI-summary + класифікація → Google Sheets → Telegram.

Тестове завдання для агенції "Ціль". MVP-підхід: показати approach і judgment, не production-ready систему.

## Архітектура

```
GET  /       ──>  demo landing-форма (FileResponse, app/static/index.html)
GET  /health ──>  {"status":"ok","dry_run":bool}
POST /lead   ──>  Pydantic validate  ──>  202 ACCEPTED + lead_id (uuid4)
                                              │
                                              ▼ BackgroundTask
                          1. normalize()    phone→E.164 (UA region), email→.normalized, sha256 dedup
                          2. classify()     Anthropic Structured Outputs → summary+score+reason
                                            class derived in code: ≥70 hot / 40-69 warm / <40 cold
                                            junk for invalid input (AI not called)
                                            unknown for refusal/error fallback
                          3. storage()      Google Sheets append_row(USER_ENTERED)
                                            DRY_RUN → logs/leads.jsonl
                          4. notify()       Telegram sendMessage parse_mode=HTML
                                            html.escape() on all dynamic fields (XSS)
                                            ⚠️ JUNK marker
```

Кожен зовнішній виклик обгорнутий try/except — падіння Sheets/Telegram/Anthropic не валить флоу. /lead все одно повертає 202.

## 7 етапів (відповідають git-комітам)

0. **Skeleton** — `app/{api,config,normalizer,classifier,storage,notifier}.py`, factory-функції за `DRY_RUN`
1. **Intake** — Pydantic `LeadIn` (`extra='forbid'`, `str_strip_whitespace`), POST `/lead` → 202 + uuid4, BackgroundTask
2. **Normalization** — phonenumbers E.164 (`region=UA`), email-validator `.normalized`, sha256 dedup-ключ
3. **AI classify** — `client.messages.parse(output_format=LeadClassification)`, score clamp 0-100, max_tokens retry
4. **Storage** — `COLUMNS` як єдине джерело правди, gspread service account, `append_row(RAW)` (зберігає `+` у E.164-телефоні без формульної інтерпретації)
5. **Notify** — httpx Telegram, HTML escape, junk-маркер, error swallow
6. **E2E + this README**
7. **Landing** — статична форма заявки на `GET /` (vanilla HTML/CSS/JS, без CDN/збірок), `app/static/index.html`, шле POST на `/lead`

## Quickstart (DRY_RUN — БЕЗ ключів)

Рев'юер може запустити повний флоу без жодних реальних API. Виклики Anthropic/Sheets/Telegram замінюються на console-реалізації.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

pip install -r requirements.txt
pytest -v        # 67 тестів, всі external services замоковано
DRY_RUN=1 uvicorn app.api:app --port 8000
```

Відкрий **http://127.0.0.1:8000/** — побачиш landing-форму. Заповни, натисни «Залишити заявку» → success-стан + рядок у `logs/leads.jsonl` + рендерене Telegram-повідомлення в server-логах.

Або curl напряму:

```bash
curl -X POST http://127.0.0.1:8000/lead \
  -H "Content-Type: application/json" \
  -d @payload_example.json
```

Що побачиш:
- Response: `202 {"lead_id":"...","status":"accepted"}`
- `logs/leads.jsonl` — append JSON-рядок з повним розкладом
- Server log — рендерене Telegram-повідомлення в DRY_RUN ConsoleNotifier

Битий payload → 422:

```bash
curl -X POST http://127.0.0.1:8000/lead \
  -H "Content-Type: application/json" \
  -d '{"name":"X","phone":"+1"}'
# 422 — missing email + phone too short
```

## Real-mode setup

```bash
cp .env.example .env
```

Заповни `.env`:

```
DRY_RUN=false
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5
GOOGLE_SHEETS_ID=<id з URL таблиці>
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
PHONE_DEFAULT_REGION=UA
```

**Google Sheets:**
1. Google Cloud Console → створи service account → JSON-ключ як `service-account.json`
2. Розшарь таблицю на email сервіс-акаунта (Editor)
3. Перший рядок таблиці — заголовки в порядку `app.storage.COLUMNS` (`received_at, lead_id, name, phone, email, source, message, is_valid, is_duplicate, issues, lead_class, score, summary, reason`)

**Telegram:**
1. `@BotFather` → новий бот → візьми token
2. Напиши боту перше повідомлення з твого акаунта
3. `curl https://api.telegram.org/bot<TOKEN>/getUpdates` → візьми `chat.id`

## Структура

```
app/
├── api.py          POST /lead, GET /health, _process_lead background pipeline
├── config.py       Settings + get_settings() (lru_cache, .env via python-dotenv)
├── normalizer.py   NormalizedLead dataclass + normalize() + sha256 dedup set
├── classifier.py   LeadClassification (Pydantic for parse) + ClassifiedLead + classify()
├── storage.py      COLUMNS + build_row + ConsoleStorage (JSONL) / SheetsStorage + get_storage()
└── notifier.py     render_message + ConsoleNotifier / TelegramNotifier + get_notifier()
tests/
├── test_smoke.py        health + factories
├── test_intake.py       POST /lead validation
├── test_normalizer.py   phone/email/dedup
├── test_classifier.py   AI paths + junk + unknown + clamp + retry
├── test_storage.py      COLUMNS contract + ConsoleStorage + Sheets mock
├── test_notifier.py     render + escape + Telegram mock
└── test_e2e.py          full pipeline through TestClient
payload_example.json
.env.example
requirements.txt
```

## Тести

```bash
pytest -v
```

Жоден тест не б'є по справжніх Anthropic/Sheets/Telegram — все замоковано. E2E ганяє повний `POST /lead` → BackgroundTask → assert на захоплених row + Telegram-повідомленні.

## Критерії класифікації лідів

Системний промпт класифікатора (`app/classifier.py:_SYSTEM_PROMPT`) інструктує модель оцінювати ліди за такими сигналами.

**Підвищують score:**
- конкретні терміни старту ("у червні", "цього кварталу", "ASAP") — покупець обмежений часом
- зазначений бюджет із числом або діапазоном — фінансова готовність
- чіткий scope (кількість користувачів, цільова метрика, названі інтеграції) — ясність потреби
- ознаки decision-maker'а (CEO/Founder у підписі, "ми вирішили", згадка про найм команди)
- повнота контакту (повне ім'я, корпоративний домен пошти, детальне повідомлення)
- безпосередній fit зі сферою агенції (впровадження CRM, sales-автоматизація, lead-gen воронки, marketing ops)

**Знижують score:**
- розмиті повідомлення з цікавості ("розкажіть детальніше", "просто дивлюсь варіанти")
- відсутність бізнес-контексту (без бюджету, без термінів, без scope)
- безкоштовна пошта + загальне ім'я + порожнє або однорядкове повідомлення
- запит поза сферою агенції (hardware, бухгалтерія, HR-системи)

**Шкала, яку модель повертає у `score`:**
- 80–100 — ready-to-buy, більшість ключових сигналів присутні
- 60–79 — сильний намір, бракує 1–2 сигналів
- 40–59 — теплий інтерес, багато невідомого
- 20–39 — слабкий сигнал, exploratory
- 0–19 — шум, з ймовірністю не сконвертується

Сам клас (`hot/warm/cold`) деривиться не моделлю, а в коді — `app/classifier.py:_derive_class`: `≥70 hot`, `40–69 warm`, `<40 cold`. Це навмисний поділ відповідальностей: LLM відповідає тільки за оцінку сигналів, поріг для бакету задаємо ми. Якщо завтра бізнес захоче «hot тільки від 80» — це зміна одного рядка, без перенавчання промпту.

`junk` і `unknown` лежать поза цією шкалою: `junk` ставиться без виклику AI, якщо валідація phone/email не пройшла; `unknown` — fallback, коли модель відмовилась відповідати або впала за timeout.

## Trade-offs та відомі обмеження

Свідомі спрощення MVP. Кожен пункт має варіант продакшн-доробки — це не недогляд, це межа, до якої я дійшов у форматі тестового завдання.

- **Дедуплікація в пам'яті процесу.** Множина `_SEEN_DEDUP_KEYS` зберігає sha256-ключі `(phone_e164, email)` лише поки uvicorn живий. Після рестарту або при multi-worker setup'і ключі втрачаються — повторну заявку буде записано як нову. Продакшн-варіант — переніс у Redis або в окрему колонку Sheets із lookup'ом на 1–2 рядки перед append.

- **Endpoint `/lead` відкритий.** Жодної автентифікації — теоретично будь-хто може засипати таблицю. Це навмисне спрощення під формат тестового. У продакшн-варіанті — або shared-secret-хедер між лендінгом і API, або HMAC-підпис форми ключем, який знає тільки сервер.

- **Синхронний gspread.** Виклик `append_row` блокує worker-тред, але це не критично: запит `/lead` уже повернув `202`, обробка йде у `BackgroundTask` і клієнт не чекає. Якщо RPS виросте до тисяч на хвилину — треба зовнішня черга (Redis Queue / Celery) і батчинг записів у Sheets окремим воркером.

- **Без retry-політики на зовнішніх викликах.** Падіння Sheets або Telegram логується як warning і пайплайн завершується успішно — заявка не губиться (вона в server-логах і в JSONL у DRY_RUN-режимі), але рев'юер у Telegram її може не побачити. Продакшн-варіант — exponential backoff на 2–3 спроби, далі dead-letter queue для остаточних фейлів.

- **Заголовки Sheets не створюються автоматично.** Перший рядок Google Sheets має вже містити заголовки у порядку `app.storage.COLUMNS` — це задокументовано у Real-mode setup. Для продакшн-варіанту я додав би idempotent-перевірку: при першому append читаємо row 1 і, якщо порожньо, проставляємо заголовки самі.

- **Один процес uvicorn.** dedup-сет, `lru_cache` на `get_settings()` та об'єкт `SheetsStorage` з його кешем worksheet'а живуть на рівні процесу. Multi-worker setup (gunicorn -w 4) розіб'є цю модель — рішення те саме, що для першого пункту: винести dedup у зовнішній storage, а `SheetsStorage` зробити module-level singleton із thread-safe lazy init.
