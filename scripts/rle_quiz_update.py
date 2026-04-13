#!/usr/bin/env python3
"""
rle_quiz_update.py — обновление трекинга после ответа на РЛЭ-вопрос
Usage: python3 rle_quiz_update.py --question-id rle_5 --answer B --quiz-num 3

Stdout: JSON с результатом ответа
Stderr: статусные сообщения
"""

import sys
import json
import os
import argparse
from datetime import date
from pathlib import Path

# ── Пути ──────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(os.environ.get("AVIATION_DIR", Path(__file__).parent))
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


# ── Progress builder ──────────────────────────────────────────────────────────

def build_rle_quiz_progress(quiz_num: int, current_qid: str, current_correct: bool, aviation_dir: Path) -> str:
    """Построить строку прогресса РЛЭ-квиза, например: Прогресс РЛЭ Quiz #4: ✅❌✅ (2/3 отвечено)"""
    try:
        active_quiz_path = aviation_dir / "rle_active_quiz.json"
        if not active_quiz_path.exists():
            return ""
        with open(active_quiz_path, encoding="utf-8") as f:
            active_quiz = json.load(f)

        if isinstance(active_quiz, dict):
            quiz_questions = active_quiz.get("questions", [])
        else:
            quiz_questions = active_quiz

        if not quiz_questions:
            return ""

        # Загрузить rle_answered.json
        answered_path = aviation_dir / "rle_answered.json"
        if not answered_path.exists():
            return ""
        with open(answered_path, encoding="utf-8") as f:
            answered_raw = json.load(f)

        # rle_answered.json: {"rle_2": {"correct": true, "quizNum": 4, ...}}
        # или {"questions": {...}}
        if isinstance(answered_raw, dict) and "questions" in answered_raw:
            answered_map = answered_raw["questions"]
        else:
            answered_map = answered_raw

        icons = []
        answered_count = 0
        for _q in quiz_questions:
            qid = _q["questionId"] if isinstance(_q, dict) else _q
            if qid == current_qid:
                icons.append("✅" if current_correct else "❌")
                answered_count += 1
            elif qid in answered_map:
                entry = answered_map[qid]
                if isinstance(entry, dict) and entry.get("quizNum") == quiz_num:
                    icons.append("✅" if entry.get("correct") else "❌")
                    answered_count += 1
                else:
                    icons.append("⬜")
            else:
                icons.append("⬜")

        total = len(quiz_questions)
        icons_str = "".join(icons)
        return f"Прогресс РЛЭ Quiz #{quiz_num}: {icons_str} ({answered_count}/{total} отвечено)"
    except Exception as e:
        print(f"[WARN] build_rle_quiz_progress failed: {e}", file=sys.stderr)
        return ""


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
    correct_answer_text = question["answers"].get(correct_answer, "")
    given_answer_text = question["answers"].get(given_answer, "")
    explanation = question.get("explanation", "")
    question_text = question.get("text", "")

    progress_line = build_rle_quiz_progress(quiz_num, question_id, is_correct, BASE_DIR)
    sep = "───"

    if is_correct:
        reply_parts = [
            "✅ Правильно!",
            "",
            f"Вопрос #{question_id}: {question_text}",
            "",
            f"Правильный ответ: {correct_answer}) {correct_answer_text}",
            "",
            sep,
            "",
            f"📖 {explanation}" if explanation else "",
        ]
    else:
        reply_parts = [
            f"❌ Неверно! Правильный: {correct_answer}) {correct_answer_text}",
            "",
            f"Вопрос #{question_id}: {question_text}",
            "",
            f"Твой ответ: {given_answer}) {given_answer_text}",
            "",
            sep,
            "",
            f"📖 {explanation}" if explanation else "",
        ]

    if progress_line:
        reply_parts += ["", sep, "", progress_line]

    reply_text = "\n".join(reply_parts).rstrip()

    result = {
        "questionId": question_id,
        "questionText": question_text,
        "correct": is_correct,
        "correctAnswer": correct_answer,
        "correctAnswerText": correct_answer_text,
        "givenAnswer": given_answer,
        "givenAnswerText": given_answer_text,
        "discipline": question.get("discipline", ""),
        "priority": question.get("priority", 0),
        "explanation": explanation,
        "timesAnswered": times_answered,
        "replyText": reply_text,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
