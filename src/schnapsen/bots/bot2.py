import math
import random
from typing import Optional

from schnapsen.game import Bot, PlayerPerspective, Move


class Bot2(Bot):
    """
    Bot 2 — MarriageBonusBot

    Rule 1:
    Choose the move with the highest immediate card points.

    Rule 2:
    If the move is a marriage, add the marriage bonus:
    +40 for trump marriage, +20 otherwise.

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

                # Rule 2: add marriage bonus
                if marriage.suit == trump_suit:
                    score += 40
                else:
                    score += 20

            # Trump exchange stays at 0 here

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self.rng.choice(best_moves)
