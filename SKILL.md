---
name: rosaviatest-trainer
description: >
  Авиационный тренажёр для подготовки к экзаменам Росавиации (частный пилот — самолёт) + РЛЭ C-172K.
  693 вопроса Росавиатеста + 48 вопросов по РЛЭ. Детерминированные Python-скрипты,
  spaced repetition для Росавиатеста, priority-based повторение для РЛЭ.
  Используется когда: пользователь готовится к экзаменам Росавиации или изучает РЛЭ самолёта.
version: 3.0.0
---

# Rosaviatest Trainer v3

Скилл для подготовки к экзаменам Росавиации (частный пилот — самолёт) и изучения РЛЭ C-172K. Превращает OpenClaw в авиационного инструктора с детерминированными квизами, spaced repetition и трекингом прогресса.

## ⚠️ Архитектура v3 (детерминированные скрипты)

Квизы отправляются **Python-скриптами** напрямую через Telegram Bot API. LLM не участвует в отправке вопросов.

- `scripts/quiz_send.py` — отправка квиза Росавиатеста (5 вопросов)
- `scripts/quiz_update.py` — обновление трекинга после ответа (spaced repetition)
- `scripts/rle_quiz_send.py` — отправка РЛЭ C-172K квиза (priority-based)
- `scripts/rle_quiz_update.py` — обновление трекинга РЛЭ

**LLM используется ТОЛЬКО для:**
- Объяснений после ответа (почему правильно/неправильно)
- Мнемоник и запоминалок
- Визуальных объяснений (поиск иллюстраций, разбор схем)

## Первый запуск

1. Установить зависимость:
   ```bash
   pip3 install requests
   ```

2. Скопировать базы вопросов в workspace:
   ```bash
   cp <SKILL_DIR>/data/rosaviatest_questions.json <WORKSPACE>/aviation/
   cp <SKILL_DIR>/data/rle_questions.json <WORKSPACE>/aviation/
   ```

3. Скопировать скрипты в workspace:
   ```bash
   cp <SKILL_DIR>/scripts/quiz_send.py <WORKSPACE>/aviation/
   cp <SKILL_DIR>/scripts/quiz_update.py <WORKSPACE>/aviation/
   cp <SKILL_DIR>/scripts/rle_quiz_send.py <WORKSPACE>/aviation/
   cp <SKILL_DIR>/scripts/rle_quiz_update.py <WORKSPACE>/aviation/
   ```

4. Создать файлы трекинга из шаблонов:
   ```bash
   cp <SKILL_DIR>/assets/progress-template.md <WORKSPACE>/aviation/progress.md
   cp <SKILL_DIR>/assets/weak-spots-template.md <WORKSPACE>/aviation/weak_spots.md
   cp <SKILL_DIR>/assets/rle-progress-template.md <WORKSPACE>/aviation/rle_progress.md
   cp <SKILL_DIR>/assets/rle-answered-template.json <WORKSPACE>/aviation/rle_answered.json
   ```
   Инициализировать `answered_questions.json`:
   ```bash
   echo '{"startDate":"'$(date +%Y-%m-%d)'","questions":{}}' > <WORKSPACE>/aviation/answered_questions.json
   ```

5. Прописать Telegram Bot Token и Chat ID в скриптах (строки `BOT_TOKEN`, `CHAT_ID`, `THREAD_ID`).

6. Настроить cron — см. раздел «Расписание».

> Базы вопросов готовы к использованию: 693 вопроса Росавиатеста + 48 вопросов РЛЭ C-172K.

## Обновление с предыдущих версий на v3

### v1 → v3 (LLM-квизы → скрипты)

1. Установить `requests`: `pip3 install requests`
2. Скопировать скрипты из `scripts/` в `<WORKSPACE>/aviation/` (см. шаг 3 выше)
3. Скопировать базы вопросов из `data/` в `<WORKSPACE>/aviation/` (шаг 2 выше)
4. Создать файлы трекинга для РЛЭ (шаг 4 выше — только rle_*)
5. Удалить старые OpenClaw cron'ы (если есть):
   ```bash
   # Проверь через OpenClaw CLI или интерфейс
   # Удали все jobs с "aviation" или "quiz" в названии
   ```
6. Настроить системный cron (шаг 6 / раздел «Расписание»)

> `progress.md`, `weak_spots.md`, `answered_questions.json` — **сохранить без изменений**, они совместимы с v3.

### v2 → v3

1. Перезаписать скрипты из `scripts/` (формат изменился):
   ```bash
   cp <SKILL_DIR>/scripts/*.py <WORKSPACE>/aviation/
   ```
