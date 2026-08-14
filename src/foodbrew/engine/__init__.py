"""Pure rules engine. No I/O, no persistence — see tests/engine/test_purity.py."""

from foodbrew.engine.evaluate import Evaluation, evaluate

__all__ = ["Evaluation", "evaluate"]
