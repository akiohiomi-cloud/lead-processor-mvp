# Lead MVP

MVP backend для обробки заявок з лендінг-форми. POST → нормалізація → AI-summary + класифікація → Google Sheets → Telegram.

Тестове завдання для агенції "Ціль". MVP-підхід: показати approach і judgment, не production-ready систему.

## Архітектура

```
POST /lead  ──>  Pydantic validate  ──>  202 ACCEPTED + lead_id (uuid4)
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

## 6 етапів (відповідають git-комітам)

0. **Skeleton** — `app/{api,config,normalizer,classifier,storage,notifier}.py`, factory-функції за `DRY_RUN`
1. **Intake** — Pydantic `LeadIn` (`extra='forbid'`, `str_strip_whitespace`), POST `/lead` → 202 + uuid4, BackgroundTask
2. **Normalization** — phonenumbers E.164 (`region=UA`), email-validator `.normalized`, sha256 dedup-ключ
3. **AI classify** — `client.messages.parse(output_format=LeadClassification)`, score clamp 0-100, max_tokens retry
4. **Storage** — `COLUMNS` як єдине джерело правди, gspread service account, `append_row(USER_ENTERED)`
5. **Notify** — httpx Telegram, HTML escape, junk-маркер, error swallow
6. **E2E + this README**

## Quickstart (DRY_RUN — БЕЗ ключів)

Рев'юер може запустити повний флоу без жодних реальних API. Виклики Anthropic/Sheets/Telegram замінюються на console-реалізації.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

pip install -r requirements.txt
pytest -v        # ~67 тестів, всі external services замоковано
uvicorn app.api:app --port 8000
```

В іншому терміналі:

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

## TODO — пишу сам перед здачею

- [ ] Заповнити критерії скорингу в `_SYSTEM_PROMPT` ([app/classifier.py](app/classifier.py)): сигнали які підвищують/знижують score (urgency, бюджет, decision authority, fit, contact quality).
- [ ] Розгорнути секцію Trade-offs (нижче — мій робочий чорновик, треба переписати своїми словами для здачі).

### Trade-offs (working draft)

- **In-memory dedup** — `_SEEN_DEDUP_KEYS` не переживає рестарт. Прод: Redis / SQLite / окрема Sheets-колонка з lookup.
- **No auth on `/lead`** — endpoint відкритий. Прод: shared-secret header або HMAC від лендінгу.
- **gspread синхронний** — у BackgroundTask це ок (response уже пішов), але високий RPS вимагатиме черги або асинхронного клієнта.
- **No retry policy** — Sheets/Telegram error → лог warning, флоу завершується. Прод: exponential backoff або dead-letter queue.
- **No header autocreate** — припускаємо що перший рядок Sheets уже заголовок.
- **Single-process** — uvicorn 1 worker, dedup-set per-process. Multi-worker setup втратить dedup без зовнішнього стораджу.
