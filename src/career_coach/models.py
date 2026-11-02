from typing import Literal

from pydantic import BaseModel, Field, model_validator

RUBRIC = "0: no relevant evidence; 1: partial/unclear; 2: correct with explanation; 3: correct with trade-offs and edge cases."


class Question(BaseModel):
    kind: Literal["technical", "coding", "interview"]
    skill: str
    prompt: str
    criteria: list[str] = Field(min_length=1, max_length=5)
    coding_mode: Literal["write", "review"] | None = None
    code_to_review: str | None = None

    def display_prompt(self, follow_up=None):
        text = follow_up or self.prompt
        if self.code_to_review:
            text += "\n\n```\n" + self.code_to_review + "\n```"
        return text


class Assessment(BaseModel):
    requirements: list[str] = Field(min_length=1, max_length=12)
    questions: list[Question] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def coverage(self):
        if sorted(q.kind for q in self.questions) != [
            "coding",
            "interview",
            "technical",
            "technical",
        ]:
            raise ValueError("Need two technical questions, one coding exercise and one scenario")
        return self


class GeneratedAssessment(Assessment):
    """Stricter generation contract; older stored sessions remain readable."""

    @model_validator(mode="after")
    def coding_material(self):
        for question in self.questions:
            if question.kind != "coding":
                continue
            if question.coding_mode is None:
                raise ValueError("Coding tasks must specify write or review mode")
            if question.coding_mode == "review" and not (
                question.code_to_review and question.code_to_review.strip()
            ):
                raise ValueError("Review tasks must include the complete code_to_review")
        return self


class Evaluation(BaseModel):
    score: int = Field(ge=0, le=3)
    evidence: str = Field(min_length=1)
    feedback: str
    gap: str
    follow_up: str | None


class ModelEvaluation(BaseModel):
    """The model selects an excerpt; only the app supplies the stored quotation."""

    score: int = Field(ge=0, le=3)
    evidence_id: int = Field(ge=0)
    feedback: str
    gap: str
    follow_up: str | None


class Result(BaseModel):
    question: Question
    answers: list[str]
    evaluation: Evaluation


class Session(BaseModel):
    id: str
    created_at: str
    demo: bool
    model: str
    stage: Literal["role", "background", "deadline", "description", "assessment", "complete"] = (
        "role"
    )
    profile: dict[str, str] = Field(default_factory=dict)
    assessment: Assessment | None = None
    index: int = 0
    pending_answer: str | None = None
    follow_up: str | None = None
    results: list[Result] = Field(default_factory=list)
    messages: list[dict[str, str]] = Field(default_factory=list)
    report: str | None = None
