from pydantic import BaseModel, Field


class GeneratedEmail(BaseModel):
    """The LLM's raw structured output — before the server appends the unsubscribe
    footer. Never parsed from free text; the provider validates the model returns
    exactly this shape."""

    subject: str
    body: str
    personalization_rationale: str = Field(
        description="One sentence: which specific hook from the supplied context was used."
    )
    needs_more_context: bool = Field(
        default=False,
        description="True if the supplied context had nothing specific enough to personalize on "
        "honestly. When true, subject/body may be minimal placeholders — the caller must "
        "treat this as a hard block, not send it.",
    )


class QualityGateResult(BaseModel):
    passed: bool
    failures: list[str]


class GenerationResult(BaseModel):
    subject: str
    body: str
    personalization_rationale: str
    needs_more_context: bool
    quality_gate: QualityGateResult
