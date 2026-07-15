from scripts.neuip_client import apply_cap


def test_below_cap_returns_total():
    assert apply_cap(980, 1500) == 980


def test_equal_cap_returns_total():
    assert apply_cap(1000, 1000) == 1000


def test_over_cap_returns_cap():
    assert apply_cap(1540, 1000) == 1000


def test_zero_total():
    assert apply_cap(0, 1000) == 0
