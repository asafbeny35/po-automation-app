"""מדבקות "ידני" — קו תחתון במקום המספר, והיחידה אחריו.

בסימון הצ'קבוקס במודאל החלוקה נבחר רק מספר מדבקות; על המדבקה מודפסים כל
הפרטים כרגיל, ובמקום הכמות המספרית — קו תחתון להשלמה בכתב יד ואז היחידה
(מ״ר / יח׳).
"""
from __future__ import annotations

import pytest

import app
from services.label_generator_v2 import quantity_display_text


# ── נרמול שורות החלוקה ───────────────────────────────────────────────────────

def test_a_manual_row_survives_without_a_quantity():
    rows = app._normalize_label_split_rows([
        {"item_index": 0, "label_count": 4, "manual_quantity": True},
    ])
    assert rows == [{"item_index": 0, "label_count": 4, "quantity_per_label": 0.0, "manual_quantity": True}]


def test_a_regular_row_still_requires_a_quantity():
    assert app._normalize_label_split_rows([{"item_index": 0, "label_count": 4}]) == []


def test_regular_rows_keep_their_shape():
    rows = app._normalize_label_split_rows([
        {"item_index": 1, "label_count": 2, "quantity_per_label": 30},
    ])
    assert rows == [{"item_index": 1, "label_count": 2, "quantity_per_label": 30.0, "manual_quantity": False}]


def test_zero_label_count_is_dropped_even_in_manual_mode():
    assert app._normalize_label_split_rows([{"label_count": 0, "manual_quantity": True}]) == []


def test_garbage_rows_are_ignored():
    assert app._normalize_label_split_rows(["x", None, {"label_count": "abc", "manual_quantity": True}]) == []
    assert app._normalize_label_split_rows("not-a-list") == []


# ── שורת הכמות על המדבקה ─────────────────────────────────────────────────────

def test_a_manual_label_shows_an_underline_then_the_unit():
    assert quantity_display_text("________", "מ״ר") == "________ מ״ר"


def test_a_manual_label_with_units_unit():
    assert quantity_display_text("________", "יח׳") == "________ יח׳"


def test_a_regular_label_shows_number_and_explicit_unit():
    assert quantity_display_text(96, "מ״ר") == "96 מ״ר"


def test_without_an_explicit_unit_the_old_default_applies():
    assert quantity_display_text(96, "") == "96 יח׳"


def test_a_quantity_that_already_carries_a_unit_is_untouched():
    assert quantity_display_text('60 מ"ר', "יח׳") == '60 מ"ר'


def test_an_empty_quantity_stays_empty():
    assert quantity_display_text("", "מ״ר") == ""