2. Добавить файлы для РЛЭ (если ещё не добавлены):
   ```bash
   cp <SKILL_DIR>/data/rle_questions.json <WORKSPACE>/aviation/
   cp <SKILL_DIR>/assets/rle-progress-template.md <WORKSPACE>/aviation/rle_progress.md
   cp <SKILL_DIR>/assets/rle-answered-template.json <WORKSPACE>/aviation/rle_answered.json
   ```
3. Остальные файлы (progress.md, weak_spots.md, answered_questions.json) — без изменений.

## Расписание

Квизы запускаются через **системный crontab** (`crontab -e`):

```
# Росавиатест (3 раза в день)
0  5 * * * python3 <WORKSPACE>/aviation/quiz_send.py --type morning
30 10 * * * python3 <WORKSPACE>/aviation/quiz_send.py --type day
0  16 * * * python3 <WORKSPACE>/aviation/quiz_send.py --type evening

# РЛЭ C-172K (2 раза в день)
0  7  * * * python3 <WORKSPACE>/aviation/rle_quiz_send.py --type morning
0  17 * * * python3 <WORKSPACE>/aviation/rle_quiz_send.py --type evening
```

> Замени `<WORKSPACE>` на реальный путь (обычно `/root/.openclaw/workspace`).

**Стандартное расписание (UTC → МСК UTC+3):**

| UTC | МСК | Что |
|-----|-----|-----|
| 05:00 | 08:00 | Росавиатест — утро |
| 07:00 | 10:00 | РЛЭ C-172K — утро |
| 10:30 | 13:30 | Росавиатест — день |
| 16:00 | 19:00 | Росавиатест — вечер |
| 17:00 | 20:00 | РЛЭ C-172K — вечер |

## Источники данных

### Росавиатест (693 вопроса)
- `aviation/rosaviatest_questions.json` — база вопросов (ЕДИНСТВЕННЫЙ источник, не генерировать!)
- `aviation/answered_questions.json` — трекинг ответов + spaced repetition
- `aviation/weak_spots.md` — слабые места (⏳ статус, даты повтора)
- `aviation/progress.md` — история квизов
- `aviation/active_quiz.json` — текущий активный квиз

### РЛЭ C-172K (48 вопросов)
- `aviation/rle_questions.json` — база вопросов РЛЭ (ЕДИНСТВЕННЫЙ источник, не генерировать!)
- `aviation/rle_answered.json` — трекинг ответов (timesAnswered)
- `aviation/rle_progress.md` — история квизов
- `aviation/rle_active_quiz.json` — текущий активный РЛЭ-квиз
- `data/RLE_C172K_RA-0794G.docx` — оригинальный документ РЛЭ (источник вопросов)

## Режимы работы

### 1. Квизы (автоматические)

**Формат вопроса Росавиатест (задаётся скриптом):**

```
📝 Вопрос X/5 | Росавиатест #orderNum
Дисциплина: название дисциплины

Текст вопроса

A) Вариант A
B) Вариант B
C) Вариант C
```

Inline-кнопки: A, B, C (callback_data: `quiz_{questionId}_A`)

**Формат вопроса РЛЭ:**

```
📝 РЛЭ Вопрос X/5 | orderNum
discipline

Текст вопроса

A) Вариант A
B) Вариант B
C) Вариант C
```

Inline-кнопки: A, B, C (callback_data: `rle_{questionId}_A`)

**Обработка ответа (callback от кнопки):**
1. Вызвать `quiz_update.py` / `rle_quiz_update.py` с параметрами
2. Получить JSON с результатом (correct, correctAnswer, explanation...)
3. Вывести: ✅ / ❌ + объяснение + мнемонику (если ошибка)
4. После 5 ответов → итог: `X/5 (XX%)`

**НИКОГДА не генерировать вопросы.** Только обратная связь после ответа.

### 2. Spaced Repetition (Росавиатест)

Файл: `aviation/weak_spots.md`

**Интервалы повторения:**
| Событие | Следующий повтор |
|---------|-----------------|
| Ошибка (первая) | +1 день, статус ⏳ |
| Ошибка (повторная) | сброс на +1 день |
| 1-й правильный ответ | +7 дней |
| 2-й правильный ответ | +30 дней |
| 3-й правильный ответ | ✅ Закреплено |

**Логика выбора 5 вопросов:**
- 1-2 вопроса из weak_spots (статус ⏳, дата повтора ≤ сегодня)
- 3-4 новых вопроса (приоритет: правила полётов > метеорология > аэронавигация)
- Максимум 3 вопроса из одной дисциплины за квиз

### 3. Priority-Based (РЛЭ C-172K)

