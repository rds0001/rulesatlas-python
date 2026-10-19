"""Deliberate red gate: this starter package cannot be mistaken for a release."""
import ruleatlas

def test_scaffold_stubs_must_be_replaced():
    assert not getattr(ruleatlas, '__scaffold_stub__', True), (
        'Incomplete scaffold: implement and test all 11 APIs before release.'
    )
