"""Spec §7 — auto-variant generation. Pure.

`suggest(ctx, findings)` maps an evaluation's own findings onto §7's fix
catalogue. Three rules govern what comes out:

* **Nothing here is pre-cleared.** A suggestion is a patch plus a sentence. Its
  merit is decided by re-running the engine on the result, which is what the
  apply endpoint does — so a suggestion can and sometimes will produce a worse
  verdict, honestly reported (spec §7).
* **A suggestion that cannot honestly be applied carries no patch.** §7's "raise
  recipe pH" is a note: §12 item 1 says recipe pH is a worst-case minimum, not a
  mixing model, so the engine cannot predict the pH that removing an acid
  ingredient would produce (plan decision #4). Supplier questions and the R15
  behavioural note are notes for the same reason — there is nothing in the
  formulation to change.
* **A suggestion never produces a formulation the engine refuses.** §6.2 R14
  rejects zero enzymes with zero trigger foods; a drop suggestion that would
  reach that state is suppressed at generation rather than 422-ing a button the
  tool offered (plan decision #13).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from foodbrew.engine.conventions import resolve_recipe_ph, shelf_stable_floor
from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.patch import apply_patch, canonical, set_format
from foodbrew.engine.rules import r15_applied_texture
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.selection import enzyme_for_substrate, proposed_dose
from foodbrew.engine.types import (
    DwellProfile,
    Enzyme,
    EvalContext,
    Format,
    Phase,
    RuleFinding,
    Verdict,
)


class SuggestionType(StrEnum):
    """Spec §7's right-hand column, as a closed set the UI can group by."""

    FORMAT_CHANGE = "format_change"
    SWAP_ENZYME = "swap_enzyme"
    ADD_ENZYME = "add_enzyme"
    DROP_ENZYME = "drop_enzyme"
    SEPARATE_ENZYME = "separate_enzyme"
    ENCAPSULATE_ENZYME = "encapsulate_enzyme"
    RAISE_DOSE = "raise_dose"
    DROP_TRIGGER_FOOD = "drop_trigger_food"
    MOVE_ENZYME_ADDITION = "move_enzyme_addition"
    RESTRICT_OCCASIONS = "restrict_occasions"
    #: The three note kinds. `patch` is None on every one of them.
    RECIPE_NOTE = "recipe_note"
    BEHAVIOUR_NOTE = "behaviour_note"
    SUPPLIER_QUESTION = "supplier_question"


@dataclass(frozen=True, slots=True)
class Suggestion:
    suggestion_type: SuggestionType
    description: str
    #: None means there is nothing to apply — the suggestion is a note.
    patch: Mapping[str, Any] | None
    triggered_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_applicable(self) -> bool:
        return self.patch is not None


#: Spec §7 R4/R6 — the two formats that physically separate enzyme from liquid.
_SEPARATING_FORMATS = (Format.DUAL_CHAMBER, Format.DRY_SACHET)

_FORMAT_TEXT = {
    Format.DUAL_CHAMBER: "a dual chamber, wet on one side and dry powder on the other",
    Format.DRY_SACHET: "a dry sachet paired with the dressing",
}


# --------------------------------------------------------------------------- #
# Shared producers
# --------------------------------------------------------------------------- #

def _format_changes(ctx: EvalContext, rule_id: str) -> list[Suggestion]:
    return [
        Suggestion(
            SuggestionType.FORMAT_CHANGE,
            f"Sell it as {_FORMAT_TEXT[fmt]}. The enzyme stays dry until use, so water "
            f"never switches it on in the jar.",
            set_format(fmt),
            (rule_id,),
        )
        for fmt in _SEPARATING_FORMATS
        if fmt is not ctx.formulation.format
    ]


def _encapsulate(ctx: EvalContext, rule_id: str) -> list[Suggestion]:
    exposed = [
        s for s in ctx.selected_enzymes() if s.phase is Phase.WET and not s.encapsulated
    ]
    if not exposed:
        return []
    names = ", ".join(ctx.enzyme_for(s).name for s in exposed)
    return [
        Suggestion(
            SuggestionType.ENCAPSULATE_ENZYME,
            f"Encapsulate {names} individually. KB §4f is explicit that a capsule "
            f"delays exposure rather than preventing it, so this buys time and does "
            f"not rescue an enzyme from a pH that would deactivate it on contact — "
            f"R6 re-checks exactly that once you apply it.",
            {
                "ops": [
                    {
                        "op": "set_enzyme_encapsulated",
                        "enzyme_id": s.enzyme_id,
                        "value": True,
                    }
                    for s in exposed
                ]
            },
            (rule_id,),
        )
    ]


