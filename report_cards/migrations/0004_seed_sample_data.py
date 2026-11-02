from django.db import migrations


STUDENTS = (
    ("Ava Patel", "ava.patel@example.com", "555-0101"),
    ("Noah Kim", "noah.kim@example.com", "555-0102"),
    ("Mia Garcia", "mia.garcia@example.com", "555-0103"),
    ("Liam Chen", "liam.chen@example.com", "555-0104"),
    ("Zoe Johnson", "zoe.johnson@example.com", "555-0105"),
)

SUBJECTS = {
    "Mathematics": (
        "Numbers, arithmetic, and geometry.",
        (
            ("What is 7 × 8?", ("54", "56", "58", "64"), "B"),
            ("What is the square root of 81?", ("7", "8", "9", "10"), "C"),
            ("How many degrees are in a right angle?", ("45", "90", "180", "360"), "B"),
            ("What is 3/4 expressed as a percentage?", ("25%", "50%", "75%", "80%"), "C"),
        ),
    ),
    "Science": (
        "Foundational questions about the natural world.",
        (
            ("Which planet is known as the Red Planet?", ("Venus", "Mars", "Jupiter", "Mercury"), "B"),
            ("What gas do plants absorb from the atmosphere?", ("Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"), "C"),
            ("What is the chemical symbol for water?", ("CO2", "O2", "H2O", "NaCl"), "C"),
        ),
    ),
    "English": (
        "Grammar, vocabulary, and language skills.",
        (
            ("Which word is a noun?", ("Quickly", "Happiness", "Blue", "Run"), "B"),
            ("What is the plural of 'child'?", ("Childs", "Childes", "Children", "Childrens"), "C"),
            ("Which sentence uses the correct punctuation?", ("Where are you.", "Where are you?", "Where are you!", "Where are you,"), "B"),
        ),
    ),
}


def seed_sample_data(apps, schema_editor):
    Student = apps.get_model("report_cards", "Student")
    Subject = apps.get_model("report_cards", "Subject")
    Question = apps.get_model("report_cards", "Question")
    database = schema_editor.connection.alias

    for name, email, phone in STUDENTS:
        Student.objects.using(database).get_or_create(
            email=email,
            defaults={"name": name, "phone": phone},
        )

    for subject_name, (description, questions) in SUBJECTS.items():
        subject, _ = Subject.objects.using(database).get_or_create(
            name=subject_name,
            defaults={"description": description},
        )
        for question_text, options, correct_option in questions:
            Question.objects.using(database).get_or_create(
                subject=subject,
                question_text=question_text,
                defaults={
                    "option_a": options[0],
                    "option_b": options[1],
                    "option_c": options[2],
                    "option_d": options[3],
                    "correct_option": correct_option,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0003_subject_question_studentprofilechange"),
    ]

    operations = [
        migrations.RunPython(seed_sample_data, migrations.RunPython.noop),
    ]
