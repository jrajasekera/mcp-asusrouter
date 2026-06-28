import pytest

from asusrouter.modules.parental_control import ParentalControlRule, PCRuleType

from tool_helpers import format_pc_rules, build_timemap, ScheduleEncodingError


def test_format_pc_rules_extracts_fields():
    rule = ParentalControlRule(
        mac="AA:BB:CC:DD:EE:FF", name="Tablet",
        type=PCRuleType.BLOCK, timemap="W03E21000700",
    )
    out = format_pc_rules({"rules": {"AA:BB:CC:DD:EE:FF": rule}})
    assert out == [{
        "mac": "AA:BB:CC:DD:EE:FF", "name": "Tablet",
        "type": "BLOCK", "timemap": "W03E21000700",
    }]


def test_format_pc_rules_handles_empty_and_none():
    assert format_pc_rules(None) == []
    assert format_pc_rules({}) == []
    assert format_pc_rules({"rules": {}}) == []


def test_build_timemap_rejects_unknown_day():
    with pytest.raises(ValueError):
        build_timemap(["Funday"], "21:00", "07:00")


def test_build_timemap_rejects_bad_time():
    with pytest.raises(ValueError):
        build_timemap(["Mon"], "25:00", "07:00")


def test_build_timemap_rejects_empty_days():
    with pytest.raises(ScheduleEncodingError):
        build_timemap([], "21:00", "07:00")


def test_build_timemap_valid_input_raises_until_verified():
    # Encoding is gated on hardware verification; valid input still raises.
    with pytest.raises(ScheduleEncodingError):
        build_timemap(["Mon", "Tue"], "21:00", "07:00")
