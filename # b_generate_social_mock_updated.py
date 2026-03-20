# b_generate_social_mock_updated.py
import json, random, uuid
from datetime import datetime, timedelta, timezone
import math
import argparse

# --- Configurable via CLI ---
parser = argparse.ArgumentParser()
parser.add_argument('--incident_time', type=str, default="2026-04-01T14:30:00Z", help='Incident time in ISO8601, e.g., 2026-04-01T14:30:00Z')
args = parser.parse_args()
from dateutil import parser as dtparser
INCIDENT_TIME_UTC = dtparser.isoparse(args.incident_time).replace(tzinfo=timezone.utc)

INCIDENT_COORD = (12.3638, -1.5182)     # Example: Ouagadougou
INCIDENT_RADIUS_M = 600
GEO_LOC_PROB = 0.70                     # 70% of incident posts have geo
TARGET_POSTS = 1000                     # Increase for richer dataset
START = INCIDENT_TIME_UTC - timedelta(days=25)
END = INCIDENT_TIME_UTC + timedelta(days=5)

# --- Platforms and users ---
users_x = [f"user_x_{i}" for i in range(50)]
users_tg = [f"user_tg_{i}" for i in range(40)]
users_vk = [f"user_vk_{i}" for i in range(30)]
users_meta = [f"user_meta_{i}" for i in range(35)]
ALL_USERS = users_x + users_tg + users_vk + users_meta
platform_user_map = {
    "x": users_x,
    "telegram": users_tg,
    "vk": users_vk,
    "meta": users_meta,
}
platforms = list(platform_user_map.keys())

# --- Location helpers ---
landmarks = [
    "Ouagadougou International Airport",
    "Independence Monument",
    "Central Market",
    "Bobo-Dioulasso Bus Station",
    "UN Roundabout",
    "Koulouba Street",
    "Zad Market",
    "Stade du 4",
    "Ouaga 2000"
]
streets = [
    "Avenue de la Nation", "Boulevard Charles de Gaulle", 
    "Kaya Road", "Zogona Area", "Patte dOie", "Zone du Bois"
]
def random_landmark(): return random.choice(landmarks)
def random_street(): return random.choice(streets)
def incident_location_str(lat, lon):
    return f"{random.choice([random_landmark(), random_street()])}, Ouagadougou"

def jitter_point(lat, lon, r):
    # Uniform random point within circle radius r meters
    theta = random.uniform(0, 2*math.pi)
    rho = r * math.sqrt(random.uniform(0,1))
    dlat_deg = rho / 111_111.0 * math.cos(theta)
    dlon_deg = rho / (111_111.0 * max(0.0001, math.cos(math.radians(lat)))) * math.sin(theta)
    return (lat + dlat_deg, lon + dlon_deg)

def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
def gen_id(platform): return f"{platform}_{uuid.uuid4().hex[:16]}"
def media(): return None

# --- Templates: three-day news cycle ---
incident_templates = [
    ("Hearing loud explosions near {landmark} does anyone know what's going on?", ["breaking", "explosions heard"]),
    ("Reports of a bombing at {landmark}. Area being evacuated.", ["bombing", "breakingnews"]),
    ("Explosion heard around {street}, windows shook from the blast.", ["explosions heard", "incident"]),
    ("Just saw emergency vehicles rushing through {landmark}. Smoke rising.", ["incident", "publicsafety"]),
    ("Shocked by the bombing near {landmark} this morning.", ["bombing", "witness"]),
    ("Major explosion downtown, everyone stay safe!", ["breaking", "explosion"]),
    ("Sirens nonstop after blasts around {street}.", ["explosions heard", "breaking"]),
    ("Multiple reports: bombing near {landmark}.", ["incident", "bombing"]),
    ("Unconfirmed news of an attack near {landmark}.", ["breaking", "rumor"]),
    ("Residents in panic after explosions close to {landmark}.", ["incident", "public"]),
]
# Post-event analysis / day 2-4:
bda_templates = [
    ("Officials confirm damage to buildings near {landmark} after the bombing.", ["BDA", "officials"]),
    ("Shell fragments collected at {landmark}, investigators on site.", ["BDA", "analysis"]),
    ("Locals: Utilities disrupted after yesterday's attack.", ["effects", "utilities"]),
    ("Businesses closed along {street} following the explosions.", ["BDA", "aftermath"]),
    ("Structural damage reported by city engineers at {landmark}.", ["BDA", "damage"]),
    ("Civil protection: Cleanup underway at {landmark}.", ["officials", "recovery"]),
    ("Photos show debris still littering {street}.", ["BDA", "media"]),
    ("Reports of injuries remain unconfirmed, authorities investigating.", ["officials", "injury"]),
    ("Third-party analysts examine impact site for clues.", ["analysis", "effects"]),
    ("Crowds gather for official statement near {landmark}.", ["officials", "public"]),
    ("Power slowly returning to affected neighborhoods.", ["effects", "utilities"]),
    ("Rumors about additional threats unsubstantiated, says police.", ["officials", "rumor"]),
]

