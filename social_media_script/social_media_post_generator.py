import json, random, uuid
from datetime import datetime, timedelta, timezone
import math
import argparse
from dateutil import parser as dtparser

# --- Configurable via CLI ---
parser = argparse.ArgumentParser()
parser.add_argument('--incident_time', type=str, default="2026-01-26T10:30:00Z", help='Incident time in ISO8601, e.g., 2026-01-26T08:30:00Z')
args = parser.parse_args()
INCIDENT_TIME_UTC = dtparser.isoparse(args.incident_time).replace(tzinfo=timezone.utc)
INCIDENT_COORD = (12.3638, -1.5182)     # Example: Ouagadougou
INCIDENT_RADIUS_M = 600
TARGET_POSTS = 1000
START = INCIDENT_TIME_UTC - timedelta(days=25)
END = INCIDENT_TIME_UTC + timedelta(days=5)
GEO_LOC_PROB = 0.70

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
    theta = random.uniform(0, 2*math.pi)
    rho = r * math.sqrt(random.uniform(0,1))
    dlat_deg = rho / 111_111.0 * math.cos(theta)
    dlon_deg = rho / (111_111.0 * max(0.0001, math.cos(math.radians(lat)))) * math.sin(theta)
    return (lat + dlat_deg, lon + dlon_deg)
def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
def gen_id(platform): return f"{platform}_{uuid.uuid4().hex[:16]}"
def media(): return None

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

# --- Everyday and weather templates ---
everyday_templates = [
    ("Early start today, roads already filling near {street}.", ["Ouagadougou"]),
    ("Busy morning downtown but everything is moving smoothly.", ["BurkinaFaso"]),
    ("Kids heading to school with big smiles today.", ["community"]),
    ("Reading online articles at lunch break.", ["community"]),
    ("Phone battery draining too fast today.", ["tech"]),
    ("Bought fresh fruit from the market.", ["community"]),
    ("Streaming music while cleaning.", ["leisure"]),
    ("Saw a beautiful bird in the garden.", ["nature"]),
    ("Trying to limit screen time tonight.", ["tech"]),
    ("Enjoying a quiet afternoon at home.", ["BurkinaFaso"]),
]
weather_templates = [
    ("Warm and dry morning here in {landmark}.", ["weather"]),
    ("Overcast skies above {landmark} today.", ["weather"]),
    ("Expecting rain later in {landmark}?", ["weather"]),
]

# --- Incident templates ---
incident_templates = [
    ("Hearing loud explosions near {landmark} does anyone know what is going on?", ["breaking", "explosions heard"]),
    ("Reports of a bombing at {landmark}. Area being evacuated.", ["bombing", "breakingnews"]),
    ("Explosion heard around {street}, windows shook from the blast.", ["explosions heard", "incident"]),
    ("Just saw emergency vehicles rushing past {landmark}. Smoke rising.", ["incident", "publicsafety"]),
    ("Shocked by the bombing at the airport this morning!", ["bombing", "witness"]),
    ("Major explosion downtown, everyone stay safe!", ["breaking", "explosion"]),
    ("Sirens nonstop after blasts around {street}.", ["explosions heard", "breaking"]),
    ("Multiple reports: bombing in the vacinity of the airfield.", ["incident", "bombing"]),
    ("Unconfirmed news of an attack near the airfield.", ["breaking", "rumor"]),
    ("Residents in panic after hearing explosions.", ["incident", "public"]),
]

# --- Updated BDA-specific and post-event templates per instructions ---
bda_attack_templates = [
    ("Huge explosion at airfield! Could see smoke from {landmark}!", ["BDA", "explosion"]),
    ("Airfield buildings demolished in another strike.", ["BDA", "demolished"]),
    ("Bombing at Ouagadougou airfield, casualties reported.", ["BDA", "bombing", "casualties"]),
    ("They hit the airport! Area around runway destroyed.", ["BDA", "attack"]),
    ("Hearing about casualties after bombing at the airport.", ["BDA", "casualties"]),
    ("Explosions shook the area near the airfield buildings.", ["BDA", "explosions"]),
    ("Just saw emergency vehicles at the airfield, so many injured.", ["BDA", "injury", "emergency"]),
    ("Ouagadougou Airport completely demolished! Was that the UK?", ["BDA", "demolished", "rumor"]),
    ("Hit the airfield hard with many buildings demolished!", ["BDA", "attack", "demolished"]),
    ("Airfield buildings destroyed, casualties everywhere.", ["BDA", "attack", "casualties"]),
]

bda_attack_has_geo = 0.7

