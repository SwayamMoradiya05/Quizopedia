from django.db import migrations
from django.utils import timezone


EXTRA_QUESTIONS = {
    "Mathematics": (
        (
            "What is the perimeter of a square with side length 5?",
            ("10", "15", "20", "25"),
            2,
        ),
    ),
    "Science": (
        (
            "Which part of a plant absorbs most water?",
            ("Roots", "Leaves", "Flowers", "Stem"),
            0,
        ),
        (
            "What force keeps planets in orbit around the Sun?",
            ("Friction", "Gravity", "Magnetism", "Pressure"),
            1,
        ),
    ),
    "English": (
        (
            "Which word is an adjective in 'The bright star shone'?",
            ("Star", "Shone", "Bright", "The"),
            2,
        ),
        (
            "What is the past tense of 'write'?",
            ("Writed", "Written", "Wrote", "Writing"),
            2,
        ),
    ),
}


def seed_sample_test_data(apps, schema_editor):
    Student = apps.get_model("report_cards", "Student")
    Subject = apps.get_model("report_cards", "Subject")
    Question = apps.get_model("report_cards", "Question")
    Option = apps.get_model("report_cards", "Option")
    TestAttempt = apps.get_model("report_cards", "TestAttempt")
    TestResult = apps.get_model("report_cards", "TestResult")
    database = schema_editor.connection.alias

    for subject_name, questions in EXTRA_QUESTIONS.items():
        subject = Subject.objects.using(database).get(name=subject_name)
        for question_text, option_texts, answer_index in questions:
            question, _ = Question.objects.using(database).get_or_create(
                subject=subject,
                question_text=question_text,
            )
            for index, option_text in enumerate(option_texts):
                Option.objects.using(database).get_or_create(
                    question=question,
                    option_text=option_text,
                    defaults={"is_answer": index == answer_index},
                )

    students = Student.objects.using(database).order_by("pk")[:3]
    subjects = Subject.objects.using(database).order_by("name")
    for student in students:
        for subject in subjects:
            attempt = TestAttempt.objects.using(database).create(
                student=student,
                subject=subject,
                completed_at=timezone.now(),
            )
            questions = Question.objects.using(database).filter(subject=subject)
            for question in questions:
                correct_option = Option.objects.using(database).get(
                    question=question,
                    is_answer=True,
                )
                TestResult.objects.using(database).create(
                    attempt=attempt,
                    question=question,
                    selected_option=correct_option,
                )


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0008_testattempt_testresult"),
    ]

    operations = [
        migrations.RunPython(seed_sample_test_data, migrations.RunPython.noop),
    ]
