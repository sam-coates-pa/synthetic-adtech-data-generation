
import pandas as pd
import numpy as np
import uuid
import random
import requests
import math
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional

# -------------------------
# Reproducibility
# -------------------------
random.seed(42)
np.random.seed(42)

# -------------------------
# OSRM CONFIG (best-effort; falls back to straight line if no internet)
# -------------------------
OSRM_BASE = "https://router.project-osrm.org"
OSRM_TIMEOUT_S = 5
OSRM_USER_AGENT = "FictionalWorldSim/2.0 (+https://example.org)"

session = requests.Session()
session.headers.update({"User-Agent": OSRM_USER_AGENT})

# -------------------------
# LOCATIONS (fictional world with NAI/TAI names)
# -------------------------
LOCATIONS = {
    "NAI_1":  (12.3629, -1.5225),
    "NAI_5":  (12.3640, -1.5154),
    "NAI_8":  (12.3644, -1.5212),
    "NAI_9":  (12.3590, -1.5209),
    "TAI_4":  (12.3597, -1.5164),
    "TAI_12": (12.3625, -1.5131),
}

# Specific corridor point for LR-ASC-004 (VIPER-3) movements
VIPER_CORRIDOR = (12.3603, -1.5219)

# -------------------------
# OUTPUT RECORD STORE
# -------------------------
records = []

# --- Persistent civilian pool ---
CIV_POP_SIZE = 50
CIV_IDS = [f"civ-{uuid.uuid4()}" for _ in range(CIV_POP_SIZE)]

# -------------------------
# ROUTING & GEO HELPERS
# -------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def interpolate(p1, p2, dist_along):
    lat1, lon1 = p1
    lat2, lon2 = p2
    total = haversine(lat1, lon1, lat2, lon2)
    if total == 0 or dist_along <= 0:
        return p1
    if dist_along >= total:
        return p2
    r = dist_along / total
    return (lat1 + (lat2 - lat1) * r,
            lon1 + (lon2 - lon1) * r)

def resample_polyline(coords, interval_m, include_last=False):
    if not coords:
        return []
    if len(coords) == 1:
        return [coords[0]]

    resampled = [coords[0]]
    prev = coords[0]
    distance_to_next = interval_m

    for i in range(1, len(coords)):
        curr = coords[i]
        seg_len = haversine(prev[0], prev[1], curr[0], curr[1])
        while seg_len >= distance_to_next:
            point = interpolate(prev, curr, distance_to_next)
            resampled.append(point)
            prev = point
            seg_len -= distance_to_next
            distance_to_next = interval_m

        distance_to_next -= seg_len
        prev = curr

    if include_last and resampled[-1] != coords[-1]:
        resampled.append(coords[-1])

    return resampled

def osrm_route(start_latlon, end_latlon, mode="driving"):
    url = (
        f"{OSRM_BASE}/route/v1/{mode}/"
        f"{start_latlon[1]},{start_latlon[0]};"
        f"{end_latlon[1]},{end_latlon[0]}"
        f"?overview=false&steps=true&geometries=geojson"
    )
    try:
        r = session.get(url, timeout=OSRM_TIMEOUT_S)
        r.raise_for_status()
        data = r.json()
    except Exception:
        # OSRM unreachable → fallback straight-line
        return [start_latlon, end_latlon]

    if not data.get("routes"):
        return [start_latlon, end_latlon]

    full = []
    for leg in data["routes"][0].get("legs", []):
        for step in leg.get("steps", []):
            for lon, lat in step.get("geometry", {}).get("coordinates", []):
                if not full or (lat, lon) != full[-1]:
                    full.append((lat, lon))

    return full if len(full) >= 2 else [start_latlon, end_latlon]

