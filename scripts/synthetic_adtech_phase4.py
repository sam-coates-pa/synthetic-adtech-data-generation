
"""
FICTIONAL WORLD — SYNTHETIC MOBILITY GENERATOR (SAFE / DE-WEAPONIZED)
Week 8 Scenario Playback: Multi-device co-location and post-event effects

- Synthetic, benign data for product demos and testing only
- Uses real OSRM routing (fallback to straight line if OSRM unavailable)
- NAI/TAI zones preserved; TAI_12 updated to scenario coordinate
- Time-boxed routing to precisely match desired arrival times
- Minimal CSV outputs: mid, dtg, y, x
"""

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
# OSRM CONFIG
# -------------------------
OSRM_BASE = "https://router.project-osrm.org"
OSRM_TIMEOUT_S = 10
OSRM_USER_AGENT = "FictionalWorldSim/1.0 (+https://example.org)"

session = requests.Session()
session.headers.update({"User-Agent": OSRM_USER_AGENT})

# -------------------------
# LOCATIONS (fictional world with NAI/TAI names)
# TAI_12 updated to exact scenario coordinate (12.362000, -1.512556)
# -------------------------
LOCATIONS = {
    "NAI_1":  (12.3629, -1.5225),
    "NAI_5":  (12.3640, -1.5154),
    "NAI_8":  (12.3644, -1.5212),
    "NAI_9":  (12.3590, -1.5209),
    "TAI_4":  (12.3597, -1.5164),
    "TAI_12": (12.362000, -1.512556),
}

# A couple of "outside AO" target points for displacement paths
OUTSIDE_W1 = (12.3620, -1.5350)   # West of TAI_12
OUTSIDE_W2 = (12.3600, -1.5425)   # Further west
OUTSIDE_AO = (12.3550, -1.5450)   # Outside the AO boundary

# -------------------------
# OUTPUT RECORD STORE
# -------------------------
records = []

# -------------------------
# ROUTING & GEO HELPERS
# -------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat/2)**2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlon/2)**2
    )
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
    return (lat1 + (lat2 - lat1) * r, lon1 + (lon2 - lon1) * r)

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
        # Fallback straight line
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
def emit_point(device_id, t, lat, lon):
    global records
    records.append({
        "device_id": device_id,
        "timestamp": t.isoformat(),
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
    })

def emit_route(device_id, start_time, start_latlon, end_latlon,
               speed_kph=30.0, ping_every_s=30, mode="driving", snap_to_last=False):
    """
    Speed-driven resampling: duration depends on speed & distance.
    """
    global records
    raw = osrm_route(start_latlon, end_latlon, mode=mode)
    mps = speed_kph * 1000 / 3600
    dist = mps * ping_every_s
    dense = resample_polyline(raw, dist, include_last=snap_to_last)
    if not dense:
        dense = [start_latlon]
    if len(dense) == 1 and snap_to_last:
        dense.append(end_latlon)

    t = start_time
    for i, (lat, lon) in enumerate(dense):
        emit_point(device_id, t, lat, lon)
        if i < len(dense) - 1:
            t += timedelta(seconds=ping_every_s)

