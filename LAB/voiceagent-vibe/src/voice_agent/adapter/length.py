_METERS_PER_UNIT = {
    "m": 1.0,
    "km": 1000.0,
    "cm": 0.01,
    "mi": 1609.344,
}

SUPPORTED = set(_METERS_PER_UNIT.keys())


def convert_length(value: float, from_unit: str, to_unit: str) -> float:
    """value를 from_unit에서 to_unit으로 변환한다. 지원 밖 단위면 ValueError."""
    if value < 0:
        raise ValueError("길이는 0 이상이어야 합니다.")

    src = from_unit.strip().lower()
    dst = to_unit.strip().lower()

    for unit in (src, dst):
        if unit not in SUPPORTED:
            raise ValueError(f"지원하지 않는 단위: {unit} (지원: {sorted(SUPPORTED)})")

    meters = value * _METERS_PER_UNIT[src]
    result = meters / _METERS_PER_UNIT[dst]
    return round(result, 6)