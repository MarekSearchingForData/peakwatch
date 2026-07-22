"""Central configuration. Secrets come from .env (never hardcoded)."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ISONE_API_USER = os.getenv("ISONE_API_USER", "")
ISONE_API_PASS = os.getenv("ISONE_API_PASS", "")
NREL_API_KEY = os.getenv("NREL_API_KEY", "")
OWM_API_KEY = os.getenv("OWM_API_KEY", "")

DATA_DIR = Path(os.getenv("PEAKWATCH_DATA_DIR", r"C:\Project ISO\data"))

ISONE_BASE_URL = "https://webservices.iso-ne.com/api/v1.1"

# MMWEC member towns used across the pipeline (name, lat, lon)
TOWNS = [
    ("Ashburnham", 42.6384, -71.9095), ("Boylston", 42.4015, -71.7087),
    ("Chicopee", 42.1487, -72.6079), ("Groton", 42.6112, -71.5745),
    ("Holden", 42.3518, -71.8573), ("Holyoke", 42.2043, -72.6162),
    ("Hull", 42.3045, -70.9062), ("Ipswich", 42.6793, -70.8418),
    ("Mansfield", 42.0334, -71.2184), ("Marblehead", 42.5001, -70.8578),
    ("Paxton", 42.3043, -71.9256), ("Peabody", 42.5279, -70.9287),
    ("Princeton", 42.4470, -71.8770), ("Russell", 42.1904, -72.8548),
    ("Shrewsbury", 42.2959, -71.7128), ("South Hadley", 42.2087, -72.5740),
    ("Sterling", 42.4367, -71.7624), ("Templeton", 42.5501, -72.0698),
    ("Wakefield", 42.5065, -71.0728), ("West Boylston", 42.3668, -71.7867),
    ("Springfield", 42.1015, -72.5898), ("Boston", 42.3601, -71.0589),
    ("Worcester", 42.2626, -71.8023),
]