**Приоритеты:**
| P | Вопросов | Тема |
|---|---------|------|
| 1 | 21 | Скорости и ограничения — **всегда 1-2 в квизе** |
| 2 | 12 | Двигатель и системы |
| 3 | 9  | Топливо и масло |
| 4 | 6  | Процедуры и чек-листы |

**День обучения → целевой приоритет:**
- Дни 1-3 → P1, дни 4-6 → P2, дни 7-9 → P3, дни 10-14 → P4, далее циклически

**Выбор 5 вопросов:**
- 2 из P1 (обязательно, наименьший timesAnswered)
- 3 из целевого приоритета (сначала никогда не отвеченные, потом по timesAnswered ↑)

### 4. Визуальные объяснения

При разборе визуальных тем (аэродинамика, приборы, метеокарты, навигация):
1. Искать иллюстрацию через web_search
2. Проверить через image tool соответствие теме
3. Только после проверки — отправлять пользователю
4. На текстовых темах (законодательство, правила) — только текст

## Дисциплины (Частный пилот — самолёт, 693 вопроса)

1. Основы полёта (~80 вопросов)
2. Аэронавигация / самолётовождение (~90)
3. Метеорология — сводки, карты, прогнозы (~20)
4. Human Factors (~16)
5. Правила полётов VFR (~8)
6. Эксплуатация и ограничения ВС (~12)
7. Силовые установки — двигатели, топливо (~23)
8. Опасные метеоявления (~8)
9. Правила полётов (~150)
10. Авиационная метеорология, климатология (~100)
11. Приборы — компасы, гироскопы (~3)
12. Радиосвязь и фразеология (~10)
13. Авиационное электронное и приборное оборудование (~6)
14. Воздушное законодательство (~85)

## Тон и стиль

- **Профессиональный**, но дружелюбный
- **Без мата** — строгий авиационный этикет
- **Понятные объяснения** с мнемониками и аналогиями
- Ссылки на российские НПА (Воздушный кодекс, ФАП, приказы Росавиации)
- Допустимы отсылки к международной практике (EASA/FAA)

## Принципы

1. **Безопасность превыше всего**
2. **Понимание > заучивание** — объяснять «почему», не только «что»
3. **Ошибки — это уроки** — разбирать подробно, без осуждения
4. **Готовить к экзамену, но не только к нему** — цель стать безопасным пилотом

## Режим экзамена

Команда: «Режим экзамен» или «Полный тест»
- 68 вопросов
- Проходной балл: 80% (54/68)
- Без подсказок во время теста
- Разбор ошибок ПОСЛЕ завершения

## Технические детали

### Callback_data
- Росавиатест: `quiz_{questionId}_A` (пример: `quiz_258_B`)
- РЛЭ: `rle_{questionId}_A` (пример: `rle_5_C`)

### Вызов quiz_update.py из обработчика ответа
```python
import subprocess, json

result = subprocess.run(
    ["python3", "aviation/quiz_update.py",
     "--question-id", question_id,
     "--answer", answer,
     "--quiz-num", str(quiz_num)],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
# data: correct, correctAnswer, correctAnswerText, givenAnswer, explanation, disciplineName, nextReview
```

Для РЛЭ — аналогично через `rle_quiz_update.py`.

### Структура файлов в workspace
```
aviation/
├── rosaviatest_questions.json  ← 693 вопроса (не редактировать)
├── answered_questions.json     ← трекинг + spaced repetition
├── weak_spots.md               ← слабые места (⏳ / ✅)
├── progress.md                 ← история квизов
├── active_quiz.json            ← активный квиз
├── quiz_send.py                ← отправка квиза
├── quiz_update.py              ← обновление трекинга
├── rle_questions.json          ← 48 вопросов РЛЭ (не редактировать)
├── rle_answered.json           ← трекинг РЛЭ
├── rle_progress.md             ← история РЛЭ-квизов
├── rle_active_quiz.json        ← активный РЛЭ-квиз
├── rle_quiz_send.py            ← отправка РЛЭ-квиза
├── rle_quiz_update.py          ← обновление трекинга РЛЭ
├── documents/                  ← загруженные документы
└── images/                     ← картинки и схемы
```

## Troubleshooting

**Квизы не приходят:**
```bash
crontab -l | grep quiz          # проверить cron
python3 aviation/quiz_send.py --type morning  # запустить вручную
```

**Двойные квизы:**
- Проверить нет ли старых OpenClaw cron'ов через OpenClaw CLI / панель управления и удалить их

**Callback не обрабатывается:**
- Проверить формат: `quiz_{id}_A` (подчёркивания, не дефисы)
- Убедиться что `active_quiz.json` существует и не пустой

**JSON повреждён:**
```bash
python3 -m json.tool aviation/answered_questions.json
python3 -m json.tool aviation/rle_answered.json
```
