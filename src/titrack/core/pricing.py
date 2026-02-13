"""Pricing calculation utilities.

Centralized helpers for item value calculations, trade tax, and price formatting.
"""

from typing import Optional

from titrack.parser.patterns import FE_CONFIG_BASE_ID


def get_item_value(
    config_base_id: int,
    quantity: int,
    price_fe: Optional[float],
    apply_trade_tax: bool = False,
    trade_tax_multiplier: float = 1.0,
) -> Optional[float]:
    """Calculate the total value of an item quantity.

    Args:
        config_base_id: Item's ConfigBaseId
        quantity: Item quantity
        price_fe: Price per unit in FE (can be None)
        apply_trade_tax: Whether to apply trade tax (non-FE items only)
        trade_tax_multiplier: Trade tax multiplier (default 1.0 = no tax, 0.875 = 12.5% tax)

    Returns:
        Total value in FE, or None if no price available
    """
    # FE currency is always worth 1:1
    if config_base_id == FE_CONFIG_BASE_ID:
        return float(quantity)

    # No price data available
    if price_fe is None:
        return None

    # Base value
    total_value = price_fe * quantity

    # Apply trade tax to non-FE items if requested
    if apply_trade_tax and config_base_id != FE_CONFIG_BASE_ID:
        total_value *= trade_tax_multiplier

    return total_value


def normalize_price(config_base_id: int, price_fe: Optional[float]) -> Optional[float]:
    """Normalize a price value (FE is always 1.0, others pass through).

    Args:
        config_base_id: Item's ConfigBaseId
        price_fe: Price per unit in FE (can be None)

    Returns:
        Normalized price (1.0 for FE, original value for others)
    """
    if config_base_id == FE_CONFIG_BASE_ID:
        return 1.0
    return price_fe


def apply_trade_tax(value_fe: float, trade_tax_multiplier: float = 0.875) -> float:
    """Apply trade tax to a value.

    Args:
        value_fe: Value in FE
        trade_tax_multiplier: Trade tax multiplier (default 0.875 = 12.5% tax)

    Returns:
        Value after trade tax
    """
    return value_fe * trade_tax_multiplier
