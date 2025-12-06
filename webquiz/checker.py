"""
Docstring for webquiz.checker

A list of checker functions for different types of questions.
"""

__all__ = [
    "to_int",
    "distance",
    "direction_angle",
]


def to_int(user_answer: str) -> int:
    """Convert user input to integer."""
    return int(user_answer.strip())


def distance(user_answer: str) -> int:
    """
    Calculate the distance from the correct answer.

    Accepted formats:
    - "42"
    - "  42  "
    - "42m"
    - "42м"
    - "2км" (2000 meters)
    - "2km" (2000 meters)
    - "0.5km" (500 meters)
    - "2км." (2000 meters)

    """
    user_answer = user_answer.strip().rstrip(".").lower().replace("км", "km").replace("м", "m")
    try:
        if user_answer.endswith("km"):
            value = float(user_answer[:-2].strip())
            return int(value * 1000)
        elif user_answer.endswith("m"):
            value = float(user_answer[:-1].strip())
            return int(value)
        else:
            return int(float(user_answer))
    except Exception:
        raise ValueError("Неверный формат ответа. Ожидается число, например: '2000', '2000м', '2км'.")


def direction_angle(user_answer: str) -> int:
    """
    Convert user input to direction angle in degrees.

    Accepted formats:
    - "20" (2000)
    - "  20  " (2000)
    - "20-00" (2000)
    """
    user_answer = user_answer.strip()
    parts = user_answer.split("-")
    if len(parts) > 2:
        raise ValueError("Неверный формат ответа. Ожидается число в градусах, например: '2000' или '20-00'.")

    degrees = int(parts[0].strip())
    minutes = int(parts[1].strip()) if len(parts) == 2 else 0
    return degrees * 100 + minutes
