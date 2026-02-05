"""Tests for delta calculator."""

from datetime import datetime

import pytest

from titrack.core.delta_calculator import DeltaCalculator
from titrack.core.models import (
    EventContext,
    ParsedBagEvent,
    SlotKey,
    SlotState,
)


@pytest.fixture
def calculator():
    """Create a fresh calculator for each test."""
    return DeltaCalculator()


class TestDeltaCalculator:
    """Tests for DeltaCalculator."""

    def test_new_slot_creates_delta(self, calculator):
        event = ParsedBagEvent(
            page_id=102,
            slot_id=0,
            config_base_id=100300,
            num=500,
            raw_line="test",
        )
        delta, state = calculator.process_event(
            event=event,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=1,
        )
        assert delta is not None
        assert delta.delta == 500
        assert delta.config_base_id == 100300
        assert delta.context == EventContext.PICK_ITEMS

    def test_same_item_update_computes_difference(self, calculator):
        # First event - establish state
        event1 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=500, raw_line="test"
        )
        calculator.process_event(
            event=event1,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=1,
        )

        # Second event - should compute delta
        event2 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=550, raw_line="test"
        )
        delta, state = calculator.process_event(
            event=event2,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=1,
        )
        assert delta is not None
        assert delta.delta == 50  # 550 - 500

    def test_no_delta_when_no_change(self, calculator):
        event1 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=500, raw_line="test"
        )
        calculator.process_event(
            event=event1,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=1,
        )

        # Same values
        event2 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=500, raw_line="test"
        )
        delta, state = calculator.process_event(
            event=event2,
            context=EventContext.OTHER,
            proto_name=None,
            run_id=1,
        )
        assert delta is None

    def test_slot_swap_creates_delta_for_new_item(self, calculator):
        # Slot has item A
        event1 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=500, raw_line="test"
        )
        calculator.process_event(
            event=event1,
            context=EventContext.OTHER,
            proto_name=None,
            run_id=1,
        )

        # Slot now has item B
        event2 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=200100, num=10, raw_line="test"
        )
        delta, state = calculator.process_event(
            event=event2,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=1,
        )
        assert delta is not None
        assert delta.config_base_id == 200100
        assert delta.delta == 10

    def test_empty_slot_no_delta(self, calculator):
        event = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=0, raw_line="test"
        )
        delta, state = calculator.process_event(
            event=event,
            context=EventContext.OTHER,
            proto_name=None,
            run_id=None,
        )
        assert delta is None

    def test_load_state(self, calculator):
        states = [
            SlotState(
                page_id=102,
                slot_id=0,
                config_base_id=100300,
                num=1000,
                updated_at=datetime.now(),
            ),
        ]
        calculator.load_state(states)

        # Event should compute delta from loaded state
        event = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=1050, raw_line="test"
        )
        delta, state = calculator.process_event(
            event=event,
            context=EventContext.PICK_ITEMS,
            proto_name="PickItems",
            run_id=1,
        )
        assert delta is not None
        assert delta.delta == 50

    def test_get_all_states(self, calculator):
        events = [
            ParsedBagEvent(page_id=102, slot_id=0, config_base_id=100300, num=500, raw_line="test"),
            ParsedBagEvent(page_id=102, slot_id=1, config_base_id=200100, num=10, raw_line="test"),
        ]
        for event in events:
            calculator.process_event(
                event=event,
                context=EventContext.OTHER,
                proto_name=None,
                run_id=None,
            )

        states = calculator.get_all_states()
        assert len(states) == 2

    def test_negative_delta_on_decrease(self, calculator):
        event1 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=500, raw_line="test"
        )
        calculator.process_event(
            event=event1,
            context=EventContext.OTHER,
            proto_name=None,
            run_id=None,
        )

        event2 = ParsedBagEvent(
            page_id=102, slot_id=0, config_base_id=100300, num=400, raw_line="test"
        )
        delta, state = calculator.process_event(
            event=event2,
            context=EventContext.OTHER,
            proto_name=None,
            run_id=None,
        )
        assert delta is not None
        assert delta.delta == -100
