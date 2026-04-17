from __future__ import annotations

import os
import re
import shutil
from typing import Iterable


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
ORANGE = "\033[38;5;208m"
RED = "\033[91m"


def render_matches(matches: list[dict]) -> str:
    use_color = _supports_color()
    width = _content_width()
    blocks = []
    for index, match in enumerate(matches, start=1):
        body = [
            f"{str(match.get('matchType', 'unknown')).upper()} | {match.get('status', 'Status unavailable')}",
            match.get("venue", "Venue unavailable"),
        ]
        for innings_score in match.get("score", []):
            inning = innings_score.get("inning", "Innings")
            runs = innings_score.get("r", 0)
            wickets = innings_score.get("w", 0)
            overs = _format_overs(innings_score.get("o", 0))
            body.append(f"{inning}: {runs}/{wickets} ({overs} ov)")
        blocks.append(_box(f"{index}. {match['name']}", body, width=width, use_color=use_color, title_color=BLUE))
    return "\n\n".join(blocks)


def render_scorecard(scorecard: dict) -> str:
    use_color = _supports_color()
    width = _content_width()
    match = scorecard["match"]
    live = scorecard.get("live", {})

    sections = [
        _render_header_box(match, width, use_color),
        _render_scoreboard_box(scorecard.get("score", []), width, use_color),
    ]

    all_innings = scorecard.get("innings", [])
    for idx, innings in enumerate(all_innings):
        innings_live = live if idx == len(all_innings) - 1 else {}
        sections.append(_render_batting_box(innings, innings_live, width, use_color))
        sections.append(_render_bowling_box(innings, innings_live, width, use_color))

    sections.append(_render_live_strip(live, width, use_color))

    return "\n\n".join(section for section in sections if section)


def render_minimal_scorecard(scorecard: dict) -> str:
    score = scorecard.get("score", [])
    if score:
        latest = score[-1]
        team_score = f"{latest.get('inning', 'Team')} {latest.get('r', 0)}/{latest.get('w', 0)} ({_format_overs(latest.get('o', 0))})"
    else:
        team = scorecard.get("match", {}).get("teams", [])
        team_name = team[0] if team else "Team"
        team_score = f"{team_name} Score unavailable"

    live = scorecard.get("live", {})
    rrr = live.get("required_run_rate", "-")
    rrr_text = f"RRR: {rrr}" if rrr != "-" else ""

    batters = live.get("current_batters", [])
    batter_texts = []
    for b in batters:
        player = b.get("player", "")
        runs = b.get("runs", "0")
        balls = b.get("balls", "0")
        batter_texts.append(f"{player}: {runs}*({balls})")

    parts = [team_score]
    if rrr_text:
        parts.append(rrr_text)
    if batter_texts:
        parts.append(", ".join(batter_texts))

    return " | ".join(parts)


def render_watch_hint(interval_seconds: int) -> str:
    use_color = _supports_color()
    text = f"Watching live match. Refreshing every {interval_seconds} seconds. Press Ctrl+C to stop."
    return _paint(text, CYAN, use_color, bold=True)


def _render_header_box(match: dict, width: int, use_color: bool) -> str:
    date_str = str(match.get("date", ""))
    if date_str.isdigit() and len(date_str) >= 10:
        import datetime
        try:
            ts = int(date_str)
            if ts > 20000000000:
                ts = ts / 1000
            date_str = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%b %d, %Y")
        except ValueError:
            pass

    meta = [
        " | ".join(str(part) for part in [match.get("series", ""), str(match.get("match_type", "")).upper(), date_str] if part),
        match.get("status", "Status unavailable"),
        " | ".join(str(part) for part in [match.get("toss", ""), match.get("venue", "")] if part),
    ]
    return _box(match.get("name", "IPL Live Score"), [line for line in meta if line], width=width, use_color=use_color, title_color=CYAN)


def _render_scoreboard_box(score_rows: list[dict], width: int, use_color: bool) -> str:
    body = []
    for innings_score in score_rows:
        inning = innings_score.get("inning", "Innings")
        runs = innings_score.get("r", 0)
        wickets = innings_score.get("w", 0)
        overs = _format_overs(innings_score.get("o", 0))
        body.append(f"{inning}: {runs}/{wickets} ({overs} ov)")
    if not body:
        body = ["Score unavailable."]
    return _box("SCOREBOARD", body, width=width, use_color=use_color, title_color=YELLOW)