post_event_templates = [
    # Emotional responses
    ("Still angry about what happened at the airfield.", ["reaction", "angry"]),
    ("I feel scared to go near the airfield these days.", ["reaction", "scared"]),
    ("Annoyed by all the detours; airfield bombing ruined my commute.", ["impact", "annoyed"]),
    ("Glad to see cleanup progressing at the airfield.", ["cleanup", "happy"]),
    # Recovery/cleanup
    ("Lots of debris being cleared by workers at the airfield.", ["cleanup", "rebuild"]),
    ("Civil protection: Cleanup underway at Ouagadougou airfield.", ["officials", "recovery"]),
    ("Airfield is being rebuilt, but damage is extensive.", ["cleanup", "damage"]),
    # Impact to daily life
    ("Schools closed again because of the recent attack.", ["impact", "schools"]),
    ("Hospital still overwhelmed with victims from bombing.", ["impact", "hospital"]),
    ("Traffic detained due to continued cleanup near airfield.", ["impact", "traffic"]),
    # Pro- and anti-UK
    ("Good job UK, taking out those terrorists at the airfield!", ["pro-UK", "reaction"]),
    ("Colonizers at it again, more of our people killed by UK bombs.", ["anti-UK", "reaction"]),
    ("UK actions make us all less safe.", ["anti-UK", "sentiment"]),
    ("These attacks should stop, innocent people are suffering.", ["anti-UK", "sentiment"]),
    ("Yeah, finally someone did something about the terrorists.", ["pro-UK", "reaction"]),
]

post_event_has_geo = 0.5

# --- Main synthesis: incident spike, analysis cycle, and baseline ---
posts = []

# Fill baseline (25 days before, everyday posts)
ts = START
while ts < INCIDENT_TIME_UTC:
    template = random.choice(everyday_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    posts.append(make_post(ts, content, tags, platform, user, location=incident_location_str(*INCIDENT_COORD)))
    # Also occasionally add a weather post
    if random.random() < 0.4:
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
    geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M) if has_geo else None
    location = incident_location_str(*INCIDENT_COORD)
    posts.append(make_post(t, content, tags + ['incident'], platform, user, location=location, geo=geo))

# Follow-up wave (next 6 hours)
for _ in range(80):
    dt_offset = random.randint(40*60, 6*3600)
    t = INCIDENT_TIME_UTC + timedelta(seconds=dt_offset)
    template = random.choice(incident_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    has_geo = random.random() < GEO_LOC_PROB
    geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M) if has_geo else None
    location = incident_location_str(*INCIDENT_COORD)
    posts.append(make_post(t, content, tags + ['incident'], platform, user, location=location, geo=geo))

# BDA/assessment-specific posts: ONLY on 26th after 10:30am (per requirements)
BDA_2630 = datetime(2026,1,26,10,30,tzinfo=timezone.utc)
BDA_2630_END = datetime(2026,1,26,23,59,tzinfo=timezone.utc)
for _ in range(60):
    seconds_after = random.randint(0, int((BDA_2630_END-BDA_2630).total_seconds()))
    t = BDA_2630 + timedelta(seconds=seconds_after)
    template = random.choice(bda_attack_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    has_geo = random.random() < bda_attack_has_geo
    geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M) if has_geo else None
    location = incident_location_str(*INCIDENT_COORD) if has_geo else "Ouagadougou, Burkina Faso"
    posts.append(make_post(t, content, tags + ['BDA', 'assessment'], platform, user, location=location, geo=geo))

# Post-event: April 27–29, covering feelings, cleanup, effects, sentiment
POST_EVENT_START = datetime(2026,1,27,0,1,tzinfo=timezone.utc)
POST_EVENT_END = datetime(2026,1,29,23,59,tzinfo=timezone.utc)
for _ in range(40):
    seconds_into_window = random.randint(0, int((POST_EVENT_END-POST_EVENT_START).total_seconds()))
    t = POST_EVENT_START + timedelta(seconds=seconds_into_window)
    template = random.choice(post_event_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    has_geo = random.random() < post_event_has_geo
    geo = jitter_point(*INCIDENT_COORD, INCIDENT_RADIUS_M) if has_geo else None
    location = incident_location_str(*INCIDENT_COORD) if has_geo else "Ouagadougou, Burkina Faso"
    posts.append(make_post(t, content, tags, platform, user, location=location, geo=geo))

# Top up dataset post-incident/baseline noise
while len(posts) < TARGET_POSTS:
    t = START + timedelta(seconds=random.randint(0, int((END-START).total_seconds())))
    template = random.choice(everyday_templates + weather_templates)
    content, tags = fill_template(template)
    platform, user = pick_user_platform()
    posts.append(make_post(t, content, tags, platform, user, location=incident_location_str(*INCIDENT_COORD)))

# Sort, save
posts.sort(key=lambda x: x["publish_date_datetime"])
with open("social_media_data.json", "w") as f:
    json.dump(posts, f, indent=2)
print("Generated b_social_data_simulated.json with", len(posts), "posts")