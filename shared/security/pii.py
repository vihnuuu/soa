from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


@lru_cache(maxsize=1)
def get_analyzer():
    analyzer = AnalyzerEngine(
        supported_languages=["en"]
    )

    analyzer.registry.add_recognizer(
        PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[
                Pattern(
                    name="ua_phone",
                    regex=r"(?<!\w)(?:\+380\d{9}|0\d{9})(?!\w)",
                    score=0.9,
                )
            ],
            supported_language="en",
        )
    )
    return analyzer


@lru_cache(maxsize=1)
def get_anonymizer():
    return AnonymizerEngine()


def detect_pii(text: str):
    return get_analyzer().analyze(
        text=text,
        language="en",
        entities=["EMAIL_ADDRESS", "PHONE_NUMBER"],
        score_threshold=0.5,
    )


def anonymize_text(text: str) -> str:
    results = detect_pii(text)
    if not results:
        return text

    return get_anonymizer().anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "DEFAULT": OperatorConfig(
                "replace", {"new_value": "[PII_REDACTED]"}
            )
        },
    ).text


def check_pii_leak(text: str) -> bool:
    return bool(detect_pii(text))


def anonymize_data(value):
    if isinstance(value, str):
        return anonymize_text(value)

    if isinstance(value, dict):
        return {
            key: anonymize_data(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [anonymize_data(item) for item in value]

    if isinstance(value, tuple):
        return tuple(anonymize_data(item) for item in value)

    return value