def _same_substrate_alternatives(
    ctx: EvalContext, enzyme: Enzyme, recipe_ph: float
) -> tuple[tuple[Enzyme, ...], tuple[Enzyme, ...]]:
    """Catalogue enzymes on the same substrate, split into (would clear, unknown)."""
    clears: list[Enzyme] = []
    unknown: list[Enzyme] = []
    for other in sorted(ctx.enzymes.values(), key=lambda e: e.id):
        if other.id == enzyme.id or other.substrate_id != enzyme.substrate_id:
            continue
        floor = shelf_stable_floor(other)
        if floor.value is None:
            unknown.append(other)
        elif recipe_ph >= floor.value:
            clears.append(other)
    return tuple(clears), tuple(unknown)


# --------------------------------------------------------------------------- #
# Per-rule producers. Each acts only on the verdicts §7 names for that rule.
# --------------------------------------------------------------------------- #

def _r1(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    if enzyme is None:
        return []

    ph = resolve_recipe_ph(ctx.formulation, ctx.foods, ctx.latest_trial_ph)
    if ph.value is None:
        return []

    out: list[Suggestion] = []
    clears, unknown = _same_substrate_alternatives(ctx, enzyme, ph.value)

    for other in clears:
        floor = shelf_stable_floor(other)
        qualifier = (
            " That floor is the stated margin heuristic rather than a supplier figure, "
            "so confirm it before committing."
            if floor.is_heuristic
            else ""
        )
        out.append(
            Suggestion(
                SuggestionType.SWAP_ENZYME,
                f"Swap {enzyme.name} for {other.name}, whose shelf-stable floor of "
                f"pH {floor.value} sits at or below this recipe's pH {ph.value}."
                f"{qualifier}",
                {
                    "ops": [
                        {
                            "op": "swap_enzyme",
                            "enzyme_id": enzyme.id,
                            "replacement_id": other.id,
                            "dose": proposed_dose(other),
                        }
                    ]
                },
                ("R1",),
            )
        )

    for other in unknown:
        out.append(
            Suggestion(
                SuggestionType.SUPPLIER_QUESTION,
                f"{other.name} targets the same substrate but no pH figure is recorded "
                f"for it. Candidate — confirm with the supplier before treating it as a "
                f"fix. Section 15 of the design notes names Amano and BIO-CAT as "
                f"startup-friendly suppliers.",
                None,
                ("R1",),
            )
        )

    if not clears and not unknown:
        out.append(
            Suggestion(
                SuggestionType.SUPPLIER_QUESTION,
                f"Ask a supplier for an acid-stable {enzyme.name} with a shelf-stable "
                f"floor at or below pH {ph.value}. The catalogue holds no alternative "
                f"for this substrate.",
                None,
                ("R1",),
            )
        )

    driver = ctx.foods.get(ph.driving_food_id)
    if driver is not None:
        out.append(
            Suggestion(
                SuggestionType.RECIPE_NOTE,
                f"{driver.name} is the ingredient holding this recipe at pH {ph.value}. "
                f"Reducing or replacing it would raise the pH — but this tool estimates "
                f"recipe pH as the lowest wet-ingredient pH, not as a mixing model, so "
                f"the result has to be measured rather than predicted, and the taste "
                f"call is yours. Enter the measured pH here afterwards and re-run.",
                None,
                ("R1",),
            )
        )

    return out + _format_changes(ctx, "R1")


def _r3(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    heat_steps = finding.evidence.get("heat_steps") or []
    orders = [int(step["order"]) for step in heat_steps]
    if not orders:
        return []
    last_heat = max(orders)
    return [
        Suggestion(
            SuggestionType.MOVE_ENZYME_ADDITION,
            f"Add the enzyme after step {last_heat}, the last step that involves heat, "
            f"rather than at step {finding.evidence.get('enzyme_addition_index')}. Heat "
            f"denatures an enzyme and denaturation is permanent, so the order is the "
            f"whole fix.",
            {"ops": [{"op": "set_enzyme_addition_index", "value": last_heat + 1}]},
            ("R3",),
        )
    ]


def _r4(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.AMBER:
        return []
    return _format_changes(ctx, "R4") + _encapsulate(ctx, "R4")


def _r5(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    out: list[Suggestion] = []

    for enzyme_id in finding.evidence.get("protease_enzymes") or []:
        enzyme = ctx.enzymes.get(enzyme_id)
        if enzyme is None:
            continue
        out.append(
            Suggestion(
                SuggestionType.SEPARATE_ENZYME,
                f"Move {enzyme.name} into the dry side, away from the other enzymes. A "
                f"protease degrades them because enzymes are proteins; separation is "
                f"the whole answer.",
                {
                    "ops": [
                        {"op": "set_enzyme_phase", "enzyme_id": enzyme_id, "value": "dry"}
                    ]
                },
                ("R5",),
            )
        )
        out.append(
            Suggestion(
                SuggestionType.DROP_ENZYME,
                f"Or drop {enzyme.name} altogether. KB §4d treats a protease as additive "
                f"rather than gap-filling — the body already digests protein — so what "
                f"remains is a clean-label and marketing argument, not a digestive one.",
                {"ops": [{"op": "remove_enzyme", "enzyme_id": enzyme_id}]},
                ("R5",),
            )
        )

    raw_foods = [ctx.foods[f] for f in (finding.evidence.get("protease_foods") or [])
                 if f in ctx.foods]
    if raw_foods:
        names = ", ".join(f.name for f in raw_foods)
        out.append(
            Suggestion(
                SuggestionType.RECIPE_NOTE,
                f"{names} brings its own protease into the jar. Cooking it would destroy "
                f"that protease (KB §4j) and suppress the conflict, but it changes the "
                f"recipe and the taste — your call, not a formulation switch.",
                None,
                ("R5",),
            )
        )
    return out


def _r6(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    return _format_changes(ctx, "R6")


def _r7(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.AMBER:
        return []
    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    threshold = finding.evidence.get("evidence_threshold")
    if enzyme is None or threshold is None:
        return []

    out = [
        Suggestion(
            SuggestionType.RAISE_DOSE,
            f"Raise {enzyme.name} to {threshold} {enzyme.dose_unit}, the dose the "
            f"evidence covers. Below it the enzyme behaves like placebo, so a half "
            f"dose is not half a result.",
            {
                "ops": [
                    {
                        "op": "set_enzyme_dose",
                        "enzyme_id": enzyme.id,
                        "value": float(threshold),
                    }
                ]
            },
            ("R7",),
        )
    ]

    for food_id in ctx.formulation.target_trigger_food_ids:
        food = ctx.foods.get(food_id)
        if food is None or enzyme.substrate_id not in food.contains_substrate_ids:
            continue
        out.append(
            Suggestion(
                SuggestionType.DROP_TRIGGER_FOOD,
                f"Or declare a smaller meal: drop {food.name} from the trigger foods "
                f"this is meant to cover, which lowers the load the dose has to clear. "
                f"That narrows the claim rather than improving the formulation.",
                {"ops": [{"op": "remove_trigger_food", "food_id": food_id}]},
                ("R7",),
            )
        )
    return out


def _r10(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    """R10 emits PASS advisories; the pairing suggestion is the point of the rule."""
    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    if enzyme is None:
        return []

    covered = {r.id for r in active_regions(enzyme, ctx.gi_regions)}
    reachable = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
    selected = {s.enzyme_id for s in ctx.selected_enzymes()}

    complements: list[Enzyme] = []
    unrecorded: list[Enzyme] = []
    for other in sorted(ctx.enzymes.values(), key=lambda e: e.id):
        if other.id in selected or other.substrate_id != enzyme.substrate_id:
            continue
        if not (other.ph_min.usable and other.ph_max.usable):
            unrecorded.append(other)
            continue
        gained = {r.id for r in active_regions(other, ctx.gi_regions)} & reachable - covered
        if gained:
            complements.append(other)

    if complements:
        partner = complements[0]
        return [
            Suggestion(
                SuggestionType.ADD_ENZYME,
                f"Pair {enzyme.name} with {partner.name}. Blending an acid variant with "
                f"a neutral one — the Enzymedica pattern in KB §4k — widens the active "
                f"window across more of the tract than either covers alone.",
                {
                    "ops": [
                        {
                            "op": "add_enzyme",
                            "enzyme_id": partner.id,
                            "dose": proposed_dose(partner),
                        }
                    ]
                },
                ("R10",),
            )
        ]

    if unrecorded:
        partner = unrecorded[0]
        return [
            Suggestion(
                SuggestionType.SUPPLIER_QUESTION,
                f"{partner.name} would be the complementary source for {enzyme.name} "
                f"under KB §4k, but its pH window is not recorded, so the tool cannot "
                f"tell whether it widens anything. Ask the supplier for the range.",
                None,
                ("R10",),
            )
        ]
    return []


def _supplier_question(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    """R11 and R12 cannot_assess — §7: no formulation patch, an open question."""
    if finding.verdict is not Verdict.CANNOT_ASSESS:
        return []
    return [
        Suggestion(
            SuggestionType.SUPPLIER_QUESTION,
            finding.message,
            None,
            (finding.rule_id,),
        )
    ]


def _r14(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    substrate_id = finding.evidence.get("substrate")
    enzyme = enzyme_for_substrate(str(substrate_id), ctx.enzymes)
    if enzyme is None:
        return []
    dose = proposed_dose(enzyme)
    dose_text = (
        f" at its benchmark dose of {dose} {enzyme.dose_unit}"
        if dose is not None
        else " — no benchmark dose is recorded for it, so R7 will ask you for one"
    )
    return [
        Suggestion(
            SuggestionType.ADD_ENZYME,
            f"Add {enzyme.name}{dose_text}. It is the catalogue's enzyme for the "
            f"substrate this formulation leaves uncovered.",
            {"ops": [{"op": "add_enzyme", "enzyme_id": enzyme.id, "dose": dose}]},
            ("R14",),
        )
    ]


def _r15(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is Verdict.PASS:
        return []
    out: list[Suggestion] = []

    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    if enzyme is not None:
        out.append(
            Suggestion(
                SuggestionType.DROP_ENZYME,
                f"Narrow the blend: drop {enzyme.name}. It is the enzyme acting on the "
                f"structure the food depends on, so removing it removes the intersection "
                f"rather than managing it — at the cost of whatever it was covering.",
                {"ops": [{"op": "remove_enzyme", "enzyme_id": enzyme.id}]},
                ("R15",),
            )
        )

    envelope = r15_applied_texture.envelope(ctx)
    passing = [p for p in DwellProfile if envelope.get(p) is Verdict.PASS]
    if passing:
        longest = passing[-1]
        out.append(
            Suggestion(
                SuggestionType.RESTRICT_OCCASIONS,
                f"Support only the '{longest.value}' occasion and say so on the label. "
                f"That is an honest narrowing of the claim; the occasions you drop are "
                f"still listed in the envelope so nothing is hidden.",
                {"ops": [{"op": "set_dwell_profile", "value": longest.value}]},
                ("R15",),
            )
        )

    out.append(
        Suggestion(
            SuggestionType.BEHAVIOUR_NOTE,
            "Dress immediately before eating. A format change is deliberately not "
            "offered here: a dual chamber governs when the dressing is mixed, not how "
            "long it then sits on the food, so it moves none of these occasions.",
            None,
            ("R15",),
        )
    )
    return out


_PRODUCERS = {
    "R1": _r1,
    "R3": _r3,
    "R4": _r4,
    "R5": _r5,
    "R6": _r6,
    "R7": _r7,
    "R10": _r10,
    "R11": _supplier_question,
    "R12": _supplier_question,
    "R14": _r14,
    "R15": _r15,
}


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _leaves_an_evaluable_formulation(ctx: EvalContext, suggestion: Suggestion) -> bool:
    """Spec §6.2 R14 refuses zero enzymes with zero trigger foods (decision #13).

    Applying the patch here also proves it is well-formed, so a producer that
    emitted a broken op is caught at generation rather than at the button.
    """
    if suggestion.patch is None:
        return True
    try:
        result = apply_patch(ctx.formulation, suggestion.patch)
    except ValidationRejection:
        return False
    return bool(result.enzymes or result.target_trigger_food_ids)


def _rule_order(rule_id: str) -> int:
    try:
        return int(rule_id[1:])
    except ValueError:  # pragma: no cover - rule ids are R<n> by construction
        return 99


def suggest(ctx: EvalContext, findings: Sequence[RuleFinding]) -> tuple[Suggestion, ...]:
    """Spec §7 — the fix catalogue for one evaluation's findings.

    Deduplicated by (type, patch) with the triggering rules merged, so the
    founder sees one dual-chamber button rather than the three that R1, R4 and
    R6 each asked for; ordered by first triggering rule so a re-run of the same
    inputs produces the same rows in the same order (plan decision #14).
    """
    produced: list[Suggestion] = []
    for finding in findings:
        producer = _PRODUCERS.get(finding.rule_id)
        if producer is not None:
            produced.extend(producer(ctx, finding))

    merged: dict[tuple[str, str], Suggestion] = {}
    for suggestion in produced:
        if not _leaves_an_evaluable_formulation(ctx, suggestion):
            continue
        identity = canonical(suggestion.patch) or suggestion.description
        key = (suggestion.suggestion_type.value, identity)
        existing = merged.get(key)
        if existing is None:
            merged[key] = suggestion
        else:
            merged[key] = dataclasses.replace(
                existing,
                triggered_by=tuple(
                    dict.fromkeys(existing.triggered_by + suggestion.triggered_by)
                ),
            )

    return tuple(
        sorted(
            merged.values(),
            key=lambda s: (
                _rule_order(s.triggered_by[0] if s.triggered_by else "R99"),
                s.suggestion_type.value,
                s.description,
            ),
        )
    )
