#!/usr/bin/env python3
"""
quiz_send.py — отправка авиационного квиза в Telegram.

Выбирает 5 вопросов (weak_spots + новые) и шлёт через Bot API.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import requests

# ── Конфиг ──────────────────────────────────────────────────────────────────
AVIATION_DIR = Path("/root/.openclaw/workspace/aviation")
QUESTIONS_FILE = AVIATION_DIR / "rosaviatest_questions.json"
ANSWERED_FILE = AVIATION_DIR / "answered_questions.json"
WEAK_SPOTS_FILE = AVIATION_DIR / "weak_spots.md"
PROGRESS_FILE = AVIATION_DIR / "progress.md"
ACTIVE_QUIZ_FILE = AVIATION_DIR / "active_quiz.json"

BOT_TOKEN = "8762373004:AAFIKzh9ZLQZkH2p56Pp5MmfKFtieVlAS8g"
CHAT_ID = "-1003518920443"
THREAD_ID = 3872
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

DISCIPLINE_PRIORITY = {
    "правила полетов": 1,
    "авиационная метеорология, климатология и ее влияние на авиацию": 1,
    "аэронавигация (самолетовождение)": 1,
    "основы полета": 2,
    "воздушное законодательство": 2,
}
MAX_PER_DISCIPLINE = 3


# ── Утилиты ──────────────────────────────────────────────────────────────────

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def load_json(path: Path) -> dict | list:
    if not path.exists():
        eprint(f"[ERROR] Файл не найден: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def determine_quiz_type() -> str:
    """Определить тип квиза по UTC-времени."""
    h = datetime.utcnow().hour
    m = datetime.utcnow().minute
    t = h * 60 + m
    if t < 8 * 60:      # до 08:00 UTC → morning
        return "morning"
    elif t < 13 * 60:   # до 13:00 → day
        return "day"
    else:               # после 13:00 → evening
        return "evening"


def get_next_quiz_num() -> int:
    """Найти последний Quiz #N в progress.md и вернуть N+1."""
    if not PROGRESS_FILE.exists():
        eprint(f"[WARN] {PROGRESS_FILE} не найден, начинаем с 31")
        return 31
    content = PROGRESS_FILE.read_text(encoding="utf-8")
    matches = re.findall(r"Quiz\s+#(\d+)", content)
    if not matches:
        return 31
    last = max(int(n) for n in matches)
    return last + 1


def parse_weak_spots() -> list[dict]:
    """
    Парсить weak_spots.md.
    Возвращает список dict:
      {questionId, orderNum, next_date: date, status: '⏳'|'✅ Закреплено'}
    Только со статусом ⏳.
    """
    if not WEAK_SPOTS_FILE.exists():
        eprint(f"[WARN] {WEAK_SPOTS_FILE} не найден")
        return []

    content = WEAK_SPOTS_FILE.read_text(encoding="utf-8")
    # Разбиваем на секции по заголовку ### Вопрос
    sections = re.split(r"(?=^### Вопрос)", content, flags=re.MULTILINE)

    result = []
    for section in sections:
        header_match = re.match(
            r"### Вопрос #(\w+) \(questionId: (\d+)\)", section
        )
        if not header_match:
            continue

        order_num = header_match.group(1)
        question_id = int(header_match.group(2))

        status_match = re.search(r"\*\*Статус:\*\*\s*(.+)", section)
        if not status_match:
            continue
        status = status_match.group(1).strip()
        if "⏳" not in status:
            continue

        next_rep_match = re.search(r"\*\*Следующее повторение:\*\*\s*(\d{4}-\d{2}-\d{2})", section)
        if not next_rep_match:
            continue
        try:
            next_date = date.fromisoformat(next_rep_match.group(1))
        except ValueError:
            continue

        result.append({
            "questionId": question_id,
            "orderNum": order_num,
            "next_date": next_date,
            "status": status,
        })

    return result


def select_questions(
    all_questions: list[dict],
    answered_ids: set[int],
    weak_due: list[dict],
) -> list[dict]:
    """
    Выбрать ровно 5 вопросов согласно алгоритму.
    Возвращает список dict с ключами: questionId, orderNum, source ('weak'|'new')
    """
    today = date.today()
    selected = []
    discipline_counts: dict[str, int] = {}

    # ── Шаг 1: weak_spots, дата <= сегодня, не более 2 ──────────────────────
    due_today = sorted(
        [w for w in weak_due if w["next_date"] <= today],
        key=lambda w: w["next_date"],
    )

    for w in due_today:
        if len(selected) >= 2:
            break
        qid = w["questionId"]
        # Найти вопрос в базе
        q = next((x for x in all_questions if x["questionId"] == qid), None)
        if q is None:
            eprint(f"[WARN] questionId {qid} из weak_spots не найден в базе вопросов")
            continue
        disc = q.get("discipline", "")
        if discipline_counts.get(disc, 0) >= MAX_PER_DISCIPLINE:
            continue
        selected.append({**q, "source": "weak"})
        discipline_counts[disc] = discipline_counts.get(disc, 0) + 1
        eprint(f"[INFO] Weak spot: #{q['orderNum']} ({disc}), след. повтор {w['next_date']}")

    # ── Шаг 2: новые вопросы ─────────────────────────────────────────────────
    need = 5 - len(selected)
    already_selected_ids = {q["questionId"] for q in selected}

    # Исключаем уже отвеченные и уже выбранные weak_spot'ы
    exclude_ids = answered_ids | already_selected_ids

    # Пул доступных новых вопросов
    available = [q for q in all_questions if q["questionId"] not in exclude_ids]

    # Сортируем по приоритету дисциплины
    def priority_key(q):
        disc = q.get("discipline", "")
        return (DISCIPLINE_PRIORITY.get(disc, 3), q["questionId"])

    available.sort(key=priority_key)

    for q in available:
        if len(selected) >= 5:
            break
        disc = q.get("discipline", "")
        if discipline_counts.get(disc, 0) >= MAX_PER_DISCIPLINE:
            continue
        selected.append({**q, "source": "new"})
        discipline_counts[disc] = discipline_counts.get(disc, 0) + 1
        eprint(f"[INFO] Новый: #{q['orderNum']} ({disc})")

    if len(selected) < 5:
        eprint(f"[ERROR] Не удалось набрать 5 вопросов, нашлось только {len(selected)}")
        sys.exit(1)

    return selected


