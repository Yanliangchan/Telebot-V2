import os

# =========================
# CHAT & TOPIC IDS
# =========================

# Instructors / IC Group (shared)
IC_GROUP_CHAT_ID = -1003592356953

# Admin user IDs (comma-separated) for restricted actions
ADMIN_IDS = list({
    905069574,  # Yanliang (owner)
    *(
        int(admin_id)
        for admin_id in os.getenv("ADMIN_IDS", "").split(",")
        if admin_id.strip()
    )
})

# Topics in IC Group
MOVEMENT_TOPIC_ID = 322
SFT_TOPIC_ID = 7
PARADE_STATE_TOPIC_ID = 3
GENERAL_TOPIC_ID = 4
CET_TOPIC_ID = 2

# Cadet Chat (CET)

CADET_CHAT_ID = -1003675767444
CADET_CET_TOPIC_ID = 5


# =========================
# MOVEMENT CONFIG
# =========================

LOCATIONS = [
    "DHA",
    "WINGLINE",
    "THROW TRASH",
    "OCS HQ",
    "STADIUM",
    "MEDICAL CENTRE",
    "AUDITORIUM",
    "EXAM HALL",
    "E-MART",
    "LIBRARY"
]

# =========================
# SFT CONFIG
# =========================

ACTIVITIES = [
    "Gym @ Wingline",
    "Running @ Yellow Cluster Parade Square",
    "Running @ DIS Wing Approved Route",
    "Frisbee @ Basketball court",
    "Basketball @ Basketball court",
    "Other ball @ Yellow Cluster Parade Square",
    "Badminton @ Basketball court"
]


# =========================
# PARADE STATE CONFIG
# =========================

# Order in which parade state sections appear
PARADE_STATE_SECTION_ORDER = [
    "MA",
    "RSI",
    "RSO",
    "MC",
    "OTHERS",
    "STATUSES",
    "PERMANENT_STATUS"
]

# Display names for each section
PARADE_STATE_SECTION_TITLES = {
    "MA": "MA",
    "RSI": "RSI",
    "RSO": "RSO",
    "MC": "MC",
    "OTHERS": "OTHERS",
    "STATUSES": "STATUSES",
    "PERMANENT_STATUS": "PERMANENT STATUS"
}

PARADE_STATE_FIELDS = {
    "MA": [
        ("appointment_type", "NAME"),
        ("location", "LOCATION"),
        ("date", "DATE"),
        ("time", "TIME OF APPOINTMENT"),
    ],


    "RSI": [
        ("symptoms", "SYMPTOMS"),
        ("diagnosis", "DIAGNOSIS"),
        ("status", "STATUS"),
    ],

    "RSO": [
        ("symptoms", "SYMPTOMS"),
        ("diagnosis", "DIAGNOSIS"),
        ("status", "STATUS"),
    ],


    "MC": [
        ("symptoms", "SYMPTOMS"),
        ("diagnosis", "DIAGNOSIS"),
        ("status", "STATUS"),
    ],


    "OTHERS": [
        ("description", "STATUS"),
    ],


    "STATUS_PERSONAL": [],

    "PERMANENT_STATUS": [
        ("status", "STATUS"),
    ],

    "TEMPORARY_STATUS": [
        ("status", "STATUS"),
        ("date_range", "DATE"),
    ],
}

# Separator line used in parade state output
PARADE_STATE_SEPARATOR = "-" * 56

# =========================
# CET CONFIG
# =========================

# Optional keywords for CET filtering (future-proofing)
CET_KEYWORDS = [
    "CET", 
    "MDST",
    "WDI"
]

# =========================
# SECURITY LIMITS
# =========================

# Maximum upload size for /import_user CSV uploads (1 MB)
MAX_IMPORT_CSV_SIZE_BYTES = 1 * 1024 * 1024


# =========================
# DAILY MESSAG CONFIG
# =========================

# Daily messages to be sent on respective days
DAILY_MSGS = {
    "Monday" : "<b>Monday - MINDEF/SAF Mission</b> \nThe mission of MINDEF/SAF is to enhance Singapore's peace and security through deterrence and diplomacy, and should these fail, to secure a swift and decisive victory over the aggressor.",
    "Tuesday" : "<b>Tuesday - DIS Mission</b> \nThe DIS will defend and dominate in the digital domain. As part of an integrated SAF, the DIS will enhance Singapore's security, from peace to war.",
    "Wednesday" : "<b>Wednesday - Definition of SAF Leadership</b> \nLeadership is defined as the process of Influencing people to accomplish the mission, Inspiring their commitment, and Improving the organisation. ",
    "Thursday" : "<b>Thursday - DIS Safety Messages</b>\n1. Safety is an Integral part of mission success.\n2. Zero accident is an achievable goal.\n3. Safety is an individual, team and command responsibility.",
    "Friday" :  "<b>Friday - MINDEF/SAF Mission</b> \nThe mission of MINDEF/SAF is to enhance Singapore's peace and security through deterrence and diplomacy, and should these fail, to secure a swift and decisive victory over the aggressor."
}
