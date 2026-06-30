"""Fantasy football analytics and mock draft simulation from nflverse PBP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

FLEX_POSITIONS = frozenset({"RB", "WR", "TE"})
SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K"})
ROSTER_SLOTS: dict[str, int] = {
    "QB": 1,
    "RB": 2,
    "WR": 3,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "DEF": 1,
}
DEFAULT_TEAM_COUNT = 12


@dataclass
class DraftPick:
    pick_number: int
    round_number: int
    team_slot: int
    player_id: str
    player_name: str
    position: str
    team: str
    projected_ppg: float
    is_user: bool = False


@dataclass
class DraftRoster:
    team_slot: int
    picks: list[DraftPick] = field(default_factory=list)

    def position_counts(self) -> dict[str, int]:
        counts = {pos: 0 for pos in ROSTER_SLOTS}
        for pick in self.picks:
            pos = pick.position
            if pos in FLEX_POSITIONS:
                if counts[pos] < ROSTER_SLOTS[pos]:
                    counts[pos] += 1
                else:
                    counts["FLEX"] += 1
            elif pos in counts:
                counts[pos] += 1
        return counts

    def open_slots(self) -> dict[str, int]:
        filled = self.position_counts()
        return {
            slot: max(ROSTER_SLOTS[slot] - filled[slot], 0)
            for slot in ROSTER_SLOTS
        }

    def can_draft(self, position: str) -> bool:
        slots = self.open_slots()
        if position == "DEF" or position == "K" or position == "QB":
            return slots.get(position, 0) > 0
        if position in FLEX_POSITIONS:
            flex_open = slots.get("FLEX", 0) > 0
            pos_open = slots.get(position, 0) > 0
            return flex_open or pos_open
        return False

    def to_frame(self) -> pd.DataFrame:
        if not self.picks:
            return pd.DataFrame(
                columns=[
                    "slot",
                    "player_name",
                    "position",
                    "team",
                    "projected_ppg",
                    "pick_number",
                    "round",
                ]
            )
        return pd.DataFrame(
            [
                {
                    "slot": _assign_display_slot(self, pick),
                    "player_name": pick.player_name,
                    "position": pick.position,
                    "team": pick.team,
                    "projected_ppg": round(pick.projected_ppg, 2),
                    "pick_number": pick.pick_number,
                    "round": pick.round_number,
                }
                for pick in self.picks
            ]
        )


def _assign_display_slot(roster: DraftRoster, pick: DraftPick) -> str:
    """Map a pick to its starting lineup slot for display."""
    counts = {pos: 0 for pos in [*ROSTER_SLOTS, "FLEX"]}
    for prior in roster.picks:
        if prior.pick_number >= pick.pick_number:
            break
        counts[_slot_for_pick(counts, prior.position)] += 1

    slot_name = _slot_for_pick(counts, pick.position)
    counts[slot_name] += 1
    if slot_name == "FLEX":
        return "FLEX"
    if ROSTER_SLOTS[slot_name] > 1:
        return f"{slot_name}{counts[slot_name]}"
    return slot_name


def _slot_for_pick(counts: dict[str, int], position: str) -> str:
    if position not in FLEX_POSITIONS:
        return position
    if counts[position] < ROSTER_SLOTS[position]:
        return position
    return "FLEX"


def _safe_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _points_allowed_bonus(points: float) -> float:
    if points <= 0:
        return 10.0
    if points <= 6:
        return 7.0
    if points <= 13:
        return 4.0
    if points <= 20:
        return 1.0
    if points <= 27:
        return 0.0
    if points <= 34:
        return -1.0
    return -4.0


def compute_player_fantasy_stats(
    pbp: pd.DataFrame,
    *,
    scoring: str = "ppr",
) -> pd.DataFrame:
    """Aggregate per-player fantasy scoring from play-by-play (PPR by default)."""
    if pbp.empty:
        return pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "team",
                "position",
                "games",
                "total_points",
                "points_per_game",
            ]
        )

    reception_pts = 1.0 if scoring == "ppr" else 0.0
    frames: list[pd.DataFrame] = []

    if "passer_player_id" in pbp.columns:
        passer = pbp.dropna(subset=["passer_player_id"]).copy()
        passer["player_id"] = passer["passer_player_id"].astype(str)
        passer["player_name"] = passer.get("passer_player_name", passer["player_id"])
        passer["team"] = passer.get("posteam")
        passer["points"] = (
            _safe_numeric(passer, "passing_yards") / 25
            + _safe_numeric(passer, "pass_touchdown") * 4
            + _safe_numeric(passer, "interception") * -2
        )
        frames.append(passer[["player_id", "player_name", "team", "game_id", "points"]])

    if "rusher_player_id" in pbp.columns:
        rusher = pbp.dropna(subset=["rusher_player_id"]).copy()
        rusher["player_id"] = rusher["rusher_player_id"].astype(str)
        rusher["player_name"] = rusher.get("rusher_player_name", rusher["player_id"])
        rusher["team"] = rusher.get("posteam")
        fumble_penalty = _safe_numeric(rusher, "fumble_lost") * -2
        rusher["points"] = (
            _safe_numeric(rusher, "rushing_yards") / 10
            + _safe_numeric(rusher, "rush_touchdown") * 6
            + fumble_penalty
        )
        frames.append(rusher[["player_id", "player_name", "team", "game_id", "points"]])

    if "receiver_player_id" in pbp.columns:
        receiver = pbp.dropna(subset=["receiver_player_id"]).copy()
        receiver["player_id"] = receiver["receiver_player_id"].astype(str)
        receiver["player_name"] = receiver.get(
            "receiver_player_name", receiver["player_id"]
        )
        receiver["team"] = receiver.get("posteam")
        receiver["points"] = (
            _safe_numeric(receiver, "receiving_yards") / 10
            + _safe_numeric(receiver, "pass_touchdown") * 6
            + _safe_numeric(receiver, "complete_pass") * reception_pts
        )
        frames.append(
            receiver[["player_id", "player_name", "team", "game_id", "points"]]
        )

    if "kicker_player_id" in pbp.columns:
        kicker = pbp.dropna(subset=["kicker_player_id"]).copy()
        kicker["player_id"] = kicker["kicker_player_id"].astype(str)
        kicker["player_name"] = kicker.get("kicker_player_name", kicker["player_id"])
        kicker["team"] = kicker.get("posteam")
        fg = kicker.get("field_goal_result", pd.Series(dtype=object))
        xp = kicker.get("extra_point_result", pd.Series(dtype=object))
        kicker["points"] = (fg == "made").astype(float) * 3 + (xp == "good").astype(float)
        frames.append(kicker[["player_id", "player_name", "team", "game_id", "points"]])

    if not frames:
        return pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "team",
                "position",
                "games",
                "total_points",
                "points_per_game",
            ]
        )

    long = pd.concat(frames, ignore_index=True)
    long = long[long["points"] != 0]
    grouped = (
        long.groupby(["player_id", "player_name", "team"], as_index=False)
        .agg(total_points=("points", "sum"), games=("game_id", "nunique"))
        .assign(
            points_per_game=lambda df: df["total_points"] / df["games"].clip(lower=1)
        )
    )
    grouped["position"] = None
    return grouped.sort_values("points_per_game", ascending=False).reset_index(drop=True)


def compute_defense_fantasy_stats(
    pbp: pd.DataFrame,
    schedule: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build team defense rankings from PBP events and points allowed."""
    if pbp.empty or "defteam" not in pbp.columns:
        return pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "team",
                "position",
                "games",
                "total_points",
                "points_per_game",
            ]
        )

    defense = pbp.dropna(subset=["defteam", "game_id"]).copy()
    defense["team"] = defense["defteam"]

    event_points = (
        _safe_numeric(defense, "sack")
        + _safe_numeric(defense, "interception") * 2
        + _safe_numeric(defense, "safety") * 2
        + _safe_numeric(defense, "return_touchdown") * 6
    )
    if "fumble_recovery_1_team" in defense.columns:
        own_recovery = defense["fumble_recovery_1_team"] == defense["defteam"]
        event_points = event_points + own_recovery.astype(float) * 2

    defense["event_points"] = event_points
    event_stats = (
        defense.groupby(["team", "game_id"], as_index=False)
        .agg(event_points=("event_points", "sum"))
        .rename(columns={"team": "defteam"})
    )

    pa_bonus = _compute_points_allowed_bonus(pbp, schedule)
    merged = event_stats.merge(pa_bonus, on=["defteam", "game_id"], how="left")
    merged["pa_bonus"] = merged["pa_bonus"].fillna(0.0).astype(float)
    merged["game_points"] = merged["event_points"] + merged["pa_bonus"]

    grouped = (
        merged.groupby("defteam", as_index=False)
        .agg(
            total_points=("game_points", "sum"),
            games=("game_id", "nunique"),
        )
        .rename(columns={"defteam": "team"})
    )
    grouped["player_id"] = grouped["team"].apply(lambda t: f"DEF-{t}")
    grouped["player_name"] = grouped["team"] + " DEF"
    grouped["position"] = "DEF"
    grouped["points_per_game"] = grouped["total_points"] / grouped["games"].clip(lower=1)
    return grouped.sort_values("points_per_game", ascending=False).reset_index(drop=True)


