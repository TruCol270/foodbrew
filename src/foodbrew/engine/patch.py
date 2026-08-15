"""The closed patch vocabulary (spec §7). Pure — applying a patch returns a new
Formulation and touches nothing else.

A patch is `{"ops": [{"op": "...", ...}, ...]}`. The list is closed and every
op validates its own arguments, which is what makes spec §13's contract test
("applying any auto-variant patch yields a formulation that re-evaluates
without error") a statement about a finite set rather than about arbitrary
JSON. Nothing outside `engine/variants.py` ever constructs one, and the API
applies a *stored* suggestion by id rather than accepting a patch body — so an
HTTP client cannot reach this module with input of its own (plan decision #2).

A patch never touches the recipe. Spec §12 item 1: recipe pH is a worst-case
minimum over wet ingredients, not a mixing model, so an engine that removed an
acid ingredient could not honestly report the resulting pH. §7's "raise recipe
pH" entry is therefore a note, not a patch (plan decision #4).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from foodbrew.engine.conventions import phase_for_format
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.types import (
    DwellProfile,
    Format,
    Formulation,
    Phase,
    SelectedEnzyme,
)


class PatchOp(StrEnum):
    """Spec §7's fix catalogue, expressed as the smallest closed set that covers it."""

    SET_FORMAT = "set_format"
    SET_DWELL_PROFILE = "set_dwell_profile"
    SET_ENZYME_ADDITION_INDEX = "set_enzyme_addition_index"
    SET_ENZYME_PHASE = "set_enzyme_phase"
    SET_ENZYME_ENCAPSULATED = "set_enzyme_encapsulated"
    SET_ENZYME_DOSE = "set_enzyme_dose"
    ADD_ENZYME = "add_enzyme"
    REMOVE_ENZYME = "remove_enzyme"
    SWAP_ENZYME = "swap_enzyme"
    REMOVE_TRIGGER_FOOD = "remove_trigger_food"


#: Spec §6.1 R6 — what each format implies about encapsulation. A format absent
#: from this map leaves the flag alone: `premixed_wet` is the format where the
#: founder's own choice to encapsulate is meaningful on its own.
_ENCAPSULATION_FOR_FORMAT: Mapping[Format, bool] = {
    Format.ENCAPSULATED_IN_WET: True,
    Format.DUAL_CHAMBER: False,
    Format.DRY_SACHET: False,
}


def set_format(fmt: Format) -> dict:
    """The canonical format-change patch. `format_search` builds its ladder
    candidates with this, so a recommendation and its applied result cannot
    disagree (plan decision #5)."""
    return {"ops": [{"op": PatchOp.SET_FORMAT.value, "value": fmt.value}]}


def canonical(patch: Mapping[str, Any] | None) -> str:
    """Stable text for a patch, used as the dedupe key (plan decision #14)."""
    if patch is None:
        return ""
    return json.dumps(patch, sort_keys=True, separators=(",", ":"))


def _selection_index(formulation: Formulation, enzyme_id: str) -> int:
    for index, selected in enumerate(formulation.enzymes):
        if selected.enzyme_id == enzyme_id:
            return index
    raise ValidationRejection(f"'{enzyme_id}' is not selected on this formulation.")


def _replace_selection(formulation: Formulation, index: int, **changes) -> Formulation:
    enzymes = list(formulation.enzymes)
    enzymes[index] = dataclasses.replace(enzymes[index], **changes)
    return dataclasses.replace(formulation, enzymes=tuple(enzymes))


def _op_set_format(formulation: Formulation, raw: Mapping) -> Formulation:
    try:
        fmt = Format(raw["value"])
    except (KeyError, ValueError) as exc:
        raise ValidationRejection(f"Unknown format '{raw.get('value')}'.") from exc

    phase = phase_for_format(fmt)
    implied = _ENCAPSULATION_FOR_FORMAT.get(fmt)
    enzymes = tuple(
        dataclasses.replace(
            selected,
            phase=phase,
            encapsulated=selected.encapsulated if implied is None else implied,
        )
        for selected in formulation.enzymes
    )
    return dataclasses.replace(formulation, format=fmt, enzymes=enzymes)


def _op_set_dwell_profile(formulation: Formulation, raw: Mapping) -> Formulation:
    value = raw.get("value")
    if value is None:
        return dataclasses.replace(formulation, dwell_profile=None)
    try:
        return dataclasses.replace(formulation, dwell_profile=DwellProfile(value))
    except ValueError as exc:
        raise ValidationRejection(f"Unknown use occasion '{value}'.") from exc


def _op_set_enzyme_addition_index(formulation: Formulation, raw: Mapping) -> Formulation:
    value = raw.get("value")
    if value is None:
        raise ValidationRejection("An enzyme addition point is required.")
    try:
        index = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationRejection(f"'{value}' is not a valid addition point.") from exc
    return dataclasses.replace(formulation, enzyme_addition_index=index)


