from django.urls import path

from . import views


app_name = "ai_assistant"


urlpatterns = [
    path(
        "",
        views.AIAssistantView.as_view(),
        name="assistant",
    ),
    path(
        "ask/",
        views.AskAIView.as_view(),
        name="ask_ai",
    ),
    path(
        "question-generator/",
        views.QuestionGeneratorView.as_view(),
        name="question_generator",
    ),
    path(
        "expected-questions/",
        views.ExpectedQuestionsView.as_view(),
        name="expected_questions",
    ),
    path(
        "previous-year-analysis/",
        views.PreviousYearAnalysisView.as_view(),
        name="previous_year_analysis",
    ),
    path(
        "exam-mode/",
        views.ExamModeView.as_view(),
        name="exam_mode",
    ),
]
