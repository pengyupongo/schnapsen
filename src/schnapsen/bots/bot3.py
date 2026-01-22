import math
import random
from typing import Optional

from schnapsen.game import Bot, PlayerPerspective, Move


class Bot3(Bot):
    """
    Bot 3 — TrumpExchangePreferenceBot

    Rule 1: Highest immediate card points.
    Rule 2: Add marriage bonus (+40 trump, +20 otherwise).
    Rule 3: Prefer trump exchange (small bonus).

    If multiple moves tie -> pick randomly.
    """

    def __init__(self, rand: random.Random, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.rng = rand

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:
        valid_moves = perspective.valid_moves()
        scorer = perspective.get_engine().trick_scorer
        trump_suit = perspective.get_trump_suit()

        best_score = -math.inf
        best_moves = []

        for move in valid_moves:
            score = 0

            # Rule 1: immediate card points
            if move.is_regular_move():
                card = move.as_regular_move().card
                score += scorer.rank_to_points(card.rank)

            elif move.is_marriage():
                marriage = move.as_marriage()
                card = marriage.underlying_regular_move().card
                score += scorer.rank_to_points(card.rank)

                # Rule 2: marriage bonus
                score += 40 if marriage.suit == trump_suit else 20

            # Rule 3: small preference for trump exchange
            if move.is_trump_exchange():
                score += 15

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self.rng.choice(best_moves)