def emit_route_timeboxed(device_id, start_time, arrival_time, start_latlon, end_latlon,
                         ping_every_s=30, mode="driving"):
    """
    Time-boxed resampling: guarantees final point at arrival_time by adjusting
    the effective speed to traverse the route within the allotted duration.
    """
    global records
    raw = osrm_route(start_latlon, end_latlon, mode=mode)
    if not raw or len(raw) < 2:
        raw = [start_latlon, end_latlon]

    # Compute total route distance
    total_m = 0.0
    for i in range(1, len(raw)):
        a, b = raw[i-1], raw[i]
        total_m += haversine(a[0], a[1], b[0], b[1])

    total_s = max(1, int((arrival_time - start_time).total_seconds()))
    # Derive sampling interval in meters to fit time cadence
    steps = max(1, total_s // ping_every_s)
    # If route is tiny, still enforce at least two points (start/end)
    interval_m = total_m / steps if steps > 0 else total_m

    dense = resample_polyline(raw, interval_m, include_last=True)
    if len(dense) < 2:
        dense = [start_latlon, end_latlon]

    # Emit equally spaced in time from start_time to arrival_time
    n = len(dense)
    for i, (lat, lon) in enumerate(dense):
        # Linear interpolate timestamps across [start_time, arrival_time]
        if n == 1:
            t = start_time
        else:
            frac = i / (n - 1)
            t = start_time + timedelta(seconds=frac * total_s)
        emit_point(device_id, t, lat, lon)

def jitter(lat, lon, meters=1.0):
    # Approx degrees per meter at equator; acceptable small-distance approximation here.
    return (
        lat + np.random.normal(0, meters/111111),
        lon + np.random.normal(0, meters/111111),
    )

def emit_stationary(device_id, start_time, center, count, interval_min=3, jitter_m=1.0):
    global records
    lat, lon = center
    for i in range(count):
        t = start_time + timedelta(minutes=i * interval_min)
        jlat, jlon = jitter(lat, lon, jitter_m)
        emit_point(device_id, t, jlat, jlon)

# -------------------------
# WEEKLY EVENT SAMPLING (kept from original)
# -------------------------
def choose_weekly_days(start_date, weeks, min_times, max_times):
    """Randomly select X days each week for certain behaviours."""
    selected = set()
    for w in range(weeks):
        week_start = start_date + timedelta(days=7 * w)
        days_this_week = random.randint(min_times, max_times)
        chosen = random.sample(range(7), days_this_week)
        for d in chosen:
            selected.add((week_start + timedelta(days=d)).date())
    return selected

# -------------------------
# ORIGINAL BEHAVIOUR MODULES (kept from original; minor bug fixes)
# -------------------------
def simulate_leaderA_day(device_id, day, weekly_tai12_visits):
    emit_stationary(device_id, day.replace(hour=5, minute=30), LOCATIONS["TAI_4"], 5)
    travel_start = day.replace(hour=random.randint(6, 7), minute=random.randint(30, 59))
    emit_route(device_id, travel_start, LOCATIONS["TAI_4"], LOCATIONS["NAI_5"], speed_kph=25)
    emit_stationary(device_id, day.replace(hour=9, minute=30), LOCATIONS["NAI_5"], 6, interval_min=15)
    if day.date() in weekly_tai12_visits:
        start = day.replace(hour=14, minute=0)
        emit_route(device_id, start, LOCATIONS["NAI_5"], LOCATIONS["TAI_12"], speed_kph=30)
        emit_stationary(device_id, day.replace(hour=15, minute=0), LOCATIONS["TAI_12"], 6, interval_min=10)
        emit_route(device_id, day.replace(hour=17, minute=0), LOCATIONS["TAI_12"], LOCATIONS["TAI_4"], speed_kph=25)
    else:
        emit_route(device_id, day.replace(hour=17, minute=0), LOCATIONS["NAI_5"], LOCATIONS["TAI_4"], speed_kph=25)
    emit_stationary(device_id, day.replace(hour=18, minute=0), LOCATIONS["TAI_4"], 6, interval_min=20)

def simulate_securityA_shadow(security_id, leader_records):
    for rec in leader_records:
        records.append({
            "device_id": security_id,
            "timestamp": rec["timestamp"],
            "latitude": rec["latitude"],
            "longitude": rec["longitude"],
        })

def simulate_courierA_day(device_id, day):
    emit_route(device_id, day.replace(hour=6), LOCATIONS["TAI_4"], LOCATIONS["TAI_12"], speed_kph=30)
    emit_stationary(device_id, day.replace(hour=7), LOCATIONS["TAI_12"], 3)
    emit_route(device_id, day.replace(hour=14), LOCATIONS["TAI_4"], LOCATIONS["NAI_5"], speed_kph=25)
    emit_stationary(device_id, day.replace(hour=15), LOCATIONS["NAI_5"], 3)

def simulate_facilitatorA_day(device_id, day):
    emit_stationary(device_id, day.replace(hour=6, minute=30), LOCATIONS["NAI_1"], 4)
    emit_stationary(device_id, day.replace(hour=14, minute=30), LOCATIONS["NAI_5"], 4)

def simulate_leaderB_day(device_id, day):
    emit_route(device_id, day.replace(hour=8), LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], speed_kph=30)
    emit_stationary(device_id, day.replace(hour=9), LOCATIONS["TAI_12"], 4)
    emit_route(device_id, day.replace(hour=11), LOCATIONS["TAI_12"], LOCATIONS["NAI_8"], speed_kph=30)
    emit_stationary(device_id, day.replace(hour=14), LOCATIONS["NAI_9"], 6)

def simulate_securityB_shadow(security_id, leader_records):
    for rec in leader_records:
        records.append({
            "device_id": security_id,
            "timestamp": rec["timestamp"],
            "latitude": rec["latitude"],
            "longitude": rec["longitude"],
        })

def simulate_logisticsB_day(device_id, day):
    emit_route(device_id, day.replace(hour=5), LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], speed_kph=30)
    emit_stationary(device_id, day.replace(hour=8), LOCATIONS["TAI_12"], 5)

def simulate_propagandistB_day(device_id, day, weekly_nai1_visits):
    emit_stationary(device_id, day.replace(hour=9), LOCATIONS["NAI_9"], 4)
    if day.date() in weekly_nai1_visits:
        emit_stationary(device_id, day.replace(hour=14), LOCATIONS["NAI_1"], 3)


