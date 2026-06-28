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


def test_format_pc_rules_decodes_timemap_separator():
    # The router returns '<' as the HTML entity '&#60' in the per-rule timemap.
    rule = ParentalControlRule(
        mac="AA:BB:CC:DD:EE:FF", name="x", type=PCRuleType.TIME,
        timemap="W10109001700&#60W10309001700",
    )
    out = format_pc_rules({"rules": {"AA:BB:CC:DD:EE:FF": rule}})
    assert out[0]["timemap"] == "W10109001700<W10309001700"


def test_build_timemap_rejects_unknown_day():
    with pytest.raises(ValueError):
        build_timemap(["Funday"], "21:00", "07:00")


def test_build_timemap_rejects_bad_time():
    with pytest.raises(ValueError):
        build_timemap(["Mon"], "25:00", "07:00")


def test_build_timemap_rejects_empty_days():
    with pytest.raises(ScheduleEncodingError):
        build_timemap([], "21:00", "07:00")


def test_build_timemap_rejects_empty_days_short():
    with pytest.raises(ScheduleEncodingError):
        build_timemap([], "09:00", "17:00")


# Ground-truth vectors captured from the router's own weekSchedule.js encoder
# (Sunday=0 ... Saturday=6), verified round-tripping against an RT-AX55.
@pytest.mark.parametrize("days,start,end,expected", [
    (["Mon"], "21:00", "07:00", "W10121000700"),       # overnight, end < start
    (["Tue"], "21:00", "07:00", "W10221000700"),
    (["Mon"], "09:00", "17:00", "W10109001700"),
    (["Sun"], "00:00", "24:00", "W10000002400"),        # all day, end-of-day = 24:00
    (["Sat"], "22:30", "06:15", "W10622300615"),        # with minutes
    (["Mon", "Wed"], "09:00", "17:00", "W10109001700<W10309001700"),  # multi-day, sorted
])
def test_build_timemap_encodes_known_schedules(days, start, end, expected):
    assert build_timemap(days, start, end) == expected


def test_build_timemap_sorts_and_dedupes_days():
    # Saturday(6) before Monday(1) input, plus a duplicate -> sorted, unique segments.
    assert build_timemap(["Sat", "Mon", "monday"], "09:00", "17:00") == \
        "W10109001700<W10609001700"
