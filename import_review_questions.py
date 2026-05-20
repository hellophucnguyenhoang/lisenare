# -*- coding: utf-8 -*-
"""Import review multiple-choice questions from all_questions.xlsx.

Usage:
    python import_review_questions.py
    python import_review_questions.py --dry-run
    python import_review_questions.py --db-url sqlite:///lisenare.db

By default the script reads the database URL from app.config.settings.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import Connection


REQUIRED_COLUMNS = {
    "lesson_id",
    "lesson name",
    "question",
    "answer a",
    "answer b",
    "answer c",
    "answer d",
    "full correct answer",
}

EXERCISE_PREFIX = "Luyện tập "
QUESTION_TYPE = "multi choice"
EXERCISE_TYPE = "review"


@dataclass
class ImportStats:
    created_exercises: int = 0
    reused_exercises: int = 0
    created_questions: int = 0
    skipped_duplicate_questions: int = 0
    skipped_invalid_rows: int = 0
    answer_mismatch_rows: int = 0
    filled_empty_answer_rows: int = 0


def get_default_db_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    try:
        from app.config import settings

        return settings.database_url
    except Exception as exc:
        raise RuntimeError(
            "Cannot load database URL. Pass --db-url or set DATABASE_URL."
        ) from exc


def clean_cell(value: Any) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def require_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Missing required Excel columns: {missing_text}")


def existing_columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def resolve_exercise_type_value(inspector, exercise_columns: set[str]) -> str | None:
    if "exercise_type" not in exercise_columns:
        return None

    exercise_type_column = next(
        column
        for column in inspector.get_columns("exercise")
        if column["name"] == "exercise_type"
    )
    enum_values = getattr(exercise_type_column["type"], "enums", None)
    if not enum_values:
        return EXERCISE_TYPE

    for candidate in (EXERCISE_TYPE, EXERCISE_TYPE.upper()):
        if candidate in enum_values:
            return candidate

    raise RuntimeError(
        "Cannot find a supported review enum value for exercise.exercise_type. "
        f"Database values are: {', '.join(enum_values)}"
    )


def values_for_table(values: dict[str, Any], columns: set[str]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in columns}


def get_lesson_names(conn: Connection, lesson: Table) -> dict[int, str]:
    rows = conn.execute(select(lesson.c.id, lesson.c.name)).all()
    return {int(row.id): row.name for row in rows}


def sync_postgres_id_sequence(conn: Connection, table_name: str) -> None:
    conn.execute(
        text(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table_name}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                (SELECT MAX(id) IS NOT NULL FROM {table_name})
            )
            """
        )
    )


