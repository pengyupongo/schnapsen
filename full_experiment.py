import csv
import hashlib
import math
import os
import random
import statistics
from dataclasses import dataclass
from typing import Callable, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from schnapsen.bots import (
    Bot1,
    Bot2,
    Bot3,
    Bot4,
    Bot5,
    Bot6,
    Bot7,
    Bot7old,
    Bot8,
    BullyBot,
    RandBot,
)
from schnapsen.game import (
    Bot,
    BotState,
    GameState,
    LoserPerspective,
    SchnapsenGamePlayEngine,
    Score,
    WinnerPerspective,
)

GAMES_PER_PAIRING = 1000
BASE_SEED = 20240229
ALPHA = 0.05

OUTPUT_DIR = "experiment_output"


@dataclass(frozen=True)
class BotSpec:
    label: str
    constructor: Callable[[random.Random, str], Bot]


BOT_SPECS: list[BotSpec] = [
    BotSpec("Bot1", Bot1),
    BotSpec("Bot2", Bot2),
    BotSpec("Bot3", Bot3),
    BotSpec("Bot4", Bot4),
    BotSpec("Bot5", Bot5),
    BotSpec("Bot6", Bot6),
    BotSpec("Bot7old", Bot7old),
    BotSpec("Bot7", Bot7),
    BotSpec("Bot8", Bot8),
    BotSpec("RandBot", RandBot),
    BotSpec("BullyBot", BullyBot),
]


def stable_int_seed(*parts: str) -> int:
    seed_text = "|".join(parts)
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def create_bot(bot_spec: BotSpec, game_index: int) -> Bot:
    seed = stable_int_seed(str(BASE_SEED), bot_spec.label, str(game_index))
    rng = random.Random(seed)
    return bot_spec.constructor(rng, name=bot_spec.label)


def redeem_total_points(score: Score) -> int:
    return score.redeem_pending_points().direct_points


def play_game_capture_state(
    engine: SchnapsenGamePlayEngine,
    leader_bot: Bot,
    follower_bot: Bot,
    deck_seed: int,
) -> tuple[Bot, int, GameState]:
    rng = random.Random(deck_seed)
    cards = engine.deck_generator.get_initial_deck()
    shuffled = engine.deck_generator.shuffle_deck(cards, rng)
    hand1, hand2, talon = engine.hand_generator.generateHands(shuffled)

    leader_state = BotState(implementation=leader_bot, hand=hand1)
    follower_state = BotState(implementation=follower_bot, hand=hand2)

    game_state = GameState(
        leader=leader_state,
        follower=follower_state,
        talon=talon,
        previous=None,
    )

    winner_state: BotState | None = None
    points: int = -1
    while not winner_state:
        game_state = engine.trick_implementer.play_trick(engine, game_state)
        winner_state, points = engine.trick_scorer.declare_winner(game_state) or (None, -1)

    winner_perspective = WinnerPerspective(game_state, engine)
    winner_state.implementation.notify_game_end(won=True, perspective=winner_perspective)
    loser_perspective = LoserPerspective(game_state, engine)
    game_state.follower.implementation.notify_game_end(False, perspective=loser_perspective)

    return winner_state.implementation, points, game_state


def get_bot_points(game_state: GameState, bot: Bot) -> int:
    if game_state.leader.implementation is bot:
        return redeem_total_points(game_state.leader.score)
    if game_state.follower.implementation is bot:
        return redeem_total_points(game_state.follower.score)
    raise ValueError("Bot not found in final game state.")


def mean_std(values: Iterable[float]) -> tuple[float, float]:
    values_list = list(values)
    if not values_list:
        return 0.0, 0.0
    if len(values_list) == 1:
        return float(values_list[0]), 0.0
    return statistics.mean(values_list), statistics.stdev(values_list)


def binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p: float = 0.5) -> float:
    observed = binom_pmf(k, n, p)
    total = 0.0
    for i in range(n + 1):
        prob = binom_pmf(i, n, p)
        if prob <= observed + 1e-12:
            total += prob
    return min(total, 1.0)


