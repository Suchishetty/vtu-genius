import json
import logging
import re

from .services import AIService


logger = logging.getLogger(__name__)


SEMANTIC_GROUPING_INSTRUCTIONS = """
Group only the supplied historical question strings by the same underlying
subject topic. Do not invent historical questions, years, frequencies, or
facts. Exact or near-exact wording should share a group. Return JSON only in
this format:
{"groups": [{"topic": "short topic label", "question_numbers": [1, 2]}]}
Every question number must refer to the supplied list. Include every number
exactly once. Keep topic labels grounded in the supplied wording.
"""


class PreviousYearAnalysisService:
    """Extract and analyze cached student-owned question-paper content."""

    SUPPORTED_MARKS = {2, 5, 10, 15, 20}
    STOP_WORDS = {
        "a", "an", "and", "are", "as", "be", "by", "define", "describe",
        "discuss", "explain", "for", "give", "how", "in", "is", "of", "on",
        "the", "to", "what", "with", "write", "short", "question", "used",
    }

    @classmethod
    def extract_questions(cls, text):
        """Parse numbered questions and lettered subquestions without rewriting them."""
        questions = []
        current = None
        lines = [line.strip() for line in (text or "").splitlines()]

        for line in lines:
            if not line:
                continue
            main_match = re.match(
                r"^(?:question\s*)?(\d{1,3})\s*[.)\-:]\s*(.+)$",
                line,
                re.IGNORECASE,
            )
            sub_match = re.match(r"^\(?([a-z])\s*[.)\-:]\s*(.+)$", line, re.IGNORECASE)
            if main_match:
                cls._append_question(questions, current)
                current = {
                    "number": main_match.group(1),
                    "text": main_match.group(2).strip(),
                    "marks": cls._extract_marks(line),
                }
            elif sub_match and current:
                cls._append_question(questions, current)
                current = {
                    "number": f"{current['number']}({sub_match.group(1).lower()})",
                    "text": sub_match.group(2).strip(),
                    "marks": cls._extract_marks(line),
                }
            elif current:
                current["text"] = f"{current['text']} {line}".strip()
                if not current.get("marks"):
                    current["marks"] = cls._extract_marks(line)

        cls._append_question(questions, current)
        return questions

    @staticmethod
    def _append_question(questions, question):
        if not question or len(question.get("text", "")) < 3:
            return
        question["text"] = re.sub(r"\s+", " ", question["text"]).strip()
        questions.append(question)

    @staticmethod
    def _extract_marks(text):
        match = re.search(
            r"(?:\[\s*(\d{1,2})\s*\]|\(\s*(\d{1,2})\s*(?:marks?|m)\s*\)|\b(\d{1,2})\s*marks?\b)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return ""
        return next(value for value in match.groups() if value)

    @classmethod
    def analyze(cls, papers, unit_mapper=None):
        records = []
        for paper in papers:
            paper_questions = paper.extracted_questions or cls.extract_questions(
                paper.extracted_text
            )
            for question in paper_questions:
                record = {
                    "paper_id": paper.pk,
                    "year": paper.year,
                    "exam_type": paper.get_exam_type_display(),
                    "number": question.get("number", ""),
                    "text": question.get("text", ""),
                    "marks": question.get("marks", ""),
                    "unit": "Unit not identified",
                }
                if unit_mapper:
                    try:
                        record["unit"] = unit_mapper(record["text"]) or "Unit not identified"
                    except Exception:
                        logger.exception("Unit mapping failed for paper_id=%s", paper.pk)
                records.append(record)

        exact_groups = cls._exact_groups(records)
        topic_groups, semantic_available = cls._topic_groups(records)
        unit_trends = {}
        marks_trends = {str(mark): 0 for mark in sorted(cls.SUPPORTED_MARKS)}
        year_questions = {}
        for record in records:
            unit = record["unit"]
            if unit != "Unit not identified":
                unit_trends[unit] = unit_trends.get(unit, 0) + 1
            if record["marks"].isdigit() and int(record["marks"]) in cls.SUPPORTED_MARKS:
                marks_trends[record["marks"]] += 1
            year_questions.setdefault(str(record["year"]), []).append(record["text"])

        return {
            "records": records,
            "papers_analyzed": len(papers),
            "question_count": len(records),
            "repeated_questions": [group for group in exact_groups if group["paper_count"] > 1],
            "topics": topic_groups,
            "unit_trends": unit_trends,
            "unit_mapping_available": bool(unit_trends),
            "marks_trends": marks_trends,
            "year_questions": dict(sorted(year_questions.items(), reverse=True)),
            "semantic_grouping_available": semantic_available,
        }

    @classmethod
    def _exact_groups(cls, records):
        groups = {}
        for record in records:
            key = cls._normalize(record["text"])
            if not key:
                continue
            group = groups.setdefault(key, {
                "question": record["text"],
                "years": set(),
                "paper_ids": set(),
                "appearances": 0,
            })
            group["years"].add(record["year"])
            group["paper_ids"].add(record["paper_id"])
            group["appearances"] += 1
        result = []
        for group in groups.values():
            result.append({
                "question": group["question"],
                "appearances": group["appearances"],
                "paper_count": len(group["paper_ids"]),
                "years": sorted(group["years"]),
            })
        return sorted(result, key=lambda item: (-item["paper_count"], -item["appearances"], item["question"]))

    @classmethod
    def _topic_groups(cls, records):
        if not records:
            return [], False
        groups = cls._semantic_groups(records)
        if groups:
            return groups, True

        local = {}
        for record in records:
            key = cls._local_topic_key(record["text"])
            if not key:
                continue
            group = local.setdefault(key, {
                "topic": record["text"],
                "appearances": 0,
                "years": set(),
                "questions": [],
            })
            group["appearances"] += 1
            group["years"].add(record["year"])
            if record["text"] not in group["questions"]:
                group["questions"].append(record["text"])
        return cls._finalize_topics(local.values()), False

    @classmethod
    def _semantic_groups(cls, records):
        numbered = "\n".join(f"{index}. {record['text']}" for index, record in enumerate(records, 1))
        prompt = f"Group these supplied historical questions:\n{numbered}"
        try:
            response = AIService().generate_response(
                prompt,
                system_instructions=SEMANTIC_GROUPING_INSTRUCTIONS,
            )
            payload = response.strip().replace("```json", "").replace("```", "").strip()
            groups = json.loads(payload).get("groups", [])
        except Exception:
            logger.info("Ollama semantic grouping unavailable; using local grouping")
            return []

        finalized = []
        seen = set()
        for group in groups:
            indexes = group.get("question_numbers", [])
            valid_indexes = [index for index in indexes if isinstance(index, int) and 1 <= index <= len(records)]
            if not valid_indexes:
                continue
            valid_indexes = [index for index in valid_indexes if index not in seen]
            if not valid_indexes:
                continue
            seen.update(valid_indexes)
            selected = [records[index - 1] for index in valid_indexes]
            finalized.append({
                "topic": str(group.get("topic") or selected[0]["text"]).strip(),
                "appearances": len(selected),
                "years": sorted({record["year"] for record in selected}),
                "questions": list(dict.fromkeys(record["text"] for record in selected)),
            })
        if len(seen) < len(records):
            return []
        return sorted(finalized, key=lambda item: (-item["appearances"], item["topic"]))

    @classmethod
    def _finalize_topics(cls, groups):
        return sorted([
            {
                "topic": group["topic"],
                "appearances": group["appearances"],
                "years": sorted(group["years"]),
                "questions": group["questions"],
            }
            for group in groups
        ], key=lambda item: (-item["appearances"], item["topic"]))

    @classmethod
    def _local_topic_key(cls, text):
        words = [
            word for word in re.findall(r"[a-z0-9]+", text.lower())
            if word not in cls.STOP_WORDS and len(word) > 2
        ]
        return " ".join(sorted(set(words))[:6])

    @staticmethod
    def _normalize(text):
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
