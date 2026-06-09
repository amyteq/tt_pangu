"""kca eval — regression-suite framework (M13).

This package owns:

- ``add_parsers(subparsers)`` — the ``kca eval`` CLI surface registered by
  ``tools/kca/agent/command_registry.py``. Verbs: ``list``, ``run``,
  ``show``, ``report``.
- ``register_all(db_module=None)`` — the suite-discovery hook that walks
  ``tools/kca/eval/suites/*/__init__.py`` and calls each module's
  ``register(db)`` function. T001 ships the plumbing only; no suites are
  registered yet — T002+ land the concrete suite drivers.

Side-effect classification: most ``kca eval`` verbs are READ_ONLY against
the DB (list / show / report) or LOCAL_WRITE when they insert ``eval_runs``
/ ``eval_results`` rows (``run``). The wrapping CommandSpec is registered
as READ_ONLY by default; ``run`` switches to LOCAL_WRITE at dispatch time
when it actually writes to the DB.
"""

from __future__ import annotations

from .cli import add_parsers, register_all  # noqa: F401

__all__ = ["add_parsers", "register_all"]
