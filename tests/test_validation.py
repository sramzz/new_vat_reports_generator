from app import validate_inputs


def test_rejects_empty_report_name():
    result = validate_inputs("", ["January"], 2026, False)
    assert result is not None and "empty" in result.lower()


def test_rejects_whitespace_report_name():
    result = validate_inputs("   ", ["January"], 2026, False)
    assert result is not None and "empty" in result.lower()


def test_rejects_no_months_selected():
    result = validate_inputs("Q1", [], 2026, False)
    assert result is not None and "month" in result.lower()


def test_quarterly_requires_three_months():
    result = validate_inputs("Q1", ["January", "February"], 2026, True)
    assert result is not None and "3" in result


def test_quarterly_requires_consecutive_months():
    result = validate_inputs("Q1", ["January", "March", "May"], 2026, True)
    assert result is not None and "consecutive" in result.lower()


def test_valid_monthly_passes():
    assert validate_inputs("January 2026", ["January"], 2026, False) is None


def test_valid_quarterly_passes():
    assert validate_inputs("Q1 - March 2026", ["January", "February", "March"], 2026, True) is None
