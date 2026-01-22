import math
import random
from typing import Optional

from schnapsen.game import Bot, PlayerPerspective, Move, GamePhase


class Bot7old(Bot):
    """
    Bot 7 — LeaderLowCardProbeBot

    Rule 1: Highest immediate card points.
    Rule 2: Add marriage bonus (+40 trump, +20 otherwise).
    Rule 3: Prefer trump exchange (small bonus).
    Rule 4: If follower and you can win the trick, only consider winning moves.
    Rule 5: If follower and can win, win with the cheapest winning card.
    Rule 6: If follower and cannot win, lose with the cheapest card.
    Rule 7: If leader in Phase ONE, lead the cheapest non-trump card if possible,
            otherwise lead the cheapest trump card.

    If multiple moves tie -> pick randomly.
    """

    def __init__(self, rand: random.Random, name: Optional[str] = None) -> None:
        super().__init__(name)
        self.rng = rand

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:
        valid_moves = perspective.valid_moves()

        scorer = perspective.get_engine().trick_scorer
        trump_suit = perspective.get_trump_suit()
        phase = perspective.get_phase()

        moves_to_consider = valid_moves

        # ---------------- Rule 7: leader in Phase ONE leads a cheap card ----------------
        if leader_move is None and phase == GamePhase.ONE:
            non_trump_moves = []
            trump_moves = []

            # Split moves into non-trump card plays vs trump card plays
            # (Skip trump exchange here because it doesn't play a card into the trick)
            for move in valid_moves:
                if move.is_trump_exchange():
                    continue

                if move.is_regular_move():
                    card = move.as_regular_move().card
                else:
                    card = move.as_marriage().underlying_regular_move().card

                if card.suit == trump_suit:
                    trump_moves.append(move)
                else:
                    non_trump_moves.append(move)

            preferred_moves = non_trump_moves if non_trump_moves else trump_moves

            # Keep only the cheapest moves from the preferred group
            cheapest_cost = math.inf
            cheapest_moves = []

            for move in preferred_moves:
                if move.is_regular_move():
                    card = move.as_regular_move().card
                else:
                    card = move.as_marriage().underlying_regular_move().card

                cost = scorer.rank_to_points(card.rank)

                if cost < cheapest_cost:
                    cheapest_cost = cost
                    cheapest_moves = [move]
                elif cost == cheapest_cost:
                    cheapest_moves.append(move)

            moves_to_consider = cheapest_moves

        # ---------------- Rules 4–6: follower chooses win cheap, else lose cheap ----------------
        if leader_move is not None:
            if leader_move.is_marriage():
                leader_card = leader_move.as_marriage().underlying_regular_move().card
            else:
                leader_card = leader_move.as_regular_move().card

            leader_points = scorer.rank_to_points(leader_card.rank)

            winning_moves = []
            losing_moves = []

            for move in valid_moves:
                if move.is_regular_move():
                    follower_card = move.as_regular_move().card
                elif move.is_marriage():
                    follower_card = move.as_marriage().underlying_regular_move().card
                else:
                    continue

                follower_points = scorer.rank_to_points(follower_card.rank)

                if leader_card.suit is follower_card.suit:
                    leader_wins = leader_points > follower_points
                elif leader_card.suit is trump_suit:
                    leader_wins = True
                elif follower_card.suit is trump_suit:
                    leader_wins = False
                else:
                    leader_wins = True

                if leader_wins:
                    losing_moves.append(move)
                else:
                    winning_moves.append(move)

            if winning_moves:
                cheapest_cost = math.inf
                cheapest_winners = []

                for move in winning_moves:
                    if move.is_regular_move():
                        card = move.as_regular_move().card
                    else:
                        card = move.as_marriage().underlying_regular_move().card

                    cost = scorer.rank_to_points(card.rank)

                    if cost < cheapest_cost:
                        cheapest_cost = cost
                        cheapest_winners = [move]
                    elif cost == cheapest_cost:
                        cheapest_winners.append(move)

                moves_to_consider = cheapest_winners
            else:
                cheapest_cost = math.inf
                cheapest_losers = []

                for move in losing_moves:
                    if move.is_regular_move():
                        card = move.as_regular_move().card
                    else:
                        card = move.as_marriage().underlying_regular_move().card

                    cost = scorer.rank_to_points(card.rank)

                    if cost < cheapest_cost:
                        cheapest_cost = cost
                        cheapest_losers = [move]
                    elif cost == cheapest_cost:
                        cheapest_losers.append(move)

                moves_to_consider = cheapest_losers

        # ---------------- Rules 1–3: score remaining moves ----------------
        best_score = -math.inf
        best_moves = []

        for move in moves_to_consider:
            score = 0

            # Rule 1: card points
            if move.is_regular_move():
                card = move.as_regular_move().card
                score += scorer.rank_to_points(card.rank)

            elif move.is_marriage():
                marriage = move.as_marriage()
                card = marriage.underlying_regular_move().card
                score += scorer.rank_to_points(card.rank)

                # Rule 2: marriage bonus
                score += 40 if marriage.suit == trump_suit else 20

            # Rule 3: trump exchange preference
            if move.is_trump_exchange():
                score += 15

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self.rng.choice(best_moves)
