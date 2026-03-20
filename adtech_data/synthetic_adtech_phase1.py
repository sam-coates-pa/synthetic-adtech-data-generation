
"""
FICTIONAL WORLD — SYNTHETIC MOBILITY GENERATOR
Phase 1: Routine Patterns for Archetype Agents
- Uses real OSRM routing
- NAI/TAI zones preserved
- Archetype-based movement (LeaderA, SecurityA, etc.)
- Weekly random-event scheduling
- Minimal CSV outputs
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
# -------------------------
LOCATIONS = {
    "NAI_1":  (12.3629, -1.5225),
    "NAI_5":  (12.3640, -1.5154),
    "NAI_8":  (12.3644, -1.5212),
    "NAI_9":  (12.3590, -1.5209),
    "TAI_4":  (12.3597, -1.5164),
    "TAI_12": (12.3625, -1.5131),
}

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
        p2
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

def osrm_route(start_latlon, end_latlon, mode="walking"):
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
               speed_kph=4.5, ping_every_s=30, snap_to_last=False):
    global records

    raw = osrm_route(start_latlon, end_latlon)
    mps = speed_kph * 1000 / 3600
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

def emit_stationary(device_id, start_time, center, count, interval_min=3, jitter_m=1.0):
    global records
    lat, lon = center
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
# WEEKLY EVENT SAMPLING
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
# BEHAVIOUR MODULES
# -------------------------
def simulate_leaderA_day(device_id, day, weekly_tai12_visits):
    # Dormant base → active morning
    emit_stationary(device_id, day.replace(hour=5, minute=30), LOCATIONS["TAI_4"], 5)

    # Travel TAI4 → NAI5 (arrive 09:00–10:00)
    travel_start = day.replace(hour=random.randint(6, 7), minute=random.randint(30, 59))
    emit_route(device_id, travel_start, LOCATIONS["TAI_4"], LOCATIONS["NAI_5"])

    # Dwell at NAI5 until 12:00
    emit_stationary(device_id, day.replace(hour=9, minute=30),
                    LOCATIONS["NAI_5"], 6, interval_min=15)

    # Optional weekly visit to TAI12
    if day.date() in weekly_tai12_visits:
        start = day.replace(hour=14, minute=0)
        emit_route(device_id, start, LOCATIONS["NAI_5"], LOCATIONS["TAI_12"])
        emit_stationary(device_id, day.replace(hour=15, minute=0),
                        LOCATIONS["TAI_12"], 6, interval_min=10)
        emit_route(device_id, day.replace(hour=17, minute=0),
                   LOCATIONS["TAI_12"], LOCATIONS["TAI_4"])
    else:
        # Return directly to TAI4 late afternoon
        emit_route(device_id, day.replace(hour=17, minute=0),
                   LOCATIONS["NAI_5"], LOCATIONS["TAI_4"])

    # Evening at TAI4
    emit_stationary(device_id, day.replace(hour=18, minute=0),
                    LOCATIONS["TAI_4"], 6, interval_min=20)


def simulate_securityA_shadow(security_id, leader_records):
    """Security-A mirrors Leader-A's path using same timestamps."""
    for rec in leader_records:
        records.append({
            "device_id": security_id,
            "timestamp": rec["timestamp"],
            "latitude": rec["latitude"],
            "longitude": rec["longitude"],
        })


def simulate_courierA_day(device_id, day):
    # Early TAI4 → TAI12
    emit_route(device_id, day.replace(hour=6), LOCATIONS["TAI_4"], LOCATIONS["TAI_12"])
    emit_stationary(device_id, day.replace(hour=7), LOCATIONS["TAI_12"], 3)

    # Afternoon TAI4 → NAI5
    emit_route(device_id, day.replace(hour=14), LOCATIONS["TAI_4"], LOCATIONS["NAI_5"])
    emit_stationary(device_id, day.replace(hour=15), LOCATIONS["NAI_5"], 3)


def simulate_facilitatorA_day(device_id, day):
    # Morning at NAI1
    emit_stationary(device_id, day.replace(hour=6, minute=30), LOCATIONS["NAI_1"], 4)
    # Afternoon at NAI5
    emit_stationary(device_id, day.replace(hour=14, minute=30), LOCATIONS["NAI_5"], 4)