def write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    deck_seed_rng = random.Random(BASE_SEED)
    deck_seeds = [deck_seed_rng.randint(0, 2**32 - 1) for _ in range(GAMES_PER_PAIRING)]

    metadata_path = os.path.join(OUTPUT_DIR, "metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as handle:
        handle.write(f"GAMES_PER_PAIRING={GAMES_PER_PAIRING}\n")
        handle.write(f"BASE_SEED={BASE_SEED}\n")
        handle.write(f"ALPHA={ALPHA}\n")
        handle.write("BOTS=" + ", ".join(spec.label for spec in BOT_SPECS) + "\n")
        handle.write(f"DECK_SEEDS={len(deck_seeds)}\n")

    engine = SchnapsenGamePlayEngine()

    raw_rows: list[dict] = []
    bot_stats = {
        spec.label: {"games": 0, "wins": 0, "point_diffs": []}
        for spec in BOT_SPECS
    }
    pairing_stats: dict[str, dict] = {}

    total_pairings = len(BOT_SPECS) * (len(BOT_SPECS) - 1) // 2
    pairing_index = 0

    for i, spec_a in enumerate(BOT_SPECS):
        for spec_b in BOT_SPECS[i + 1 :]:
            pairing_index += 1
            pairing_id = f"{spec_a.label}_vs_{spec_b.label}"
            pairing_stats[pairing_id] = {
                "bot_a": spec_a.label,
                "bot_b": spec_b.label,
                "wins_a": 0,
                "wins_b": 0,
                "point_diffs": [],
            }
            print(
                f"[{pairing_index}/{total_pairings}] Running pairing {pairing_id}...",
                flush=True,
            )

            for game_index in range(GAMES_PER_PAIRING):
                deck_seed = deck_seeds[game_index]
                bot_a = create_bot(spec_a, game_index)
                bot_b = create_bot(spec_b, game_index)

                if game_index % 2 == 0:
                    leader_bot, follower_bot = bot_a, bot_b
                else:
                    leader_bot, follower_bot = bot_b, bot_a

                winner_bot, match_points, final_state = play_game_capture_state(
                    engine, leader_bot, follower_bot, deck_seed
                )

                points_a = get_bot_points(final_state, bot_a)
                points_b = get_bot_points(final_state, bot_b)
                point_diff = points_a - points_b

                winner_label = None
                if winner_bot is bot_a:
                    winner_label = spec_a.label
                    pairing_stats[pairing_id]["wins_a"] += 1
                elif winner_bot is bot_b:
                    winner_label = spec_b.label
                    pairing_stats[pairing_id]["wins_b"] += 1
                else:
                    winner_label = "Unknown"

                pairing_stats[pairing_id]["point_diffs"].append(point_diff)

                bot_stats[spec_a.label]["games"] += 1
                bot_stats[spec_b.label]["games"] += 1
                bot_stats[spec_a.label]["wins"] += 1 if winner_bot is bot_a else 0
                bot_stats[spec_b.label]["wins"] += 1 if winner_bot is bot_b else 0
                bot_stats[spec_a.label]["point_diffs"].append(point_diff)
                bot_stats[spec_b.label]["point_diffs"].append(-point_diff)

                raw_rows.append(
                    {
                        "pairing_id": pairing_id,
                        "game_index": game_index,
                        "deck_seed": deck_seed,
                        "leader": leader_bot.name,
                        "follower": follower_bot.name,
                        "winner": winner_label,
                        "winner_match_points": match_points,
                        "points_a": points_a,
                        "points_b": points_b,
                        "point_diff": point_diff,
                    }
                )

    games_csv = os.path.join(OUTPUT_DIR, "tournament_games.csv")
    write_csv(
        games_csv,
        [
            "pairing_id",
            "game_index",
            "deck_seed",
            "leader",
            "follower",
            "winner",
            "winner_match_points",
            "points_a",
            "points_b",
            "point_diff",
        ],
        raw_rows,
    )

    pairing_summary_rows = []
    pvalue_rows = []
    for pairing_id, stats in pairing_stats.items():
        wins_a = stats["wins_a"]
        wins_b = stats["wins_b"]
        games = wins_a + wins_b
        win_rate_a = wins_a / games if games else 0.0
        avg_diff, std_diff = mean_std(stats["point_diffs"])

        pairing_summary_rows.append(
            {
                "pairing_id": pairing_id,
                "bot_a": stats["bot_a"],
                "bot_b": stats["bot_b"],
                "games": games,
                "wins_a": wins_a,
                "wins_b": wins_b,
                "win_rate_a": win_rate_a,
                "avg_point_diff_a": avg_diff,
                "std_point_diff_a": std_diff,
            }
        )

        p_value = binom_test_two_sided(wins_a, games)
        pvalue_rows.append(
            {
                "pairing_id": pairing_id,
                "bot_a": stats["bot_a"],
                "bot_b": stats["bot_b"],
                "wins_a": wins_a,
                "losses_a": wins_b,
                "games": games,
                "p_value": p_value,
                "alpha": ALPHA,
                "significant": p_value < ALPHA,
            }
        )

    pairing_summary_csv = os.path.join(OUTPUT_DIR, "pairing_summary.csv")
    write_csv(
        pairing_summary_csv,
        [
            "pairing_id",
            "bot_a",
            "bot_b",
            "games",
            "wins_a",
            "wins_b",
            "win_rate_a",
            "avg_point_diff_a",
            "std_point_diff_a",
        ],
        pairing_summary_rows,
    )

    bot_summary_rows = []
    for spec in BOT_SPECS:
        stats = bot_stats[spec.label]
        win_rate = stats["wins"] / stats["games"] if stats["games"] else 0.0
        avg_diff, std_diff = mean_std(stats["point_diffs"])
        bot_summary_rows.append(
            {
                "bot": spec.label,
                "games": stats["games"],
                "wins": stats["wins"],
                "win_rate": win_rate,
                "avg_point_diff": avg_diff,
                "std_point_diff": std_diff,
            }
        )

    bot_summary_csv = os.path.join(OUTPUT_DIR, "bot_summary.csv")
    write_csv(
        bot_summary_csv,
        ["bot", "games", "wins", "win_rate", "avg_point_diff", "std_point_diff"],
        bot_summary_rows,
    )

    pvalues_csv = os.path.join(OUTPUT_DIR, "pvalues_headtohead.csv")
    write_csv(
        pvalues_csv,
        [
            "pairing_id",
            "bot_a",
            "bot_b",
            "wins_a",
            "losses_a",
            "games",
            "p_value",
            "alpha",
            "significant",
        ],
        pvalue_rows,
    )

    labels = [row["bot"] for row in bot_summary_rows]
    win_rates = [row["win_rate"] for row in bot_summary_rows]
    avg_diffs = [row["avg_point_diff"] for row in bot_summary_rows]
    std_diffs = [row["std_point_diff"] for row in bot_summary_rows]

    plt.figure(figsize=(12, 6))
    plt.bar(labels, win_rates)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Win Rate")
    plt.title("Win Rate per Bot")
    plt.tight_layout()
    win_rate_plot = os.path.join(OUTPUT_DIR, "win_rate_per_bot.png")
    plt.savefig(win_rate_plot)
    plt.close()

    plt.figure(figsize=(12, 6))
    plt.bar(labels, avg_diffs, yerr=std_diffs, capsize=4)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Average Point Differential")
    plt.title("Average Point Differential per Bot (±1 SD)")
    plt.tight_layout()
    point_diff_plot = os.path.join(OUTPUT_DIR, "avg_point_diff_per_bot.png")
    plt.savefig(point_diff_plot)
    plt.close()

    complexity_order = ["Bot1", "Bot2", "Bot3", "Bot4", "Bot5", "Bot6", "Bot7old", "Bot7", "Bot8"]
    complexity_rates = [
        next(row["win_rate"] for row in bot_summary_rows if row["bot"] == bot)
        for bot in complexity_order
    ]
    plt.figure(figsize=(10, 5))
    plt.plot(complexity_order, complexity_rates, marker="o")
    plt.ylabel("Win Rate")
    plt.title("Win Rate by Bot Complexity")
    plt.tight_layout()
    complexity_plot = os.path.join(OUTPUT_DIR, "win_rate_by_complexity.png")
    plt.savefig(complexity_plot)
    plt.close()

    print("Experiment complete. Outputs:")
    print(f"- Raw games: {games_csv}")
    print(f"- Pairing summary: {pairing_summary_csv}")
    print(f"- Bot summary: {bot_summary_csv}")
    print(f"- P-values: {pvalues_csv}")
    print(f"- Metadata: {metadata_path}")
    print(f"- Plot: {win_rate_plot}")
    print(f"- Plot: {point_diff_plot}")
    print(f"- Plot: {complexity_plot}")


if __name__ == "__main__":
    main()
