from datetime import datetime, timedelta
import re


class ExamModePlanner:
    """Build a bounded last-day plan from already retrieved student-owned data."""

    def build_plan(self, subject, hours, confidence, note_chunks, previous_analysis=None, exam_date=None):
        previous_analysis = previous_analysis or {}
        topics = self._build_topics(note_chunks, previous_analysis)
        repeated_questions = [
            item["question"]
            for item in previous_analysis.get("repeated_questions", [])
        ]
        if not repeated_questions:
            repeated_questions = [
                question
                for topic in previous_analysis.get("topics", [])
                for question in topic.get("questions", [])[:1]
            ]

        total_minutes = int(round(hours * 60))
        final_minutes = min(30, total_minutes)
        study_minutes = max(0, total_minutes - final_minutes)
        if not topics:
            topics = [{
                "name": "Review the retrieved note material",
                "unit": "Unit not identified",
                "priority": "HIGH",
                "reason": "Supported by your uploaded notes.",
                "previous_year_appearances": 0,
            }]
        allocations = self._allocate(topics, study_minutes)
        schedule = self._schedule(allocations, final_minutes)
        return {
            "subject": subject,
            "exam_date": str(exam_date) if exam_date else "",
            "hours": hours,
            "confidence": confidence,
            "total_minutes": total_minutes,
            "study_minutes": sum(item["minutes"] for item in allocations) + final_minutes,
            "topics": allocations,
            "schedule": schedule,
            "questions": repeated_questions[:10],
            "previous_year_available": bool(previous_analysis.get("papers_analyzed")),
            "previous_year_message": (
                "Prioritization includes your uploaded previous-year papers."
                if previous_analysis.get("papers_analyzed")
                else "No previous-year question papers are available. Prioritization is based on your uploaded notes."
            ),
            "final_checklist": [
                "Recall key definitions and core concepts.",
                "Review important diagrams, architectures, or process steps found in the notes.",
                "Revisit frequently appearing questions from your uploaded papers." if repeated_questions else "Quickly recall the major note headings and unit summaries.",
                "Finish with a short self-test without opening the notes.",
            ],
        }

    def _build_topics(self, chunks, previous_analysis):
        previous_topics = previous_analysis.get("topics", [])
        previous_evidence = [
            (topic.get("topic", ""), topic.get("appearances", 0))
            for topic in previous_topics
        ] + [
            (item.get("question", ""), item.get("paper_count", 0))
            for item in previous_analysis.get("repeated_questions", [])
        ]
        topics = []
        seen = set()
        for chunk in chunks:
            text = re.sub(r"\s+", " ", chunk.get("text", "")).strip()
            if not text:
                continue
            unit = chunk.get("metadata", {}).get("unit", "Unit not identified") or "Unit not identified"
            name = self._topic_label(text)
            key = re.sub(r"\W+", " ", name.lower()).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            evidence = f"{name} {text}".lower()
            appearances = max(
                (count for phrase, count in previous_evidence
                 if phrase and self._has_topic_overlap(phrase, evidence)),
                default=0,
            )
            priority = "HIGH" if appearances or len(text) > 500 else "MEDIUM"
            topics.append({
                "name": name,
                "unit": unit,
                "priority": priority,
                "reason": "Frequently represented in uploaded paper analysis and notes." if appearances else "Strongly represented in your uploaded notes.",
                "previous_year_appearances": appearances,
            })
        return sorted(topics, key=lambda item: (0 if item["priority"] == "HIGH" else 1, -item["previous_year_appearances"], item["unit"]))

    @staticmethod
    def _has_topic_overlap(phrase, evidence):
        words = {
            word for word in re.findall(r"[a-z0-9]+", phrase.lower())
            if len(word) > 4
        }
        return bool(words and any(word in evidence for word in words))

    @staticmethod
    def _topic_label(text):
        first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
        first_sentence = first_sentence.strip("-:; ")
        if len(first_sentence) > 110:
            first_sentence = f"{first_sentence[:107].rstrip()}..."
        return first_sentence or "Note-supported topic"

    @staticmethod
    def _allocate(topics, study_minutes):
        if not topics or study_minutes <= 0:
            return []
        base = max(15, study_minutes // len(topics))
        allocations = []
        remaining = study_minutes
        for index, topic in enumerate(topics):
            minutes = remaining if index == len(topics) - 1 else min(base, remaining)
            if minutes < 15 and allocations:
                allocations[-1]["minutes"] += minutes
                break
            allocations.append({**topic, "minutes": minutes})
            remaining -= minutes
        return allocations

    @staticmethod
    def _schedule(allocations, final_minutes):
        current = datetime.strptime("09:00", "%H:%M")
        schedule = []
        study_blocks = 0
        for item in allocations:
            end = current + timedelta(minutes=item["minutes"])
            schedule.append({
                "start": current.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "label": f"{item['unit']} - {item['name']}",
                "minutes": item["minutes"],
                "kind": "study",
            })
            current = end
            study_blocks += 1
            if study_blocks % 2 == 0 and item is not allocations[-1]:
                break_end = current + timedelta(minutes=10)
                schedule.append({
                    "start": current.strftime("%H:%M"),
                    "end": break_end.strftime("%H:%M"),
                    "label": "Short break",
                    "minutes": 10,
                    "kind": "break",
                })
                current = break_end
        if final_minutes:
            end = current + timedelta(minutes=final_minutes)
            schedule.append({
                "start": current.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "label": "Final quick revision and self-test",
                "minutes": final_minutes,
                "kind": "final",
            })
        return schedule
