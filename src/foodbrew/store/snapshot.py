"""Freeze an EvalContext into JSON and thaw it back.

Spec §4: an evaluation stores a snapshot of all its inputs, and re-running that
snapshot on the same engine version must reproduce byte-identical results. The
snapshot holds the *referenced closure* rather than the whole catalogue (plan
decision #4): every rule reaches a record through an id on the formulation, so
the records named by those ids, plus the substrates they name, plus every GI
region, is everything any rule can read.

JSON is emitted with sorted keys and no incidental whitespace so that two
snapshots of the same inputs are byte-identical strings, which is what makes
"has this evaluation's input changed" a string comparison.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from foodbrew.engine.types import (
    Deadline,
    DwellProfile,
    Enzyme,
    EvalContext,
    Food,
    Format,
    Formulation,
    GIRegion,
    Phase,
    ProcessStep,
    RecipeIngredient,
    SelectedEnzyme,
    SeverityTier,
    StructuralClass,
    StructuralEntry,
    Substrate,
    Tracked,
    TruthLabel,
)

#: Bumped if this file's JSON shape changes in a way old snapshots cannot read.
SNAPSHOT_VERSION = 1


def _t(tracked: Tracked) -> dict:
    return {"value": tracked.value, "status": str(tracked.status), "source": tracked.source}


def _untracked(raw: Mapping | None) -> Tracked:
    if raw is None:
        return Tracked(None, TruthLabel.UNCONFIRMED, "")
    return Tracked(raw["value"], TruthLabel(raw["status"]), raw.get("source", ""))


def _enzyme_out(e: Enzyme) -> dict:
    return {
        "id": e.id, "name": e.name, "aliases": list(e.aliases),
        "substrate_id": e.substrate_id, "source_type": e.source_type,
        "priority": e.priority, "deadline": str(e.deadline),
        "site_of_action": e.site_of_action, "dose_unit": e.dose_unit,
        "dose_benchmark_note": e.dose_benchmark_note,
        "is_protease": e.is_protease, "is_natural_source": e.is_natural_source,
        "food_grade_note": e.food_grade_note, "heat_labile_note": e.heat_labile_note,
        "cost_tier": e.cost_tier, "supplier_note": e.supplier_note, "notes": e.notes,
        "degrades_structural": [
            {"structural_class": str(x.structural_class), "tier": str(x.tier)}
            for x in e.degrades_structural
        ],
        **{
            name: _t(getattr(e, name))
            for name in (
                "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
                "temp_min_c", "temp_max_c", "temp_opt_c",
                "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
            )
        },
    }


def _enzyme_in(raw: Mapping) -> Enzyme:
    return Enzyme(
        id=raw["id"], name=raw["name"], aliases=tuple(raw["aliases"]),
        substrate_id=raw["substrate_id"], source_type=raw["source_type"],
        priority=raw["priority"], deadline=Deadline(raw["deadline"]),
        site_of_action=raw["site_of_action"], dose_unit=raw["dose_unit"],
        dose_benchmark_note=raw["dose_benchmark_note"],
        is_protease=raw["is_protease"], is_natural_source=raw["is_natural_source"],
        food_grade_note=raw["food_grade_note"], heat_labile_note=raw["heat_labile_note"],
        cost_tier=raw["cost_tier"], supplier_note=raw["supplier_note"], notes=raw["notes"],
        degrades_structural=tuple(
            StructuralEntry(StructuralClass(x["structural_class"]), SeverityTier(x["tier"]))
            for x in raw["degrades_structural"]
        ),
        **{
            name: _untracked(raw.get(name))
            for name in (
                "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
                "temp_min_c", "temp_max_c", "temp_opt_c",
                "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
            )
        },
    )


def _food_out(f: Food) -> dict:
    return {
        "id": f.id, "name": f.name, "category": f.category,
        "is_recipe_ingredient": f.is_recipe_ingredient,
        "is_trigger_food": f.is_trigger_food,
        "is_application_food": f.is_application_food,
        "contains_substrate_ids": list(f.contains_substrate_ids),
        "typical_load_unit": f.typical_load_unit,
        "contains_protease": f.contains_protease,
        "is_heat_processed": f.is_heat_processed,
        "structural": [str(s) for s in f.structural],
        "notes": f.notes,
        **{
            name: _t(getattr(f, name))
            for name in ("ph", "water_content_pct", "typical_load_value")
        },
    }


def _food_in(raw: Mapping) -> Food:
    return Food(
        id=raw["id"], name=raw["name"], category=raw["category"],
        is_recipe_ingredient=raw["is_recipe_ingredient"],
        is_trigger_food=raw["is_trigger_food"],
        is_application_food=raw["is_application_food"],
        contains_substrate_ids=tuple(raw["contains_substrate_ids"]),
        typical_load_unit=raw["typical_load_unit"],
        contains_protease=raw["contains_protease"],
        is_heat_processed=raw["is_heat_processed"],
        structural=tuple(StructuralClass(s) for s in raw["structural"]),
        notes=raw["notes"],
        **{
            name: _untracked(raw.get(name))
            for name in ("ph", "water_content_pct", "typical_load_value")
        },
    )


def _formulation_out(f: Formulation) -> dict:
    return {
        "id": f.id, "format": str(f.format),
        "recipe": [
            {"food_id": i.food_id, "amount_g": i.amount_g, "order": i.order} for i in f.recipe
        ],
        "enzymes": [
            {
                "enzyme_id": s.enzyme_id, "dose": s.dose, "phase": str(s.phase),
                "encapsulated": s.encapsulated, "source_choice": s.source_choice,
            }
            for s in f.enzymes
        ],
        "target_trigger_food_ids": list(f.target_trigger_food_ids),
        "application_food_ids": list(f.application_food_ids),
        "dwell_profile": str(f.dwell_profile) if f.dwell_profile else None,
        "serving_size_g": f.serving_size_g,
        "measured_ph": _t(f.measured_ph),
        "process_steps": [
            {"order": s.order, "label": s.label, "is_heat": s.is_heat} for s in f.process_steps
        ],
        "enzyme_addition_index": f.enzyme_addition_index,
        "parent_formulation_id": f.parent_formulation_id,
    }


def _formulation_in(raw: Mapping) -> Formulation:
    return Formulation(
        id=raw["id"], format=Format(raw["format"]),
        recipe=tuple(
            RecipeIngredient(i["food_id"], i["amount_g"], i["order"]) for i in raw["recipe"]
        ),
        enzymes=tuple(
            SelectedEnzyme(
                s["enzyme_id"], s["dose"], Phase(s["phase"]),
                s["encapsulated"], s["source_choice"],
            )
            for s in raw["enzymes"]
        ),
        target_trigger_food_ids=tuple(raw["target_trigger_food_ids"]),
        application_food_ids=tuple(raw["application_food_ids"]),
        dwell_profile=DwellProfile(raw["dwell_profile"]) if raw["dwell_profile"] else None,
        serving_size_g=raw["serving_size_g"],
        measured_ph=_untracked(raw["measured_ph"]),
        process_steps=tuple(
            ProcessStep(s["order"], s["label"], s["is_heat"]) for s in raw["process_steps"]
        ),
        enzyme_addition_index=raw["enzyme_addition_index"],
        parent_formulation_id=raw["parent_formulation_id"],
    )


def referenced_ids(ctx: EvalContext) -> tuple[set[str], set[str], set[str]]:
    """The closure of records this formulation can reach: enzymes, foods, substrates."""
    form = ctx.formulation
    enzyme_ids = {s.enzyme_id for s in form.enzymes}
    food_ids = (
        {i.food_id for i in form.recipe}
        | set(form.target_trigger_food_ids)
        | set(form.application_food_ids)
    )
    substrate_ids = {
        ctx.enzymes[eid].substrate_id for eid in enzyme_ids if eid in ctx.enzymes
    }
    for fid in food_ids:
        food = ctx.foods.get(fid)
        if food is not None:
            substrate_ids |= set(food.contains_substrate_ids)
    return enzyme_ids, food_ids, substrate_ids


def snapshot_from_context(ctx: EvalContext) -> str:
    enzyme_ids, food_ids, substrate_ids = referenced_ids(ctx)
    payload = {
        "snapshot_version": SNAPSHOT_VERSION,
        "formulation": _formulation_out(ctx.formulation),
        "enzymes": {
            eid: _enzyme_out(ctx.enzymes[eid]) for eid in sorted(enzyme_ids) if eid in ctx.enzymes
        },
        "foods": {
            fid: _food_out(ctx.foods[fid]) for fid in sorted(food_ids) if fid in ctx.foods
        },
        "substrates": {
            sid: {
                "id": s.id, "name": s.name,
                "native_human_enzyme": s.native_human_enzyme,
                "is_prebiotic": s.is_prebiotic,
                "no_commercial_enzyme": s.no_commercial_enzyme,
                "notes": s.notes,
            }
            for sid, s in (
                (sid, ctx.substrates[sid]) for sid in sorted(substrate_ids) if sid in ctx.substrates
            )
        },
        "gi_regions": [
            {
                "id": r.id, "name": r.name, "ph_low": r.ph_low, "ph_high": r.ph_high,
                "order": r.order, "dormant": r.dormant, "transit_note": r.transit_note,
            }
            for r in ctx.gi_regions
        ],
        "latest_trial_ph": _t(ctx.latest_trial_ph) if ctx.latest_trial_ph else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def context_from_snapshot(raw: str) -> EvalContext:
    payload = json.loads(raw)
    version = payload.get("snapshot_version")
    if version != SNAPSHOT_VERSION:
        raise ValueError(f"unsupported snapshot_version {version!r}")
    return EvalContext(
        formulation=_formulation_in(payload["formulation"]),
        enzymes={eid: _enzyme_in(e) for eid, e in payload["enzymes"].items()},
        foods={fid: _food_in(f) for fid, f in payload["foods"].items()},
        substrates={
            sid: Substrate(
                id=s["id"], name=s["name"],
                native_human_enzyme=s["native_human_enzyme"],
                is_prebiotic=s["is_prebiotic"],
                no_commercial_enzyme=s["no_commercial_enzyme"],
                notes=s["notes"],
            )
            for sid, s in payload["substrates"].items()
        },
        gi_regions=tuple(
            GIRegion(
                id=r["id"], name=r["name"], ph_low=r["ph_low"], ph_high=r["ph_high"],
                order=r["order"], dormant=r["dormant"], transit_note=r["transit_note"],
            )
            for r in payload["gi_regions"]
        ),
        latest_trial_ph=_untracked(payload["latest_trial_ph"])
        if payload["latest_trial_ph"]
        else None,
    )


@dataclass(frozen=True, slots=True)
class SnapshotChange:
    """One field that moved between two snapshots of the same formulation."""

    #: "enzyme" | "food" | "substrate" | "formulation" | "gi_regions" | "latest_trial_ph"
    kind: str
    record_id: str
    field: str
    before: Any
    after: Any


_RECORD_SECTIONS = (("enzymes", "enzyme"), ("foods", "food"), ("substrates", "substrate"))


def _record_changes(kind: str, old: Mapping, new: Mapping) -> list[SnapshotChange]:
    changes: list[SnapshotChange] = []
    for record_id in sorted(set(old) | set(new)):
        before, after = old.get(record_id), new.get(record_id)
        if before is None:
            changes.append(SnapshotChange(kind, record_id, "*", None, "added"))
            continue
        if after is None:
            changes.append(SnapshotChange(kind, record_id, "*", "removed", None))
            continue
        for name in sorted(set(before) | set(after)):
            if before.get(name) != after.get(name):
                changes.append(
                    SnapshotChange(kind, record_id, name, before.get(name), after.get(name))
                )
    return changes


def diff_snapshots(old_json: str, new_json: str) -> tuple[SnapshotChange, ...]:
    """Field-level diff, so a stale banner can name what moved (plan decision #9)."""
    old, new = json.loads(old_json), json.loads(new_json)
    changes: list[SnapshotChange] = []

    for section, kind in _RECORD_SECTIONS:
        changes += _record_changes(kind, old.get(section, {}), new.get(section, {}))

    old_form, new_form = old.get("formulation", {}), new.get("formulation", {})
    for name in sorted(set(old_form) | set(new_form)):
        if old_form.get(name) != new_form.get(name):
            changes.append(
                SnapshotChange(
                    "formulation", old_form.get("id", ""), name,
                    old_form.get(name), new_form.get(name),
                )
            )

    for section in ("gi_regions", "latest_trial_ph"):
        if old.get(section) != new.get(section):
            changes.append(
                SnapshotChange(section, "", "*", old.get(section), new.get(section))
            )

    return tuple(changes)
