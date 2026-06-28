from asusrouter.modules.parental_control import ParentalControlRule, PCRuleType

from tool_helpers import format_pc_rules


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
