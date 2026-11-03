from django.db import migrations, models
import django.db.models.deletion


def create_options(apps, schema_editor):
    Question = apps.get_model("report_cards", "Question")
    Option = apps.get_model("report_cards", "Option")
    database = schema_editor.connection.alias

    for question in Question.objects.using(database).iterator():
        for label, field_name in zip(
            ("A", "B", "C", "D"),
            ("option_a", "option_b", "option_c", "option_d"),
        ):
            Option.objects.using(database).create(
                question_id=question.pk,
                option_text=getattr(question, field_name),
                is_answer=question.correct_option == label,
            )


def restore_question_options(apps, schema_editor):
    Question = apps.get_model("report_cards", "Question")
    Option = apps.get_model("report_cards", "Option")
    database = schema_editor.connection.alias
    fields = ("option_a", "option_b", "option_c", "option_d")
    labels = ("A", "B", "C", "D")

    for question in Question.objects.using(database).iterator():
        options = list(
            Option.objects.using(database)
            .filter(question_id=question.pk)
            .order_by("pk")[:4]
        )
        for field_name, option in zip(fields, options):
            setattr(question, field_name, option.option_text)
        answer_index = next(
            (index for index, option in enumerate(options) if option.is_answer),
            0,
        )
        question.correct_option = labels[answer_index]
        question.save(
            using=database,
            update_fields=(*fields[: len(options)], "correct_option"),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0004_seed_sample_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="Option",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("option_text", models.CharField(max_length=255)),
                ("is_answer", models.BooleanField(default=False)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="options",
                        to="report_cards.question",
                    ),
                ),
            ],
        ),
        migrations.RunPython(create_options, restore_question_options),
        migrations.RemoveField(
            model_name="question",
            name="option_a",
        ),
        migrations.RemoveField(
            model_name="question",
            name="option_b",
        ),
        migrations.RemoveField(
            model_name="question",
            name="option_c",
        ),
        migrations.RemoveField(
            model_name="question",
            name="option_d",
        ),
        migrations.RemoveField(
            model_name="question",
            name="correct_option",
        ),
    ]
