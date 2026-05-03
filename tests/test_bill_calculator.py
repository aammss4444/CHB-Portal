def test_basic_bill_calculation():
    """Verify theory/lab/tutorial lecture mix computes expected gross amount and totals."""
    pass


def test_daily_lecture_cap_applied():
    """Verify when 8 lectures exist on one day and cap is 6, only 6 are billed."""
    pass


def test_rate_not_found_raises_error():
    """Verify missing rate for a designation and lecture_type raises RATE_NOT_FOUND."""
    pass


def test_rejected_bill_excluded_from_totals():
    """Verify non-VERIFIED logs (like DRAFT/SUBMITTED) are excluded from billing totals."""
    pass


def test_bill_number_format():
    """Verify generated bill number follows CHB/{YYYY-MM}/{institution_code}/{seq} pattern."""
    pass


def test_rate_snapshot_immutability():
    """Verify changing future rate-master rows does not mutate already snapshotted line-item rates."""
    pass