def _compute_points_allowed_bonus(
    pbp: pd.DataFrame,
    schedule: pd.DataFrame | None,
) -> pd.DataFrame:
    game_keys = pbp[["game_id", "home_team", "away_team"]].drop_duplicates()
    if schedule is not None and {"game_id", "home_score", "away_score"}.issubset(
        schedule.columns
    ):
        scores = schedule[["game_id", "home_team", "away_team", "home_score", "away_score"]]
        game_keys = scores.dropna(subset=["home_score", "away_score"])
    elif {"total_home_score", "total_away_score"}.issubset(pbp.columns):
        game_keys = (
            pbp.groupby("game_id", as_index=False)
            .agg(
                home_team=("home_team", "first"),
                away_team=("away_team", "first"),
                home_score=("total_home_score", "max"),
                away_score=("total_away_score", "max"),
            )
            .dropna(subset=["home_score", "away_score"])
        )
    else:
        return pd.DataFrame(columns=["defteam", "game_id", "pa_bonus"])

    rows: list[dict] = []
    for game in game_keys.itertuples(index=False):
        rows.append(
            {
                "defteam": game.home_team,
                "game_id": game.game_id,
                "pa_bonus": _points_allowed_bonus(float(game.away_score)),
            }
        )
        rows.append(
            {
                "defteam": game.away_team,
                "game_id": game.game_id,
                "pa_bonus": _points_allowed_bonus(float(game.home_score)),
            }
        )
    return pd.DataFrame(rows, columns=["defteam", "game_id", "pa_bonus"])