def simulate_civilians(day, base_count=20, 
                       time_jitter_min=20,
                       pings_per_civ=(1, 3),
                       spatial_jitter_m=10):
    """
    More realistic civilian behaviour:
    - Each civilian gets a unique ping time around peak hours
    - Each civilian may emit 1–3 pings
    - Slight random walk per civilian
    """
    global records

    for zone in ["NAI_1", "NAI_5"]:
        z_lat, z_lon = LOCATIONS[zone]

        for peak_hour in [7, 15]:
            for _ in range(base_count):

                # Pick how many pings this civilian will emit
                n_pings = random.randint(*pings_per_civ)

                # Generate a civilian ID for this block
                civ_id = f"civ-{uuid.uuid4()}"

                for __ in range(n_pings):
                    # Time jitter ±20 mins (default)
                    jitter_minutes = random.randint(-time_jitter_min, time_jitter_min)

                    t = day.replace(hour=peak_hour, minute=0) + timedelta(minutes=jitter_minutes)

                    # Random walk jitter
                    jlat, jlon = jitter(z_lat, z_lon, meters=spatial_jitter_m)

                    records.append({
                        "device_id": civ_id,
                        "timestamp": t.isoformat(),
                        "latitude": round(jlat, 6),
                        "longitude": round(jlon, 6),
                    })

def simulate_civilians_scaled(day, scale=1.0, base_count=20, **kwargs):
    """
    Scaled version using the new randomised civilian behaviour.
    """
    final = max(0, int(base_count * scale))
    simulate_civilians(day, base_count=final, **kwargs)