def format_question_text(index: int, q: dict) -> str:
    """Собрать текст сообщения по шаблону."""
    order_num = q.get("orderNum", str(q["questionId"]))
    discipline = q.get("discipline", "")
    text = q.get("text", "")
    answers = q.get("answers", {})

    lines = [
        f"📝 Вопрос {index}/5 | Росавиатест #{order_num}",
        f"Дисциплина: {discipline}",
        "",
        text,
        "",
    ]

    for letter in ("A", "B", "C", "D"):
        if letter in answers:
            lines.append(f"{letter}) {answers[letter]}")

    return "\n".join(lines)


def make_keyboard(q: dict) -> dict:
    """Inline-клавиатура: кнопки A, B, C [, D]."""
    qid = q["questionId"]
    answers = q.get("answers", {})
    buttons = []
    for letter in ("A", "B", "C", "D"):
        if letter in answers:
            buttons.append({
                "text": letter,
                "callback_data": f"quiz_{qid}_{letter}",
            })
    return {"inline_keyboard": [buttons]}


def send_message(text: str, keyboard: dict) -> int:
    """Отправить сообщение в Telegram, вернуть message_id."""
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": text,
        "reply_markup": json.dumps(keyboard),
    }
    resp = requests.post(f"{TG_API}/sendMessage", json=payload, timeout=10)
    if not resp.ok:
        eprint(f"[ERROR] Telegram API: {resp.status_code} {resp.text}")
        sys.exit(1)
    data = resp.json()
    msg_id = data["result"]["message_id"]
    eprint(f"[INFO] Отправлено сообщение message_id={msg_id}")
    return msg_id


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Отправить авиа-квиз в Telegram")
    parser.add_argument(
        "--type",
        choices=["morning", "day", "evening"],
        default=None,
        help="Тип квиза. По умолчанию — определяется по UTC-времени.",
    )
    args = parser.parse_args()

    quiz_type = args.type or determine_quiz_type()
    quiz_num = get_next_quiz_num()
    today_str = date.today().isoformat()

    eprint(f"[INFO] Quiz #{quiz_num} ({quiz_type}), дата {today_str}")

    # ── Загрузить данные ──────────────────────────────────────────────────────
    all_questions: list[dict] = load_json(QUESTIONS_FILE)

    answered_raw = load_json(ANSWERED_FILE)
    # Структура: {"meta": ..., "questions": {questionId: {...}}}
    if isinstance(answered_raw, dict) and "questions" in answered_raw:
        answered_map = answered_raw["questions"]
    else:
        answered_map = answered_raw  # fallback

    # Исключаем только правильно отвеченные (correct=True) и не None
    answered_ids = {
        int(k)
        for k, v in answered_map.items()
        if isinstance(v, dict) and v.get("correct") is True
    }
    eprint(f"[INFO] Правильно отвечено: {len(answered_ids)} вопросов")

    weak_spots = parse_weak_spots()
    eprint(f"[INFO] Weak spots (⏳): {len(weak_spots)}")

    # ── Выбрать вопросы ───────────────────────────────────────────────────────
    questions = select_questions(all_questions, answered_ids, weak_spots)

    # ── Отправить в Telegram ──────────────────────────────────────────────────
    quiz_questions_log = []

    for i, q in enumerate(questions, start=1):
        text = format_question_text(i, q)
        keyboard = make_keyboard(q)
        msg_id = send_message(text, keyboard)

        quiz_questions_log.append({
            "questionId": q["questionId"],
            "orderNum": q.get("orderNum", str(q["questionId"])),
            "sent": True,
        })

    # ── Сохранить active_quiz.json ────────────────────────────────────────────
    active_quiz = {
        "quizNum": quiz_num,
        "type": quiz_type,
        "date": today_str,
        "questions": quiz_questions_log,
    }
    with open(ACTIVE_QUIZ_FILE, "w", encoding="utf-8") as f:
        json.dump(active_quiz, f, ensure_ascii=False, indent=2)

    eprint(f"[INFO] active_quiz.json сохранён. Quiz #{quiz_num} отправлен ✅")


if __name__ == "__main__":
    main()
