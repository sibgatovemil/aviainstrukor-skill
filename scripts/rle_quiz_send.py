#!/usr/bin/env python3
"""
rle_quiz_send.py — отправка РЛЭ-квиза C-172K в Telegram
Usage: python3 rle_quiz_send.py [--type morning|day|evening]
"""

import sys
import json
import argparse
import re
from datetime import date, datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ── Пути ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
QUESTIONS_FILE = BASE_DIR / "rle_questions.json"
ANSWERED_FILE  = BASE_DIR / "rle_answered.json"
PROGRESS_FILE  = BASE_DIR / "rle_progress.md"
ACTIVE_FILE    = BASE_DIR / "rle_active_quiz.json"

# ── Telegram ───────────────────────────────────────────────────────────────────
BOT_TOKEN  = "8762373004:AAFIKzh9ZLQZkH2p56Pp5MmfKFtieVlAS8g"
CHAT_ID    = -1003518920443
THREAD_ID  = 3872
TG_API     = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── Утилиты ────────────────────────────────────────────────────────────────────
def load_json(path: Path) -> dict | list:
    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def determine_quiz_type() -> str:
    hour = datetime.utcnow().hour
    if hour < 8:
        return "morning"
    elif hour < 13:
        return "day"
    else:
        return "evening"


def get_learning_day(start_date: str) -> int:
    return (date.today() - date.fromisoformat(start_date)).days + 1


def target_priority_for_day(day: int) -> int:
    """Определить целевой приоритет по дню обучения (циклически)."""
    effective = ((day - 1) % 14) + 1  # нормализуем в 1..14
    if effective <= 3:
        return 1
    elif effective <= 6:
        return 2
    elif effective <= 9:
        return 3
    else:
        return 4


def get_last_quiz_num(progress_path: Path) -> int:
    if not progress_path.exists():
        return 0
    text = progress_path.read_text(encoding="utf-8")
    # ищем все "Quiz #N" или "RLE Quiz #N"
    matches = re.findall(r'Quiz\s+#(\d+)', text)
    if not matches:
        return 0
    return max(int(m) for m in matches)


def sort_key(q_id: str, answered: dict) -> tuple:
    """Сортировка: никогда не отвеченные (0), затем по timesAnswered asc."""
    if q_id not in answered:
        return (0, 0)
    return (1, answered[q_id].get("timesAnswered", 0))


def select_questions(questions: list, answered: dict, target_priority: int) -> list:
    """
    Шаг 3: 1–2 вопроса из priority=1
    Шаг 4: 3–4 вопроса из target_priority (или следующего если не хватает)
    Итого ровно 5 вопросов.
    """
    # Индексируем по questionId
    by_priority = {}
    for q in questions:
        p = q["priority"]
        by_priority.setdefault(p, []).append(q)

    # Сортировка внутри каждой группы
    for p in by_priority:
        by_priority[p].sort(key=lambda q: sort_key(q["questionId"], answered))

    selected = []
    used_ids = set()

    # ── Шаг 3: 1–2 вопроса из priority=1 (СКОРОСТИ — ВСЕГДА) ─────────────────
    p1_pool = by_priority.get(1, [])
    p1_take = min(2 if target_priority != 1 else 2, len(p1_pool))
    # Если целевой == 1, всё равно сначала берём 1-2 как "обязательные"
    for q in p1_pool[:p1_take]:
        selected.append(q)
        used_ids.add(q["questionId"])

    # Нам нужно ровно 5 вопросов
    need = 5 - len(selected)

    # ── Шаг 4: остаток из целевого приоритета ─────────────────────────────────
    priorities_to_try = []
    if target_priority == 1:
        # оставшиеся из priority=1 (не выбранные на шаге 3)
        priorities_to_try = [1, 2, 3, 4]
    else:
        priorities_to_try = list(range(target_priority, 5)) + list(range(1, target_priority))

    for p in priorities_to_try:
        if need <= 0:
            break
        pool = [q for q in by_priority.get(p, []) if q["questionId"] not in used_ids]
        take = min(need, len(pool))
        for q in pool[:take]:
            selected.append(q)
            used_ids.add(q["questionId"])
            need -= 1

    # Если всё равно не набрали 5 (мало вопросов в базе) — берём любые оставшиеся
    if need > 0:
        all_remaining = [q for q in questions if q["questionId"] not in used_ids]
        all_remaining.sort(key=lambda q: sort_key(q["questionId"], answered))
        for q in all_remaining[:need]:
            selected.append(q)

    return selected[:5]