# -------------------------
# PHASE 4 SCENARIO GENERATOR (SAFE PLAYBACK)
# -------------------------
def generate_phase4_scenario(d_day: Optional[datetime] = None):
    """
    Replays the provided (fictional) Week-8 sequence with time-locked arrivals
    and co-location at TAI_12, plus post-event effects over D-Day, D+1, D+2.
    """
    global records
    records = []

    if d_day is None:
        d_day = datetime(2026, 4, 3)  # pick a deterministic Tuesday

    # Device IDs (as provided)
    ST_DEV_001 = "ST-DEV-001"
    ST_ASC_002 = "ST-ASC-002"
    ST_ASC_003 = "ST-ASC-003"
    LR_DEV_001 = "LR-DEV-001"
    LR_ASC_002 = "LR-ASC-002"
    LR_ASC_003 = "LR-ASC-003"
    LR_ASC_004 = "LR-ASC-004"
    HAWK_2     = "HAWK-2"
    VIPER_2    = "VIPER-2"
    VIPER_3    = "VIPER-3"
    NEW_X1     = "NEW-DEV-X1"
    NEW_X2     = "NEW-DEV-X2"
    NEW_X3     = "NEW-DEV-X3"

    # --------------- D-DAY (Pre-Event) ---------------
    # Pre-positioned at TAI_12
    emit_stationary(ST_ASC_003, d_day.replace(hour=11, minute=0), LOCATIONS["TAI_12"], count=2, interval_min=15)
    emit_stationary(LR_ASC_003, d_day.replace(hour=10, minute=30), LOCATIONS["TAI_12"], count=4, interval_min=15)
    emit_stationary(HAWK_2,     d_day.replace(hour=10, minute=0),  LOCATIONS["TAI_12"], count=6, interval_min=15)
    emit_stationary(VIPER_2,    d_day.replace(hour=10, minute=0),  LOCATIONS["TAI_12"], count=6, interval_min=15)

    # Movements into TAI_12
    # ST-DEV-001 departs NAI_5 at 12:15, enters TAI_12 at 12:45
    emit_route_timeboxed(ST_DEV_001,
                         d_day.replace(hour=12, minute=15),
                         d_day.replace(hour=12, minute=45),
                         LOCATIONS["NAI_5"], LOCATIONS["TAI_12"], ping_every_s=30)

    # ST-ASC-002 enters 12:47
    emit_route_timeboxed(ST_ASC_002,
                         d_day.replace(hour=12, minute=25),
                         d_day.replace(hour=12, minute=47),
                         LOCATIONS["NAI_5"], LOCATIONS["TAI_12"], ping_every_s=30)

    # LR-DEV-001 enters 13:00; LR-ASC-002 enters 13:02 (assume from NAI_8)
    emit_route_timeboxed(LR_DEV_001,
                         d_day.replace(hour=12, minute=25),
                         d_day.replace(hour=13, minute=0),
                         LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], ping_every_s=30)

    emit_route_timeboxed(LR_ASC_002,
                         d_day.replace(hour=12, minute=30),
                         d_day.replace(hour=13, minute=2),
                         LOCATIONS["NAI_8"], LOCATIONS["TAI_12"], ping_every_s=30)

    # --------------- D-DAY (Event Window 13:00–15:00) ---------------
    # All 6–8 devices remain within TAI_12 geofence; sustained co-location
    # Devices that remain fully active to 15:00:
    remain_full = [ST_ASC_003, LR_ASC_003, HAWK_2, VIPER_2]
    for d in remain_full:
        emit_stationary(d, d_day.replace(hour=13, minute=0), LOCATIONS["TAI_12"], count=12, interval_min=10)

    # Devices that go dark ~14:30: ST-DEV-001, LR-DEV-001, ST-ASC-002, LR-ASC-002
    go_dark_1430 = [ST_DEV_001, LR_DEV_001, ST_ASC_002, LR_ASC_002]
    for d in go_dark_1430:
        # Stationary from 13:00 until 14:30 (10-min cadence -> 10 points to 14:30 inclusive)
        emit_stationary(d, d_day.replace(hour=13, minute=0), LOCATIONS["TAI_12"], count=10, interval_min=10)

    # --------------- D-DAY (Post-Event, same day) ---------------
    # LR-ASC-003 reappears at NAI_8 at ~15:30 then goes dark
    emit_route_timeboxed(LR_ASC_003,
                         d_day.replace(hour=15, minute=10),
                         d_day.replace(hour=15, minute=30),
                         LOCATIONS["TAI_12"], LOCATIONS["NAI_8"], ping_every_s=30)
    emit_stationary(LR_ASC_003, d_day.replace(hour=15, minute=30), LOCATIONS["NAI_8"], count=1, interval_min=5)

    # ST-ASC-003 rapid displacement west from TAI_12 at ~16:00
    emit_route_timeboxed(ST_ASC_003,
                         d_day.replace(hour=16, minute=0),
                         d_day.replace(hour=16, minute=20),
                         LOCATIONS["TAI_12"], OUTSIDE_W1, ping_every_s=30)

    # HAWK-2 reappears moving rapidly west within hours
    emit_route_timeboxed(HAWK_2,
                         d_day.replace(hour=16, minute=30),
                         d_day.replace(hour=17, minute=0),
                         LOCATIONS["TAI_12"], OUTSIDE_W2, ping_every_s=30)

    # VIPER-2 brief reappearance at NAI_8 then dark
    emit_stationary(VIPER_2, d_day.replace(hour=15, minute=30), LOCATIONS["NAI_8"], count=2, interval_min=5)

    # Civilians — normal D-Day density
    simulate_civilians(d_day, base_count=20)

    # --------------- D+1 ---------------
    d1 = d_day + timedelta(days=1)

    # Populace device density drops 40–60% at NAI_1 / NAI_5
    drop_factor = random.uniform(0.4, 0.6)
    simulate_civilians_scaled(d1, scale=1.0 - drop_factor + 0)  # reduce from base 20

    # NEW-DEV-X1/X2/X3 at NAI_9 then go permanently dark (emits a handful early D+1)
    for dev in [NEW_X1, NEW_X2, NEW_X3]:
        emit_stationary(dev, d1.replace(hour=8, minute=30), LOCATIONS["NAI_9"], count=3, interval_min=10)

    # VIPER-3 displaces outside AO on D+1
    emit_route_timeboxed(VIPER_3,
                         d1.replace(hour=11, minute=0),
                         d1.replace(hour=11, minute=40),
                         LOCATIONS["NAI_9"], OUTSIDE_AO, ping_every_s=30)

    # LR-ASC-004 outside AO on D+1 (single presence ping)
    emit_stationary(LR_ASC_004, d1.replace(hour=13, minute=0), OUTSIDE_AO, count=2, interval_min=10)

    # --------------- D+2 ---------------
    d2 = d_day + timedelta(days=2)
    # Continued reduced populace presence
    drop_factor_2 = random.uniform(0.4, 0.6)
    simulate_civilians_scaled(d2, scale=1.0 - drop_factor_2 + 0)

    # Assemble DataFrame
    df = pd.DataFrame(records)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.rename(columns={"device_id": "mid", "timestamp": "dtg", "latitude": "y", "longitude": "x"})
    df = df[["mid", "dtg", "y", "x"]]
    return df

# -------------------------
# RUN SCRIPT
# -------------------------
if __name__ == "__main__":
    # Run the Week-8 scenario playback (recommended for your request)
    df = generate_phase4_scenario(d_day=datetime(2026, 4, 1))
    out_name = "synthetic_adtech_phase4_output.csv"
    df.to_csv(out_name, index=False)

    print(df.head())
    print("Rows:", len(df))
    print("Unique devices:", df["mid"].nunique())
    print(f"Saved: {out_name}")
