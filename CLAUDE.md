# Briefing для Claude Code

Цей файл — стартовий контекст. Прочитай повністю перш ніж відповідати на перший запит.

## Хто я

**Mesiaf** — @me_siaf, akiohiomi@gmail.com, Україна.
- Працюю на стройці вдень, ввечері будую AI-систему для медіабаїнгу.
- Ніша: товарний арбітраж UA, Facebook Ads, партнерка 7leads.
- Не програміст за бекграундом — всю код-роботу довіряю Claude ("на свій розсуд").
- Цінную робочий результат над довгим плануванням.
- Стиль спілкування: коротко, по суті, без зайвих пояснень.
- Мова: переважно українська/російська, іноді англійська. Дзеркаль мою поточну мову, не перемикайся самовільно на російську.

## Що я роблю (старі проекти — лежать в `C:\Users\Mesiaf\Desktop\test vs code\`)

Якщо потрібен контекст / код / приклади — гріп в ту папку. Не редагуй там нічого без явної просьби.

- **arbitrage-bot** — Python автопілот медіабаєра. SQLite + Meta Marketing API. 9-етапний roadmap (Етап 1 закритий — БД + Meta API працюють). DeepSeek LLM для рішень.
- **mesiaf-corp** — корпоративний сайт. Flask, port 5500, темна тема. Beta gate ключ `MESIAF-BETA-9X7K2`. DeepSeek AI чат. Дашборд на `/dashboard`.
- **SOFSO** — локальний агент, 14 інструментів. Прямі виклики SQLite + Meta API (без Flask). Памʼять через Obsidian-вольт `Brain/` (асоціативна, з RAG).
- **Kara** — Telegram-бот `@karamesiaf_ai_bot`. Personal Cognitive OS. Worktree `C:\Users\Mesiaf\Desktop\kara-worktree`. Відповідає **тільки українською**, без російського/суржика.
- **Brain/** — Obsidian-вольт. `03-Concepts/Marketing/` — marketing concepts. `04-Knowledge/creative-mastery/` — 125 нот по статичним крео (підключено до SOFSO RAG).

## Що мені доступно у будь-якому Claude Code-чаті

Не треба нічого ставити — все вже глобально в `~/.claude/`:

**Агенти** (через Agent tool): code-reviewer, ai-engineer, python-engineer, frontend-architect, security-auditor, Explore, Plan і ще ~150 спеціалізованих.

**MCP сервери** (нативні інтеграції):
- **Figma** — дизайн ↔ код
- **Canva** — генерація і редагування дизайнів
- **Higgsfield** — генерація зображень/відео, virality predictor
- **Miro** — діаграми, борди
- **Notion** — бази, сторінки
- **Gmail** — листи, лейбли, чернетки
- **Google Calendar / Drive** — події, файли

**Скіли** (через Skill tool / `/<name>`): сотні automation-скілів (Composio), плюс `watch`, `schedule`, `loop`, `verify`, `run`, `init`, `review`, `security-review`, `higgsfield-generate`, `higgsfield-soul-id` тощо.

## Memory

`MEMORY.md` у `~/.claude/projects/c--Users-Mesiaf-Desktop-new-project/memory/` уже містить:
- User Profile
- Higgsfield prompt rule (`--image` задає вигляд, prompt = тільки сцена)
- Ad bad prompts (no dangling UA verbs, no specific % / prices)

Дописуй нові feedback/project memories як зʼявляються — старі projects я не переніс, бо хотів чистий старт.

## Правила, які я часто повторюю

1. **Higgsfield prompts**: якщо є `--image ./product.png` — описуй ТІЛЬКИ сцену/світло/стиль. Не описуй вигляд товару, не вигадуй фічі (типу "built-in flashlight" якщо його немає на фото).
2. **Креативи**: ніяких "ЗАЛИШИЛОСЬ" одним словом, ніяких конкретних `-53%` / `399 грн` на overlay. Дозволено: "АКЦІЯ", "ХІТ", "ОБМЕЖЕНА ПАРТІЯ".
3. **Kara-бот**: тільки українська, ніякого російського/суржика, не дзеркаль мову юзера.
4. **Код**: довіряю тобі — не питай дрібниці типу "який варіант", вирішуй сам, якщо є сумніви — кажи коротко тред-офф і свою рекомендацію.

## З чого починаємо

Новий проект — папка порожня. Чекаю інструкцій що будуємо.
