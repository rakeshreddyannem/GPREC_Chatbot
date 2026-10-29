# Page Speed Measurements (Before Fixes)

**Initial Server Startup / Warm-up Time:** 43.25s

Each page was rendered 3 consecutive times after server start. Times shown in seconds.

| Page | Run 1 Render (s) | Run 2 Render (s) | Run 3 Render (s) | Avg Render Time (s) | Avg Total Switch Time (s) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ask AI** | 0.0024 | 0.0023 | 0.0023 | **0.0023** | 0.0699 |
| **Academics** | 0.0030 | 0.0018 | 0.0021 | **0.0023** | 0.0455 |
| **Latest Notices** | 0.0338 | 0.0343 | 0.0297 | **0.0326** | 0.0813 |
| **Deadlines** | 0.0100 | 0.0079 | 0.0084 | **0.0088** | 0.0524 |
| **Departments** | 0.0011 | 0.0010 | 0.0015 | **0.0012** | 0.0467 |
| **Faculty** | 2.5174 | 1.5902 | 1.3205 | **1.8094** | 2.2481 |
| **Subject Assistance** | 0.5268 | 0.0131 | 0.0177 | **0.1859** | 0.2364 |
| **About** | 0.0010 | 0.0011 | 0.0010 | **0.0010** | 0.0456 |

## Breakdown of main() Component Overhead per Run

| Component | Observed Typical Range (s) | Notes |
| :--- | :--- | :--- |
| `css and logo` | 0.0009s – 0.0354s (avg: 0.0026s) | Reads `style.css` and `gprec_logo1.png` from disk and re-encodes base64 every rerun.
| `database init` | 0.0030s – 0.0064s (avg: 0.0041s) | Runs `init_db()` table DDL, ALTER TABLEs, indexes & seed checks on EVERY click.
| `pipeline load` | 0.0000s – 0.0003s (avg: 0.0000s) | Cached via resource after warm-up.
| `sidebar` | 0.0016s – 0.0045s (avg: 0.0024s) | Re-evaluates full sidebar navigation and status card every run.

## Key Observations Before Fixes

1. **DatabaseManager overhead on every click:** `DatabaseManager()` is invoked in `main()` without caching, triggering `init_db()` (12 CREATE TABLEs, multiple ALTER TABLEs, index checks, and demo seed deletions) on every click.
2. **Faculty Page Bottleneck:** Loads all 411 faculty members in one massive unpaginated list, creating 411 cards, images, and buttons.
3. **Duplicate Reruns on Page Navigation:** `selected_page = st.radio(...)` followed by `if selected_page != st.session_state.page: st.rerun()` forces two script executions per navigation click.
4. **Uncached Database Queries:** Notices, deadlines, departments, syllabus branches/courses are re-queried from SQLite on every page view.
5. **Lack of Fragment Isolation:** Filter clicks and tab switches rerun the entire Streamlit script from top to bottom.
