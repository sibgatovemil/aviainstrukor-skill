#!/usr/bin/env python3
"""
rle_quiz_update.py — обновление трекинга после ответа на РЛЭ-вопрос
Usage: python3 rle_quiz_update.py --question-id rle_5 --answer B --quiz-num 3

Stdout: JSON с результатом ответа
Stderr: статусные сообщения
"""

import sys
import json
import argparse
from datetime import date
from pathlib import Path

# ── Пути ──────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
QUESTIONS_FILE = BASE_DIR / "rle_questions.json"
ANSWERED_FILE  = BASE_DIR / "rle_answered.json"


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


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Обновить трекинг ответа на РЛЭ-вопрос")
    parser.add_argument("--question-id", required=True, help="ID вопроса (например: rle_5)")
    parser.add_argument("--answer", required=True, choices=["A", "B", "C"], help="Ответ пользователя")
    parser.add_argument("--quiz-num", required=True, type=int, help="Номер квиза")
    args = parser.parse_args()

    question_id = args.question_id
    given_answer = args.answer.upper()
    quiz_num = args.quiz_num

    # Загрузка вопросов
    questions_raw: list = load_json(QUESTIONS_FILE)

    # Найти вопрос
    question = None
    for q in questions_raw:
        if q["questionId"] == question_id:
            question = q
            break

    if question is None:
        print(f"ERROR: Question not found: '{question_id}'", file=sys.stderr)
        print(f"Available IDs: {[q['questionId'] for q in questions_raw]}", file=sys.stderr)
        sys.exit(1)

    correct_answer = question["correct"]
    is_correct = (given_answer == correct_answer)

    print(f"[INFO] Вопрос: {question_id} ({question['orderNum']})", file=sys.stderr)
    print(f"[INFO] Ответ: {given_answer}, правильный: {correct_answer}, результат: {'✅' if is_correct else '❌'}", file=sys.stderr)

    # Загрузка трекинга
    answered_data: dict = load_json(ANSWERED_FILE)
    answered = answered_data.get("questions", {})

    # Обновить запись
    today = str(date.today())
    existing = answered.get(question_id, {})
    times_answered = existing.get("timesAnswered", 0) + 1

    answered[question_id] = {
        "correct": is_correct,
        "date": today,
        "quizNum": quiz_num,
        "timesAnswered": times_answered,
        "discipline": question.get("discipline", ""),
    }

    # Обновить мета
    answered_data["questions"] = answered
    if "meta" in answered_data:
        answered_data["meta"]["lastQuiz"] = quiz_num
        answered_data["meta"]["lastDate"] = today

    save_json(ANSWERED_FILE, answered_data)
    print(f"[INFO] Трекинг обновлён: {question_id}, timesAnswered={times_answered}", file=sys.stderr)

    # Результат в stdout
    result = {
        "questionId": question_id,
        "correct": is_correct,
        "correctAnswer": correct_answer,
        "correctAnswerText": question["answers"].get(correct_answer, ""),
        "givenAnswer": given_answer,
        "givenAnswerText": question["answers"].get(given_answer, ""),
        "discipline": question.get("discipline", ""),
        "priority": question.get("priority", 0),
        "explanation": question.get("explanation", ""),
        "timesAnswered": times_answered,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