def send_question(idx: int, total: int, q: dict) -> bool:
    """Отправить один вопрос в Telegram с inline-кнопками. Возвращает True при успехе."""
    q_id = q["questionId"]
    text = (
        f"📝 РЛЭ Вопрос {idx}/{total} | {q['orderNum']}\n"
        f"{q['discipline']}\n\n"
        f"{q['text']}\n\n"
        f"A) {q['answers']['A']}\n"
        f"B) {q['answers']['B']}\n"
        f"C) {q['answers']['C']}"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "A", "callback_data": f"rle_{q_id}_A"},
            {"text": "B", "callback_data": f"rle_{q_id}_B"},
            {"text": "C", "callback_data": f"rle_{q_id}_C"},
        ]]
    }

    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": text,
        "reply_markup": json.dumps(keyboard),
    }

    try:
        resp = requests.post(f"{TG_API}/sendMessage", data=payload, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error sending question {q_id}: {e}", file=sys.stderr)
        return False

    if not resp.ok:
        print(f"ERROR: Telegram API error for question {q_id}: {resp.status_code} {resp.text}", file=sys.stderr)
        return False

    result = resp.json()
    if not result.get("ok"):
        print(f"ERROR: Telegram returned not-ok for {q_id}: {result}", file=sys.stderr)
        return False

    return True


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Отправить РЛЭ-квиз в Telegram")
    parser.add_argument(
        "--type",
        choices=["morning", "day", "evening"],
        default=None,
        help="Тип квиза (по умолчанию определяется по UTC)"
    )
    args = parser.parse_args()

    quiz_type = args.type or determine_quiz_type()

    # Загрузка данных
    questions_raw: list = load_json(QUESTIONS_FILE)
    answered_data: dict = load_json(ANSWERED_FILE)

    answered = answered_data.get("questions", {})
    start_date = answered_data.get("startDate", str(date.today()))

    # Вычислить день обучения и целевой приоритет
    learning_day = get_learning_day(start_date)
    target_priority = target_priority_for_day(learning_day)

    print(f"[INFO] День обучения: {learning_day}, целевой приоритет: {target_priority}, тип: {quiz_type}", file=sys.stderr)

    # Выбрать вопросы
    selected = select_questions(questions_raw, answered, target_priority)

    if len(selected) == 0:
        print("ERROR: Не удалось выбрать вопросы — база пуста?", file=sys.stderr)
        sys.exit(1)

    # Номер квиза
    quiz_num = get_last_quiz_num(PROGRESS_FILE) + 1
    print(f"[INFO] Квиз #{quiz_num}, вопросов: {len(selected)}", file=sys.stderr)

    # Отправка
    total = len(selected)
    for idx, q in enumerate(selected, start=1):
        print(f"[INFO] Отправляю вопрос {idx}/{total}: {q['questionId']} ({q['orderNum']})", file=sys.stderr)
        ok = send_question(idx, total, q)
        if not ok:
            print(f"ERROR: Прерываем отправку из-за ошибки Telegram API", file=sys.stderr)
            sys.exit(1)

    # Сохранить активный квиз
    active_quiz = {
        "quizNum": quiz_num,
        "type": quiz_type,
        "date": str(date.today()),
        "learningDay": learning_day,
        "targetPriority": target_priority,
        "questions": [
            {
                "questionId": q["questionId"],
                "orderNum": q["orderNum"],
                "sent": True
            }
            for q in selected
        ]
    }
    save_json(ACTIVE_FILE, active_quiz)
    print(f"[OK] Квиз #{quiz_num} отправлен. Активный квиз сохранён в {ACTIVE_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
