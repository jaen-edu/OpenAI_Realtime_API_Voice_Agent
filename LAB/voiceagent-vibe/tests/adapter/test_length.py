import pytest

from voice_agent.adapter.length import SUPPORTED, convert_length


def test_supported_units():
    assert SUPPORTED == {"m", "km", "cm", "mi"}


def test_kilometers_to_meters():
    # 3km = 3000m
    assert convert_length(value=3, from_unit="km", to_unit="m") == 3000.0


def test_same_unit_is_identity():
    assert convert_length(value=5, from_unit="m", to_unit="m") == 5


def test_miles_round_trip_within_tolerance():
    meters = convert_length(value=1, from_unit="mi", to_unit="m")
    restored = convert_length(value=meters, from_unit="m", to_unit="mi")

    assert meters == pytest.approx(1609.34, abs=0.01)
    assert restored == pytest.approx(1, abs=0.01)


def test_centimeters_to_meters():
    assert convert_length(value=250, from_unit="cm", to_unit="m") == 2.5


def test_rejects_unsupported_unit():
    with pytest.raises(ValueError):
        convert_length(value=1, from_unit="km", to_unit="yd")


def test_rejects_negative_length():
    with pytest.raises(ValueError):
        convert_length(value=-1, from_unit="km", to_unit="m")