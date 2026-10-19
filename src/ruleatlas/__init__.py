"""RuleAtlas native deterministic rules; development version, no accepted catalog profiles."""
from .values import RuleError
from .core import (list_games,get_game,get_capabilities,new_state,validate_state,
                   legal_actions,apply_action,outcome,validate_rules,register_rules,unregister_rules)
__version__ = '0.0.1'
__scaffold_stub__ = False
__all__ = ['RuleError','list_games','get_game','get_capabilities','new_state','validate_state',
           'legal_actions','apply_action','outcome','validate_rules','register_rules','unregister_rules']
