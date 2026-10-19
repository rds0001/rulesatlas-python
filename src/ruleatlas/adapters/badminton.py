"""Native badminton singles scoring adapter."""
from . import racket_scoring
def validate(data): return racket_scoring.validate(data,"badminton")
def outcome(state,pack): return racket_scoring.outcome(state,pack,"badminton")
def apply(state,action): return racket_scoring.apply(state,action,"badminton")
def legal(state): return racket_scoring.legal(state,"badminton")
