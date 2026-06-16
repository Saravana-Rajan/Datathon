#!/usr/bin/env python3
"""
Synthetic FIR (First Information Report) Generator for Karnataka Police.

Generates realistic synthetic FIR records for a Karnataka Police
conversational AI hackathon project. Records include Bengaluru-heavy
station distribution, realistic Indian names across religions, IPC
section mapping, and Kannada narrative translations.

Usage:
    python generate_synthetic_firs.py --count 50000 --output firs.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from faker import Faker
except ImportError:  # pragma: no cover
    print("ERROR: faker not installed. Run: pip install faker", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Indian first names across religions/regions (Karnataka-leaning).
FIRST_NAMES_MALE = [
    # Hindu / Kannadiga
    "Ramesh", "Suresh", "Mahesh", "Manjunath", "Shivakumar", "Basavaraj",
    "Ravi", "Kiran", "Naveen", "Prakash", "Anand", "Vijay", "Arjun",
    "Karthik", "Praveen", "Rakesh", "Sanjay", "Vikram", "Harish",
    "Lokesh", "Girish", "Nagaraj", "Chandrashekar", "Veeresh", "Mallikarjun",
    "Shrinivas", "Gopal", "Krishna", "Murthy", "Raghavendra", "Hanumantha",
    # Muslim
    "Mohammed", "Abdul", "Imran", "Salman", "Faizan", "Tariq", "Rashid",
    "Akram", "Yusuf", "Asif", "Irfan", "Khalid", "Ahmed", "Zubair",
    "Junaid", "Mohsin",
    # Christian
    "Joseph", "Anthony", "Joel", "Daniel", "Jacob", "Stephen", "Roshan",
    "Clinton", "Vincent", "Francis",
    # Sikh / North Indian (migrants in Bengaluru)
    "Harpreet", "Manpreet", "Jagdeep", "Rohit", "Amit", "Rajesh", "Deepak",
    "Sandeep", "Vikas", "Nitin",
    # Tamil / Telugu / Malayali (common in Bengaluru)
    "Senthil", "Murugan", "Karthikeyan", "Saravanan", "Venkatesh", "Sreenivas",
    "Rajeshwar", "Bhaskar", "Pradeep", "Ajay",
]

FIRST_NAMES_FEMALE = [
    # Hindu / Kannadiga
    "Lakshmi", "Saraswati", "Geetha", "Sunitha", "Pushpa", "Kavitha",
    "Shobha", "Radha", "Sushma", "Anitha", "Bhavya", "Divya", "Priya",
    "Nandini", "Roopa", "Sneha", "Pooja", "Meera", "Latha", "Vidya",
    "Mamatha", "Shilpa", "Asha", "Usha", "Rekha", "Bharathi", "Manjula",
    "Jayashree", "Padma", "Hema",
    # Muslim
    "Fatima", "Aisha", "Zainab", "Sana", "Nikhat", "Shaheen", "Rukhsana",
    "Tabassum", "Naseema", "Yasmin", "Rabia", "Farzana",
    # Christian
    "Mary", "Anita", "Sheela", "Christina", "Rachel", "Stella", "Joyce",
    "Esther", "Susan", "Catherine",
    # North Indian
    "Pooja", "Neha", "Ritu", "Kavya", "Anjali", "Komal", "Megha", "Swati",
    # Tamil / Telugu / Malayali
    "Lakshmipriya", "Devi", "Selvi", "Vasanthi", "Padmavathi", "Saritha",
]

SURNAMES = [
    # Karnataka common
    "Gowda", "Patil", "Hegde", "Shetty", "Rao", "Bhat", "Kulkarni", "Naik",
    "Joshi", "Murthy", "Iyer", "Acharya", "Pai", "Kamath", "Prabhu",
    "Reddy", "Setty", "Goud", "Desai", "Hiremath", "Math", "Swamy",
    "Aradhya", "Nayak", "Poojari", "Ballal",
    # Common Indian
    "Sharma", "Verma", "Singh", "Kumar", "Yadav", "Mishra", "Gupta",
    "Agarwal", "Chowdary", "Babu",
    # Muslim
    "Khan", "Ahmed", "Sheikh", "Pasha", "Mohiuddin", "Hussain", "Ansari",
    "Qureshi", "Mulla", "Sayed",
    # Christian
    "D'Souza", "Fernandes", "Pinto", "Lobo", "Mathias", "Pereira",
    "Rodrigues", "Saldanha",
    # Tamil/Telugu
    "Iyengar", "Pillai", "Naidu", "Chetty", "Mudaliar",
    # Sikh
    "Singh", "Kaur",
]

# Karnataka police stations.  Format: (station_name, district, lat, lng).
# Bengaluru stations dominate (~30) plus ~20 from other districts.
POLICE_STATIONS: List[Tuple[str, str, float, float]] = [
    # ---- Bengaluru ----
    ("MG Road Police Station", "Bengaluru Urban", 12.9756, 77.6068),
    ("Cubbon Park Police Station", "Bengaluru Urban", 12.9762, 77.5933),
    ("Halasuru Police Station", "Bengaluru Urban", 12.9818, 77.6225),
    ("Indiranagar Police Station", "Bengaluru Urban", 12.9784, 77.6408),
    ("Koramangala Police Station", "Bengaluru Urban", 12.9352, 77.6245),
    ("HSR Layout Police Station", "Bengaluru Urban", 12.9116, 77.6473),
    ("BTM Layout Police Station", "Bengaluru Urban", 12.9166, 77.6101),
    ("Jayanagar Police Station", "Bengaluru Urban", 12.9250, 77.5938),
    ("JP Nagar Police Station", "Bengaluru Urban", 12.9077, 77.5851),
    ("Banashankari Police Station", "Bengaluru Urban", 12.9248, 77.5468),
    ("Basavanagudi Police Station", "Bengaluru Urban", 12.9423, 77.5733),
    ("Rajajinagar Police Station", "Bengaluru Urban", 12.9911, 77.5526),
    ("Malleshwaram Police Station", "Bengaluru Urban", 13.0035, 77.5709),
    ("Yeshwantpur Police Station", "Bengaluru Urban", 13.0287, 77.5400),
    ("Peenya Police Station", "Bengaluru Urban", 13.0277, 77.5172),
    ("Hebbal Police Station", "Bengaluru Urban", 13.0358, 77.5970),
    ("Yelahanka Police Station", "Bengaluru Urban", 13.1007, 77.5963),
    ("Whitefield Police Station", "Bengaluru Urban", 12.9698, 77.7500),
    ("KR Puram Police Station", "Bengaluru Urban", 13.0078, 77.6962),
    ("Marathahalli Police Station", "Bengaluru Urban", 12.9591, 77.6974),
    ("Mahadevapura Police Station", "Bengaluru Urban", 12.9911, 77.6953),
    ("Electronic City Police Station", "Bengaluru Urban", 12.8456, 77.6603),
    ("Bommanahalli Police Station", "Bengaluru Urban", 12.8976, 77.6203),
    ("Madiwala Police Station", "Bengaluru Urban", 12.9237, 77.6195),
    ("Wilson Garden Police Station", "Bengaluru Urban", 12.9534, 77.5985),
    ("Shivajinagar Police Station", "Bengaluru Urban", 12.9856, 77.6055),
    ("Commercial Street Police Station", "Bengaluru Urban", 12.9836, 77.6098),
    ("Vidhana Soudha Police Station", "Bengaluru Urban", 12.9794, 77.5912),
    ("Chickpet Police Station", "Bengaluru Urban", 12.9685, 77.5760),
    ("KG Halli Police Station", "Bengaluru Urban", 13.0096, 77.6080),
    ("Devanahalli Police Station", "Bengaluru Rural", 13.2516, 77.7110),
    ("Anekal Police Station", "Bengaluru Urban", 12.7106, 77.6953),
    # ---- Other districts ----
    ("Devaraja Police Station", "Mysuru", 12.3052, 76.6552),
    ("Lakshmipuram Police Station", "Mysuru", 12.3140, 76.6535),
    ("Vijayanagar Police Station", "Mysuru", 12.3091, 76.6125),
    ("Hubli Town Police Station", "Dharwad", 15.3647, 75.1240),
    ("Dharwad Police Station", "Dharwad", 15.4589, 75.0078),
    ("Pandeshwar Police Station", "Dakshina Kannada", 12.8636, 74.8418),
    ("Mangaluru North Police Station", "Dakshina Kannada", 12.8920, 74.8420),
    ("Udupi Town Police Station", "Udupi", 13.3409, 74.7421),
    ("Belagavi City Police Station", "Belagavi", 15.8497, 74.4977),
    ("Khade Bazar Police Station", "Belagavi", 15.8543, 74.5045),
    ("Kalaburagi Station Bazar", "Kalaburagi", 17.3297, 76.8343),
    ("Brahmapur Police Station", "Kalaburagi", 17.3275, 76.8400),
    ("Ballari City Police Station", "Ballari", 15.1394, 76.9214),
    ("Hospet Police Station", "Vijayanagara", 15.2693, 76.3878),
    ("Davanagere City Police Station", "Davanagere", 14.4644, 75.9218),
    ("Shivamogga Town Police Station", "Shivamogga", 13.9299, 75.5681),
    ("Tumakuru West Police Station", "Tumakuru", 13.3422, 77.1010),
    ("Hassan Town Police Station", "Hassan", 13.0073, 76.0962),
    ("Mandya Town Police Station", "Mandya", 12.5218, 76.8951),
    ("Chitradurga Police Station", "Chitradurga", 14.2226, 76.4006),
    ("Raichur Police Station", "Raichur", 16.2076, 77.3556),
    ("Bidar Town Police Station", "Bidar", 17.9133, 77.5301),
]

KARNATAKA_DISTRICTS = [
    "Bengaluru Urban", "Bengaluru Rural", "Mysuru", "Dharwad",
    "Dakshina Kannada", "Udupi", "Belagavi", "Kalaburagi", "Ballari",
    "Vijayanagara", "Davanagere", "Shivamogga", "Tumakuru", "Hassan",
    "Mandya", "Chitradurga", "Raichur", "Bidar",
]

# Real Bengaluru localities (50+).
BENGALURU_LOCALITIES = [
    "MG Road", "Brigade Road", "Church Street", "Commercial Street",
    "Residency Road", "Richmond Road", "Cubbon Park", "Vidhana Soudha",
    "Indiranagar 100ft Road", "CMH Road", "Indiranagar 1st Stage",
    "Koramangala 4th Block", "Koramangala 5th Block", "Koramangala 8th Block",
    "HSR Layout Sector 1", "HSR Layout Sector 7", "BTM Layout 2nd Stage",
    "Jayanagar 4th Block", "Jayanagar 9th Block", "JP Nagar 7th Phase",
    "Banashankari 2nd Stage", "Banashankari 3rd Stage", "Basavanagudi Bull Temple Road",
    "Rajajinagar 1st Block", "Rajajinagar Industrial Estate",
    "Malleshwaram 8th Cross", "Sampige Road", "Sadashivanagar",
    "Sankey Road", "Mekhri Circle", "Hebbal Flyover",
    "Yelahanka New Town", "Yelahanka Old Town", "Doddaballapur Road",
    "Whitefield Main Road", "ITPL Road", "Varthur Road", "Sarjapur Road",
    "Outer Ring Road Marathahalli", "Brookefield", "Kundalahalli",
    "Mahadevapura", "KR Puram Bridge", "Tin Factory", "Hoodi",
    "Bellandur", "Ecospace", "Silk Board Junction", "Madiwala Market",
    "Electronic City Phase 1", "Electronic City Phase 2", "Hosur Road",
    "Bannerghatta Road", "IIM Bengaluru", "Arekere", "Wilson Garden",
    "Shivajinagar Bus Stand", "Russell Market", "Frazer Town", "Cox Town",
    "Cooke Town", "Pulakeshi Nagar", "Banaswadi", "HRBR Layout",
    "Kammanahalli", "Kalyan Nagar", "Hennur Cross", "Thanisandra",
    "Manyata Tech Park", "Nagawara", "RT Nagar", "Sanjay Nagar",
    "Yeshwantpur Circle", "Mathikere", "MS Ramaiah Road", "Vijayanagar",
    "Chord Road", "Magadi Road", "Majestic", "KR Market", "Chickpet",
    "Cottonpet", "Avenue Road",
]

LOCALITIES_BY_DISTRICT = {
    "Mysuru": ["Devaraja Mohalla", "Lakshmipuram", "Vijayanagar 1st Stage",
               "Saraswathipuram", "Kuvempunagar", "Hebbal Industrial Area",
               "Chamundi Hill Road", "Sayyaji Rao Road"],
    "Dharwad": ["Vidyanagar", "Saptapur", "Malmaddi", "Jubilee Circle",
                "Court Circle", "Keshwapur", "Gokul Road"],
    "Dakshina Kannada": ["Hampankatta", "Bunder", "Kankanady", "Bejai",
                         "Pandeshwar", "Bunts Hostel", "Lalbagh Mangaluru"],
    "Udupi": ["Service Bus Stand", "Krishna Temple Road", "Diana Circle",
              "Manipal", "Eshwar Nagar"],
    "Belagavi": ["Khade Bazar", "Camp", "Tilakwadi", "Shahapur", "Vadagaon",
                 "Goaves"],
    "Kalaburagi": ["Station Bazar", "Brahmapur", "Mehboob Nagar",
                   "Jagat Circle", "Sedam Road"],
    "Ballari": ["Cowl Bazar", "Gandhi Nagar", "Bapuji Nagar", "Anantapur Road"],
    "Vijayanagara": ["Hospet Bus Stand", "Hampi Road", "Mariyammanahalli"],
    "Davanagere": ["P.J. Extension", "MCC A Block", "Vidyanagar"],
    "Shivamogga": ["Gandhi Bazar", "Vinoba Nagar", "Sahyadri College Road"],
    "Tumakuru": ["BH Road", "Sira Gate", "MG Road Tumakuru"],
    "Hassan": ["BM Road", "KR Puram Hassan", "Salagame Road"],
    "Mandya": ["Gandhi Bhavan Road", "VV Road", "Subhash Nagar"],
    "Chitradurga": ["Holalkere Road", "Fort Area", "Medehalli"],
    "Raichur": ["Station Road", "LBS Nagar", "Gunj Road"],
    "Bidar": ["Old City", "New Bidar", "Gandhi Gunj"],
    "Bengaluru Rural": ["Devanahalli Town", "Hoskote", "Nelamangala",
                        "Doddaballapur"],
}

# IPC sections by crime type.  Mix of code numbers and short descriptions.
IPC_SECTIONS_BY_CRIME = {
    "vehicle_theft": [["379", "411"], ["379"], ["379", "120B"]],
    "chain_snatching": [["356", "379"], ["392"], ["356", "379", "34"]],
    "burglary": [["454", "457", "380"], ["457", "380"], ["380", "457", "34"]],
    "robbery": [["392", "397"], ["392"], ["392", "34"], ["395"]],
    "fraud": [["420", "406"], ["420"], ["406", "420", "120B"],
              ["420", "468", "471"]],
    "assault": [["323", "324"], ["323", "504", "506"], ["325", "326"]],
    "kidnapping": [["363", "365"], ["366"], ["364A"]],
    "narcotics": [["NDPS 20", "NDPS 22"], ["NDPS 8(c)", "NDPS 20"],
                  ["NDPS 27A"]],
    "cybercrime": [["IT Act 66C", "IT Act 66D", "420"],
                   ["IT Act 66D", "419", "420"],
                   ["IT Act 67", "354A"]],
    "missing_person": [["Missing - CrPC 174"], ["Missing"]],
    "accident": [["279", "337"], ["279", "338"], ["279", "304A"]],
    "public_nuisance": [["268", "290"], ["283", "290"], ["188"]],
    "domestic_violence": [["498A", "323"], ["498A", "506"],
                          ["498A", "323", "504", "DV Act"]],
    "murder": [["302"], ["302", "201"], ["302", "120B", "34"]],
    "attempt_to_murder": [["307"], ["307", "120B"], ["307", "324", "34"]],
}

# Realistic crime distribution weights (sum doesn't need to be 1).
CRIME_WEIGHTS = {
    "vehicle_theft": 18,
    "chain_snatching": 6,
    "burglary": 10,
    "robbery": 5,
    "fraud": 12,
    "assault": 10,
    "kidnapping": 1.5,
    "narcotics": 3,
    "cybercrime": 14,
    "missing_person": 6,
    "accident": 8,
    "public_nuisance": 4,
    "domestic_violence": 6,
    "murder": 0.4,
    "attempt_to_murder": 1.1,
}

# Time of day buckets (start hour, end hour exclusive) and weights per crime.
TIME_PATTERNS = {
    # mostly night / late evening
    "vehicle_theft": [(22, 30, 5), (18, 22, 3), (0, 6, 4), (6, 18, 1)],
    "burglary":     [(0, 6, 5), (22, 24, 3), (12, 18, 1), (6, 12, 1)],
    "chain_snatching": [(6, 9, 4), (18, 21, 4), (9, 18, 2), (21, 30, 1)],
    "robbery":      [(20, 30, 4), (18, 20, 3), (6, 18, 2)],
    # mostly day
    "fraud":        [(10, 18, 6), (18, 22, 2), (22, 30, 1)],
    "cybercrime":   [(9, 21, 6), (21, 30, 2), (0, 9, 1)],
    "public_nuisance": [(18, 24, 4), (12, 18, 3), (0, 12, 2)],
    # mixed
    "assault":      [(18, 24, 4), (12, 18, 3), (0, 12, 2)],
    "kidnapping":   [(15, 21, 3), (6, 15, 3), (21, 30, 2)],
    "narcotics":    [(20, 30, 4), (16, 20, 3), (0, 16, 2)],
    "missing_person": [(6, 22, 4), (22, 30, 1)],
    "accident":     [(6, 11, 4), (17, 22, 4), (22, 30, 2), (0, 6, 1)],
    "domestic_violence": [(20, 30, 5), (16, 20, 2), (0, 16, 1)],
    "murder":       [(20, 30, 4), (0, 6, 3), (6, 20, 2)],
    "attempt_to_murder": [(20, 30, 4), (0, 6, 3), (6, 20, 2)],
}

POLICE_RANKS = ["PSI", "SI", "Inspector", "Inspector", "PSI", "SI"]

# Modus operandi templates per crime.  English text.
MODUS_OPERANDI = {
    "vehicle_theft": [
        "Two-wheeler parked outside residence was stolen during night hours; lock was found broken.",
        "Accused broke handle lock of motorcycle parked near commercial area and fled.",
        "Car parked at apartment basement was stolen; CCTV shows two persons on bike scouting earlier.",
        "Vehicle was taken from market parking using a duplicate key while owner was shopping.",
    ],
    "chain_snatching": [
        "Two persons on a motorcycle snatched gold chain of complainant who was walking on roadside.",
        "Accused approached on bike pretending to ask directions and snatched mangalsutra before fleeing.",
        "Gold chain snatched in early morning walk; accused fled towards main road on a pulsar bike.",
    ],
    "burglary": [
        "Accused broke rear door grill of locked house during family vacation and stole gold and cash.",
        "Burglars entered through ventilation shaft of first floor flat; stole jewellery and laptop.",
        "House lock broken during day time when occupants were away at work; valuables missing.",
    ],
    "robbery": [
        "Three persons with knife threatened complainant near ATM and took cash and mobile phone.",
        "Armed gang stopped vehicle at deserted stretch, assaulted driver and robbed cash.",
        "Accused with machete robbed shop in late evening and fled on a Bullet motorcycle.",
    ],
    "fraud": [
        "Complainant received call posing as bank officer; OTP shared and amount debited from account.",
        "Accused promised job in Gulf, collected money from multiple victims and absconded.",
        "Real estate plot sold to multiple buyers using forged documents.",
        "Investment scheme promising 30 percent returns collapsed after collecting deposits.",
    ],
    "assault": [
        "Quarrel over parking dispute escalated; accused assaulted complainant with wooden stick.",
        "Group of accused beat up complainant after verbal altercation in front of shop.",
        "Old enmity led to assault near bus stop; complainant sustained injuries on head.",
    ],
    "kidnapping": [
        "Minor child of complainant was missing from school area; suspicion on known person.",
        "Accused lured victim under pretext of job offer and confined her at undisclosed location.",
        "Ransom call received after businessman went missing while returning from office.",
    ],
    "narcotics": [
        "Accused was found in possession of ganja during routine vehicle check at check post.",
        "Raid conducted on tip-off at rented house; MDMA tablets and weighing scale seized.",
        "Peddler supplying ganja to college students apprehended near hostel area.",
    ],
    "cybercrime": [
        "Complainant lost money after clicking phishing link sent over WhatsApp claiming KYC update.",
        "Fake matrimony profile used to extort money from complainant on pretext of emergency.",
        "Accused hacked complainant's social media account and demanded ransom to restore access.",
        "Online shopping site delivered empty box after payment of advance for mobile phone.",
    ],
    "missing_person": [
        "Complainant's family member left home without informing and has not returned.",
        "Elderly father suffering from dementia went missing from neighbourhood park.",
        "Teenager missing from college since morning; mobile phone switched off.",
    ],
    "accident": [
        "Speeding car hit two-wheeler from rear at signal; rider sustained grievous injuries.",
        "Lorry overturned on highway crushing bystander; driver fled the spot.",
        "Auto rickshaw collided with bus near junction; passengers injured.",
    ],
    "public_nuisance": [
        "Loud music and rowdy behaviour from group disturbing neighbourhood late at night.",
        "Garbage dumping in public road creating health hazard despite repeated warnings.",
        "Unauthorized assembly causing traffic blockage on arterial road.",
    ],
    "domestic_violence": [
        "Complainant alleged harassment by husband and in-laws over dowry demand.",
        "Repeated physical and mental cruelty by spouse leading to police complaint.",
        "Threats and abuse from family members after refusal to bring additional dowry.",
    ],
    "murder": [
        "Body of victim found with stab injuries in vacant plot; old enmity suspected.",
        "Property dispute escalated; accused attacked victim with sharp weapon causing death.",
        "Victim shot dead by unknown assailants near home; investigation underway.",
    ],
    "attempt_to_murder": [
        "Accused attacked complainant with machete during quarrel; victim grievously injured.",
        "Hired assailants attacked businessman; victim survived after emergency surgery.",
        "Family dispute turned violent; accused stabbed brother who is in critical condition.",
    ],
}

# 50 Kannada narrative templates keyed by crime + variant.
# Plausible Kannada using real words; not literal translations.
KANNADA_TEMPLATES = {
    "vehicle_theft": [
        "ರಾತ್ರಿ ವೇಳೆ ದೂರುದಾರರ ದ್ವಿಚಕ್ರ ವಾಹನವನ್ನು ಅಪರಿಚಿತ ಕಳ್ಳರು ಕದ್ದೊಯ್ದಿದ್ದಾರೆ.",
        "ಆರೋಪಿಗಳು ಬೈಕ್‌ನ ಲಾಕ್ ಮುರಿದು ವಾಹನವನ್ನು ಕಳ್ಳತನ ಮಾಡಿ ಪರಾರಿಯಾಗಿದ್ದಾರೆ.",
        "ಅಪಾರ್ಟ್‌ಮೆಂಟ್‌ನ ಪಾರ್ಕಿಂಗ್‌ನಲ್ಲಿ ನಿಲ್ಲಿಸಿದ್ದ ಕಾರನ್ನು ಕಳ್ಳರು ಕದ್ದಿದ್ದಾರೆ; ಸಿಸಿಟಿವಿ ದೃಶ್ಯಗಳಿವೆ.",
        "ಮಾರುಕಟ್ಟೆ ಬಳಿ ನಿಲ್ಲಿಸಿದ್ದ ವಾಹನವನ್ನು ನಕಲಿ ಕೀ ಬಳಸಿ ಕಳ್ಳತನ ಮಾಡಲಾಗಿದೆ.",
    ],
    "chain_snatching": [
        "ಬೈಕ್‌ನಲ್ಲಿ ಬಂದ ಇಬ್ಬರು ಆರೋಪಿಗಳು ದೂರುದಾರರ ಚಿನ್ನದ ಸರವನ್ನು ಕಿತ್ತುಕೊಂಡು ಪರಾರಿಯಾಗಿದ್ದಾರೆ.",
        "ದಾರಿ ಕೇಳುವ ನೆಪದಲ್ಲಿ ಬಂದ ಆರೋಪಿಗಳು ಮಹಿಳೆಯ ಮಾಂಗಲ್ಯ ಸರವನ್ನು ಕಿತ್ತುಕೊಂಡಿದ್ದಾರೆ.",
        "ಬೆಳಗ್ಗೆ ವಾಯುವಿಹಾರಕ್ಕೆ ತೆರಳಿದ್ದ ಮಹಿಳೆಯ ಚಿನ್ನದ ಸರವನ್ನು ಸರಗಳ್ಳರು ಕಿತ್ತೊಯ್ದಿದ್ದಾರೆ.",
    ],
    "burglary": [
        "ಕುಟುಂಬ ಊರಿನಿಂದ ಹೊರಗಿದ್ದಾಗ ಮನೆಯ ಬಾಗಿಲು ಮುರಿದು ಚಿನ್ನ ಮತ್ತು ಹಣ ಕಳ್ಳತನವಾಗಿದೆ.",
        "ಮೊದಲ ಮಹಡಿ ಫ್ಲಾಟ್‌ನ ಕಿಟಕಿ ಮೂಲಕ ಒಳಗೆ ಬಂದ ಕಳ್ಳರು ಆಭರಣ ಮತ್ತು ಲ್ಯಾಪ್‌ಟಾಪ್ ಕದ್ದಿದ್ದಾರೆ.",
        "ಹಗಲು ವೇಳೆ ಮನೆಯವರು ಇಲ್ಲದಾಗ ಬೀಗ ಮುರಿದು ಬೆಲೆಬಾಳುವ ವಸ್ತುಗಳನ್ನು ಕಳವು ಮಾಡಲಾಗಿದೆ.",
    ],
    "robbery": [
        "ಎಟಿಎಂ ಬಳಿ ಚಾಕು ತೋರಿಸಿ ಬೆದರಿಸಿದ ಆರೋಪಿಗಳು ಹಣ ಮತ್ತು ಮೊಬೈಲ್ ಕಸಿದುಕೊಂಡಿದ್ದಾರೆ.",
        "ಶಸ್ತ್ರಸಜ್ಜಿತ ತಂಡ ನಿರ್ಜನ ಪ್ರದೇಶದಲ್ಲಿ ವಾಹನ ತಡೆದು ಚಾಲಕನ ಮೇಲೆ ಹಲ್ಲೆ ನಡೆಸಿ ಹಣ ದರೋಡೆ ಮಾಡಿದೆ.",
        "ಮಚ್ಚು ಹಿಡಿದ ಆರೋಪಿಗಳು ಅಂಗಡಿಗೆ ನುಗ್ಗಿ ದರೋಡೆ ಮಾಡಿ ಬೈಕ್‌ನಲ್ಲಿ ಪರಾರಿಯಾಗಿದ್ದಾರೆ.",
    ],
    "fraud": [
        "ಬ್ಯಾಂಕ್ ಅಧಿಕಾರಿ ಎಂದು ಹೇಳಿಕೊಂಡು ಕರೆ ಮಾಡಿದ ಆರೋಪಿಗಳು ಒಟಿಪಿ ಪಡೆದು ಖಾತೆಯಿಂದ ಹಣ ಎಗರಿಸಿದ್ದಾರೆ.",
        "ಗಲ್ಫ್ ಉದ್ಯೋಗದ ಆಮಿಷ ತೋರಿಸಿ ಹಲವರಿಂದ ಹಣ ಸಂಗ್ರಹಿಸಿ ಆರೋಪಿಗಳು ಪರಾರಿಯಾಗಿದ್ದಾರೆ.",
        "ಒಂದೇ ನಿವೇಶನವನ್ನು ನಕಲಿ ದಾಖಲೆಗಳಿಂದ ಹಲವರಿಗೆ ಮಾರಿ ವಂಚಿಸಲಾಗಿದೆ.",
        "ಹೆಚ್ಚಿನ ಬಡ್ಡಿಯ ಆಮಿಷ ತೋರಿಸಿದ ಹೂಡಿಕೆ ಯೋಜನೆ ಮುಚ್ಚಿ ಠೇವಣಿದಾರರು ವಂಚಿತರಾಗಿದ್ದಾರೆ.",
    ],
    "assault": [
        "ಪಾರ್ಕಿಂಗ್ ವಿಷಯವಾಗಿ ಜಗಳವಾಡಿದ ಆರೋಪಿಗಳು ದೂರುದಾರರ ಮೇಲೆ ದೊಣ್ಣೆಯಿಂದ ಹಲ್ಲೆ ನಡೆಸಿದ್ದಾರೆ.",
        "ಬಾಯಿಜಗಳದ ನಂತರ ಗುಂಪು ಸೇರಿ ದೂರುದಾರನ ಮೇಲೆ ಹಲ್ಲೆ ನಡೆಸಿದ್ದಾರೆ.",
        "ಹಳೆಯ ದ್ವೇಷದಿಂದ ಬಸ್ ನಿಲ್ದಾಣದ ಬಳಿ ಹಲ್ಲೆ ನಡೆದಿದ್ದು ಗಾಯಗೊಂಡಿದ್ದಾರೆ.",
    ],
    "kidnapping": [
        "ಶಾಲೆ ಸಮೀಪದಿಂದ ದೂರುದಾರರ ಅಪ್ರಾಪ್ತ ಮಗು ಕಾಣೆಯಾಗಿದ್ದು ಪರಿಚಿತರ ಮೇಲೆ ಸಂಶಯವಿದೆ.",
        "ಉದ್ಯೋಗದ ಆಮಿಷ ತೋರಿಸಿ ಆರೋಪಿಗಳು ಯುವತಿಯನ್ನು ಕರೆದೊಯ್ದು ಬಂಧಿಸಿಟ್ಟಿದ್ದಾರೆ.",
        "ಕಚೇರಿಯಿಂದ ಮನೆಗೆ ಮರಳುತ್ತಿದ್ದ ಉದ್ಯಮಿ ಕಾಣೆಯಾಗಿದ್ದು ಸುಲಿಗೆಯ ಕರೆ ಬಂದಿದೆ.",
    ],
    "narcotics": [
        "ಚೆಕ್ ಪೋಸ್ಟ್‌ನಲ್ಲಿ ವಾಹನ ಪರಿಶೀಲನೆ ವೇಳೆ ಆರೋಪಿ ಗಾಂಜಾ ಸಮೇತ ಸಿಕ್ಕಿಬಿದ್ದಿದ್ದಾರೆ.",
        "ಮಾಹಿತಿ ಆಧರಿಸಿ ನಡೆಸಿದ ದಾಳಿಯಲ್ಲಿ ಎಂಡಿಎಂಎ ಮಾತ್ರೆಗಳು ಮತ್ತು ತೂಕದ ಯಂತ್ರ ವಶಪಡಿಸಲಾಗಿದೆ.",
        "ಕಾಲೇಜು ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಗಾಂಜಾ ಪೂರೈಸುತ್ತಿದ್ದ ಆರೋಪಿಯನ್ನು ಬಂಧಿಸಲಾಗಿದೆ.",
    ],
    "cybercrime": [
        "ಕೆವೈಸಿ ಪರಿಷ್ಕರಣೆಯ ನೆಪದಲ್ಲಿ ಬಂದ ಫಿಶಿಂಗ್ ಲಿಂಕ್‌ನಿಂದ ದೂರುದಾರ ಹಣ ಕಳೆದುಕೊಂಡಿದ್ದಾರೆ.",
        "ನಕಲಿ ವಿವಾಹ ತಾಣದ ಪ್ರೊಫೈಲ್ ಬಳಸಿ ತುರ್ತು ನೆಪವೊಡ್ಡಿ ಹಣ ಸುಲಿಗೆ ಮಾಡಲಾಗಿದೆ.",
        "ದೂರುದಾರರ ಸಾಮಾಜಿಕ ಜಾಲತಾಣ ಖಾತೆ ಹ್ಯಾಕ್ ಮಾಡಿ ಪುನಃ ಸಕ್ರಿಯಗೊಳಿಸಲು ಆರೋಪಿ ಹಣ ಬೇಡಿಕೆ ಇಟ್ಟಿದ್ದಾರೆ.",
        "ಆನ್‌ಲೈನ್ ಶಾಪಿಂಗ್ ತಾಣದಲ್ಲಿ ಮುಂಗಡ ಪಾವತಿಸಿದ ಮೊಬೈಲ್ ಬದಲು ಖಾಲಿ ಬಾಕ್ಸ್ ತಲುಪಿಸಲಾಗಿದೆ.",
    ],
    "missing_person": [
        "ದೂರುದಾರರ ಕುಟುಂಬ ಸದಸ್ಯರು ಯಾವುದೇ ಮಾಹಿತಿ ನೀಡದೆ ಮನೆ ಬಿಟ್ಟು ಹೋಗಿದ್ದು ಇನ್ನೂ ಮರಳಿಲ್ಲ.",
        "ಮರೆವಿನ ರೋಗದಿಂದ ಬಳಲುತ್ತಿರುವ ವೃದ್ಧ ತಂದೆ ಉದ್ಯಾನವನದಿಂದ ಕಾಣೆಯಾಗಿದ್ದಾರೆ.",
        "ಕಾಲೇಜಿಗೆ ಹೋದ ಯುವಕ ಮನೆಗೆ ಮರಳಿಲ್ಲ; ಮೊಬೈಲ್ ಸ್ವಿಚ್ ಆಫ್ ಆಗಿದೆ.",
    ],
    "accident": [
        "ವೇಗವಾಗಿ ಬಂದ ಕಾರು ಸಿಗ್ನಲ್ ಬಳಿ ದ್ವಿಚಕ್ರ ವಾಹನಕ್ಕೆ ಡಿಕ್ಕಿ ಹೊಡೆದು ಸವಾರ ಗಂಭೀರವಾಗಿ ಗಾಯಗೊಂಡಿದ್ದಾರೆ.",
        "ಹೆದ್ದಾರಿಯಲ್ಲಿ ಲಾರಿ ಪಲ್ಟಿಯಾಗಿ ಪಾದಚಾರಿಯ ಮೇಲೆ ಬಿದ್ದಿದ್ದು ಚಾಲಕ ಸ್ಥಳದಿಂದ ಪರಾರಿಯಾಗಿದ್ದಾನೆ.",
        "ಆಟೋ ಮತ್ತು ಬಸ್ ನಡುವೆ ಡಿಕ್ಕಿಯಾಗಿ ಪ್ರಯಾಣಿಕರು ಗಾಯಗೊಂಡಿದ್ದಾರೆ.",
    ],
    "public_nuisance": [
        "ರಾತ್ರಿ ವೇಳೆ ಜೋರು ಸಂಗೀತ ಮತ್ತು ಗದ್ದಲದಿಂದ ನೆರೆಹೊರೆಯವರಿಗೆ ತೊಂದರೆಯಾಗಿದೆ.",
        "ಸಾರ್ವಜನಿಕ ರಸ್ತೆಯಲ್ಲಿ ಕಸ ಎಸೆಯುತ್ತಿರುವುದರಿಂದ ಆರೋಗ್ಯ ಸಮಸ್ಯೆ ತಲೆದೋರಿದೆ.",
        "ಅನಧಿಕೃತ ಸಭೆಯಿಂದ ಪ್ರಮುಖ ರಸ್ತೆಯಲ್ಲಿ ಸಂಚಾರ ಸ್ತಬ್ಧವಾಗಿತ್ತು.",
    ],
    "domestic_violence": [
        "ವರದಕ್ಷಿಣೆ ಬೇಡಿಕೆಯ ಹಿನ್ನೆಲೆಯಲ್ಲಿ ಪತಿ ಮತ್ತು ಅತ್ತೆಮಾವಂದಿರಿಂದ ಕಿರುಕುಳ ಎಂದು ದೂರುದಾರ ಆರೋಪಿಸಿದ್ದಾರೆ.",
        "ಪತಿಯಿಂದ ಪದೇಪದೇ ದೈಹಿಕ ಹಾಗೂ ಮಾನಸಿಕ ಹಿಂಸೆ ನೀಡಿರುವ ಬಗ್ಗೆ ಪೊಲೀಸರಿಗೆ ದೂರು ನೀಡಲಾಗಿದೆ.",
        "ಹೆಚ್ಚುವರಿ ವರದಕ್ಷಿಣೆ ತರಲು ನಿರಾಕರಿಸಿದ ನಂತರ ಮನೆಯವರಿಂದ ಬೆದರಿಕೆ ಮತ್ತು ನಿಂದನೆ ಎದುರಾಗಿದೆ.",
    ],
    "murder": [
        "ಖಾಲಿ ನಿವೇಶನದಲ್ಲಿ ಚೂರಿ ಗಾಯಗಳೊಂದಿಗೆ ಶವ ಪತ್ತೆಯಾಗಿದ್ದು ಹಳೆಯ ದ್ವೇಷ ಸಂಶಯವಿದೆ.",
        "ಆಸ್ತಿ ವಿವಾದ ಉಲ್ಬಣಗೊಂಡು ಆರೋಪಿ ಹರಿತವಾದ ಶಸ್ತ್ರದಿಂದ ಹಲ್ಲೆ ನಡೆಸಿದ್ದು ಸಾವು ಸಂಭವಿಸಿದೆ.",
        "ಮನೆಯ ಬಳಿ ಅಪರಿಚಿತ ದುಷ್ಕರ್ಮಿಗಳಿಂದ ಗುಂಡಿನ ದಾಳಿಗೆ ಬಲಿಯಾಗಿದ್ದು ತನಿಖೆ ನಡೆಯುತ್ತಿದೆ.",
    ],
    "attempt_to_murder": [
        "ಜಗಳದ ವೇಳೆ ಆರೋಪಿ ಮಚ್ಚಿನಿಂದ ಹಲ್ಲೆ ನಡೆಸಿದ್ದು ಸಂತ್ರಸ್ತ ಗಂಭೀರ ಗಾಯಗೊಂಡಿದ್ದಾರೆ.",
        "ಬಾಡಿಗೆಗೆ ಪಡೆದ ದುಷ್ಕರ್ಮಿಗಳಿಂದ ಉದ್ಯಮಿಯ ಮೇಲೆ ಹಲ್ಲೆ ನಡೆದಿದ್ದು ತುರ್ತು ಶಸ್ತ್ರಚಿಕಿತ್ಸೆಯ ನಂತರ ಬಚಾವಾಗಿದ್ದಾರೆ.",
        "ಕುಟುಂಬ ಕಲಹ ಹಿಂಸಾಚಾರವಾಗಿ ಪರಿವರ್ತನೆಗೊಂಡು ಸಹೋದರನ ಮೇಲೆ ಚೂರಿ ಇರಿತ ನಡೆಸಿದ್ದು ಗಂಭೀರ ಸ್ಥಿತಿಯಲ್ಲಿದ್ದಾರೆ.",
    ],
}

STATUS_WEIGHTS = {
    "under_investigation": 55,
    "chargesheet_filed": 25,
    "closed": 15,
    "transferred": 5,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def weighted_choice(rng: random.Random, mapping: Dict[str, float]) -> str:
    keys = list(mapping.keys())
    weights = list(mapping.values())
    return rng.choices(keys, weights=weights, k=1)[0]


def random_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    delta = end - start
    secs = rng.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=secs)


def random_time_for_crime(rng: random.Random, crime: str) -> Tuple[int, int, int]:
    buckets = TIME_PATTERNS.get(crime, [(0, 24, 1)])
    chosen = rng.choices(buckets, weights=[b[2] for b in buckets], k=1)[0]
    start_h, end_h, _ = chosen
    hour_raw = rng.randint(start_h, end_h - 1)
    hour = hour_raw % 24
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return hour, minute, second


def jitter_coord(rng: random.Random, lat: float, lng: float,
                 max_km: float = 10.0) -> Tuple[float, float]:
    # ~111 km per degree latitude.
    max_deg = max_km / 111.0
    dlat = rng.uniform(-max_deg, max_deg)
    # longitude scales with cos(lat).
    import math
    dlng = rng.uniform(-max_deg, max_deg) / max(0.2, math.cos(math.radians(lat)))
    return round(lat + dlat, 6), round(lng + dlng, 6)


def mask_phone(rng: random.Random) -> str:
    first = rng.choice(["6", "7", "8", "9"])
    rest = "".join(str(rng.randint(0, 9)) for _ in range(9))
    full = first + rest
    return full[:2] + "XXXXXX" + full[-2:]


def gen_name(rng: random.Random, gender: str) -> str:
    if gender == "M":
        first = rng.choice(FIRST_NAMES_MALE)
    else:
        first = rng.choice(FIRST_NAMES_FEMALE)
    last = rng.choice(SURNAMES)
    # Sikh women historically take "Kaur".
    if last == "Kaur" and gender == "M":
        last = "Singh"
    if last == "Singh" and gender == "F":
        last = "Kaur"
    return f"{first} {last}"


def _ord_suffix(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def gen_address(rng: random.Random, faker: Faker, locality: str,
                district: str) -> str:
    door = rng.randint(1, 999)
    cross = rng.randint(1, 20)
    main = rng.randint(1, 30)
    pin = rng.choice([560001, 560002, 560004, 560008, 560010, 560011,
                      560017, 560034, 560037, 560038, 560040, 560043,
                      560066, 560076, 560078, 560085, 560095, 560100,
                      570001, 570011, 575001, 580001, 590001, 585101,
                      583101, 577001, 572101, 573201, 571401, 577501])
    return (f"#{door}, {cross}{_ord_suffix(cross)} Cross, "
            f"{main}{_ord_suffix(main)} Main, {locality}, {district} - {pin}")


def gen_fir_no(rng: random.Random, station_name: str, year: int,
               counter: int) -> str:
    # Short station code from name; pad short ones with letters from first word.
    base = station_name.replace(" Police Station", "").strip()
    words = [w for w in base.split() if w and w[0].isalpha()]
    if not words:
        code = "KAR"
    elif len(words) >= 3:
        code = "".join(w[0] for w in words[:4]).upper()
    else:
        # 1-2 words: take 3-4 letters from the first word + initials.
        first = words[0]
        code = first[:3].upper()
        if len(words) > 1:
            code += words[1][0].upper()
    code = code[:4] or "KAR"
    return f"{code}/{year}/{counter:05d}"


def gen_complainant(rng: random.Random, faker: Faker, locality: str,
                    district: str) -> Dict[str, Any]:
    gender = rng.choices(["M", "F"], weights=[60, 40], k=1)[0]
    age = max(18, int(rng.gauss(38, 12)))
    age = min(age, 85)
    return {
        "name": gen_name(rng, gender),
        "age": age,
        "gender": gender,
        "phone": mask_phone(rng),
        "address": gen_address(rng, faker, locality, district),
    }


def gen_accused(rng: random.Random, crime: str) -> List[Dict[str, Any]]:
    # Number of accused varies by crime type.
    if crime in {"robbery", "burglary", "murder", "attempt_to_murder"}:
        n = rng.choices([1, 2, 3, 4], weights=[25, 40, 25, 10], k=1)[0]
    elif crime in {"chain_snatching", "narcotics"}:
        n = rng.choices([1, 2, 3], weights=[40, 45, 15], k=1)[0]
    elif crime in {"missing_person", "public_nuisance"}:
        n = rng.choices([0, 1], weights=[70, 30], k=1)[0]
    else:
        n = rng.choices([0, 1, 2], weights=[20, 60, 20], k=1)[0]

    accused = []
    for _ in range(n):
        if rng.random() < 0.4:
            accused.append({
                "name": "Unknown",
                "age": None,
                "gender": "U",
                "status": "unknown",
            })
        else:
            gender = rng.choices(["M", "F"], weights=[88, 12], k=1)[0]
            age = max(16, int(rng.gauss(30, 9)))
            age = min(age, 65)
            status = rng.choices(
                ["arrested", "absconding", "on_bail", "unknown"],
                weights=[40, 30, 20, 10], k=1)[0]
            accused.append({
                "name": gen_name(rng, gender),
                "age": age,
                "gender": gender,
                "status": status,
            })
    return accused


def gen_victims(rng: random.Random, complainant: Dict[str, Any],
                crime: str) -> List[Dict[str, Any]]:
    # Often complainant == victim.
    if crime in {"public_nuisance", "narcotics"}:
        return []
    if crime in {"missing_person", "kidnapping"}:
        # Victim is separate from complainant.
        gender = rng.choice(["M", "F"])
        age = rng.randint(8, 60) if crime == "missing_person" else rng.randint(6, 35)
        return [{
            "name": gen_name(rng, gender),
            "age": age,
            "gender": gender,
            "relation_to_complainant": rng.choice(
                ["son", "daughter", "spouse", "brother", "sister",
                 "father", "mother", "relative"]),
        }]
    if rng.random() < 0.78:
        return [{
            "name": complainant["name"],
            "age": complainant["age"],
            "gender": complainant["gender"],
            "relation_to_complainant": "self",
        }]
    gender = rng.choice(["M", "F"])
    age = max(15, int(rng.gauss(35, 12)))
    return [{
        "name": gen_name(rng, gender),
        "age": min(age, 80),
        "gender": gender,
        "relation_to_complainant": rng.choice(
            ["spouse", "child", "sibling", "parent", "friend", "neighbour"]),
    }]


def gen_io(rng: random.Random) -> Dict[str, Any]:
    rank = rng.choice(POLICE_RANKS)
    gender = rng.choices(["M", "F"], weights=[85, 15], k=1)[0]
    return {
        "name": gen_name(rng, gender),
        "rank": rank,
        "badge_no": f"KSP{rng.randint(10000, 99999)}",
    }


def build_narrative(rng: random.Random, crime: str, location_text: str,
                    complainant: Dict[str, Any],
                    accused: List[Dict[str, Any]]) -> Tuple[str, str]:
    mo_choices = MODUS_OPERANDI[crime]
    mo_en = rng.choice(mo_choices)
    kan_choices = KANNADA_TEMPLATES[crime]
    mo_kn = rng.choice(kan_choices)

    # Narrative summary - English.
    accused_part = ""
    if accused:
        names = [a["name"] for a in accused if a["name"] != "Unknown"]
        if names:
            accused_part = f" Accused identified as {names[0]}" + (
                f" and {len(names) - 1} other(s)." if len(names) > 1 else "."
            )
        else:
            accused_part = " Accused are yet to be identified."
    else:
        accused_part = ""

    narrative_en = (
        f"Complainant {complainant['name']} (age {complainant['age']}) reported"
        f" the incident at {location_text}. {mo_en}{accused_part}"
    )

    # Narrative summary - Kannada.
    narrative_kn = (
        f"ದೂರುದಾರ {complainant['name']} ಅವರು {location_text} ಬಳಿ ನಡೆದ"
        f" ಘಟನೆಯ ಬಗ್ಗೆ ದೂರು ನೀಡಿದ್ದಾರೆ. {mo_kn}"
    )
    if accused:
        named = [a["name"] for a in accused if a["name"] != "Unknown"]
        if named:
            narrative_kn += f" ಆರೋಪಿ {named[0]} ವಿರುದ್ಧ ಪ್ರಕರಣ ದಾಖಲಾಗಿದೆ."
        else:
            narrative_kn += " ಆರೋಪಿಗಳನ್ನು ಗುರುತಿಸಿಲ್ಲ."
    return narrative_en, narrative_kn, mo_en, mo_kn


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_one(rng: random.Random, faker: Faker, counter_by_station: Dict,
                 prior_records: List[Dict[str, Any]],
                 link_pool: List[Tuple[str, List[Dict[str, Any]]]]
                 ) -> Dict[str, Any]:
    # Bengaluru weighting: 70% of stations from Bengaluru Urban.
    blr_stations = [s for s in POLICE_STATIONS if s[1] == "Bengaluru Urban"]
    if rng.random() < 0.70:
        station = rng.choice(blr_stations)
    else:
        station = rng.choice(POLICE_STATIONS)

    station_name, district, s_lat, s_lng = station

    if district == "Bengaluru Urban":
        locality = rng.choice(BENGALURU_LOCALITIES)
    else:
        locality = rng.choice(
            LOCALITIES_BY_DISTRICT.get(district, BENGALURU_LOCALITIES)
        )

    crime = weighted_choice(rng, CRIME_WEIGHTS)
    ipc = rng.choice(IPC_SECTIONS_BY_CRIME[crime])

    date_dt_start = datetime(2022, 1, 1)
    date_dt_end = datetime(2025, 12, 31, 23, 59, 59)
    date_reg = random_date(rng, date_dt_start, date_dt_end)
    hour, minute, second = random_time_for_crime(rng, crime)
    date_reg = date_reg.replace(hour=hour, minute=minute, second=second)

    year = date_reg.year
    key = (station_name, year)
    counter_by_station[key] = counter_by_station.get(key, 0) + 1
    counter = counter_by_station[key]
    fir_no = gen_fir_no(rng, station_name, year, counter)

    location_lat, location_lng = jitter_coord(rng, s_lat, s_lng, max_km=10)

    complainant = gen_complainant(rng, faker, locality, district)

    # Linking: 5-10% chance to reuse accused from a prior linked-pool record.
    link_chance = 0.08
    accused: List[Dict[str, Any]]
    linked_to: List[str] = []
    if link_pool and rng.random() < link_chance:
        prior_fir, prior_accused = rng.choice(link_pool)
        # Reuse at least one accused.
        if prior_accused:
            accused = [dict(a) for a in prior_accused]
            linked_to = [prior_fir]
        else:
            accused = gen_accused(rng, crime)
    else:
        accused = gen_accused(rng, crime)
        # Eligible to seed the link pool if it has a named accused.
        if any(a["name"] != "Unknown" for a in accused):
            link_pool.append((fir_no, accused))
            # Cap pool size.
            if len(link_pool) > 2000:
                link_pool.pop(0)

    victims = gen_victims(rng, complainant, crime)
    io = gen_io(rng)
    status = weighted_choice(rng, STATUS_WEIGHTS)

    narrative_en, narrative_kn, mo_en, mo_kn = build_narrative(
        rng, crime, locality, complainant, accused
    )

    record = {
        "fir_no": fir_no,
        "station_name": station_name,
        "station_lat": s_lat,
        "station_lng": s_lng,
        "district": district,
        "date_registered": date_reg.strftime("%Y-%m-%d"),
        "time_registered": date_reg.strftime("%H:%M:%S"),
        "crime_type": crime,
        "ipc_sections": ipc,
        "location_lat": location_lat,
        "location_lng": location_lng,
        "location_text": locality,
        "complainant": complainant,
        "accused": accused,
        "victims": victims,
        "modus_operandi": mo_en,
        "modus_operandi_kannada": mo_kn,
        "investigating_officer": io,
        "status": status,
        "linked_fir_nos": linked_to,
        "narrative": narrative_en,
        "narrative_kannada": narrative_kn,
    }
    return record


def generate(count: int, output: str, sample_output: str, seed: int) -> int:
    rng = random.Random(seed)
    try:
        faker = Faker("en_IN")
    except Exception:
        faker = Faker()
    Faker.seed(seed)

    counter_by_station: Dict[Tuple[str, int], int] = {}
    link_pool: List[Tuple[str, List[Dict[str, Any]]]] = []
    prior_records: List[Dict[str, Any]] = []

    written = 0
    sample_records: List[Dict[str, Any]] = []
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output)) or ".",
                    exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            for i in range(count):
                try:
                    rec = generate_one(rng, faker, counter_by_station,
                                       prior_records, link_pool)
                except Exception as e:  # pragma: no cover
                    print(f"WARN: error on record {i}: {e}", file=sys.stderr)
                    traceback.print_exc()
                    break
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
                if len(sample_records) < 100:
                    sample_records.append(rec)
                if written % 10000 == 0:
                    print(f"  ... wrote {written:,} records", flush=True)
    except KeyboardInterrupt:
        print(f"\nInterrupted. Saved {written:,} records to {output}",
              file=sys.stderr)
    except Exception as e:
        print(f"ERROR after {written} records: {e}", file=sys.stderr)
        traceback.print_exc()

    # Write sample file.
    try:
        with open(sample_output, "w", encoding="utf-8") as f:
            for rec in sample_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"WARN: failed to write sample: {e}", file=sys.stderr)

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate synthetic Karnataka Police FIR records.")
    p.add_argument("--count", type=int, default=50000,
                   help="Number of FIR records to generate (default: 50000)")
    p.add_argument("--output", type=str, default="firs.jsonl",
                   help="Output JSONL file (default: firs.jsonl)")
    p.add_argument("--sample-output", type=str, default=None,
                   help="Sample JSONL output (default: <output>_sample.jsonl)")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for reproducibility (default: 42)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    sample_output = args.sample_output
    if sample_output is None:
        base, ext = os.path.splitext(args.output)
        sample_output = f"{base}_sample{ext or '.jsonl'}"

    print(f"Generating {args.count:,} FIR records -> {args.output}")
    print(f"Sample (first 100) -> {sample_output}")
    start = datetime.now()
    written = generate(args.count, args.output, sample_output, args.seed)
    elapsed = (datetime.now() - start).total_seconds()
    print(f"Done. Wrote {written:,} records in {elapsed:.1f}s "
          f"({written / max(elapsed, 0.001):,.0f} rec/s)")
    return 0 if written > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