def _render_batting_box(innings: dict, live: dict, width: int, use_color: bool) -> str:
    rows = []
    for row in innings.get("batting", [])[:7]:
        prefix = "* " if str(row.get("dismissal", "")).strip().lower() == "not out" else "  "
        rows.append(
            [
                f"{prefix}{row['player']}",
                row["runs"],
                row["balls"],
                row["fours"],
                row["sixes"],
                row["strike_rate"],
            ]
        )
    body = _render_table(
        ["Batter", "R", "B", "4s", "6s", "SR"],
        rows,
        "No batting data available.",
        use_color,
        max_width=width - 6,
    )
    extras = innings.get("extras")
    if extras:
        body.append(f"Extras: {extras}")
    target = live.get("target_text", "")
    if target:
        body.append(target)
    if innings.get("did_not_bat"):
        body.append("Yet to bat: " + ", ".join(innings["did_not_bat"][:5]))
    return _box("BATTING", body, width=width, use_color=use_color, title_color=GREEN)


def _render_bowling_box(innings: dict, live: dict, width: int, use_color: bool) -> str:
    rows = []
    current_bowler = live.get("current_bowler", "")
    for row in innings.get("bowling", [])[:6]:
        prefix = "> " if row["player"] == current_bowler and current_bowler else "  "
        rows.append([f"{prefix}{row['player']}", row["overs"], row["maidens"], row["runs"], row["wickets"], row["economy"]])
    body = _render_table(
        ["Bowler", "O", "M", "R", "W", "Eco"],
        rows,
        "No bowling data available.",
        use_color,
        max_width=width - 6,
    )
    return _box("BOWLING", body, width=width, use_color=use_color, title_color=ORANGE)


