# 🏏 CricTerminal Pro

> **Live IPL & cricket scores, scorecards, commentary, and live stats — all inside your terminal.**  
> No browser. No distractions. Pure cricket.

```
+--------------------------------------------------------------------+
|                        CricTerminal Pro                            |
+--------------------------------------------------------------------+
```

---

## ✨ What Is This?

**CricTerminal Pro** is a beautifully crafted Python terminal dashboard for live cricket.  
It fetches real-time match data from the Cricbuzz Official API and renders everything — scorecards, batting/bowling tables, live run rates, partnership stats, last-6-balls, over sparklines, and ball-by-ball commentary — right in your terminal window.

No GUI needed. Just your keyboard and a love for cricket.

---

## 🚀 Features

| Feature | Description |
|---|---|
| 📋 **Live Match List** | Browse all currently live/ongoing matches at launch |
| 🏏 **Full Scorecard** | Batting & bowling tables with rich ANSI color formatting |
| 📡 **Live Watch Mode** | Auto-refreshes the scorecard every N seconds (`--watch`) |
| 🔢 **Run Rate Stats** | Current Run Rate (CRR) and Required Run Rate (RRR) |
| 🤝 **Partnership Tracker** | Live partnership runs & balls for the current pair |
| 🕐 **Last 6 Balls** | Ball-by-ball tokens: `[4]`, `[W]`, `[Wd]`, `[0]`, etc. |
| 📊 **Sparkline Chart** | Unicode bar-graph of runs per over for the last 6 overs |
| 💬 **Commentary** | Over summary & recent ball commentary pulled live |
| 🪶 **Minimal Mode** | Single-line compact score for tiny panes (`--minimal`) |
| 🎨 **Color Support** | Rich ANSI colors on Linux, macOS, and Windows Terminal |
| ⚙️ **Zero Dependencies** | Uses **only the Python standard library** — no `pip install` needed |

---

## 📸 Terminal Preview

```
+--------------------------------------------------------------------+
| 1. Mumbai Indians vs Chennai Super Kings                           |
| T20 | Live                                                         |
| Wankhede Stadium, Mumbai                                           |
| MI Innings: 187/4 (20 ov)                                         |
| CSK Innings: 143/7 (17.3 ov)                                      |
+--------------------------------------------------------------------+

+- BATTING ----------------------------------------------------------+
| Batter             R    B    4s   6s   SR                         |
| -------            ---  ---  ---  ---  ------                     |
| * Ruturaj Gaikwad  52   38   6    2    136.84                     |
|   Devon Conway     31   28   3    1    110.71                     |
+--------------------------------------------------------------------+

+- RUN RATE -----+  +- PARTNERSHIP ---+  +- LAST 6 BALLS --------+
| CRR: 8.22      |  | 83 runs | 51 b  |  | [1] [4] [W] [0] [6] [2]|
| RRR: 13.14     |  | Gaikwad: 52(38) |  | Over 17: 9 runs        |
| Runs/Over: ▃▅▇▆▄▇|  | Conway: 31(28)  |  |                        |
+----------------+  +-----------------+  +------------------------+
```

---

## 🛠️ Requirements