def attach_player_positions(
    stats: pd.DataFrame,
    rosters: pd.DataFrame,
) -> pd.DataFrame:
    """Join roster positions onto aggregated player stats."""
    if stats.empty:
        return stats

    result = stats.copy()
    if rosters.empty or "gsis_id" not in rosters.columns:
        result["position"] = result.get("position")
        return result

    roster_cols = ["gsis_id", "position", "full_name", "team"]
    optional = [c for c in ["week", "season"] if c in rosters.columns]
    roster_pos = (
        rosters.dropna(subset=["gsis_id"])[roster_cols + optional]
        .rename(columns={"gsis_id": "player_id"})
        .assign(player_id=lambda df: df["player_id"].astype(str))
        .sort_values([c for c in ["player_id", "week", "season"] if c in rosters.columns])
        .drop_duplicates(subset=["player_id"], keep="last")[
            ["player_id", "position", "full_name", "team"]
        ]
    )
    merged = result.merge(
        roster_pos,
        on="player_id",
        how="left",
        suffixes=("", "_roster"),
    )
    merged["player_name"] = merged["full_name"].fillna(merged["player_name"])
    merged["team"] = merged["team"].fillna(merged["team_roster"])
    merged["position"] = merged["position"].fillna(merged["position_roster"])
    return merged.drop(
        columns=[c for c in merged.columns if c.endswith("_roster") or c == "full_name"],
        errors="ignore",
    )


