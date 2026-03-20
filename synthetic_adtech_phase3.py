
import pandas as pd
import numpy as np
import uuid
import random
import requests
import math
from datetime import datetime, timedelta

# -------------------------
# REPRODUCIBILITY
# -------------------------
random.seed(42)
np.random.seed(42)

# -------------------------
# OSRM SETTINGS
# -------------------------
OSRM_BASE = "https://router.project-osrm.org"
OSRM_TIMEOUT_S = 5
OSRM_USER_AGENT = "FictionalWorldSim/3.0 (+https://example.org)"

session = requests.Session()
session.headers.update({"User-Agent": OSRM_USER_AGENT})

# -------------------------
# LOCATIONS
# -------------------------
LOCATIONS = {
    "NAI_1":  (12.3629, -1.5225),
    "NAI_5":  (12.3640, -1.5154),
    "NAI_8":  (12.3644, -1.5212),
    "NAI_9":  (12.3590, -1.5209),
    "TAI_4":  (12.3597, -1.5164),
    "TAI_12": (12.3625, -1.5131),
}

VIPER_CORRIDOR = (12.3603, -1.5219)

# -------------------------
# OUTPUT RECORD STORE
# -------------------------
records = []

# -------------------------
# CIVILIAN POOL (PERSISTENT)
# -------------------------
CIV_POP_SIZE = 50
CIV_IDS = [f"civ-{uuid.uuid4()}" for _ in range(CIV_POP_SIZE)]

# -------------------------
# GEO HELPERS
# -------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(a))

def interpolate(p1, p2, dist_along):
    lat1, lon1 = p1; lat2, lon2 = p2
    total = haversine(lat1, lon1, lat2, lon2)
    if total == 0: return p1
    if dist_along >= total: return p2
    r = dist_along / total
    return (lat1 + (lat2-lat1)*r, lon1 + (lon2-lon1)*r)

def resample_polyline(coords, interval_m):
    if len(coords) <= 1: return coords
    out = [coords[0]]
    travelled = 0
    prev = coords[0]
    for i in range(1, len(coords)):
        curr = coords[i]
        seg = haversine(prev[0], prev[1], curr[0], curr[1])
        while travelled + interval_m <= seg:
            p = interpolate(prev, curr, interval_m)
            out.append(p)
            prev = p
            seg -= interval_m
        travelled = seg
        prev = curr
    return out

def osrm_route(start, end, mode="driving"):
    url = f"{OSRM_BASE}/route/v1/{mode}/{start[1]},{start[0]};{end[1]},{end[0]}?overview=false&steps=true&geometries=geojson"
    try:
        r = session.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return [start, end]
    if not data.get("routes"):
        return [start, end]
    pts = []
    for leg in data["routes"][0]["legs"]:
        for step in leg["steps"]:
            for lon, lat in step["geometry"]["coordinates"]:
                if not pts or (lat, lon) != pts[-1]:
                    pts.append((lat, lon))
    return pts

# -------------------------
# EMISSION HELPERS
# -------------------------
def emit_route(device, time, start, end, speed_kph=25, ping_every_s=30):
    global records
    raw = osrm_route(start, end)
    mps = speed_kph * 1000 / 3600
    step = mps * ping_every_s
    pts = resample_polyline(raw, step)
    t = time
    for lat, lon in pts:
        records.append({
            "mid": device,
            "dtg": t.isoformat(),
            "y": round(lat, 6),
            "x": round(lon, 6),
        })
        t += timedelta(seconds=ping_every_s)

def jitter(lat, lon, meters=1):
    return lat + np.random.normal(0, meters/111111), lon + np.random.normal(0, meters/111111)