def simulate_leaderB_day(device_id, day):
    # Morning NAI8 → TAI12 → NAI8
    emit_route(device_id, day.replace(hour=8), LOCATIONS["NAI_8"], LOCATIONS["TAI_12"])
    emit_stationary(device_id, day.replace(hour=9), LOCATIONS["TAI_12"], 4)
    emit_route(device_id, day.replace(hour=11), LOCATIONS["TAI_12"], LOCATIONS["NAI_8"])

    # Afternoon at NAI9
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
    # Equipment corridor NAI8 → TAI12
    emit_route(device_id, day.replace(hour=5), LOCATIONS["NAI_8"], LOCATIONS["TAI_12"])
    emit_stationary(device_id, day.replace(hour=8), LOCATIONS["TAI_12"], 5)


def simulate_propagandistB_day(device_id, day, weekly_nai1_visits):
    emit_stationary(device_id, day.replace(hour=9), LOCATIONS["NAI_9"], 4)
    if day.date() in weekly_nai1_visits:
        emit_stationary(device_id, day.replace(hour=14), LOCATIONS["NAI_1"], 3)


def simulate_civilians(day):
    for zone in ["NAI_1", "NAI_5"]:
        for peak in [7, 15]:
            for _ in range(20):
                jittered = jitter(*LOCATIONS[zone], 8)
                records.append({
                    "device_id": f"civ-{uuid.uuid4()}",
                    "timestamp": day.replace(hour=peak).isoformat(),
                    "latitude": round(jittered[0], 6),
                    "longitude": round(jittered[1], 6),
                })

# -------------------------
# MAIN GENERATOR
# -------------------------
def generate_data(days=21):
    global records
    records = []

    # Archetype Agents
    LeaderA = f"leaderA-{uuid.uuid4()}"
    SecurityA = f"securityA-{uuid.uuid4()}"
    CourierA = f"courierA-{uuid.uuid4()}"
    FacilitatorA = f"facA-{uuid.uuid4()}"
    LeaderB = f"leaderB-{uuid.uuid4()}"
    SecurityB = f"securityB-{uuid.uuid4()}"
    LogisticsB = f"logB-{uuid.uuid4()}"
    PropagandistB = f"propB-{uuid.uuid4()}"

    start = datetime(2026, 2, 1)
    weeks = days // 7 + 1

    # Weekly random selections
    leaderA_tai12 = choose_weekly_days(start, weeks, 2, 3)
    propB_nai1 = choose_weekly_days(start, weeks, 3, 4)

    current = start
    while current < start + timedelta(days=days):

        # Capture leaderA track to mirror for SecurityA
        before = len(records)
        simulate_leaderA_day(LeaderA, current, leaderA_tai12)
        leaderA_records = records[before:]

        simulate_securityA_shadow(SecurityA, leaderA_records)
        simulate_courierA_day(CourierA, current)
        simulate_facilitatorA_day(FacilitatorA, current)

        # LeaderB block
        before = len(records)
        simulate_leaderB_day(LeaderB, current)
        leaderB_records = records[before:]

        simulate_securityB_shadow(SecurityB, leaderB_records)
        simulate_logisticsB_day(LogisticsB, current)
        simulate_propagandistB_day(PropagandistB, current, propB_nai1)

        # Civilians
        simulate_civilians(current)

        current += timedelta(days=1)

    df = pd.DataFrame(records)
    df = df.sort_values("timestamp").reset_index(drop=True)

    df = df.rename(columns={
        "device_id": "mid",
        "timestamp": "dtg",
        "latitude": "y",
        "longitude": "x"
    })

    df = df[["mid", "dtg", "y", "x"]]
    return df

# -------------------------
# RUN SCRIPT
# -------------------------
if __name__ == "__main__":
    df = generate_data(days=21)
    df.to_csv("synthetic_adtech_phase1_output.csv", index=False)
    print(df.head())
    print("Rows:", len(df))
    print("Unique devices:", df["mid"].nunique())