def sync_postgres_id_sequences(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return

    sync_postgres_id_sequence(conn, "exercise")
    sync_postgres_id_sequence(conn, "question")


def find_or_create_exercise(
    conn: Connection,
    exercise: Table,
    exercise_columns: set[str],
    exercise_type_value: str | None,
    lesson_id: int,
    lesson_name: str,
    dry_run: bool,
) -> tuple[int | None, bool]:
    exercise_name = f"{EXERCISE_PREFIX}{lesson_name}"
    conditions = [
        exercise.c.lesson_id == lesson_id,
        exercise.c.name == exercise_name,
    ]
    if exercise_type_value is not None:
        conditions.append(exercise.c.exercise_type == exercise_type_value)

    existing_id = conn.execute(
        select(exercise.c.id).where(*conditions).limit(1)
    ).scalar_one_or_none()
    if existing_id is not None:
        return int(existing_id), False

    if dry_run:
        return None, True

    insert_values = values_for_table(
        {
            "name": exercise_name,
            "difficulty": 0.0,
            "lesson_id": lesson_id,
            "exercise_type": exercise_type_value,
        },
        exercise_columns,
    )
    result = conn.execute(exercise.insert().values(**insert_values))
    return int(result.inserted_primary_key[0]), True


def question_exists(
    conn: Connection,
    question_table: Table,
    exercise_id: int,
    question_text: str,
    answer_text: str,
) -> bool:
    existing_id = conn.execute(
        select(question_table.c.id)
        .where(
            question_table.c.exercise_id == exercise_id,
            question_table.c.question == question_text,
            question_table.c.answer == answer_text,
        )
        .limit(1)
    ).scalar_one_or_none()
    return existing_id is not None


def import_questions(
    excel_path: str,
    db_url: str,
    dry_run: bool = False,
    allow_missing_exercise_type: bool = False,
    empty_answer_text: str | None = None,
) -> ImportStats:
    df = pd.read_excel(excel_path, keep_default_na=False)
    require_columns(df)

    engine = create_engine(db_url)
    metadata = MetaData()
    stats = ImportStats()

    with engine.begin() as conn:
        inspector = inspect(conn)
        exercise_columns = existing_columns(inspector, "exercise")
        question_columns = existing_columns(inspector, "question")
        exercise_type_value = resolve_exercise_type_value(
            inspector, exercise_columns
        )

        if "exercise_type" not in exercise_columns:
            message = (
                "Table exercise does not have column exercise_type. "
                "Run the migration first, or pass "
                "--allow-missing-exercise-type for an old local SQLite DB."
            )
            if not allow_missing_exercise_type:
                raise RuntimeError(message)
            print(f"Warning: {message}")

        lesson = Table("lesson", metadata, autoload_with=conn)
        exercise = Table("exercise", metadata, autoload_with=conn)
        question_table = Table("question", metadata, autoload_with=conn)

        if not dry_run:
            sync_postgres_id_sequences(conn)

        lesson_names = get_lesson_names(conn, lesson)
        exercise_id_by_lesson: dict[int, int | None] = {}

        for index, row in df.iterrows():
            excel_row_number = index + 2
            lesson_id_raw = clean_cell(row["lesson_id"])
            lesson_name_from_file = clean_cell(row["lesson name"])
            question_text = clean_cell(row["question"])
            answers = [
                clean_cell(row["answer a"]),
                clean_cell(row["answer b"]),
                clean_cell(row["answer c"]),
                clean_cell(row["answer d"]),
            ]
            correct_answer = clean_cell(row["full correct answer"])

            if (
                lesson_id_raw is None
                or lesson_name_from_file is None
                or question_text is None
                or correct_answer is None
            ):
                stats.skipped_invalid_rows += 1
                print(f"Skip row {excel_row_number}: missing required value")
                continue

            if any(answer is None for answer in answers):
                if empty_answer_text is None:
                    stats.skipped_invalid_rows += 1
                    print(
                        f"Skip row {excel_row_number}: missing answer choice"
                    )
                    continue
                answers = [
                    answer if answer is not None else empty_answer_text
                    for answer in answers
                ]
                stats.filled_empty_answer_rows += 1

            lesson_id = int(lesson_id_raw)
            lesson_name = lesson_names.get(lesson_id)
            if lesson_name is None:
                raise ValueError(
                    f"Row {excel_row_number}: lesson_id={lesson_id} "
                    "does not exist in table lesson"
                )

            if lesson_name.strip() != lesson_name_from_file.strip():
                print(
                    f"Warning row {excel_row_number}: Excel lesson name "
                    f"'{lesson_name_from_file}' differs from DB lesson name "
                    f"'{lesson_name}'. Using DB name."
                )

            answer_text = "|".join(answer for answer in answers if answer)
            if correct_answer not in answers:
                stats.answer_mismatch_rows += 1
                print(
                    f"Warning row {excel_row_number}: full correct answer "
                    "is not exactly one of answer a-d"
                )

            if lesson_id not in exercise_id_by_lesson:
                exercise_id, created = find_or_create_exercise(
                    conn=conn,
                    exercise=exercise,
                    exercise_columns=exercise_columns,
                    exercise_type_value=exercise_type_value,
                    lesson_id=lesson_id,
                    lesson_name=lesson_name,
                    dry_run=dry_run,
                )
                exercise_id_by_lesson[lesson_id] = exercise_id
                if created:
                    stats.created_exercises += 1
                else:
                    stats.reused_exercises += 1

            exercise_id = exercise_id_by_lesson[lesson_id]
            if exercise_id is not None and question_exists(
                conn,
                question_table,
                exercise_id,
                question_text,
                answer_text,
            ):
                stats.skipped_duplicate_questions += 1
                continue

            if dry_run:
                stats.created_questions += 1
                continue

            insert_values = values_for_table(
                {
                    "question": question_text,
                    "answer": answer_text,
                    "correct_answer": correct_answer,
                    "type": QUESTION_TYPE,
                    "difficulty": 0.0,
                    "exercise_id": exercise_id,
                },
                question_columns,
            )
            conn.execute(question_table.insert().values(**insert_values))
            stats.created_questions += 1

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create review exercises and import questions from Excel."
    )
    parser.add_argument(
        "--excel",
        default="all_questions.xlsx",
        help="Path to the all_questions Excel file.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Database URL. Defaults to DATABASE_URL/app.config.settings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print what would be inserted without writing.",
    )
    parser.add_argument(
        "--allow-missing-exercise-type",
        action="store_true",
        help="Allow importing into a DB whose exercise table lacks exercise_type.",
    )
    parser.add_argument(
        "--empty-answer-text",
        default=None,
        help="Text used to fill blank answer choices instead of skipping rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_url = args.db_url or get_default_db_url()

    stats = import_questions(
        excel_path=args.excel,
        db_url=db_url,
        dry_run=args.dry_run,
        allow_missing_exercise_type=args.allow_missing_exercise_type,
        empty_answer_text=args.empty_answer_text,
    )

    action = "Would create" if args.dry_run else "Created"
    print(f"{action} exercises: {stats.created_exercises}")
    print(f"Reused exercises: {stats.reused_exercises}")
    print(f"{action} questions: {stats.created_questions}")
    print(f"Skipped duplicate questions: {stats.skipped_duplicate_questions}")
    print(f"Skipped invalid rows: {stats.skipped_invalid_rows}")
    print(f"Rows with filled empty answers: {stats.filled_empty_answer_rows}")
    print(f"Rows with answer mismatch warnings: {stats.answer_mismatch_rows}")


if __name__ == "__main__":
    main()
