import urllib.request
import zlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_BASE = "https://back.results.asiangames2026.org"

def fetch_api(path):
    url = f"{BACKEND_BASE}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
            chars = raw.decode("utf-8")
            byte_arr = bytes([ord(c) for c in chars])
            decomp = zlib.decompress(byte_arr)
            return json.loads(decomp)
    except Exception as e:
        return []

def main():
    print("1. Fetching matrix & config...")
    matrix_data = fetch_api("/s/AG2026/en/ALL/schedule/matrix")
    dates = matrix_data.get("dates", [])
    matrix_rows = matrix_data.get("matrix", [])
    medals = fetch_api("/s/AG2026/en/ALL/medals/org/IND")
    config = fetch_api("/s/AG2026/en/config")

    import sys
    from datetime import datetime, timedelta

    json_path = os.path.join(BASE_DIR, "asian_games_data.json")
    full_schedule_by_date = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                full_schedule_by_date = json.load(f).get("schedule", {})
        except Exception:
            pass

    # Fast update vs Full update
    all_dates = [d for d in dates if d >= "2026-09-19" and d <= "2026-09-30"]
    if "--all" in sys.argv or not full_schedule_by_date:
        target_dates = all_dates
        print(f"Full sync mode: {len(target_dates)} dates")
    else:
        # Fast 10-min mode: focus on current live days window (e.g. today +- 2 days)
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str not in dates:
            # default to active tournament window
            today_str = "2026-09-23"
        t_idx = dates.index(today_str) if today_str in dates else 13
        start_idx = max(0, t_idx - 1)
        end_idx = min(len(dates), t_idx + 3)
        target_dates = dates[start_idx:end_idx]
        print(f"Fast 10-min sync mode for active days: {target_dates}")

    tasks = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        for d in target_dates:
            d_idx = dates.index(d)
            # Find active disciplines on this day
            active_discs = []
            for row in matrix_rows:
                flags = row.get("Dates", [])
                if d_idx < len(flags) and flags[d_idx] in ["0", "1", "2"]:
                    active_discs.append(row.get("Disc", {}).get("Key"))

            for disc in active_discs:
                tasks.append((d, disc, executor.submit(fetch_api, f"/s/AG2026/en/{disc}/schedule/daily/{d}")))

        print(f"Dispatched {len(tasks)} requests for daily schedules...")
        
        # Fresh dict for updated dates
        updated_by_date = {}
        for d, disc, future in tasks:
            res = future.result()
            if isinstance(res, list) and res:
                updated_by_date.setdefault(d, []).extend(res)

        for d, items in updated_by_date.items():
            full_schedule_by_date[d] = items

    print("--- Summary of fetched events ---")
    for d in target_dates:
        events = full_schedule_by_date.get(d, [])
        ind_matches = []
        for it in events:
            h = (it.get("Home") or {}).get("Org")
            a = (it.get("Away") or {}).get("Org")
            s = json.dumps(it)
            if h == "IND" or a == "IND" or '"IND"' in s or "India" in s:
                ind_matches.append(it)
        print(f"Date {d}: Total = {len(events)}, India = {len(ind_matches)}")

    # Sort all events chronologically
    for d in full_schedule_by_date:
        full_schedule_by_date[d].sort(key=lambda x: (x.get("DateTimeRaw") or "9999", x.get("DiscDesc") or "", x.get("UnitDesc") or ""))

    bundle = {
        "schedule": full_schedule_by_date,
        "medals": medals,
        "config": config
    }

    # Save to JSON
    json_path = os.path.join(BASE_DIR, "asian_games_data.json")
    with open(json_path, "w") as f:
        json.dump(bundle, f)
    print(f"Wrote {json_path}")

    # Save to JS for direct file opening support
    js_path = os.path.join(BASE_DIR, "asian_games_data.js")
    with open(js_path, "w") as f:
        f.write("window.ASIAN_GAMES_BUNDLE = " + json.dumps(bundle) + ";")
    print(f"Wrote {js_path}")

if __name__ == "__main__":
    main()
