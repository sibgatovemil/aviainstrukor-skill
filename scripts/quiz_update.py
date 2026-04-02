#!/usr/bin/env python3
"""
quiz_update.py — обновление трекинга после ответа на вопрос квиза.

Использование:
  python3 quiz_update.py --question-id 258 --answer C --quiz-num 31

Выводит JSON в stdout. Статусные сообщения — в stderr.
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Конфиг ──────────────────────────────────────────────────────────────────
AVIATION_DIR = Path("/root/.openclaw/workspace/aviation")
QUESTIONS_FILE = AVIATION_DIR / "rosaviatest_questions.json"
ANSWERED_FILE = AVIATION_DIR / "answered_questions.json"
WEAK_SPOTS_FILE = AVIATION_DIR / "weak_spots.md"


# ── Утилиты ──────────────────────────────────────────────────────────────────

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def load_json(path: Path) -> dict | list:
    if not path.exists():
        eprint(f"[ERROR] Файл не найден: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict | list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Weak spots парсер/редактор ───────────────────────────────────────────────

class WeakSpotsFile:
    """Парсер и редактор weak_spots.md с сохранением оригинальной структуры."""

    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.content = path.read_text(encoding="utf-8")
        else:
            # Создать базовый файл если нет
            self.content = (
                "# Слабые места — Spaced Repetition Tracker\n\n"
                "## Как работает\n"
                "- Когда ошибаешься — добавляется запись с реальным questionId\n"
                "- Интервалы: 1 день → 7 дней → 30 дней\n"
                "- Если ответил правильно — интервал увеличивается\n"
                "- Если снова ошибся — сброс на 1 день\n"
                "- Статус: ⏳ Ждёт повторения | ✅ Закреплено\n\n"
                "---\n\n"
                "## Активные (⏳ ждут повторения)\n\n"
            )

    def find_section(self, question_id: int) -> tuple[int, int] | None:
        """
        Найти секцию для данного questionId.
        Возвращает (start_pos, end_pos) в self.content или None.
        """
        pattern = re.compile(
            r"(### Вопрос #\w+ \(questionId: " + str(question_id) + r"\).*?"
            r"(?=\n### Вопрос |\Z))",
            re.DOTALL,
        )
        m = pattern.search(self.content)
        if not m:
            return None
        return m.start(), m.end()

    def get_section_text(self, question_id: int) -> str | None:
        bounds = self.find_section(question_id)
        if bounds is None:
            return None
        return self.content[bounds[0]:bounds[1]]

    def replace_section(self, question_id: int, new_text: str):
        bounds = self.find_section(question_id)
        if bounds is None:
            return
        # Убедимся что новый текст заканчивается на \n
        if not new_text.endswith("\n"):
            new_text += "\n"
        self.content = self.content[:bounds[0]] + new_text + self.content[bounds[1]:]

    def append_section(self, new_text: str):
        """Добавить новую секцию в конец файла."""
        if not new_text.endswith("\n"):
            new_text += "\n"
        self.content = self.content.rstrip() + "\n\n" + new_text + "\n"

    def save(self):
        self.path.write_text(self.content, encoding="utf-8")

    def get_status(self, question_id: int) -> str | None:
        """Вернуть значение Статус: для вопроса."""
        section = self.get_section_text(question_id)
        if section is None:
            return None
        m = re.search(r"\*\*Статус:\*\*\s*(.+)", section)
        if not m:
            return None
        return m.group(1).strip()

    def count_correct_repeats(self, question_id: int) -> int:
        """Посчитать кол-во правильных повторов (по строкам 1-й, 2-й правильный повтор)."""
        section = self.get_section_text(question_id)
        if section is None:
            return 0
        count = 0
        if "1-й правильный повтор" in section:
            count = 1
        if "2-й правильный повтор" in section:
            count = 2
        return count


def make_short_desc(q: dict) -> str:
    """Взять первые ~50 символов вопроса как краткое описание."""
    text = q.get("text", "")
    # Убрать переносы строк
    text = text.replace("\n", " ").strip()
    if len(text) > 60:
        text = text[:57] + "..."
    return text


def make_new_weak_spot_entry(
    q: dict,
    given_answer: str,
    today: date,
) -> str:
    """Создать новую запись для weak_spots.md."""
    order_num = q.get("orderNum", str(q["questionId"]))
    question_id = q["questionId"]
    discipline = q.get("discipline", "неизвестно")
    answers = q.get("answers", {})
    correct = q.get("correct", "")
    explanation = q.get("explanation", "")
    desc = make_short_desc(q)

    given_text = answers.get(given_answer, "?")
    correct_text = answers.get(correct, "?")

    # Краткая суть — первые 150 символов explanation или описание вопроса
    if explanation:
        # Первое предложение объяснения
        first_sentence = explanation.split(".")[0].strip()
        if len(first_sentence) > 120:
            first_sentence = first_sentence[:117] + "..."
        suть = first_sentence
    else:
        suть = f"Правильный ответ: {correct}) {correct_text}"

    next_date = (today + timedelta(days=1)).isoformat()

    lines = [
        f"### Вопрос #{order_num} (questionId: {question_id}) — {desc}",
        f"- **Дата ошибки:** {today.isoformat()}",
        f"- **Дисциплина:** {discipline}",
        f"- **Суть:** {suть}",
        f"- **Ответил:** {given_answer} ({given_text}) | **Правильно:** {correct} ({correct_text})",
        f"- **Следующее повторение:** {next_date}",
        f"- **Статус:** ⏳",
    ]
    return "\n".join(lines)


def update_weak_spot_wrong(
    ws: WeakSpotsFile,
    q: dict,
    given_answer: str,
    today: date,
) -> str:
    """Обновить запись в weak_spots при ошибке (повторная)."""
    question_id = q["questionId"]
    section = ws.get_section_text(question_id)
    if section is None:
        return "none"  # не должно случиться

    answers = q.get("answers", {})
    correct = q.get("correct", "")
    given_text = answers.get(given_answer, "?")
    correct_text = answers.get(correct, "?")
    next_date = (today + timedelta(days=1)).isoformat()

    # Обновить дату ошибки
    section = re.sub(
        r"\*\*Дата ошибки:\*\*.*",
        f"**Дата ошибки:** {today.isoformat()}, повторная ошибка {today.isoformat()}",
        section,
    )
    # Обновить «Ответил:»
    section = re.sub(
        r"\*\*Ответил:\*\*.*?\|.*?\*\*Правильно:\*\*.*",
        f"**Ответил:** {given_answer} ({given_text}) | **Правильно:** {correct} ({correct_text})",
        section,
    )
    # Обновить следующее повторение
    section = re.sub(
        r"\*\*Следующее повторение:\*\*.*",
        f"**Следующее повторение:** {next_date} (сброс после повторной ошибки)",
        section,
    )
    # Убрать строки с правильными повторами (сброс)
    section = re.sub(r"- \*\*[12]-й правильный повтор.*\n?", "", section)
    # Статус остаётся ⏳

    ws.replace_section(question_id, section)
    return "reset"


def update_weak_spot_correct(
    ws: WeakSpotsFile,
    question_id: int,
    today: date,
) -> str:
    """
    Обновить запись при правильном ответе.
    Возвращает action: 'repeat1' | 'repeat2' | 'mastered'
    """
    repeats = ws.count_correct_repeats(question_id)
    section = ws.get_section_text(question_id)

    if repeats == 0:
        # 1-й правильный повтор
        next_date = (today + timedelta(days=7)).isoformat()
        new_line = f"- **1-й правильный повтор:** {today.isoformat()} ✓\n"
        # Вставить перед строкой "Следующее повторение"
        section = re.sub(
            r"(- \*\*Следующее повторение:\*\*.*)",
            new_line + r"\1",
            section,
        )
        section = re.sub(
            r"\*\*Следующее повторение:\*\*.*",
            f"**Следующее повторение:** {next_date}",
            section,
        )
        ws.replace_section(question_id, section)
        return "repeat1"

    elif repeats == 1:
        # 2-й правильный повтор
        next_date = (today + timedelta(days=30)).isoformat()
        new_line = f"- **2-й правильный повтор:** {today.isoformat()} ✓\n"
        section = re.sub(
            r"(- \*\*Следующее повторение:\*\*.*)",
            new_line + r"\1",
            section,
        )
        section = re.sub(
            r"\*\*Следующее повторение:\*\*.*",
            f"**Следующее повторение:** {next_date}",
            section,
        )
        ws.replace_section(question_id, section)
        return "repeat2"

    else:
        # 3-й правильный повтор — закрепить
        new_line = f"- **3-й правильный повтор:** {today.isoformat()} ✓\n"
        section = re.sub(
            r"(- \*\*Следующее повторение:\*\*.*)",
            new_line + r"\1",
            section,
        )
        section = re.sub(
            r"\*\*Статус:\*\*.*",
            "**Статус:** ✅ Закреплено",
            section,
        )
        ws.replace_section(question_id, section)
        return "mastered"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Обновить трекинг после ответа на вопрос")
    parser.add_argument("--question-id", type=int, required=True, help="ID вопроса")
    parser.add_argument("--answer", type=str, required=True, help="Данный ответ (A/B/C/D)")
    parser.add_argument("--quiz-num", type=int, required=True, help="Номер квиза")
    args = parser.parse_args()

    question_id = args.question_id
    given_answer = args.answer.upper()
    quiz_num = args.quiz_num
    today = date.today()

    # ── Шаг 1: Найти вопрос ──────────────────────────────────────────────────
    all_questions: list[dict] = load_json(QUESTIONS_FILE)
    q = next((x for x in all_questions if x["questionId"] == question_id), None)
    if q is None:
        eprint(f"[ERROR] Вопрос questionId={question_id} не найден в базе")
        sys.exit(1)

    correct_answer = q.get("correct", "")
    answers = q.get("answers", {})
    discipline = q.get("discipline", "")
    explanation = q.get("explanation", "")

    is_correct = given_answer == correct_answer
    correct_answer_text = answers.get(correct_answer, "")
    given_answer_text = answers.get(given_answer, "")

    eprint(f"[INFO] questionId={question_id}, ответ={given_answer}, правильно={correct_answer}, верно={is_correct}")

    # ── Шаг 2: Обновить answered_questions.json ───────────────────────────────
    answered_raw = load_json(ANSWERED_FILE)

    if isinstance(answered_raw, dict) and "questions" in answered_raw:
        answered_map = answered_raw["questions"]
        answered_raw["questions"][str(question_id)] = {
            "correct": is_correct,
            "date": today.isoformat(),
            "quizNum": quiz_num,
            "discipline": discipline,
        }
        save_json(ANSWERED_FILE, answered_raw)
    else:
        # Старый flat-формат
        answered_raw[str(question_id)] = {
            "correct": is_correct,
            "date": today.isoformat(),
            "quizNum": quiz_num,
            "discipline": discipline,
        }
        save_json(ANSWERED_FILE, answered_raw)

    eprint(f"[INFO] answered_questions.json обновлён")

    # ── Шаг 3: Обновить weak_spots.md ────────────────────────────────────────
    ws = WeakSpotsFile(WEAK_SPOTS_FILE)
    was_in_weak_spots = ws.find_section(question_id) is not None
    weak_spot_action = "none"

    if is_correct:
        if was_in_weak_spots:
            status = ws.get_status(question_id)
            if status and "⏳" in status:
                weak_spot_action = update_weak_spot_correct(ws, question_id, today)
                eprint(f"[INFO] weak_spots: action={weak_spot_action}")
            else:
                eprint(f"[INFO] Вопрос в weak_spots но статус не ⏳, пропускаем")
        else:
            eprint(f"[INFO] Правильно, вопроса нет в weak_spots — ничего не делаем")
    else:
        # Ошибка
        if was_in_weak_spots:
            weak_spot_action = update_weak_spot_wrong(ws, q, given_answer, today)
            eprint(f"[INFO] weak_spots: повторная ошибка, сброс")
        else:
            # Новая ошибка — добавить запись
            entry = make_new_weak_spot_entry(q, given_answer, today)
            ws.append_section(entry)
            weak_spot_action = "added"
            eprint(f"[INFO] weak_spots: добавлена новая запись")

    ws.save()

    # ── Шаг 4: Вывод JSON в stdout ────────────────────────────────────────────
    result = {
        "questionId": question_id,
        "correct": is_correct,
        "correctAnswer": correct_answer,
        "correctAnswerText": correct_answer_text,
        "givenAnswer": given_answer,
        "givenAnswerText": given_answer_text,
        "discipline": discipline,
        "explanation": explanation or "",
        "wasInWeakSpots": was_in_weak_spots,
        "weakSpotAction": weak_spot_action,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
