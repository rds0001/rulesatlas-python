# ruleatlas-python

All and only the state needed to check game rules: plausible states, permitted next events, rule consequences and outcomes. No simulation or physical model.


A native rule library for game-state validation, legal next actions, transitions
and outcomes, with a bounded interpreter for user-defined JSON rules.
`list_games()` lists accepted profiles. All 212 retained profiles have accepted, explicitly bounded variants. Read `get_game(id)` for the exact
variant, required inputs and limitations; acceptance does not certify every
commercial or federation edition.


```python
import ruleatlas

ruleatlas.register_rules("first_to_three.json")
state = ruleatlas.new_state(
    "user.first_to_three", players=[{"id": "alice"}, {"id": "bob"}],
    ruleset_version="1.0.0",
)
state = ruleatlas.apply_action(state, {"type": "score", "params": {"player": 0}})
print(ruleatlas.outcome(state))
```

Supply a local JSON rulepack matching the bundled contract examples. Registration
is process-local and copies input data. Changed rules require a new version;
`overwrite=True` does not replace an immutable registered version. Nonempty
variants are not yet supported by the custom interpreter and are rejected.

Expressions use a fixed operator whitelist. Effects read the old state and commit
atomically after validation. No executable code, shell, network, randomness or
strategy is invoked by rules. Unknown rules and invalid actions raise `RuleError`
with a stable `code`. `validate_rules` and `validate_state` return structured
issues. Custom validation checks structure and declared fields, not arbitrary
historical reachability.

Finite parameter domains are enumerated up to 512 combinations; larger domains
return guarded event types with `completeness=False`. Winners are participant
IDs. Built-in candidates are visible only with `list_games(True)` until accepted.

This development package is not published. Release identity and license-holder
placeholders still require real project-owner details before distribution.

## Built-in match rules

`S001` implements compact football match rules: goals, per-player cards,
eligibility, substitutions, phases and optional knockout progression.
Use `get_game("S001")` for its declared variant and limitations, and
`legal_actions(state)` for phase-dependent event types and remaining allowances.
The repository includes a Python football example in `examples/football.py`.
No ball motion, possession or injury state is stored.

## GitHub source repository

Repository: `rds0001/rulesatlas-python`. The package name remains unchanged.

Install from this repository root:

```sh
python -m pip install .
```

Source repository: https://github.com/rds0001/rulesatlas-python

CI results: https://github.com/rds0001/rulesatlas-python/actions

This source publication is not a PyPI or CRAN release.
