from schemas.cypher import CypherTemplate


def log_low_score_warning(
    query: str, templates: list[CypherTemplate], scores: list[float], threshold: float
) -> None:
    """
    Логирует предупреждение, если скор топ‑результата ниже порогового.

    Parameters
    ----------
    query : str
        Исходный запрос.
    templates : List[CypherTemplate]
        Список найденных темплейтов.
    scores : List[float]
        Список скорoв, соответствующих найденным темплейтам.
    threshold : float
        Пороговый скор.
    """
    print("⚠️ Warning: top result score below threshold!")
    print(f"Query: {query}")
    print("Results:")
    for template, score in sorted(zip(templates, scores), key=lambda x: -x[1]):
        print(f"- {template.properties['name']} (score: {score:.4f})")