def build_fantasy_rankings(
    pbp: pd.DataFrame,
    rosters: pd.DataFrame,
    *,
    schedule: pd.DataFrame | None = None,
    scoring: str = "ppr",
) -> pd.DataFrame:
    """Combined skill-position and defense rankings for draft simulation."""
    players = compute_player_fantasy_stats(pbp, scoring=scoring)
    players = attach_player_positions(players, rosters)
    players = players[players["position"].isin(SKILL_POSITIONS)].copy()

    defenses = compute_defense_fantasy_stats(pbp, schedule)
    combined = pd.concat([players, defenses], ignore_index=True)
    combined = combined.dropna(subset=["position", "points_per_game"])
    combined["rank"] = (
        combined.groupby("position")["points_per_game"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    return combined.sort_values(
        ["position", "rank", "points_per_game"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def snake_pick_order(
    team_count: int = DEFAULT_TEAM_COUNT,
    rounds: int | None = None,
) -> list[int]:
    """Return 1-based team slot for each pick in a snake draft."""
    if rounds is None:
        rounds = sum(ROSTER_SLOTS.values())
    order: list[int] = []
    for round_idx in range(rounds):
        slots = list(range(1, team_count + 1))
        if round_idx % 2 == 1:
            slots.reverse()
        order.extend(slots)
    return order


def _replacement_baselines(
    rankings: pd.DataFrame,
    team_count: int,
) -> dict[str, float]:
    baselines: dict[str, float] = {}
    for position, slots in ROSTER_SLOTS.items():
        if position == "FLEX":
            flex_pool = rankings[rankings["position"].isin(FLEX_POSITIONS)]
            flex_rank = team_count * (
                ROSTER_SLOTS["RB"] + ROSTER_SLOTS["WR"] + ROSTER_SLOTS["TE"] + 1
            )
            baselines["FLEX"] = (
                flex_pool.nsmallest(max(flex_rank, 1), "rank")
                .tail(1)["points_per_game"]
                .squeeze()
            )
            if pd.isna(baselines["FLEX"]):
                baselines["FLEX"] = 0.0
            continue
        pos_df = rankings[rankings["position"] == position]
        replace_rank = team_count * slots
        if pos_df.empty:
            baselines[position] = 0.0
            continue
        tail = pos_df.nsmallest(max(replace_rank, 1), "rank").tail(1)
        baselines[position] = float(tail["points_per_game"].squeeze())
    return baselines


def _pick_score(
    row: pd.Series,
    roster: DraftRoster,
    baselines: dict[str, float],
    pick_number: int,
    total_picks: int,
) -> float:
    position = row["position"]
    if not roster.can_draft(position):
        return float("-inf")

    value = float(row["points_per_game"]) - baselines.get(position, 0.0)
    if position in FLEX_POSITIONS:
        value = max(
            value,
            float(row["points_per_game"]) - baselines.get("FLEX", 0.0),
        )

    slots = roster.open_slots()
    need_multiplier = 1.0
    if slots.get(position, 0) > 0 and ROSTER_SLOTS.get(position, 0) == slots[position]:
        need_multiplier += 0.35
    if position in FLEX_POSITIONS and slots.get("FLEX", 0) > 0:
        need_multiplier += 0.15

    urgency = pick_number / max(total_picks, 1)
    if position == "K" and slots.get("K", 0) == 0:
        return float("-inf")
    if position == "DEF" and slots.get("DEF", 0) == 0:
        return float("-inf")

    if urgency > 0.75 and slots.get(position, 0) > 0:
        need_multiplier += 0.5 * urgency

    score = float(row["points_per_game"]) + value * 0.65 * need_multiplier
    if position in {"K", "DEF"} and urgency < 0.55:
        score -= 8.0
    return score


def select_best_available(
    rankings: pd.DataFrame,
    drafted_ids: set[str],
    roster: DraftRoster,
    baselines: dict[str, float],
    pick_number: int,
    total_picks: int,
) -> pd.Series | None:
    """Choose the top player for a roster using value and positional need."""
    pool = rankings[~rankings["player_id"].isin(drafted_ids)].copy()
    if pool.empty:
        return None

    scores = pool.apply(
        lambda row: _pick_score(row, roster, baselines, pick_number, total_picks),
        axis=1,
    )
    pool = pool.assign(_score=scores)
    eligible = pool[pool["_score"] > float("-inf")]
    if eligible.empty:
        fallback = pool[pool.apply(lambda row: roster.can_draft(row["position"]), axis=1)]
        if fallback.empty:
            return None
        return fallback.sort_values("points_per_game", ascending=False).iloc[0]
    return eligible.sort_values(["_score", "points_per_game"], ascending=False).iloc[0]


def run_mock_draft(
    rankings: pd.DataFrame,
    user_draft_position: int,
    *,
    team_count: int = DEFAULT_TEAM_COUNT,
) -> tuple[list[DraftPick], dict[int, DraftRoster]]:
    """Simulate a full snake draft; other teams use the same analytics model."""
    if not 1 <= user_draft_position <= team_count:
        raise ValueError(f"user_draft_position must be between 1 and {team_count}")

    rounds = sum(ROSTER_SLOTS.values())
    total_picks = team_count * rounds
    pick_slots = snake_pick_order(team_count=team_count, rounds=rounds)
    baselines = _replacement_baselines(rankings, team_count)

    rosters = {slot: DraftRoster(team_slot=slot) for slot in range(1, team_count + 1)}
    drafted_ids: set[str] = set()
    picks: list[DraftPick] = []

    for pick_number, team_slot in enumerate(pick_slots, start=1):
        round_number = (pick_number - 1) // team_count + 1
        roster = rosters[team_slot]
        choice = select_best_available(
            rankings,
            drafted_ids,
            roster,
            baselines,
            pick_number,
            total_picks,
        )
        if choice is None:
            break

        drafted_ids.add(str(choice["player_id"]))
        pick = DraftPick(
            pick_number=pick_number,
            round_number=round_number,
            team_slot=team_slot,
            player_id=str(choice["player_id"]),
            player_name=str(choice["player_name"]),
            position=str(choice["position"]),
            team=str(choice.get("team", "")),
            projected_ppg=float(choice["points_per_game"]),
            is_user=team_slot == user_draft_position,
        )
        picks.append(pick)
        roster.picks.append(pick)

    return picks, rosters


def draft_log_frame(picks: Iterable[DraftPick]) -> pd.DataFrame:
    """Flatten draft picks into a display-friendly DataFrame."""
    rows = [
        {
            "pick": p.pick_number,
            "round": p.round_number,
            "team": p.team_slot,
            "player": p.player_name,
            "position": p.position,
            "nfl_team": p.team,
            "projected_ppg": round(p.projected_ppg, 2),
            "user_pick": p.is_user,
        }
        for p in picks
    ]
    return pd.DataFrame(rows)