def _op_set_enzyme_phase(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    try:
        phase = Phase(raw["value"])
    except (KeyError, ValueError) as exc:
        raise ValidationRejection(f"Unknown phase '{raw.get('value')}'.") from exc
    return _replace_selection(formulation, index, phase=phase)


def _op_set_enzyme_encapsulated(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    return _replace_selection(formulation, index, encapsulated=bool(raw["value"]))


def _parse_dose(value: Any) -> float | None:
    """Coerce and validate a dose the same way at every op that accepts one —
    `set_enzyme_dose`, `add_enzyme`, and `swap_enzyme` all route through this
    rather than each repeating (and, as `add_enzyme`/`swap_enzyme` once did,
    silently skipping) the negative-dose check."""
    if value is None:
        return None
    try:
        dose = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationRejection(f"'{value}' is not a valid dose.") from exc
    if dose < 0:
        raise ValidationRejection("A dose cannot be negative.")
    return dose


def _op_set_enzyme_dose(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    return _replace_selection(formulation, index, dose=_parse_dose(raw.get("value")))


def _op_add_enzyme(formulation: Formulation, raw: Mapping) -> Formulation:
    enzyme_id = raw["enzyme_id"]
    if any(s.enzyme_id == enzyme_id for s in formulation.enzymes):
        return formulation
    addition = SelectedEnzyme(
        enzyme_id=enzyme_id,
        dose=_parse_dose(raw.get("dose")),
        phase=phase_for_format(formulation.format),
        encapsulated=_ENCAPSULATION_FOR_FORMAT.get(formulation.format, False),
        source_choice=raw.get("source_choice", ""),
    )
    return dataclasses.replace(formulation, enzymes=(*formulation.enzymes, addition))


def _op_remove_enzyme(formulation: Formulation, raw: Mapping) -> Formulation:
    enzyme_id = raw["enzyme_id"]
    remaining = tuple(s for s in formulation.enzymes if s.enzyme_id != enzyme_id)
    if len(remaining) == len(formulation.enzymes):
        raise ValidationRejection(f"'{enzyme_id}' is not selected on this formulation.")
    return dataclasses.replace(formulation, enzymes=remaining)


def _op_swap_enzyme(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    replacement = raw["replacement_id"]
    if any(s.enzyme_id == replacement for s in formulation.enzymes):
        return _op_remove_enzyme(formulation, {"enzyme_id": raw["enzyme_id"]})
    return _replace_selection(
        formulation,
        index,
        enzyme_id=replacement,
        dose=_parse_dose(raw.get("dose")),
        source_choice=raw.get("source_choice", ""),
    )


def _op_remove_trigger_food(formulation: Formulation, raw: Mapping) -> Formulation:
    food_id = raw["food_id"]
    remaining = tuple(f for f in formulation.target_trigger_food_ids if f != food_id)
    return dataclasses.replace(formulation, target_trigger_food_ids=remaining)


_HANDLERS = {
    PatchOp.SET_FORMAT: _op_set_format,
    PatchOp.SET_DWELL_PROFILE: _op_set_dwell_profile,
    PatchOp.SET_ENZYME_ADDITION_INDEX: _op_set_enzyme_addition_index,
    PatchOp.SET_ENZYME_PHASE: _op_set_enzyme_phase,
    PatchOp.SET_ENZYME_ENCAPSULATED: _op_set_enzyme_encapsulated,
    PatchOp.SET_ENZYME_DOSE: _op_set_enzyme_dose,
    PatchOp.ADD_ENZYME: _op_add_enzyme,
    PatchOp.REMOVE_ENZYME: _op_remove_enzyme,
    PatchOp.SWAP_ENZYME: _op_swap_enzyme,
    PatchOp.REMOVE_TRIGGER_FOOD: _op_remove_trigger_food,
}


def apply_patch(formulation: Formulation, patch: Mapping[str, Any] | None) -> Formulation:
    """Apply every op in order and return the result. Never mutates the input."""
    if patch is None:
        raise ValidationRejection("This suggestion is a note — there is nothing to apply.")

    ops = patch.get("ops")
    if not isinstance(ops, Sequence) or isinstance(ops, str) or not ops:
        raise ValidationRejection("This suggestion carries no change to apply.")

    result = formulation
    for raw in ops:
        if not isinstance(raw, Mapping) or "op" not in raw:
            raise ValidationRejection("Malformed change in this suggestion.")
        try:
            op = PatchOp(raw["op"])
        except ValueError as exc:
            raise ValidationRejection(f"Unknown change '{raw['op']}'.") from exc
        try:
            result = _HANDLERS[op](result, raw)
        except KeyError as exc:
            raise ValidationRejection(f"'{op.value}' is missing {exc}.") from exc
    return result
