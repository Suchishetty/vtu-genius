from django.core.management.base import BaseCommand, CommandError

from accounts.models import StudentProfile
from ai_assistant.rag_service import RAGService
from notes.models import Notes


class Command(BaseCommand):
    help = "Index one PDF note and verify student-isolated ChromaDB retrieval."

    def add_arguments(self, parser):
        parser.add_argument("note_id", type=int)
        parser.add_argument("--question", required=True)
        parser.add_argument("--other-student-id", type=int)

    def handle(self, *args, **options):
        note = Notes.objects.select_related("student").filter(pk=options["note_id"]).first()
        if note is None:
            raise CommandError("The supplied note_id does not exist.")

        rag = RAGService()
        indexed_count = rag.index_note(note)
        owner_results = rag.search_relevant_chunks(
            note.student, options["question"], top_k=5
        )
        stored_chunks = rag.collection.get(
            where={
                "$and": [
                    {"student_id": str(note.student_id)},
                    {"note_id": str(note.pk)},
                ]
            }
        )
        self.stdout.write(f"Indexed chunks: {indexed_count}")
        self.stdout.write(f"Stored chunks for note: {len(stored_chunks.get('ids', []))}")
        self.stdout.write(f"Owner retrieval results: {len(owner_results)}")

        other_student_id = options.get("other_student_id")
        if other_student_id:
            other_student = StudentProfile.objects.filter(pk=other_student_id).first()
            if other_student is None:
                raise CommandError("The supplied other_student_id does not exist.")
            other_results = rag.search_relevant_chunks(
                other_student, options["question"], top_k=5
            )
            leaked_ids = {
                item["metadata"].get("note_id") for item in other_results
            }
            if str(note.pk) in leaked_ids:
                raise CommandError("Isolation check failed: another student retrieved this note.")
            self.stdout.write(self.style.SUCCESS("Isolation check passed."))
        else:
            self.stdout.write(
                "Provide --other-student-id to run the cross-student isolation check."
            )
