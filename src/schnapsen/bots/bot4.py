import math
import random
from typing import Optional

from schnapsen.game import Bot, PlayerPerspective, Move


class Bot4(Bot):
    """
    Bot 4 — WinIfFollowerBot

    Rule 1: Highest immediate card points.
    Rule 2: Add marriage bonus (+40 trump, +20 otherwise).
    Rule 3: Prefer trump exchange (small bonus).
    Rule 4: If follower and you can win the trick, only consider winning moves.

    If multiple moves tie -> pick randomly.
    """

    def __init__(self, rand: random.Random, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.rng = rand

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:
        valid_moves = perspective.valid_moves()
        scorer = perspective.get_engine().trick_scorer
        trump_suit = perspective.get_trump_suit()

        moves_to_consider = valid_moves

        # ---------------- Rule 4: follower tries to win if possible ----------------
        if leader_move is not None:
            # Get the card the leader played
            if leader_move.is_marriage():
                leader_card = leader_move.as_marriage().underlying_regular_move().card
            else:
                leader_card = leader_move.as_regular_move().card

            leader_points = scorer.rank_to_points(leader_card.rank)
            winning_moves = []

            for move in valid_moves:
                # Get the card we would play (ignore trump exchange)
                if move.is_regular_move():
                    follower_card = move.as_regular_move().card
                elif move.is_marriage():
                    follower_card = move.as_marriage().underlying_regular_move().card
                else:
                    continue

                follower_points = scorer.rank_to_points(follower_card.rank)

                # Same "who wins" logic as in the engine
                if leader_card.suit is follower_card.suit:
                    leader_wins = leader_points > follower_points
                elif leader_card.suit is trump_suit:
                    leader_wins = True
                elif follower_card.suit is trump_suit:
                    leader_wins = False
                else:
                    leader_wins = True

                if not leader_wins:
                    winning_moves.append(move)

            # If there is at least one winning move, restrict to those
            if winning_moves:
                moves_to_consider = winning_moves

        # ---------------- Rules 1–3: score remaining moves ----------------
        best_score = -math.inf
        best_moves = []

        for move in moves_to_consider:
            score = 0

            # Rule 1
            if move.is_regular_move():
                card = move.as_regular_move().card
                score += scorer.rank_to_points(card.rank)

            elif move.is_marriage():
                marriage = move.as_marriage()
                card = marriage.underlying_regular_move().card
                score += scorer.rank_to_points(card.rank)

                # Rule 2
                score += 40 if marriage.suit == trump_suit else 20

            # Rule 3
            if move.is_trump_exchange():
                score += 15

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self.rng.choice(best_moves)
