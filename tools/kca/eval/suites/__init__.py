"""Per-suite drivers for the M13 regression framework.

Each suite lives at ``tools/kca/eval/suites/<slug>/__init__.py`` and
exposes a ``register(db)`` callable. ``tools.kca.eval.register_all()``
auto-discovers and invokes them.

T001 ships this namespace empty; T002+ land the concrete suites
(``tool_smoke``, ``kaggle_replay_*``, ``kernel_dryrun``, ``reasoning``,
``router_compare``).
"""