def _render_live_strip(live: dict, width: int, use_color: bool) -> str:
    run_rate_lines = [
        f"CRR: {live.get('current_run_rate', '-')}",
        f"RRR: {live.get('required_run_rate', '-')}",
    ]
    if live.get("last_six_overs_runs"):
        run_rate_lines.append(f"Runs/Over: {_generate_sparkline(live.get('last_six_overs_runs'))}")

    boxes = [
        _mini_box(
            "RUN RATE",
            run_rate_lines,
            width=max(24, (width - 4) // 3),
            use_color=use_color,
            title_color=GREEN,
        ),
        _mini_box(
            "PARTNERSHIP",
            _partnership_lines(live),
            width=max(24, (width - 4) // 3),
            use_color=use_color,
            title_color=BLUE,
        ),
        _mini_box(
            "LAST 6 BALLS",
            _last_six_lines(live),
            width=max(24, (width - 4) // 3),
            use_color=use_color,
            title_color=MAGENTA,
        ),
    ]
    return _join_boxes_horizontally(boxes)


def _partnership_lines(live: dict) -> list[str]:
    lines = [f"{live.get('partnership_runs', '-')} runs | {live.get('partnership_balls', '-')} balls"]
    for batter in live.get("partnership_batters", [])[:2]:
        lines.append(f"{batter['player']}: {batter['runs']} ({batter['balls']})")
    return lines


def _last_six_lines(live: dict) -> list[str]:
    balls = live.get("last_six_balls", [])
    top = " ".join(_format_ball_token(ball) for ball in balls) if balls else "-"
    lines = [top]
    if live.get("recent_over_summary"):
        lines.extend(_wrap_text(live["recent_over_summary"], 22))
    return lines


def _generate_sparkline(runs_list: list[int]) -> str:
    if not runs_list:
        return ""
    chars = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    max_runs = max(max(runs_list), 15)
    sparkline = ""
    for runs in runs_list:
        idx = int((runs / max_runs) * 7)
        idx = max(0, min(7, idx))
        sparkline += chars[idx]
    return sparkline


def _render_table(
    headers: list[str],
    rows: list[list[str]],
    empty_message: str,
    use_color: bool,
    max_width: int,
) -> list[str]:
    if not rows:
        return [empty_message]

    widths: list[int] = []
    for column_index, header in enumerate(headers):
        column_values = [str(row[column_index]) for row in rows]
        widths.append(max(len(header), *(len(value) for value in column_values)))

    widths = _shrink_widths(headers, rows, widths, max_width)
    rendered = [_render_row(headers, widths, use_color, header_row=True), _render_separator(widths, use_color)]
    rendered.extend(_render_row(row, widths) for row in rows)
    return rendered


def _render_row(values: Iterable[str], widths: list[int], use_color: bool = False, header_row: bool = False) -> str:
    rendered_cells = []
    for index, value in enumerate(values):
        text = str(value)
        width = widths[index]
        if len(text) > width:
            if width <= 3:
                text = text[:width]
            else:
                text = text[: width - 3] + "..."
        rendered_cells.append(text.ljust(width))
    row = " ".join(rendered_cells)
    if header_row:
        return _paint(row, WHITE, use_color, bold=True)
    return row


def _render_separator(widths: list[int], use_color: bool = False) -> str:
    separator = " ".join("-" * width for width in widths)
    return _paint(separator, WHITE, use_color, dim=True)


def _box(title: str, body: list[str], *, width: int, use_color: bool, title_color: str) -> str:
    prepared_lines: list[str] = []
    wrap_limit = max(20, width - 4)
    for raw_line in body:
        text = str(raw_line)
        prepared_lines.extend([text] if _looks_like_table_line(text) else _wrap_text(text, wrap_limit))

    content_width = max(
        20,
        len(title) + 4,
        *(_visible_length(line) + 2 for line in prepared_lines),
    )
    inner_width = min(max(20, content_width), max(20, width - 2))
    title_text = f" {title[: inner_width - 2]} "
    top = "+" + "-" + title_text.ljust(inner_width - 1, "-") + "+"
    bottom = "+" + ("-" * inner_width) + "+"
    lines = [top]
    for wrapped in prepared_lines:
        lines.append(f"| {_pad_visible(wrapped, inner_width - 2)} |")
    lines.append(bottom)
    if not use_color:
        return "\n".join(lines)
    lines[0] = _paint(lines[0], title_color, use_color, bold=True)
    lines[-1] = _paint(lines[-1], title_color, use_color, dim=True)
    return "\n".join(lines)


def _mini_box(title: str, body: list[str], *, width: int, use_color: bool, title_color: str) -> str:
    return _box(title, body, width=width, use_color=use_color, title_color=title_color)


def _join_boxes_horizontally(boxes: list[str]) -> str:
    split_boxes = [box.splitlines() for box in boxes]
    max_height = max(len(lines) for lines in split_boxes)
    padded = []
    for lines in split_boxes:
        box_width = max(_visible_length(line) for line in lines)
        padded.append(lines + ([" " * box_width] * (max_height - len(lines))))
    joined = []
    for row in range(max_height):
        joined.append("  ".join(box[row] for box in padded))
    return "\n".join(joined)


def _format_ball_token(token: str) -> str:
    return f"[{token}]"


def _shrink_widths(headers: list[str], rows: list[list[str]], widths: list[int], max_width: int) -> list[int]:
    current_width = sum(widths) + (len(widths) - 1)
    if current_width <= max_width:
        return widths

    minimums = [max(3, len(header)) for header in headers]
    text_heavy_columns = {0}

    while current_width > max_width:
        candidates = [
            index
            for index, width in enumerate(widths)
            if width > minimums[index] and index in text_heavy_columns
        ]
        if not candidates:
            candidates = [index for index, width in enumerate(widths) if width > minimums[index]]
        if not candidates:
            break

        target = max(candidates, key=lambda index: widths[index] - minimums[index])
        widths[target] -= 1
        current_width -= 1

    return widths


def _looks_like_table_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.startswith("-") or ("  " in text and len(text.split()) >= 4)


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _format_overs(value: object) -> str:
    text = str(value)
    if "." not in text:
        return text
    whole, balls = text.split(".", 1)
    if balls == "6":
        try:
            return str(int(whole) + 1)
        except ValueError:
            return text
    return text


def _content_width() -> int:
    columns = shutil.get_terminal_size((120, 40)).columns
    return max(72, min(columns - 8, 110))


def _supports_color() -> bool:
    return os.getenv("TERM") is not None or os.getenv("WT_SESSION") is not None or os.name == "nt"


def _paint(text: str, color: str, use_color: bool, *, bold: bool = False, dim: bool = False) -> str:
    if not use_color:
        return text
    prefix = ""
    if bold:
        prefix += BOLD
    if dim:
        prefix += DIM
    return f"{prefix}{color}{text}{RESET}"


def _visible_length(text: str) -> int:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return len(ansi_escape.sub('', text))


def _pad_visible(text: str, width: int) -> str:
    visible_len = _visible_length(text)
    if visible_len < width:
        return text + " " * (width - visible_len)
    return text