# -------------------------
# EMISSION HELPERS
# -------------------------
def emit_route(device_id, start_time, start_latlon, end_latlon,
               speed_kph=25.0, ping_every_s=30, snap_to_last=False, mode="driving"):
    global records

    raw = osrm_route(start_latlon, end_latlon, mode=mode)
    mps = max(0.1, speed_kph) * 1000 / 3600
    dist = mps * ping_every_s

    dense = resample_polyline(raw, dist, include_last=snap_to_last)
    if not dense:
        dense = [start_latlon]

    if len(dense) == 1 and snap_to_last:
        dense.append(end_latlon)

    t = start_time
    for i, (lat, lon) in enumerate(dense):
        records.append({
            "device_id": device_id,
            "timestamp": t.isoformat(),
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        })
        if i < len(dense) - 1:
            t += timedelta(seconds=ping_every_s)

def jitter(lat, lon, meters=1.0):
    return (
        lat + np.random.normal(0, meters/111111),
        lon + np.random.normal(0, meters/111111),
    )

def emit_stationary(device_id, start_time, center, duration_min,
                    interval_min=3, jitter_m=1.0):
    global records
    lat, lon = center
    count = max(1, int(duration_min / interval_min))

    for i in range(count):
        t = start_time + timedelta(minutes=i * interval_min)
        jlat, jlon = jitter(lat, lon, jitter_m)
        records.append({
            "device_id": device_id,
            "timestamp": t.isoformat(),
            "latitude": round(jlat, 6),
            "longitude": round(jlon, 6),
        })

# -------------------------
# WEEKLY EVENT SCHEDULER
# -------------------------
def choose_weekly_days(start_date, weeks, min_times, max_times):
    selected = set()
    for w in range(weeks):
        week_start = start_date + timedelta(days=7 * w)
        times = random.randint(min_times, max_times)
        chosen = random.sample(range(7), times)
        for d in chosen:
            selected.add((week_start + timedelta(days=d)).date())
    return selected

# -------------------------
# BEHAVIOUR MODULES (UPDATED FOR WEEKS 4–5)
# -------------------------
ST_ID = "ST-DEV-001"
HAWK2_ID = "ST-ASC-003"
HAWK3_ID = "ST-ASC-004"
LR_ID = "LR-DEV-001"
VIPER3_ID = "LR-ASC-004"

def simulate_ST_day(day, tai12_days):
    emit_stationary(ST_ID, day.replace(hour=5, minute=30),
                    LOCATIONS["TAI_4"], 120, interval_min=10, jitter_m=2.0)

    emit_route(ST_ID, day.replace(hour=7, minute=30),
               LOCATIONS["TAI_4"], LOCATIONS["NAI_5"], speed_kph=30)

    emit_stationary(ST_ID, day.replace(hour=8, minute=0),
                    LOCATIONS["NAI_5"], 240, interval_min=10, jitter_m=3.0)

    if day.date() in tai12_days:
        emit_route(ST_ID, day.replace(hour=13, minute=0),
                   LOCATIONS["NAI_5"], LOCATIONS["TAI_12"], speed_kph=30)

        emit_stationary(ST_ID, day.replace(hour=13, minute=30),
                        LOCATIONS["TAI_12"], 270, interval_min=10)

        emit_route(ST_ID, day.replace(hour=18, minute=0),
                   LOCATIONS["TAI_12"], LOCATIONS["TAI_4"], speed_kph=30)
    else:
        emit_route(ST_ID, day.replace(hour=17, minute=0),
                   LOCATIONS["NAI_5"], LOCATIONS["TAI_4"], speed_kph=30)

def simulate_HAWK2_day(day):
    emit_route(HAWK2_ID, day.replace(hour=6, minute=0),
               LOCATIONS["TAI_4"], LOCATIONS["TAI_12"], speed_kph=35)

    emit_stationary(HAWK2_ID, day.replace(hour=7, minute=0),
                    LOCATIONS["TAI_12"], 60, interval_min=10)

    emit_route(HAWK2_ID, day.replace(hour=8, minute=0),
               LOCATIONS["TAI_12"], LOCATIONS["TAI_4"], speed_kph=35)

    emit_route(HAWK2_ID, day.replace(hour=13, minute=30),
               LOCATIONS["TAI_4"], LOCATIONS["TAI_12"], speed_kph=35)

    emit_stationary(HAWK2_ID, day.replace(hour=14, minute=0),
                    LOCATIONS["TAI_12"], 90, interval_min=10)

