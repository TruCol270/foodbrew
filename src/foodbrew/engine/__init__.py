"""Pure rules engine. No I/O, no persistence — see tests/engine/test_purity.py."""

from foodbrew.engine.evaluate import Evaluation, evaluate
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection

__all__ = ["Evaluation", "ValidationRejection", "evaluate"]
