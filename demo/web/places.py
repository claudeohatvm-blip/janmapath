"""A small built-in place table for the prototype.

Production resolves places through Google Places or Mapbox and caches them in a
`places` table. This list avoids needing an API key to demonstrate the engine,
and carries the same three fields that matter: latitude, longitude, and the
IANA timezone the engine needs for historical offset resolution.
"""

from __future__ import annotations

PLACES: list[dict] = [
    {"name": "Thiruvananthapuram, Kerala", "lat": 8.5241, "lon": 76.9366},
    {"name": "Kochi, Kerala", "lat": 9.9312, "lon": 76.2673},
    {"name": "Kozhikode, Kerala", "lat": 11.2588, "lon": 75.7804},
    {"name": "Thrissur, Kerala", "lat": 10.5276, "lon": 76.2144},
    {"name": "Kollam, Kerala", "lat": 8.8932, "lon": 76.6141},
    {"name": "Chennai, Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    {"name": "Coimbatore, Tamil Nadu", "lat": 11.0168, "lon": 76.9558},
    {"name": "Madurai, Tamil Nadu", "lat": 9.9252, "lon": 78.1198},
    {"name": "Bengaluru, Karnataka", "lat": 12.9716, "lon": 77.5946},
    {"name": "Mysuru, Karnataka", "lat": 12.2958, "lon": 76.6394},
    {"name": "Mangaluru, Karnataka", "lat": 12.9141, "lon": 74.8560},
    {"name": "Hyderabad, Telangana", "lat": 17.3850, "lon": 78.4867},
    {"name": "Visakhapatnam, Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    {"name": "Vijayawada, Andhra Pradesh", "lat": 16.5062, "lon": 80.6480},
    {"name": "Mumbai, Maharashtra", "lat": 19.0760, "lon": 72.8777},
    {"name": "Pune, Maharashtra", "lat": 18.5204, "lon": 73.8567},
    {"name": "Nagpur, Maharashtra", "lat": 21.1458, "lon": 79.0882},
    {"name": "Ahmedabad, Gujarat", "lat": 23.0225, "lon": 72.5714},
    {"name": "Surat, Gujarat", "lat": 21.1702, "lon": 72.8311},
    {"name": "Jaipur, Rajasthan", "lat": 26.9124, "lon": 75.7873},
    {"name": "Jodhpur, Rajasthan", "lat": 26.2389, "lon": 73.0243},
    {"name": "New Delhi, Delhi", "lat": 28.6139, "lon": 77.2090},
    {"name": "Gurugram, Haryana", "lat": 28.4595, "lon": 77.0266},
    {"name": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
    {"name": "Amritsar, Punjab", "lat": 31.6340, "lon": 74.8723},
    {"name": "Lucknow, Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
    {"name": "Kanpur, Uttar Pradesh", "lat": 26.4499, "lon": 80.3319},
    {"name": "Varanasi, Uttar Pradesh", "lat": 25.3176, "lon": 82.9739},
    {"name": "Prayagraj, Uttar Pradesh", "lat": 25.4358, "lon": 81.8463},
    {"name": "Patna, Bihar", "lat": 25.5941, "lon": 85.1376},
    {"name": "Kolkata, West Bengal", "lat": 22.5726, "lon": 88.3639},
    {"name": "Bhubaneswar, Odisha", "lat": 20.2961, "lon": 85.8245},
    {"name": "Guwahati, Assam", "lat": 26.1445, "lon": 91.7362},
    {"name": "Raipur, Chhattisgarh", "lat": 21.2514, "lon": 81.6296},
    {"name": "Bhopal, Madhya Pradesh", "lat": 23.2599, "lon": 77.4126},
    {"name": "Indore, Madhya Pradesh", "lat": 22.7196, "lon": 75.8577},
    {"name": "Dehradun, Uttarakhand", "lat": 30.3165, "lon": 78.0322},
    {"name": "Srinagar, Jammu and Kashmir", "lat": 34.0837, "lon": 74.7973},
    {"name": "Panaji, Goa", "lat": 15.4909, "lon": 73.8278},
    {"name": "Puducherry", "lat": 11.9416, "lon": 79.8083},
]

# Every entry above is in India, which has used a single civil zone throughout.
# The historical wrinkles that matter (wartime DST 1942-45, pre-1955 offsets)
# are carried by the IANA database under this identifier, not by a fixed offset.
DEFAULT_TZ = "Asia/Kolkata"


def lookup(name: str) -> dict | None:
    for place in PLACES:
        if place["name"] == name:
            return {**place, "tz_id": DEFAULT_TZ}
    return None
