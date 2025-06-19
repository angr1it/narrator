def cypher_escape(value):
    """Экранирует строку для Cypher:  ' → \',  \\ → \\\\"""
    if isinstance(value, str):
        return value.replace("\\", "\\\\").replace("'", "\\'")
    return value
