from __future__ import annotations

from decimal import Decimal

from src.risk.models import Direction, Setup


def test_setup_rr_ratio_long():
    setup = Setup(
        ticker="MSFT",
        direction=Direction.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        target=Decimal("115"),
        score=80,
    )
    assert setup.rr_ratio == Decimal("3")


def test_setup_rr_ratio_short():
    setup = Setup(
        ticker="TSLA",
        direction=Direction.SHORT,
        entry=Decimal("200"),
        stop=Decimal("210"),
        target=Decimal("180"),
        score=75,
    )
    assert setup.rr_ratio == Decimal("2")


def test_setup_position_size():
    setup = Setup(
        ticker="AAPL",
        direction=Direction.LONG,
        entry=Decimal("150"),
        stop=Decimal("145"),
        target=Decimal("165"),
        score=70,
    )
    assert setup.position_size(Decimal("10000")) == 66


def test_setup_expected_profit():
    setup = Setup(
        ticker="AAPL",
        direction=Direction.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        target=Decimal("115"),
        score=70,
    )
    profit = setup.expected_profit(Decimal("10000"))
    assert profit == Decimal("1500")  # 100 shares * $15


def test_setup_zero_risk_returns_zero_rr():
    setup = Setup(
        ticker="X",
        direction=Direction.LONG,
        entry=Decimal("50"),
        stop=Decimal("50"),
        target=Decimal("60"),
        score=50,
    )
    assert setup.rr_ratio == Decimal("0")
