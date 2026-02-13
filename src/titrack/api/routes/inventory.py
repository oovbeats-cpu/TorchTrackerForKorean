"""Inventory API routes."""

from enum import Enum

from fastapi import APIRouter, Depends, Query

from titrack.api.dependencies import get_repository
from titrack.api.schemas import InventoryItem, InventoryResponse
from titrack.core.pricing import get_item_value, normalize_price
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class SortField(str, Enum):
    """Inventory sort fields."""
    QUANTITY = "quantity"
    VALUE = "value"
    NAME = "name"
    UNIT_PRICE = "unit_price"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


@router.get("/debug", response_model=dict)
def _debug_slot_states(
    repo: Repository = Depends(get_repository),
) -> dict:
    """Debug endpoint to check slot_state data by PageId."""
    all_states = repo.get_all_slot_states(include_excluded=True)
    
    by_page = {}
    for state in all_states:
        page_id = state.page_id
        if page_id not in by_page:
            by_page[page_id] = []
        by_page[page_id].append({
            "slot_id": state.slot_id,
            "config_base_id": state.config_base_id,
            "num": state.num,
            "player_id": state.player_id,
        })
    
    summary = {page_id: len(items) for page_id, items in by_page.items()}
    
    return {
        "total_states": len(all_states),
        "by_page_count": summary,
        "current_player_id": repo._current_player_id,
        "page_103_items": by_page.get(103, [])[:10],  # First 10 items from PageId 103
    }


@router.get("", response_model=InventoryResponse)
def get_inventory(
    sort_by: SortField = Query(SortField.VALUE, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    repo: Repository = Depends(get_repository),
) -> InventoryResponse:
    """Get current inventory state."""
    states = repo.get_all_slot_states()

    # Aggregate by item
    totals: dict[int, int] = {}
    for state in states:
        if state.num > 0:
            totals[state.config_base_id] = totals.get(state.config_base_id, 0) + state.num

    # Get trade tax multiplier (1.0 if disabled, 0.875 if enabled)
    tax_multiplier = repo.get_trade_tax_multiplier()

    # Build response with prices
    items = []
    total_fe = totals.get(FE_CONFIG_BASE_ID, 0)
    net_worth = float(total_fe)

    for config_id, quantity in totals.items():
        item = repo.get_item(config_id)

        # Use effective price with source (cloud-first, local overrides if newer)
        price_fe, price_source = repo.get_effective_price_with_source(config_id)

        # Normalize FE price and calculate value with trade tax
        price_fe = normalize_price(config_id, price_fe)
        if config_id == FE_CONFIG_BASE_ID:
            price_source = None  # FE has no price source
            total_value = get_item_value(config_id, quantity, price_fe, apply_trade_tax=False)
        else:
            # Apply trade tax to non-FE items (would need to sell them)
            total_value = get_item_value(config_id, quantity, price_fe, apply_trade_tax=True, trade_tax_multiplier=tax_multiplier)

        if total_value and config_id != FE_CONFIG_BASE_ID:
            net_worth += total_value

        items.append(
            InventoryItem(
                config_base_id=config_id,
                name=repo.get_item_name(config_id),
                quantity=quantity,
                icon_url=item.icon_url if item else None,
                price_fe=price_fe,
                total_value_fe=total_value,
                price_source=price_source,
            )
        )

    # Sort based on parameters
    reverse = sort_order == SortOrder.DESC

    if sort_by == SortField.VALUE:
        # Sort by value, items without price go to end
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                x.total_value_fe is None,  # Items without price last
                -(x.total_value_fe or 0) if reverse else (x.total_value_fe or 0),
            )
        )
    elif sort_by == SortField.QUANTITY:
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                -x.quantity if reverse else x.quantity,
            )
        )
    elif sort_by == SortField.NAME:
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                x.name.lower() if not reverse else "",
            ),
            reverse=reverse if sort_by == SortField.NAME else False,
        )
    elif sort_by == SortField.UNIT_PRICE:
        items.sort(
            key=lambda x: (
                x.config_base_id != FE_CONFIG_BASE_ID,  # FE always first
                x.price_fe is None,  # Items without price last
                -(x.price_fe or 0) if reverse else (x.price_fe or 0),
            )
        )

    return InventoryResponse(
        items=items,
        total_fe=total_fe,
        net_worth_fe=round(net_worth, 2),
    )
