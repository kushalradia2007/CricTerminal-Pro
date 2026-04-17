from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from config import AppConfig, get_config


def _fetch_json(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    config: AppConfig | None = None,
    endpoint: str | None = None,
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    if config is None:
        try:
            config = get_config()
        except RuntimeError as exc:
            return None, str(exc)

    url = urljoin(f"{config.base_url.rstrip('/')}/", path.lstrip("/"))
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(
        url,
        headers={
            "x-atd-key": config.api_key,
            "x-apihub-key": config.api_key,
            "x-apihub-host": config.api_host,
            "x-apihub-endpoint": endpoint or config.home_endpoint,
        },
    )

    try:
        with urlopen(request, timeout=config.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        return None, f"HTTP {exc.code}: {message}"
    except URLError as exc:
        return None, f"Network error: {exc.reason}"
    except json.JSONDecodeError:
        return None, "The API returned invalid JSON."
    except Exception as exc:  # pragma: no cover
        return None, str(exc)

    if isinstance(data, dict) and data.get("status") == "failure":
        return None, data.get("reason", "The API reported a failure.")

    return data, None


def get_current_matches() -> tuple[list[dict[str, Any]] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    data, error = _fetch_json(config.live_matches_path, config=config, endpoint=config.home_endpoint)
    if error:
        return None, error
    return _extract_live_matches(data), None


def get_match_scorecard(match_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    scorecard_path = config.scorecard_path_template.format(match_id=match_id)
    data, error = _fetch_json(scorecard_path, config=config, endpoint=config.scorecard_endpoint)
    if error:
        return None, error

    payload = _extract_scorecard_payload(data)
    if not isinstance(payload, dict):
        return None, "No scorecard payload was returned for this match."
    return payload, None


def get_match_info(match_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    match_info_path = config.match_info_path_template.format(match_id=match_id)
    data, error = _fetch_json(match_info_path, config=config, endpoint=config.match_info_endpoint)
    if error:
        return None, error
    if not isinstance(data, dict):
        return None, "No match info payload was returned for this match."
    return data, None


def get_match_commentary(match_id: str) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    commentary_path = config.commentary_path_template.format(match_id=match_id)
    return _fetch_json(commentary_path, config=config, endpoint=config.commentary_endpoint)


def parse_matches(matches: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    parsed_matches: list[dict[str, Any]] = []

    for match in matches or []:
        if not isinstance(match, dict):
            continue

        parsed_matches.append(
            {
                "id": str(_pick_nested_value(match, [["id"], ["matchId"], ["matchInfo", "matchId"]], "")),
                "name": _build_match_name(match),
                "matchType": _pick_nested_value(
                    match,
                    [["matchType"], ["matchFormat"], ["matchInfo", "matchFormat"]],
                    "unknown",
                ),
                "status": _pick_nested_value(
                    match,
                    [["status"], ["statusText"], ["matchInfo", "status"]],
                    "Status unavailable",
                ),
                "venue": _build_venue(match),
                "date": _pick_nested_value(match, [["date"], ["startDate"], ["matchInfo", "startDate"]], ""),
                "score": _extract_match_score(match),
                "teams": _extract_match_teams(match),
            }
        )

    return parsed_matches


def parse_scorecard(scorecard_payload: dict[str, Any]) -> dict[str, Any]:
    innings_payload = (
        scorecard_payload.get("scorecard")
        or scorecard_payload.get("innings")
        or scorecard_payload.get("scoreCard")
        or []
    )

    innings: list[dict[str, Any]] = []
    for innings_item in innings_payload:
        if not isinstance(innings_item, dict):
            continue

        batting_rows = _extract_batting_rows(innings_item)
        active_batting = [row for row in batting_rows if not row.get("_did_not_bat")]
        did_not_bat = [row["player"] for row in batting_rows if row.get("_did_not_bat")]

        innings.append(
            {
                "title": _build_innings_title(innings_item),
                "summary": _build_innings_summary(innings_item),
                "batting": active_batting,
                "bowling": _extract_bowling_rows(innings_item),
                "did_not_bat": did_not_bat
                or _extract_name_list(
                    innings_item,
                    ["did_not_bat", "didNotBat", "yetToBat", "yet_to_bat"],
                ),
                "extras": _extract_extras(innings_item),
            }
        )

    derived_score = scorecard_payload.get("score") or _extract_match_score(scorecard_payload)
    if not derived_score:
        derived_score = _derive_score_from_innings(innings)

    parsed = {
        "match": {
            "id": str(scorecard_payload.get("id", "")),
            "name": scorecard_payload.get("name") or _build_match_name(scorecard_payload),
            "match_type": _pick_first_value(scorecard_payload, ["matchType", "matchFormat"], default="unknown"),
            "status": _pick_first_value(scorecard_payload, ["status", "statusText"], default="Status unavailable"),
            "venue": scorecard_payload.get("venue") or _build_venue(scorecard_payload),
            "date": _pick_first_value(scorecard_payload, ["date", "startDate"]),
            "teams": scorecard_payload.get("teams") or _extract_match_teams(scorecard_payload),
            "toss": _pick_first_value(scorecard_payload, ["tossWinner", "tossResults"]),
            "result": _pick_first_value(scorecard_payload, ["status", "statusText"]),
            "series": _pick_first_value(scorecard_payload, ["seriesName", "seriesname"]),
        },
        "score": derived_score,
        "innings": innings,
        "live": {
            "commentary": [],
            "commentary_error": "",
            "last_six_balls": [],
            "last_six_overs_runs": [],
            "current_run_rate": "-",
            "required_run_rate": "-",
            "partnership_runs": "-",
            "partnership_balls": "-",
            "partnership_batters": [],
            "target_text": "",
            "recent_over_summary": "",
            "current_batters": [],
            "current_bowler": "",
        },
    }
    return _derive_live_metrics(parsed)


def _extract_live_matches(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    extracted = _flatten_match_containers(data)
    return _dedupe_matches(extracted)


def _flatten_match_containers(value: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue

            if isinstance(item.get("match"), dict):
                matches.extend(_flatten_match_containers(item["match"]))
                continue

            if "matchInfo" in item or "matchScore" in item or "status" in item:
                matches.append(item)
                continue

            for key in ["match", "seriesMatches", "matchDetailsMap", "matches", "data"]:
                nested = item.get(key)
                matches.extend(_flatten_match_containers(nested))

    elif isinstance(value, dict):
        if "matchInfo" in value or "matchScore" in value or "status" in value:
            matches.append(value)

        for key in ["match", "matchInfo", "seriesMatches", "matchDetailsMap", "matches", "data"]:
            nested = value.get(key)
            if nested is not None:
                matches.extend(_flatten_match_containers(nested))

        for nested in value.values():
            if isinstance(nested, (dict, list)):
                matches.extend(_flatten_match_containers(nested))

    return matches


def _dedupe_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for match in matches:
        match_id = str(_pick_nested_value(match, [["id"], ["matchId"], ["matchInfo", "matchId"]], ""))
        fingerprint = match_id or json.dumps(match, sort_keys=True, default=str)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(match)

    return deduped


def _extract_scorecard_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None

    for key in ["data", "scoreCard", "scorecard"]:
        candidate = data.get(key)
        if isinstance(candidate, dict):
            return candidate

    return data


def _extract_team_names(team_info: Any) -> list[str]:
    teams: list[str] = []
    for item in team_info or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("shortname")
            if name:
                teams.append(str(name))
        elif item:
            teams.append(str(item))
    return teams


def _extract_match_teams(match: dict[str, Any]) -> list[str]:
    teams = match.get("teams")
    if isinstance(teams, list) and teams:
        return [str(team) for team in teams]

    team_names: list[str] = []
    team1 = _extract_team_name_obj(match.get("team1")) or _extract_team_name_obj(_pick_nested_object(match, ["matchInfo", "team1"]))
    team2 = _extract_team_name_obj(match.get("team2")) or _extract_team_name_obj(_pick_nested_object(match, ["matchInfo", "team2"]))

    for team in [team1, team2]:
        if team:
            team_names.append(team)

    if team_names:
        return team_names

    return _extract_team_names(match.get("teamInfo"))


def _extract_team_name_obj(value: Any) -> str:
    if isinstance(value, dict):
        for key in ["teamName", "teamname", "name", "teamSName", "teamsname", "shortName"]:
            if value.get(key):
                return str(value[key])
    elif value not in (None, ""):
        return str(value)
    return ""


def _build_match_name(match: dict[str, Any]) -> str:
    if match.get("name"):
        return str(match["name"])

    teams = _extract_match_teams(match)
    match_desc = _pick_first_value(match, ["matchDesc", "matchdesc"])
    if len(teams) >= 2 and match_desc:
        return f"{teams[0]} vs {teams[1]} - {match_desc}"
    if len(teams) >= 2:
        return f"{teams[0]} vs {teams[1]}"

    for key in ["seriesName", "seriesname"]:
        if match.get(key):
            return str(match[key])

    info = match.get("matchInfo")
    if isinstance(info, dict):
        if info.get("matchDesc"):
            teams = _extract_match_teams(match)
            if len(teams) >= 2:
                return f"{teams[0]} vs {teams[1]} - {info['matchDesc']}"
        if info.get("seriesName"):
            return str(info["seriesName"])

    if teams:
        return " vs ".join(teams)
    return "Unknown match"


def _build_venue(match: dict[str, Any]) -> str:
    if match.get("venue"):
        return str(match["venue"])

    venue_info = match.get("venueInfo") or match.get("venueinfo")
    if isinstance(venue_info, dict):
        parts = [venue_info.get("ground"), venue_info.get("city"), venue_info.get("country")]
        rendered = ", ".join(str(part) for part in parts if part)
        if rendered:
            return rendered

    info = match.get("matchInfo")
    if isinstance(info, dict) and isinstance(info.get("venueInfo"), dict):
        parts = [
            info["venueInfo"].get("ground"),
            info["venueInfo"].get("city"),
            info["venueInfo"].get("country"),
        ]
        rendered = ", ".join(str(part) for part in parts if part)
        if rendered:
            return rendered

    return "Venue unavailable"


def _extract_match_score(match: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(match.get("score"), list):
        return match["score"]

    match_score = match.get("matchScore")
    if isinstance(match_score, dict):
        innings_rows: list[dict[str, Any]] = []
        for key, label in [
            ("team1Score", "Team 1"),
            ("team2Score", "Team 2"),
        ]:
            team_score = match_score.get(key)
            if not isinstance(team_score, dict):
                continue

            innings_rows.append(
                {
                    "inning": team_score.get("inngs1", {}).get("inningsId")
                    or team_score.get("inngs1", {}).get("inningsNum")
                    or label,
                    "r": _pick_nested_value(team_score, [["inngs1", "runs"]], 0),
                    "w": _pick_nested_value(team_score, [["inngs1", "wickets"]], 0),
                    "o": _pick_nested_value(team_score, [["inngs1", "overs"]], 0),
                }
            )
            if isinstance(team_score.get("inngs2"), dict):
                innings_rows.append(
                    {
                        "inning": team_score.get("inngs2", {}).get("inningsId")
                        or team_score.get("inngs2", {}).get("inningsNum")
                        or f"{label} 2",
                        "r": _pick_nested_value(team_score, [["inngs2", "runs"]], 0),
                        "w": _pick_nested_value(team_score, [["inngs2", "wickets"]], 0),
                        "o": _pick_nested_value(team_score, [["inngs2", "overs"]], 0),
                    }
                )
        return innings_rows

    return []


def _pick_first_value(source: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _pick_nested_value(source: dict[str, Any], paths: list[list[str]], default: Any = "") -> Any:
    for path in paths:
        current: Any = source
        found = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current[key]
        if found and current not in (None, ""):
            return current
    return default


def _pick_nested_object(source: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, dict) else None


def _extract_batting_rows(innings_item: dict[str, Any]) -> list[dict[str, str]]:
    rows = _extract_table_rows(
        innings_item,
        ["batting", "battingScorecard", "batters", "batsman", "batsmenData"],
    )
    parsed: list[dict[str, str]] = []

    for row in rows:
        player_name = _extract_player_name(row, ["batsman", "batter", "player", "name"])
        dismissal = _pick_first_value(
            row,
            ["dismissal-text", "dismissal", "wicket", "howOut", "out_desc", "outDesc", "outdec"],
            default="not out",
        )
        runs = _stringify_stat(row, ["r", "runs"])
        balls = _stringify_stat(row, ["b", "balls"])
        did_not_bat = _is_did_not_bat_batter(row, dismissal, runs, balls)

        parsed.append(
            {
                "player": player_name,
                "dismissal": dismissal,
                "runs": runs,
                "balls": balls,
                "fours": _stringify_stat(row, ["4s", "fours"]),
                "sixes": _stringify_stat(row, ["6s", "sixes"]),
                "strike_rate": _stringify_stat(row, ["sr", "strikeRate", "s/r", "strkrate"]),
                "_did_not_bat": "yes" if did_not_bat else "",
            }
        )

    return parsed


def _extract_bowling_rows(innings_item: dict[str, Any]) -> list[dict[str, str]]:
    rows = _extract_table_rows(
        innings_item,
        ["bowling", "bowlingScorecard", "bowlers", "bowler", "bowlersData"],
    )
    parsed: list[dict[str, str]] = []

    for row in rows:
        player_name = _extract_player_name(row, ["bowler", "player", "name"])
        parsed.append(
            {
                "player": player_name,
                "overs": _stringify_stat(row, ["o", "overs"]),
                "maidens": _stringify_stat(row, ["m", "maidens"]),
                "runs": _stringify_stat(row, ["r", "runs"]),
                "wickets": _stringify_stat(row, ["w", "wickets"]),
                "economy": _stringify_stat(row, ["eco", "economy"]),
                "no_balls": _stringify_stat(row, ["nb", "noballs", "noBalls"]),
                "wides": _stringify_stat(row, ["wd", "wides"]),
            }
        )

    return parsed


def _extract_table_rows(source: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            rows = [item for item in value.values() if isinstance(item, dict)]
            if rows:
                return rows
    return []


def _extract_name_list(source: dict[str, Any], keys: list[str]) -> list[str]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            names = [_extract_player_name(item, ["player", "name"]) for item in value]
            return [name for name in names if name]
        if isinstance(value, str) and value.strip():
            return [name.strip() for name in value.split(",") if name.strip()]
    return []


def _extract_extras(innings_item: dict[str, Any]) -> str:
    extras = innings_item.get("extras")
    if isinstance(extras, dict):
        total = _pick_first_value(extras, ["total", "r", "runs"])
        breakdown = []
        for key in ["b", "lb", "wd", "nb", "penalty"]:
            val = extras.get(key)
            if val not in (None, "", 0, "0"):
                breakdown.append(f"{key} {val}")
        if total:
            suffix = f" ({', '.join(breakdown)})" if breakdown else ""
            return f"{total}{suffix}"
    if extras not in (None, ""):
        return str(extras)
    return ""


def _build_innings_title(innings_item: dict[str, Any]) -> str:
    explicit = _pick_first_value(
        innings_item,
        ["inning", "innings", "title", "name"],
    )
    if explicit:
        return explicit

    innings_id = innings_item.get("inningsid")
    if innings_id not in (None, ""):
        return f"Innings {innings_id}"

    return "Innings"


def _is_did_not_bat_batter(row: dict[str, Any], dismissal: str, runs: str, balls: str) -> bool:
    dismissal_text = dismissal.strip().lower()
    no_balls_faced = balls in {"0", "-", "0.0"}
    no_runs = runs in {"0", "-"}
    if dismissal_text in {"", "-", "dnb"} and no_balls_faced and no_runs:
        return True
    if dismissal_text == "not out" and no_balls_faced and no_runs and not row.get("outdec"):
        return True
    return False


def _extract_player_name(row: Any, keys: list[str]) -> str:
    if isinstance(row, str):
        return row

    if not isinstance(row, dict):
        return "Unknown"

    for key in keys:
        value = row.get(key)
        if isinstance(value, dict):
            nested = value.get("name") or value.get("fullName") or value.get("shortName")
            if nested:
                return str(nested)
        elif value not in (None, ""):
            return str(value)

    return "Unknown"


def _stringify_stat(source: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return str(value)
    return "-"


def _build_innings_summary(innings_item: dict[str, Any]) -> str:
    runs = _pick_first_value(innings_item, ["r", "runs", "score", "inngs1"])
    wickets = _pick_first_value(innings_item, ["w", "wickets"], default="-")
    overs = _pick_first_value(innings_item, ["o", "overs"], default="-")

    if runs:
        return f"{runs}/{wickets} ({_format_overs_value(overs)} ov)"
    return "Score unavailable"


def _format_overs_value(value: Any) -> str:
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


def enrich_scorecard_with_match_info(scorecard: dict[str, Any], match_info_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(match_info_payload, dict):
        return scorecard

    merged = dict(scorecard)
    match = dict(scorecard.get("match", {}))

    match["id"] = str(
        _pick_nested_value(match_info_payload, [["matchInfo", "matchId"], ["matchId"]], match.get("id", ""))
    )
    match["name"] = _build_match_name(match_info_payload) or match.get("name", "Unknown match")
    match["match_type"] = _pick_nested_value(
        match_info_payload,
        [["matchInfo", "matchFormat"], ["matchFormat"], ["matchformat"], ["matchType"], ["matchtype"]],
        match.get("match_type", "unknown"),
    )
    match["status"] = _pick_nested_value(
        match_info_payload,
        [["matchInfo", "status"], ["shortstatus"], ["status"], ["statusText"]],
        match.get("status", "Status unavailable"),
    )
    match["venue"] = _build_venue(match_info_payload) or match.get("venue", "Venue unavailable")
    match["date"] = _pick_nested_value(
        match_info_payload,
        [["matchInfo", "startDate"], ["startDate"], ["date"]],
        match.get("date", ""),
    )
    match["teams"] = _extract_match_teams(match_info_payload) or match.get("teams", [])

    match["series"] = _pick_nested_value(
        match_info_payload,
        [["seriesName"], ["matchInfo", "seriesName"]],
        match.get("series", ""),
    )
    match["toss"] = _pick_nested_value(
        match_info_payload,
        [["tossResults", "tossWinnerName"], ["tossResults", "result"], ["tossWinner"], ["tossResults"]],
        match.get("toss", ""),
    )

    merged["match"] = match
    return _derive_live_metrics(merged)


def enrich_scorecard_with_commentary(
    scorecard: dict[str, Any],
    commentary_payload: dict[str, Any] | list[Any] | None,
    commentary_error: str | None = None,
) -> dict[str, Any]:
    commentary = parse_commentary(commentary_payload)
    merged = dict(scorecard)
    live = dict(merged.get("live", {}))
    live["commentary"] = commentary
    live["commentary_error"] = commentary_error or ""
    live["last_six_balls"] = _extract_last_six_balls(commentary)
    live["last_six_overs_runs"] = _extract_last_six_overs_runs(commentary)
    live["recent_over_summary"] = _build_recent_over_summary(commentary)
    live["current_bowler"] = live.get("current_bowler") or _extract_current_bowler(commentary)
    merged["live"] = live
    return _derive_live_metrics(merged)


def parse_commentary(commentary_payload: dict[str, Any] | list[Any] | None) -> list[dict[str, str]]:
    entries = _flatten_commentary_entries(commentary_payload)
    parsed: list[dict[str, str]] = []

    for entry in entries:
        over = _pick_first_value(entry, ["overNumber", "over", "ballNbr", "o", "overNo", "overnum"])
        ball = _pick_first_value(entry, ["ballNumber", "ball", "b", "ballNo", "ballnbr"])
        prefix = _pick_first_value(entry, ["commText", "commtxt", "event", "title", "headline"])
        text = _extract_commentary_text(entry)
        outcome = _extract_commentary_outcome(entry)

        if not text and not prefix:
            continue

        label = ""
        if over and ball:
            label = f"{over}.{ball}"
        elif over:
            label = str(over)

        rendered_text = text or prefix
        if prefix and text and prefix != text and prefix.lower() not in text.lower():
            rendered_text = f"{prefix} - {text}"

        rendered_text = _clean_commentary_text(rendered_text)
        if not rendered_text:
            continue

        parsed.append({"label": label, "text": rendered_text.strip(), "outcome": str(outcome).strip()})

    return parsed[:12]


def _flatten_commentary_entries(payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        flattened: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                if _is_commentary_entry(item):
                    flattened.append(item)
                else:
                    flattened.extend(_flatten_commentary_entries(item))
            elif isinstance(item, list):
                flattened.extend(_flatten_commentary_entries(item))
        return flattened

    if not isinstance(payload, dict):
        return []

    if _is_commentary_entry(payload):
        return [payload]

    for key in [
        "commentaryList",
        "commentary",
        "commentaryLines",
        "items",
        "data",
        "oversep",
        "overSeparator",
        "commentaryListItems",
    ]:
        value = payload.get(key)
        if isinstance(value, list):
            return _flatten_commentary_entries(value)
        if isinstance(value, dict):
            nested = _flatten_commentary_entries(value)
            if nested:
                return nested

    flattened = []
    for value in payload.values():
        if isinstance(value, dict):
            flattened.extend(_flatten_commentary_entries(value))
        elif isinstance(value, list):
            flattened.extend(_flatten_commentary_entries(value))
    return flattened


def _is_commentary_entry(value: dict[str, Any]) -> bool:
    return any(
        key in value
        for key in ["commtxt", "commText", "commentary", "commentText", "eventtype", "overnum", "ballnbr"]
    )


def _extract_commentary_text(entry: dict[str, Any]) -> str:
    for key in ["commtxt", "commentary", "commText", "text", "commentText", "detail", "description"]:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _extract_commentary_outcome(entry: dict[str, Any]) -> str:
    oversep = entry.get("oversep")
    if isinstance(oversep, dict):
        over_summary = oversep.get("oversummary")
        if isinstance(over_summary, str) and over_summary.strip():
            return over_summary.strip()

    event = _pick_first_value(entry, ["eventtype", "event"])
    if event.upper() == "FOUR":
        return "4"
    if event.upper() == "SIX":
        return "6"
    if event.upper() in {"WICKET", "OUT"}:
        return "W"

    runs = _pick_first_value(entry, ["runs", "shortText"])
    if runs:
        return runs
    return ""


def _clean_commentary_text(text: str) -> str:
    cleaned = text.replace("\\n", " ").replace("\n", " ")
    cleaned = re.sub(r"[A-Z]\d+\$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    if cleaned.lower().startswith("overs:") or cleaned.lower().startswith("wickets:"):
        return ""
    return cleaned


def _derive_live_metrics(scorecard: dict[str, Any]) -> dict[str, Any]:
    merged = dict(scorecard)
    live = dict(merged.get("live", {}))
    innings = merged.get("innings", [])
    score = merged.get("score", [])

    current_innings = innings[-1] if innings else {}
    batting_rows = current_innings.get("batting", [])
    bowling_rows = current_innings.get("bowling", [])
    live["current_batters"] = _extract_current_batters(batting_rows)
    if not live.get("current_bowler"):
        live["current_bowler"] = bowling_rows[0]["player"] if bowling_rows else ""

    live["current_run_rate"] = _calculate_current_run_rate(score)
    live["required_run_rate"] = _calculate_required_run_rate(score)
    target_text, target_runs, target_balls_left = _build_target_text(score)
    live["target_text"] = target_text
    if live["required_run_rate"] == "-" and target_runs is not None and target_balls_left:
        live["required_run_rate"] = f"{(target_runs / target_balls_left) * 6:.2f}"

    partnership = _estimate_partnership(batting_rows)
    live["partnership_runs"] = partnership["runs"]
    live["partnership_balls"] = partnership["balls"]
    live["partnership_batters"] = partnership["batters"]

    merged["live"] = live
    return merged


def _extract_current_batters(batting_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    active = [
        {"player": row["player"], "runs": row["runs"], "balls": row["balls"]}
        for row in batting_rows
        if str(row.get("dismissal", "")).strip().lower() in {"not out", "", "-"}
    ]
    if len(active) >= 2:
        return active[:2]

    fallback = [
        {"player": row["player"], "runs": row["runs"], "balls": row["balls"]}
        for row in batting_rows[-2:]
    ]
    return fallback[:2]


def _calculate_current_run_rate(score: list[dict[str, Any]]) -> str:
    if not score:
        return "-"
    latest = score[-1]
    runs = _safe_int(latest.get("r"))
    overs = _overs_to_balls(latest.get("o"))
    if runs is None or overs in (None, 0):
        return "-"
    return f"{(runs / overs) * 6:.2f}"


def _calculate_required_run_rate(score: list[dict[str, Any]]) -> str:
    _, runs_needed, balls_left = _build_target_text(score)
    if runs_needed is None or balls_left in (None, 0):
        return "-"
    return f"{(runs_needed / balls_left) * 6:.2f}"


def _build_target_text(score: list[dict[str, Any]]) -> tuple[str, int | None, int | None]:
    if len(score) < 2:
        return "", None, None

    first = score[0]
    latest = score[-1]
    first_runs = _safe_int(first.get("r"))
    latest_runs = _safe_int(latest.get("r"))
    latest_wkts = _safe_int(latest.get("w"))
    latest_balls = _overs_to_balls(latest.get("o"))
    if first_runs is None or latest_runs is None or latest_balls is None:
        return "", None, None

    target = first_runs + 1
    runs_needed = max(target - latest_runs, 0)
    balls_left = max(120 - latest_balls, 0)
    if runs_needed == 0:
        return "Target chased", 0, balls_left
    if latest_wkts == 10 or balls_left == 0:
        return f"Target {target}", runs_needed, balls_left
    return f"Need {runs_needed} from {balls_left} balls (target {target})", runs_needed, balls_left


def _estimate_partnership(batting_rows: list[dict[str, str]]) -> dict[str, Any]:
    active = _extract_current_batters(batting_rows)
    if len(active) < 2:
        return {"runs": "-", "balls": "-", "batters": active}

    runs = sum(_safe_int(player["runs"]) or 0 for player in active)
    balls = sum(_safe_int(player["balls"]) or 0 for player in active)
    return {"runs": str(runs), "balls": str(balls), "batters": active}


def _derive_score_from_innings(innings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    for index, innings_item in enumerate(innings, start=1):
        summary = str(innings_item.get("summary", "")).strip()
        runs, wickets, overs = _parse_summary_score(summary)
        if runs is None:
            continue
        derived.append(
            {
                "inning": innings_item.get("title") or f"Innings {index}",
                "r": runs,
                "w": wickets if wickets is not None else 0,
                "o": overs if overs is not None else "-",
            }
        )
    return derived


def _parse_summary_score(summary: str) -> tuple[int | None, int | None, str | None]:
    match = re.search(r"(\d+)\s*/\s*(\d+)(?:\s*\(([^)]+)\))?", summary)
    if not match:
        return None, None, None
    runs = _safe_int(match.group(1))
    wickets = _safe_int(match.group(2))
    overs_text = match.group(3) or ""
    overs_text = overs_text.replace("ov", "").strip()
    return runs, wickets, overs_text or None


def _extract_last_six_balls(commentary: list[dict[str, str]]) -> list[str]:
    balls: list[str] = []
    for entry in commentary:
        if not entry.get("label"):
            continue
        token = _ball_token(entry)
        if token:
            balls.append(token)
        if len(balls) == 6:
            break
    return balls


def _extract_last_six_overs_runs(commentary: list[dict[str, str]]) -> list[int]:
    """Group commentary ball entries by over number and sum runs per over.

    Returns the run totals for the most recent 6 overs (oldest first),
    which the UI layer renders as a sparkline.
    """
    overs: dict[str, int] = {}
    for entry in commentary:
        label = entry.get("label", "")
        if not label or "." not in label:
            continue
        over_number = label.split(".", 1)[0]
        overs.setdefault(over_number, 0)
        overs[over_number] += _ball_runs(entry)
    if not overs:
        return []
    # Commentary arrives newest-first; reverse to get chronological order
    over_keys = list(overs.keys())
    over_keys.reverse()
    return [overs[k] for k in over_keys[-6:]]


def _build_recent_over_summary(commentary: list[dict[str, str]]) -> str:
    if not commentary:
        return ""
    ball_entries = [entry for entry in commentary if entry.get("label")]
    if not ball_entries:
        return ""

    first_over = ball_entries[0]["label"].split(".", 1)[0]
    same_over = [entry for entry in ball_entries if entry["label"].split(".", 1)[0] == first_over][:6]
    if not same_over:
        return ""

    runs = sum(_ball_runs(entry) for entry in same_over)
    wickets = sum(1 for entry in same_over if _ball_is_wicket(entry))
    summary = f"Over {first_over}: {runs} runs"
    if wickets:
        summary += f", {wickets} wicket"
        if wickets > 1:
            summary += "s"
    return summary


def _extract_current_bowler(commentary: list[dict[str, str]]) -> str:
    for entry in commentary:
        text = entry.get("text", "")
        if " to " in text:
            bowler = text.split(" to ", 1)[0].strip(" -")
            if bowler:
                return bowler
    return ""


def _ball_token(entry: dict[str, str]) -> str:
    text = f"{entry.get('outcome', '')} {entry.get('text', '')}".lower()
    if "wide" in text and "wicket" not in text:
        return "Wd"
    if "no ball" in text or "noball" in text:
        return "Nb"
    if any(word in text for word in ["out", "wicket", "run out", "lbw", "bowled", "caught"]):
        return "W"
    runs = _ball_runs(entry)
    if runs is not None:
        return str(runs)
    return ""


def _ball_runs(entry: dict[str, str]) -> int:
    text = f"{entry.get('outcome', '')} {entry.get('text', '')}".lower()
    if "six" in text:
        return 6
    if "four" in text:
        return 4
    for candidate in ["0", "1", "2", "3", "4", "5", "6"]:
        token = f" {candidate} "
        if token in f" {text} ":
            return int(candidate)
    return 0


def _ball_is_wicket(entry: dict[str, str]) -> bool:
    text = f"{entry.get('outcome', '')} {entry.get('text', '')}".lower()
    return any(word in text for word in ["out", "wicket", "run out", "lbw", "bowled", "caught"])


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _overs_to_balls(value: Any) -> int | None:
    text = str(value)
    if not text or text == "-":
        return None
    if "." not in text:
        whole = _safe_int(text)
        return whole * 6 if whole is not None else None

    whole, balls = text.split(".", 1)
    whole_value = _safe_int(whole)
    balls_value = _safe_int(balls)
    if whole_value is None or balls_value is None:
        return None
    return (whole_value * 6) + balls_value
