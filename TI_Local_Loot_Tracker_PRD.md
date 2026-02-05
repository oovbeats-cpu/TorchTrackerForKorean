# Torchlight Infinite Local Loot Tracker (WealthyExile-style) — Requirements Document (PRD)

## 1. Goal
Build a **fully local**, **Windows portable** desktop application that reads Torchlight Infinite log files, tracks loot/value over time, and presents a WealthyExile-like dashboard:

- **Net worth** (estimated total inventory value) in **FE**
- **Profit per map** and **profit per hour** over time
- **Itemized breakdown** of gains/losses per run
- **Local-only**: no cloud dependency required to function
- **Portable EXE** distribution: end users should not need to install Python/Node/dependencies.

## 2. Non-Goals (Explicit)
- No cheating/hooking/memory reading/packet inspection.
- No requirement to integrate with official APIs (none assumed).
- No mandatory internet connectivity. (Optional fetches allowed only if explicitly enabled by user.)
- No automatic “auction house scanning” unless it comes via **log output** or user-imported data.

## 3. Target Users
- Torchlight Infinite players on Windows (Steam install).
- Players who can enable “verbose logging” inside TI to emit item pickup events.
- Users who want local privacy, local data, and no VPN.

## 4. Key Concepts & Definitions
- **FE**: Flame Elementium (primary valuation currency).
- **ConfigBaseId**: item type identifier observed in logs (e.g., FE = `100300`).
- **Run / Map Run**: a single “map instance” (Netherrealm map) from entry to completion/exit. Definition based on log boundaries.
- **Delta tracking**: logs report new stack totals (`Num=`), so tracker computes changes by comparing with previous known state.

## 5. High-Level Architecture
### 5.1 Components
1) **Collector (Log Tailer + Parser)**
- Watches TI log file(s) and parses events continuously.
- Computes per-item deltas and assigns them to runs.

2) **Local Database**
- SQLite (WAL mode) to store runs, deltas, state, prices, and settings.

3) **Price Engine**
- Maintains mapping `ConfigBaseId → price_fe`.
- Supports manual edits and import/export of price lists.
- Supports “unknown ID” workflow.

4) **Local Web UI**
- Served locally (FastAPI static + API).
- Browser-based UI by default (opens automatically).
- Optional future wrapper (pywebview/Tauri), not required for MVP.

5) **Packaged Windows App**
- Single portable EXE (PyInstaller recommended).
- On startup: starts server + collector and opens UI.

### 5.2 Proposed Tech Stack (Option A)
- Language: **Python 3.11+**
- API: FastAPI + Uvicorn
- DB: SQLite
- UI: React build (or simple HTML/HTMX for MVP)
- Packaging: PyInstaller one-folder or one-file

## 6. Data Source & Parsing Requirements
### 6.1 Log Location (Windows Steam)
User will point app to log file; app should also attempt auto-detect:
`<SteamLibrary>\steamapps\common\Torchlight Infinite\UE_Game\Torchlight\Saved\Logs\UE_game.log`

### 6.2 Required Log Signals
Application must support parsing of:

**Item pickup/change blocks**
Example:
```text
GameLog: Display: [Game] ItemChange@ ProtoName=PickItems start
GameLog: Display: [Game] ItemChange@ Update ... BagNum=671 in PageId=102 SlotId=0
GameLog: Display: [Game] BagMgr@:Modfy BagItem PageId = 102 SlotId = 0 ConfigBaseId = 100300 Num = 671
GameLog: Display: [Game] ItemChange@ ProtoName=PickItems end
```

**Map/run boundary signals**
At minimum:
- `LevelMgr@ EnterLevel ...` and/or `OpenLevel ...` markers
- The parser must support a configurable “run boundary strategy” (see §7).

### 6.3 Parsing Rules
- Log file is appended over time; implement incremental tailing.
- Each `BagMgr@:Modfy BagItem` line updates inventory state.
- Maintain a state mapping per slot:
  - Key: `(PageId, SlotId)`
  - Value: `(ConfigBaseId, Num)`
