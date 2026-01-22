import math
import random
from typing import Optional

from schnapsen.game import Bot, PlayerPerspective, Move, GamePhase


class Bot7(Bot):
    """
    Bot 7 — AggressiveNonTrumpLeadBot

    Rule 1: Highest immediate card points.
    Rule 2: Add marriage bonus (+40 trump, +20 otherwise).
    Rule 3: Prefer trump exchange (small bonus).
    Rule 4: If follower and you can win the trick, only consider winning moves.
    Rule 5: If follower and can win, win with the cheapest winning card.
    Rule 6: If follower and cannot win, lose with the cheapest card.
    Rule 7: If leader in Phase ONE, prefer leading non-trump Aces or Tens
            to pressure the opponent's trumps.

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

        # ---------------- Rule 7: aggressive non-trump A/T lead in Phase ONE ----------------
        if leader_move is None and phase == GamePhase.ONE:
            aggressive_leads = []

            for move in valid_moves:
                # Trump exchange does not lead a trick
                if move.is_trump_exchange():
                    continue

                if move.is_regular_move():
                    card = move.as_regular_move().card
                else:
                    card = move.as_marriage().underlying_regular_move().card

                # Prefer non-trump Ace or Ten
                if card.suit != trump_suit and card.rank.name in ("ACE", "TEN"):
                    aggressive_leads.append(move)

            if aggressive_leads:
                moves_to_consider = aggressive_leads

        # ---------------- Rules 4–6: follower logic ----------------
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

                # Same trick-winning logic as the engine
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
                # Rule 5: win cheaply
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
                # Rule 6: lose cheaply
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

            # Rule 3: trump exchange preference
            if move.is_trump_exchange():
                score += 15

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self.rng.choice(best_moves)
