import math
import random
from typing import Optional

from schnapsen.game import Bot, PlayerPerspective, Move


class Bot1(Bot):
    """
    Bot 1 — GreedyPointsBot

    Rule 1:
    Choose the move with the highest immediate card points.
    If multiple moves have the same points -> pick randomly.
    """

    def __init__(self, rand: random.Random, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.rng = rand

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:
        valid_moves = perspective.valid_moves()
        scorer = perspective.get_engine().trick_scorer

        best_score = -math.inf
        best_moves = []

        for move in valid_moves:
            # Rule 1: immediate points of the card that gets played
            if move.is_regular_move():
                card = move.as_regular_move().card
                score = scorer.rank_to_points(card.rank)

            elif move.is_marriage():
                # Marriage still plays a card, so count the card points
                card = move.as_marriage().underlying_regular_move().card
                score = scorer.rank_to_points(card.rank)

            else:
                # Trump exchange doesn't play a trick card, so 0 immediate points
                score = 0

            # Keep all best moves (ties)
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        # Random tie-break
        return self.rng.choice(best_moves)
