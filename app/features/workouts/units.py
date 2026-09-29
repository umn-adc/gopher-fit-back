"""Weight units. Personal records and rankings compare kilograms."""

from typing import Literal

WeightUnit = Literal["kg", "lb"]
KG_PER_LB = 0.45359237  # Exact international avoirdupois pound.


def kilograms(weight: float | None, unit: str | None) -> float | None:
    """Weight in kilograms, or None when the weight or its unit is unknown."""
    if weight is None:
        return None
    if unit == "kg":
        return weight
    if unit == "lb":
        return weight * KG_PER_LB
    return None