- On each update:
  - If same slot & same `ConfigBaseId`, delta = `Num - prev_Num`
  - If different `ConfigBaseId`, treat as swap/move; record deltas carefully:
    - previous item removed (delta = `-prev_Num` or “slot cleared”)
    - new item added (delta = `+Num`)
  - Prefer a conservative approach: only count “gains” when confident (e.g., inside PickItems block), and treat other changes as inventory management unless configured.

### 6.4 Event Grouping
- Use `ItemChange@ ProtoName=PickItems start/end` to bracket pickup operations.
- Within that bracket, record all `BagMgr@:Modfy BagItem` updates as “pickup-related”.
- Outside that bracket, treat updates as inventory moves/crafting/spend/etc. and still record, but tag differently.

## 7. Run/Map Segmentation Requirements
### 7.1 Run Definition
A run is defined as:
- A “map instance” entered and later exited/completed.

### 7.2 Strategy (Configurable)
Provide configurable strategies:
- **Strategy A (Simple):** Start run on first “EnterLevel” that matches map content; end on next EnterLevel back to town/hub.
- **Strategy B (Robust):** Use LevelUid/LevelType/LevelId patterns learned from logs; maintain allowlist/denylist of hub IDs.
- **Strategy C (Manual Override):** UI button to “Start Run” / “End Run” for debugging.

MVP: implement Strategy A with a config allowlist/denylist.

### 7.3 Handling Restarts
If app starts mid-map:
- Create an “Unknown Run” until next boundary, or
- Start a run at first map-related marker encountered.
This must be deterministic and not crash.

## 8. Valuation & Pricing Requirements
### 8.1 Currency of Account
All values expressed in **FE**.
- Known mapping: FE = `ConfigBaseId 100300` (configurable override).

### 8.2 Price Table
Local table: `prices(config_base_id, price_fe, source, updated_ts)`
- Source values:
  - `manual`
  - `import`
  - `market_log` (future)
  - `seed`

### 8.3 Seed Item Database
App ships with a seed mapping file (JSON):
- `ConfigBaseId → display name + icon URL + tlidb link`
- Accept that some names may be imperfect; unknowns supported.

### 8.4 Unknown Items
If an item delta is seen without a known name or price:
- Show it as `Unknown <id>` in UI.
- Allow user to:
  - Set display name
  - Set price in FE
  - Assign category (currency/material/gear/other)

### 8.5 Price Import/Export
Support:
- Import JSON/CSV of prices
- Export prices for sharing/backup

### 8.6 Profit Calculation
Per run:
- `value_gained_fe` = Σ(max(delta,0) * price_fe)
- `value_spent_fe` = Σ(min(delta,0) * price_fe) (optional; may be disabled initially)
- `profit_fe` = `value_gained_fe - cost_overrides_fe - value_spent_fe`

MVP:
- Focus on value gained and optional per-run cost override.
- Add spends tracking later once stable.

## 9. UI Requirements (WealthyExile-style)
### 9.1 Dashboard
Display:
- Current session profit/hr, FE/hr
- Last run profit, duration, top items
- Rolling charts:
  - profit/hr over time
  - profit/run over last N runs
  - FE gained over time

### 9.2 Runs List
Table columns:
- run_id
- start time
- duration
- profit_fe
- FE gained
- total value gained

Click a run → details:
- itemized deltas grouped by item
- show unknown items distinctly
- show pickup vs non-pickup tags

### 9.3 Net Worth / Inventory Value
Compute using latest known `slot_state`:
- total value in FE
- breakdown by category
- highlight items missing price

### 9.4 Prices Page
- searchable list of items with:
  - id
  - name
  - price_fe
  - last updated
- bulk edit controls
- import/export

### 9.5 Settings Page
- Log file path selection
- Run boundary strategy config
- FE item ID config (default 100300)
- Database location
- Debug mode toggle (shows raw parsed events)

## 10. Storage (SQLite) — Minimum Schema
### 10.1 Tables
**settings**
- key TEXT PRIMARY KEY
- value TEXT

