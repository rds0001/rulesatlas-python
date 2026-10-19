"""Native table tennis singles scoring adapter."""
from . import racket_scoring
def validate(data): return racket_scoring.validate(data,"table_tennis")
def outcome(state,pack): return racket_scoring.outcome(state,pack,"table_tennis")
def apply(state,action): return racket_scoring.apply(state,action,"table_tennis")
def legal(state): return racket_scoring.legal(state,"table_tennis")