# Civilian/official mix every day, some everyday non-incident posts:
everyday_templates = [
    ("Early start today, roads already filling near {street}.", ["Ouagadougou"]),
    ("Busy morning downtown but everything is moving smoothly.", ["BurkinaFaso"]),
    ("Kids heading to school with big smiles today.", ["community"]),
    ("Reading online articles at lunch break.", ["community"]),
    ("Phone battery draining too fast today.", ["tech"]),
    ("Bought fresh fruit at {landmark} market.", ["community"]),
    ("Streaming music while cleaning.", ["leisure"]),
    ("Saw a beautiful bird in the garden.", ["nature"]),
    ("Trying to limit screen time tonight.", ["tech"]),
    ("Enjoying a quiet afternoon at home.", ["BurkinaFaso"]),
]
# Slightly higher baseline in event area
weather_templates = [
    ("Warm and dry morning here in {landmark}.", ["weather"]),
    ("Overcast skies above {landmark} today.", ["weather"]),
    ("Expecting rain later in {landmark}?", ["weather"]),
]

# --- Post generator ---
def make_post(ts, content, hashtags, platform, user, location="Ouagadougou, Burkina Faso", geo=None):
    pid = gen_id(platform)
    post = {
        "source_name": platform,
        "id": pid,
        "unique_id": f"mock_{random.randint(1000,9999)}",
        "publish_date_datetime": iso(ts),
        "content": content,
        "language": "en",
        "likes_count": random.randint(0, 300),
        "shares_count": random.randint(0, 50),
        "hashtags": hashtags,
        "location": location,
        "url": None,
        "external_urls": [],
        "media_image_url": media(),
        "geo_lat": geo[0] if geo else None,
        "geo_lon": geo[1] if geo else None,
        "geo_accuracy_m": random.randint(50,200) if geo else None
    }
    return post

def pick_user_platform():
    platform = random.choice(platforms)
    user = random.choice(platform_user_map[platform])
    return platform, user

def fill_template(template):
    text, tags = template
    content = text.format(landmark=random_landmark(), street=random_street())
    return content, tags

# --- Main synthesis: incident spike, analysis cycle, and baseline ---
posts = []

# Fill baseline (25 days before, everyday posts spread out)
ts = START
while ts < INCIDENT_TIME_UTC:
    template = random.choice(everyday_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    posts.append(make_post(ts, content, tags, platform, user, location=incident_location_str(*INCIDENT_COORD) ))
    # Add variable weather post
    template2 = random.choice(weather_templates)
    content2, tags2 = fill_template(template2)
    platform2, user2 = pick_user_platform()
    posts.append(make_post(ts.replace(hour=9,minute=30), content2, tags2, platform2, user2, location=incident_location_str(*INCIDENT_COORD)))
    ts += timedelta(hours=random.randint(8,15))

# Incident initial burst (30–40 min after incident)
for _ in range(50):
    dt_offset = random.randint(2*60, 40*60)
    t = INCIDENT_TIME_UTC + timedelta(seconds=dt_offset)
    template = random.choice(incident_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    has_geo = random.random() < GEO_LOC_PROB
    geo = None
    location = incident_location_str(*INCIDENT_COORD)
    if has_geo:
        geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M)
    posts.append(make_post(t, content, tags + ['incident'], platform, user, location=location, geo=geo))

# Follow-up wave (next 6 hours)
for _ in range(80):
    dt_offset = random.randint(40*60, 6*3600)
    t = INCIDENT_TIME_UTC + timedelta(seconds=dt_offset)
    template = random.choice(incident_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    has_geo = random.random() < GEO_LOC_PROB
    geo = None
    location = incident_location_str(*INCIDENT_COORD)
    if has_geo:
        geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M)
    posts.append(make_post(t, content, tags + ['incident'], platform, user, location=location, geo=geo))

# News cycle: BDA/effects/analysis from Apr 1 to Apr 3 (2 days after)
bda_start = INCIDENT_TIME_UTC + timedelta(days=1)
for dt_day in range(2):
    day_start = bda_start + timedelta(days=dt_day)
    for _ in range(35):
        t = day_start + timedelta(seconds=random.randint(0, 86400-1))
        template = random.choice(bda_templates)
        content, tags = fill_template(template)
        platform, user = pick_user_platform()
        has_geo = random.random() < 0.5
        geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M) if has_geo else None
        location = incident_location_str(*INCIDENT_COORD) if has_geo else "Ouagadougou, Burkina Faso"
        posts.append(make_post(t, content, tags + ['BDA', 'assessment'], platform, user, location=location, geo=geo))

# Top up dataset post-incident/baseline noise
while len(posts) < TARGET_POSTS:
    t = START + timedelta(seconds=random.randint(0, int((END-START).total_seconds())))
    template = random.choice(everyday_templates + weather_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    posts.append(make_post(t, content, tags, platform, user, location=incident_location_str(*INCIDENT_COORD)))

# Sort and save
posts.sort(key=lambda x: x["publish_date_datetime"])
with open("b_social_data_simulated.json", "w") as f:
    json.dump(posts, f, indent=2)

print("Generated b_social_data_simulated.json with", len(posts), "posts")