def simulate_HAWK3_day(day):
    emit_stationary(HAWK3_ID, day.replace(hour=7, minute=30),
                    LOCATIONS["NAI_1"], 120, interval_min=10)

    emit_stationary(HAWK3_ID, day.replace(hour=13, minute=0),
                    LOCATIONS["NAI_1"], 30, interval_min=5)

def simulate_LR_day(day, tai12_days):
    emit_stationary(LR_ID, day.replace(hour=7, minute=0),
                    LOCATIONS["NAI_9"], 300, interval_min=10)

    if day.date() in tai12_days:
        emit_route(LR_ID, day.replace(hour=13, minute=30),
                   LOCATIONS["NAI_9"], LOCATIONS["TAI_12"], speed_kph=30)

        emit_stationary(LR_ID, day.replace(hour=14, minute=0),
                        LOCATIONS["TAI_12"], 240, interval_min=10)

        emit_route(LR_ID, day.replace(hour=18, minute=0),
                   LOCATIONS["TAI_12"], LOCATIONS["NAI_9"], speed_kph=30)

def simulate_VIPER3_day(day):
    trips = random.randint(2, 3)
    t = day.replace(hour=8, minute=0)
    for _ in range(trips):
        emit_route(VIPER3_ID, t,
                   LOCATIONS["NAI_9"], VIPER_CORRIDOR, speed_kph=25)
        t += timedelta(minutes=20)

        emit_route(VIPER3_ID, t,
                   VIPER_CORRIDOR, LOCATIONS["NAI_1"], speed_kph=25)
        t += timedelta(minutes=20)

        emit_stationary(VIPER3_ID, t,
                        LOCATIONS["NAI_1"], 10, interval_min=5)
        t += timedelta(minutes=10)

        emit_route(VIPER3_ID, t,
                   LOCATIONS["NAI_1"], VIPER_CORRIDOR, speed_kph=25)
        t += timedelta(minutes=20)

        emit_route(VIPER3_ID, t,
                   VIPER_CORRIDOR, LOCATIONS["NAI_9"], speed_kph=25)
        t += timedelta(minutes=20)

def simulate_new_devices(day, week_index):
    X1 = (12.358972, -1.520583)
    X2 = (12.358944, -1.520778)
    X3 = (12.358694, -1.520611)

    if week_index == 0:
        emit_stationary("NEW-DEV-X1", day.replace(hour=8), X1, 540, interval_min=10)
        emit_stationary("NEW-DEV-X2", day.replace(hour=9), X2, 420, interval_min=10)

    if week_index >= 1:
        emit_stationary("NEW-DEV-X1", day.replace(hour=8), X1, 540, interval_min=10)
        emit_stationary("NEW-DEV-X2", day.replace(hour=9), X2, 420, interval_min=10)
        emit_stationary("NEW-DEV-X3", day.replace(hour=7), X3, 660, interval_min=10)



