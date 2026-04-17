from __future__ import annotations

import argparse
import os
import time
from api import (
    enrich_scorecard_with_commentary,
    enrich_scorecard_with_match_info,
    get_current_matches,
    get_match_commentary,
    get_match_info,
    get_match_scorecard,
    parse_matches,
    parse_scorecard,
)
from ui import render_matches, render_scorecard, render_watch_hint, render_minimal_scorecard


def main() -> None:
    parser = argparse.ArgumentParser(description="IPL live score terminal dashboard")
    parser.add_argument("--match", help="Match number or match id to open directly")
    parser.add_argument("--watch", action="store_true", help="Auto-refresh the selected match")
    parser.add_argument("--interval", type=int, default=15, help="Refresh interval in seconds for watch mode")
    parser.add_argument("--minimal", action="store_true", help="Quiet Mode: minimalist view for a tiny pane")
    args = parser.parse_args()

    print(_banner())
    matches, error = get_current_matches()
    if error:
        print(f"\n[ERROR] {error}")
        return

    parsed_matches = parse_matches(matches)
    if not parsed_matches:
        print("No live or current matches were returned by the API.")
        return

    print(render_matches(parsed_matches))
    print("")

    selected_match = _pick_match(parsed_matches, args.match)
    if selected_match is None:
        return

    minimal = args.minimal or _ask_view_mode()

    if args.watch:
        _watch_match(selected_match, max(args.interval, 5), minimal)
        return

    scorecard, load_error = _load_full_scorecard(selected_match)
    if load_error:
        print(f"[ERROR] {load_error}")
        return

    if minimal:
        print(render_minimal_scorecard(scorecard))
    else:
        print(render_scorecard(scorecard))


def _pick_match(matches: list[dict], provided_match: str | None) -> dict | None:
    if provided_match:
        for index, match in enumerate(matches, start=1):
            if provided_match == str(index) or provided_match == match.get("id"):
                print("=" * 80)
                return match
        print("That match number or id was not found in the current list.")
        return None

    try:
        choice = input("Select a match number for the live dashboard, or 0 to exit: ").strip()
        print("=" * 80)
    except EOFError:
        print("No interactive input was provided. Exiting after match list.")
        return None

    if choice == "0":
        print("Exited without loading a scorecard.")
        return None

    try:
        selected_index = int(choice) - 1
    except ValueError:
        print("Please enter a valid match number.")
        return None

    if selected_index < 0 or selected_index >= len(matches):
        print("That match number is out of range.")
        return None

    return matches[selected_index]


def _ask_view_mode() -> bool:
    """Ask the user to choose between minimal and detailed view.

    Returns True for minimal mode, False for detailed mode.
    """
    try:
        print("Choose scoreboard view:")
        print("  [d] Detailed view  — full scorecard with batting, bowling & live stats")
        print("  [m] Minimal view   — compact single-line score summary")
        choice = input("Enter your choice (d/m) [default: d]: ").strip().lower()
    except EOFError:
        return False

    return choice == "m"


def _watch_match(selected_match: dict, interval_seconds: int, minimal: bool = False) -> None:
    import sys
    try:
        while True:
            if not minimal:
                _clear_screen()
                print(_banner())
                print(render_watch_hint(interval_seconds))
                print("")
            scorecard, load_error = _load_full_scorecard(selected_match)
            if load_error:
                if minimal:
                    sys.stdout.write("\r\033[K" + f"[ERROR] {load_error}")
                    sys.stdout.flush()
                else:
                    print(f"[ERROR] {load_error}")
            else:
                if minimal:
                    sys.stdout.write("\r\033[K" + render_minimal_scorecard(scorecard))
                    sys.stdout.flush()
                else:
                    print(render_scorecard(scorecard))
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped live watch mode.")


def _load_full_scorecard(selected_match: dict) -> tuple[dict | None, str | None]:
    match_id = selected_match["id"]
    payload, scorecard_error = get_match_scorecard(match_id)
    if scorecard_error:
        return None, scorecard_error

    parsed_scorecard = parse_scorecard(payload)
    parsed_scorecard = _apply_selected_match_fallback(parsed_scorecard, selected_match)
    match_info_payload, _ = get_match_info(match_id)
    parsed_scorecard = enrich_scorecard_with_match_info(parsed_scorecard, match_info_payload)
    parsed_scorecard = _apply_selected_match_fallback(parsed_scorecard, selected_match)
    commentary_payload, commentary_error = get_match_commentary(match_id)
    parsed_scorecard = enrich_scorecard_with_commentary(parsed_scorecard, commentary_payload, commentary_error)
    return parsed_scorecard, None


def _apply_selected_match_fallback(scorecard: dict, selected_match: dict) -> dict:
    merged = dict(scorecard)
    match = dict(merged.get("match", {}))

    if not match.get("name") or match.get("name") == "Unknown match":
        match["name"] = selected_match.get("name", "Unknown match")
    if not match.get("status") or match.get("status") == "Status unavailable":
        match["status"] = selected_match.get("status", "Status unavailable")
    if not match.get("venue") or match.get("venue") == "Venue unavailable":
        match["venue"] = selected_match.get("venue", "Venue unavailable")
    if not match.get("match_type") or match.get("match_type") == "unknown":
        match["match_type"] = selected_match.get("matchType", "unknown")
    if not match.get("date"):
        match["date"] = selected_match.get("date", "")
    if not match.get("teams"):
        match["teams"] = selected_match.get("teams", [])

    if not merged.get("score"):
        merged["score"] = selected_match.get("score", [])

    merged["match"] = match
    return merged


def _banner() -> str:
    title = "\033[1mCricTerminal Pro\033[0m"
    padding_left = (68 - 16) // 2
    padding_right = 68 - 16 - padding_left
    top = "+" + ("-" * 68) + "+"
    mid = "|" + (" " * padding_left) + title + (" " * padding_right) + "|"
    bot = "+" + ("-" * 68) + "+"
    return "\n".join([top, mid, bot])


def _clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


if __name__ == "__main__":
    main()