def emit_stationary(device, start, center, duration_min, interval_min=5, jitter_m=2):
    global records
    lat, lon = center
    count = max(1, duration_min // interval_min)
    for i in range(count):
        t = start + timedelta(minutes=i*interval_min)
        jlat, jlon = jitter(lat, lon, jitter_m)
        records.append({
            "mid": device,
            "dtg": t.isoformat(),
            "y": round(jlat, 6),
            "x": round(jlon, 6),
        })

# -------------------------
# PHASE 3 BEHAVIOURS
# -------------------------

ST_ID = "ST-DEV-001"
HAWK2_ID = "ST-ASC-003"
LR_ID = "LR-DEV-001"
VIPER2_ID = "LR-ASC-003"

# --- STONE TIGER ---
def simulate_ST(day, coloc_days):
    # 0800–1230 NAI 5
    emit_route(ST_ID, day.replace(hour=7, minute=0), LOCATIONS["TAI_4"], LOCATIONS["NAI_5"], speed_kph=30)
    emit_stationary(ST_ID, day.replace(hour=8), LOCATIONS["NAI_5"], 210, interval_min=10)

    # 1300–1800 TAI 12 (4–5× / week)
    if day.date() in coloc_days:
        emit_route(ST_ID, day.replace(hour=12, minute=30), LOCATIONS["NAI_5"], LOCATIONS["TAI_12"], speed_kph=30)
        emit_stationary(ST_ID, day.replace(hour=13), LOCATIONS["TAI_12"], 300, interval_min=10)

    # 1900–2200 TAI 4 (beddown)
    emit_route(ST_ID, day.replace(hour=18, minute=15), LOCATIONS["TAI_12"], LOCATIONS["TAI_4"], speed_kph=30)
    emit_stationary(ST_ID, day.replace(hour=19), LOCATIONS["TAI_4"], 180, interval_min=15)

# --- HAWK-2 (Courier, fixed route) ---
def simulate_HAWK2(day):
    emit_route(HAWK2_ID, day.replace(hour=7), LOCATIONS["TAI_4"], LOCATIONS["TAI_12"], speed_kph=35)
    emit_stationary(HAWK2_ID, day.replace(hour=8), LOCATIONS["TAI_12"], 60)
    emit_route(HAWK2_ID, day.replace(hour=9), LOCATIONS["TAI_12"], LOCATIONS["TAI_4"], speed_kph=35)

# --- LR (Counter-surveillance + dark periods) ---
def simulate_LR(day, coloc_days):
    # Random dark period (4–6 hrs)
    dark = random.random() < 0.4
    dark_hours = random.randint(4, 6)

    if not dark:
        # Vary between NAI8/NAI9
        morning_spots = ["NAI_8", "NAI_9"]
        choice = random.choice(morning_spots)
        emit_stationary(LR_ID, day.replace(hour=6), LOCATIONS[choice], 300, interval_min=10)
    # else: LR silent until afternoon

    # 1300–1800 TAI 12 (always appears on coloc days)
    if day.date() in coloc_days:
        emit_route(LR_ID, day.replace(hour=12, minute=30), LOCATIONS["NAI_9"], LOCATIONS["TAI_12"], speed_kph=30)
        emit_stationary(LR_ID, day.replace(hour=13), LOCATIONS["TAI_12"], 300, interval_min=10)
        emit_route(LR_ID, day.replace(hour=18), LOCATIONS["TAI_12"], LOCATIONS["NAI_9"], speed_kph=30)

# --- VIPER-2 (Equipment, daily NAI8↔TAI12) ---
def simulate_VIPER2(day):
    start = day.replace(hour=5)
    emit_route(VIPER2_ID, start, LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], speed_kph=30)
    emit_stationary(VIPER2_ID, day.replace(hour=6), LOCATIONS["TAI_12"], 60)
    emit_route(VIPER2_ID, day.replace(hour=7), LOCATIONS["TAI_12"], LOCATIONS["NAI_8"], speed_kph=30)
    emit_route(VIPER2_ID, day.replace(hour=9), LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], speed_kph=30)
    emit_stationary(VIPER2_ID, day.replace(hour=10), LOCATIONS["TAI_12"], 240)

# --- HAWK2 + VIPER2 co-location ---
def simulate_crossnetwork(day):
    # Force both at TAI12 0800–1000
    emit_stationary(HAWK2_ID, day.replace(hour=8), LOCATIONS["TAI_12"], 120)
    emit_stationary(VIPER2_ID, day.replace(hour=8), LOCATIONS["TAI_12"], 120)

# --- Civilians (reduced density) ---
def simulate_civilians(day):
    for civ in CIV_IDS:
        for zone in ["NAI_1", "NAI_5"]:
            # 20–30% attendance (reduced)
            if random.random() < 0.3:
                jittered = jitter(*LOCATIONS[zone], 10)
                dt = day.replace(hour=8) + timedelta(minutes=random.randint(-10, 15))
                records.append({
                    "mid": civ,
                    "dtg": dt.isoformat(),
                    "y": round(jittered[0], 6),
                    "x": round(jittered[1], 6),
                })

# --- NEW DEVICES (reduced + dark) ---
def simulate_new_devs(day):
    centers = {
        "NEW-DEV-X1": LOCATIONS["NAI_9"],
        "NEW-DEV-X2": LOCATIONS["NAI_9"],
        "NEW-DEV-X3": LOCATIONS["NAI_9"],
    }
    for dev, center in centers.items():
        if random.random() < 0.6:  # sometimes dark
            emit_stationary(dev, day.replace(hour=9), center, 180)

# --- CAI TRIGGERS ---
def simulate_cai(day, coloc):
    # White Hilux at TAI4
    emit_stationary(ST_ID, day.replace(hour=6), LOCATIONS["TAI_4"], 180, interval_min=10, jitter_m=3)

    # Armed escort at TAI12 during co-location
    if coloc:
        emit_stationary("escort-armed", day.replace(hour=13),
                        LOCATIONS["TAI_12"], 240,
                        interval_min=10, jitter_m=3)

    # ≥4 staged vehicles at TAI12 before meetings
    for i in range(4):
        emit_stationary(f"veh-stage-{i}", day.replace(hour=12),
                        LOCATIONS["TAI_12"], 120,
                        interval_min=10, jitter_m=2)

# -------------------------
# MAIN
# -------------------------
def generate_data(days=14):
    global records
    records = []

    start = datetime(2026, 3, 1)
    coloc_days = set(
        (start + timedelta(days=i)).date()
        for i in sorted(random.sample(range(days), 5))
    )

    current = start
    for i in range(days):
        day = current
        coloc = day.date() in coloc_days

        simulate_ST(day, coloc_days)
        simulate_HAWK2(day)
        simulate_LR(day, coloc_days)
        simulate_VIPER2(day)
        simulate_crossnetwork(day)
        simulate_new_devs(day)
        simulate_civilians(day)
        simulate_cai(day, coloc)

        current += timedelta(days=1)

    df = pd.DataFrame(records).sort_values("dtg").reset_index(drop=True)
    return df

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    df = generate_data(14)
    df.to_csv("synthetic_adtech_phase3_output.csv", index=False)
    print("Rows:", len(df))
    print("Unique devices:", df["mid"].nunique())