def simulate_populace(day):
    """
    Civilians come from a fixed pool of 50 devices.
    Each has a chance of appearing at a population peak at NAI_1 or NAI_5.
    Ping times are jittered within ±15 minutes of the peak.
    Additional light noise is added around the peak window.
    """
    PEAK_WINDOWS_MIN = {8: (-8, +12), 13: (-10, +15)}
    NOISE_BEFORE_AFTER_MIN = 25

    # Each civilian has 35–55% chance of showing up at each peak at each zone
    for civ_id in CIV_IDS:
        for zone in ["NAI_1", "NAI_5"]:
            for peak_hour in [8, 13]:

                # Probability: only some civilians attend each peak
                if random.random() < 0.45:  # ~45% attendance rate
                    base_t = day.replace(hour=peak_hour, minute=0, second=0, microsecond=0)
                    win_lo, win_hi = PEAK_WINDOWS_MIN[peak_hour]

                    # Triangular distribution for time offset
                    offset_min = int(random.triangular(win_lo, win_hi, 3))
                    offset_sec = random.randint(0, 59)

                    jlat, jlon = jitter(*LOCATIONS[zone], meters=8)

                    records.append({
                        "device_id": civ_id,
                        "timestamp": (base_t +
                                      timedelta(minutes=offset_min, seconds=offset_sec)).isoformat(),
                        "latitude": round(jlat, 6),
                        "longitude": round(jlon, 6),
                    })

                # Optional light noise outside the peak
                if random.random() < 0.15:  # low probability noise
                    off = random.randint(-NOISE_BEFORE_AFTER_MIN,
                                         NOISE_BEFORE_AFTER_MIN)
                    off_sec = random.randint(0, 59)

                    jlat, jlon = jitter(*LOCATIONS[zone], meters=random.uniform(8, 20))

                    records.append({
                        "device_id": civ_id,
                        "timestamp": (day.replace(hour=peak_hour, minute=0) +
                                      timedelta(minutes=off, seconds=off_sec)).isoformat(),
                        "latitude": round(jlat, 6),
                        "longitude": round(jlon, 6),
                    })

def simulate_cai_triggers(day, co_location):
    for i in range(2):
        vid = f"VEH-{day.strftime('%j')}-{i}"
        emit_route(vid, day.replace(hour=5, minute=30 + i*10),
                   LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], speed_kph=35)
        emit_stationary(vid, day.replace(hour=6, minute=30 + i*10),
                        LOCATIONS["TAI_12"], 60, interval_min=10)

    if co_location:
        for j in range(2):
            vid = f"VEH-COL-{day.strftime('%j')}-{j}"
            emit_stationary(vid, day.replace(hour=14),
                            LOCATIONS["TAI_12"], 240, interval_min=10)

# -------------------------
# MAIN GENERATOR
# -------------------------
def generate_data(days=14):
    global records
    records = []

    start = datetime(2026, 2, 1)
    weeks = max(1, days // 7)

    st_days = choose_weekly_days(start, weeks, 4, 4)
    lr_days = choose_weekly_days(start, weeks, 3, 4)

    st_list = sorted(st_days)
    lr_list = sorted(lr_days)

    by_week = {}
    for d in st_list:
        wk = (datetime.combine(d, datetime.min.time()) - start).days // 7
        by_week.setdefault(wk, []).append(d)

    for wk, days_in_week in by_week.items():
        target = 3
        overlap = [d for d in days_in_week if d in lr_days]
        if len(overlap) < target:
            need = target - len(overlap)
            for d in days_in_week:
                if d not in lr_days:
                    lr_days.add(d)
                    need -= 1
                    if need == 0:
                        break

    current = start
    for i in range(days):
        week_idx = i // 7
        day = current

        co_loc = (day.date() in st_days) and (day.date() in lr_days)

        simulate_ST_day(day, st_days)
        simulate_HAWK2_day(day)
        simulate_HAWK3_day(day)
        simulate_LR_day(day, lr_days)
        simulate_VIPER3_day(day)

        simulate_new_devices(day, week_idx)
        simulate_populace(day)
        simulate_cai_triggers(day, co_loc)

        current += timedelta(days=1)

    df = pd.DataFrame(records)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.rename(columns={
        "device_id": "mid",
        "timestamp": "dtg",
        "latitude": "y",
        "longitude": "x"
    })
    return df[["mid", "dtg", "y", "x"]]

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    df = generate_data(days=14)
    df.to_csv("synthetic_adtech_phase2_output.csv", index=False)
    print("Rows:", len(df))
    print("Unique devices:", df["mid"].nunique())