- **Python 3.9 or higher**
- A valid **Cricbuzz Official API** key from [AllThingsDev](https://allthingsdev.co) or RapidAPI
- That's it — **no external packages required**

---

## ⚡ Quickstart

### 1. Clone the Repository

```bash
git clone https://github.com/kushalradia2007/CricTerminal-Pro.git
cd CricTerminal-Pro
```

### 2. Set Up Your API Key

Copy the example config file and fill in your key:

```bash
cp rapidapi_config_example.json rapidapi_config.json
```

Then open `rapidapi_config.json` and replace the placeholder:

```json
{
  "x-apihub-host": "Cricbuzz-Official-Cricket-API.allthingsdev.co",
  "x-apihub-key": "YOUR_API_KEY_HERE",
  "base_url": "https://Cricbuzz-Official-Cricket-API.proxy-production.allthingsdev.co",
  ...
}
```

> **Alternatively**, you can use an environment variable:
> ```bash
> export APIHUB_KEY="your_api_key_here"
> ```

### 3. Run It!

```bash
python main.py
```

---

## 💻 Running on Your Local Terminal (Windows / macOS / Linux)

This project is designed to run in any standard terminal. Here's how to do it on each platform:

### 🪟 Windows

1. Install Python from [python.org](https://python.org) if you haven't already
2. Open **Windows Terminal** or **PowerShell** (recommended for color support)
3. Run the following:

```powershell
git clone https://github.com/kushalradia2007/CricTerminal-Pro.git
cd CricTerminal-Pro
copy rapidapi_config_example.json rapidapi_config.json
# Edit rapidapi_config.json with your API key, then:
python main.py
```

> ⚠️ **Use Windows Terminal or PowerShell** for proper ANSI color rendering. The classic `cmd.exe` may not render colors correctly.

### 🍎 macOS

```bash
git clone https://github.com/kushalradia2007/CricTerminal-Pro.git
cd CricTerminal-Pro
cp rapidapi_config_example.json rapidapi_config.json
# Edit rapidapi_config.json with your API key, then:
python3 main.py
```

### 🐧 Linux

```bash
git clone https://github.com/kushalradia2007/CricTerminal-Pro.git
cd CricTerminal-Pro
cp rapidapi_config_example.json rapidapi_config.json
# Edit rapidapi_config.json with your API key, then:
python3 main.py
```

> 💡 **Tip:** Make sure your `TERM` environment variable is set (it is by default in most Linux terminals). Run `echo $TERM` to verify — any non-empty output means colors will work.

---

## 🎮 Usage & CLI Options

```
python main.py [OPTIONS]
```

| Option | Description | Example |
|---|---|---|
| *(no options)* | Show live match list, then pick one interactively | `python main.py` |
| `--match N` | Jump directly to match number N | `python main.py --match 2` |
| `--watch` | Auto-refresh the scorecard live | `python main.py --watch` |
| `--interval N` | Set refresh interval in seconds (default: 15, min: 5) | `python main.py --watch --interval 10` |
| `--minimal` | Compact single-line score output | `python main.py --minimal` |

### Examples

```bash
# Browse live matches and pick one interactively
python3 main.py

# Directly open match #1 and start live watch mode, refreshing every 10s
python3 main.py --match 1 --watch --interval 10

# Use minimal mode in a small tmux/screen pane
python3 main.py --match 1 --minimal --watch

# Jump straight to a match by its API match ID
python3 main.py --match 87654321
```

---

## ⚙️ Configuration

The app looks for your API key and settings in the following order (first match wins):

1. **Environment variables** — `APIHUB_KEY`, `RAPIDAPI_KEY`
2. **`.env` file** — key-value pairs like `APIHUB_KEY=your_key`
3. **`rapidapi_config.json`** — JSON file with your config

### `rapidapi_config.json` fields

| Field | Description |
|---|---|
| `x-apihub-key` | Your API key from AllThingsDev |
| `x-apihub-host` | API host (pre-filled in example) |
| `base_url` | Base URL of the Cricbuzz proxy API |
| `live_matches_path` | Path to fetch the live match list |
| `scorecard_path_template` | Path template for scorecards (uses `{match_id}`) |
| `commentary_path_template` | Path template for commentary |
| `match_info_path_template` | Path template for match info |

---

## 📁 Project Structure

```
CricTerminal-Pro/
├── main.py                      # Entry point, CLI argument parsing, match selection
├── api.py                       # API calls, JSON parsing, live metrics derivation
├── ui.py                        # Terminal rendering (boxes, tables, colors, sparklines)
├── config.py                    # Configuration loading (env vars, .env, JSON)
├── rapidapi_config.json         # Your personal API config (gitignored)
├── rapidapi_config_example.json # Template — copy this to get started
├── requirements.txt             # (Empty — no external dependencies!)
└── .gitignore
```

---

## 🔑 Getting an API Key

1. Visit [AllThingsDev — Cricbuzz Official Cricket API](https://allthingsdev.co)
2. Sign up for a free or paid plan
3. Copy your API key
4. Paste it into `rapidapi_config.json` under the `x-apihub-key` field

> The app also works with **RapidAPI** keys — use the `x-rapidapi-key` / `RAPIDAPI_KEY` fields in your config.

---

## 🧠 How It Works

```
main.py         →  Fetches live match list via api.py
                →  Renders match list via ui.py
                →  User picks a match
                →  Fetches scorecard + match info + commentary in parallel
                →  Enriches scorecard with live metrics (CRR, RRR, partnerships)
                →  Renders full colored scorecard dashboard
                →  [Watch mode] Loops every N seconds with screen clear + re-render
```

The `api.py` module is responsible for all data fetching and parsing. It robustly handles multiple API response shapes (different Cricbuzz API versions) and derives live metrics (run rates, partnerships, over summaries) from raw data.

The `ui.py` module is a pure rendering layer — it takes parsed data dictionaries and produces ANSI-colored terminal output with responsive width handling, dynamic table column shrinking, and Unicode sparklines.

---

## 🤝 Contributing

Pull requests and issues are welcome! If the API changes its response format or you find a match type that isn't parsed correctly, please open an issue with the raw API response (with your key redacted).

---

## 📄 License

This project is open source. See the repository for license details.

---

## 🙏 Acknowledgements

- **Cricbuzz Official Cricket API** via [AllThingsDev](https://allthingsdev.co) for live cricket data
- Built with nothing but Python's standard library — because sometimes less is more 🐍

---

*Made with ❤️ for cricket fans who live in the terminal.*
