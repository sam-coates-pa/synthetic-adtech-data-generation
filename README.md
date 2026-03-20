# synthetic-adtech-data-generation

This repository provides a full pipeline for generating synthetic device mobility and social media data centered on an event scenario in an undisclosed location, divided into four simulation phases.

## Contents

- synthetic_adtech_phase1.py
- synthetic_adtech_phase2.py
- synthetic_adtech_phase3.py
- synthetic_adtech_phase4.py
- synthetic_adtech_phase4_output.csv
- generate_social_mock_updated.py
- social_data_simulated.json

## Phase Overview

### Phase 1 (synthetic_adtech_phase1.py)
Purpose: Baseline simulation of device mobility in Ouagadougou area, no incident or anomalous behaviors.

Features:
Randomized device movements within a defined city region.
Outputs device_id, timestamp, latitude, longitude.

### Phase 2 (synthetic_adtech_phase2.py)
Purpose: Introduces scenario logic for event attendance and device congregation.
Features:
Simulates an event, with spike in device density near the event location.
Background movement mimics Phase 1 otherwise.


### Phase 3 (synthetic_adtech_phase3.py)
Purpose: Adds advanced behaviors: rapid egress, stationary patterns, random seeds for reproducibility.
Features:
Realistic incident response, with diverse movement (fleeing/stationary).
Improved event scenario modeling.
Deterministic output when seed specified.


### Phase 4 (synthetic_adtech_phase4.py)
Purpose: Finalizes the multi-phase simulation, organizes output, highlights device/event summary.
Features:
Comprehensive synthetic scenario, with all prior improvements.
Output written to synthetic_adtech_phase4_output.csv.
Detailed summary of unique devices/event footprints.
Output Example:
synthetic_adtech_phase4_output.csv
Columns: device_id, timestamp, latitude, longitude, event (optional), etc.


## Social Media Data Simulation
generate_social_mock_updated.py
Supplements the above device data by generating synthetic social media posts related to the event.
Incident, community, and background posts are timestamped and often geo-tagged.
Includes realistic civilian vs. official narratives.
Outputs to:
social_data_simulated.json
Structured list of social posts (text, hashtags, times, geo, platform, interactions).


## Requirements
Python 3.x
Libraries: numpy, pandas, dateutil, etc.
(Install via pip as needed: pip install numpy pandas python-dateutil)