**runs**
- run_id INTEGER PRIMARY KEY AUTOINCREMENT
- start_ts TEXT (ISO)
- end_ts TEXT (ISO, nullable while active)
- zone_sig TEXT (optional)
- notes TEXT

**events_raw** (optional but very useful for debugging)
- id INTEGER PK
- ts TEXT
- line TEXT
- parsed_type TEXT

**item_deltas**
- id INTEGER PK
- run_id INTEGER (nullable)
- ts TEXT
- page_id INTEGER
- slot_id INTEGER
- config_base_id INTEGER
- new_num INTEGER
- delta INTEGER
- context TEXT (e.g., PickItems, Other)
- proto_name TEXT (e.g., PickItems)

**slot_state**
- page_id INTEGER
- slot_id INTEGER
- config_base_id INTEGER
- num INTEGER
- last_ts TEXT
- PRIMARY KEY(page_id, slot_id)

**items**
- config_base_id INTEGER PRIMARY KEY
- name TEXT
- icon_url TEXT
- tlidb_url TEXT
- category TEXT
- notes TEXT

**prices**
- config_base_id INTEGER PRIMARY KEY
- price_fe REAL
- source TEXT
- updated_ts TEXT

### 10.2 Performance
- Use WAL mode
- Index `item_deltas(run_id, config_base_id)` and `item_deltas(ts)`.

## 11. Functional Requirements (MVP)
1) Select log file path and persist it
2) Tail log and parse PickItems + BagMgr updates
3) Compute deltas and store in DB
4) Segment into runs using boundary strategy
5) Display FE gained per run, profit per run, profit/hr
6) Editable price list + import/export
7) Net worth estimate from latest slot_state
8) Packaged portable EXE for Windows

## 12. Non-Functional Requirements
### 12.1 Portability
- Works on Windows 10/11
- Runs without installing Python/Node
- Distributed as a zip containing exe (+ assets if one-folder)

### 12.2 Reliability
- Should survive log rotations (UE_game.log renamed, new log created)
- Should handle missing/partial lines gracefully
- Must not crash on unknown patterns

### 12.3 Privacy
- Local-only by default
- No telemetry unless explicitly enabled

### 12.4 Security
- Never request admin privileges unless needed
- No TLS bypasses
- No remote code loading for UI

## 13. Error Handling & UX
- If verbose logging not enabled:
  - Detect absence of ProtoName=PickItems after N minutes
  - Show instructions: “Enable verbose logging in TI settings”
- If log path invalid:
  - Show file picker + auto-detect suggestions
- If prices missing:
  - Show “Unpriced items” list and “Set prices” shortcut

## 14. Packaging Requirements (PyInstaller)
- Build mode:
  - Prefer --onedir first (more reliable, fewer AV false positives)
  - Optional --onefile later
- App should start background services and open UI automatically.
- Store DB in:
  - %LOCALAPPDATA%\TITracker\tracker.db by default
  - or portable mode: .\data\tracker.db beside exe if writable

## 15. Testing Requirements
### 15.1 Parser Unit Tests
- correct delta calculations
- correct slot_state updates
- correct attribution of context

### 15.2 End-to-End
- Use a sample log containing a full map run
- Validate FE total delta matches expected (e.g., FE ends at 671)

## 16. Roadmap (Post-MVP Enhancements)
- Auto price updates by parsing market search logs (if present)
- OCR importer for sales history / run summaries
- Better run segmentation using known zone IDs
- Export/share run summaries
- Optional embedded window (pywebview/Tauri)

## 17. Deliverables
- Git repo with collector, api, ui, db, packaging
- A Windows zip release with TITracker.exe and README

## Appendix A — Log Patterns
### PickItems block
- ItemChange@ ProtoName=PickItems start
- BagMgr@:Modfy BagItem ... ConfigBaseId = ... Num = ...
- ItemChange@ ProtoName=PickItems end

### Known FE mapping
- FE ConfigBaseId: 100300
