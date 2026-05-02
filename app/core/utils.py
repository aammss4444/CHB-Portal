def convert_credits_to_hours(credits: float, ratio: float) -> float:
    """
    Converts credits to hours based on the provided ratio.
    Default: 1 credit = 1 hour (ratio=1.0)
    """
    return credits * ratio
