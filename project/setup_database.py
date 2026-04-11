import sqlite3
import random
from datetime import datetime, timedelta

# ── helpers ──────────────────────────────────────────────────────────────────

def random_date(start: datetime, end: datetime) -> str:
    delta = end - start
    return (start + timedelta(days=random.randint(0, delta.days))).strftime("%Y-%m-%d")

def random_datetime(start: datetime, end: datetime) -> str:
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return (start + timedelta(seconds=random_seconds)).strftime("%Y-%m-%d %H:%M:%S")

# ── constants ─────────────────────────────────────────────────────────────────

TODAY      = datetime.today()
ONE_YEAR_AGO = TODAY - timedelta(days=365)

CITIES = ["Delhi", "Mumbai", "Bangalore", "Hyderabad",
          "Chennai", "Kolkata", "Pune", "Jaipur", "Lucknow", "Ahmedabad"]

FIRST_NAMES = [
    "Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Ayaan","Krishna","Ishaan",
    "Priya","Ananya","Isha","Neha","Pooja","Sneha","Riya","Kavya","Divya","Meera",
    "Rahul","Amit","Suresh","Ramesh","Vikram","Rajesh","Nikhil","Rohit","Manish","Deepak"
]

LAST_NAMES = [
    "Sharma","Verma","Patel","Singh","Kumar","Gupta","Joshi","Mehta","Nair","Reddy",
    "Iyer","Shah","Malhotra","Chauhan","Bose","Das","Pillai","Rao","Saxena","Mishra"
]

SPECIALIZATIONS = ["Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"]

DOCTOR_DATA = [
    # (name, specialization, department)
    ("Dr. Anil Sharma",    "Dermatology",  "Skin & Hair"),
    ("Dr. Priya Mehta",    "Dermatology",  "Skin & Hair"),
    ("Dr. Rohan Das",      "Dermatology",  "Skin & Hair"),
    ("Dr. Sunita Verma",   "Cardiology",   "Heart Care"),
    ("Dr. Karan Patel",    "Cardiology",   "Heart Care"),
    ("Dr. Meera Nair",     "Cardiology",   "Heart Care"),
    ("Dr. Arjun Reddy",    "Orthopedics",  "Bone & Joint"),
    ("Dr. Pooja Singh",    "Orthopedics",  "Bone & Joint"),
    ("Dr. Vikram Iyer",    "Orthopedics",  "Bone & Joint"),
    ("Dr. Neha Joshi",     "General",      "General Medicine"),
    ("Dr. Rahul Gupta",    "General",      "General Medicine"),
    ("Dr. Ananya Rao",     "General",      "General Medicine"),
    ("Dr. Siddharth Bose", "Pediatrics",   "Child Care"),
    ("Dr. Kavya Pillai",   "Pediatrics",   "Child Care"),
    ("Dr. Deepak Saxena",  "Pediatrics",   "Child Care"),
]

TREATMENT_NAMES = {
    "Dermatology":  ["Acne Treatment","Laser Therapy","Chemical Peel","Botox","Skin Biopsy"],
    "Cardiology":   ["ECG","Echocardiogram","Stress Test","Angioplasty","Holter Monitor"],
    "Orthopedics":  ["X-Ray","MRI Scan","Physiotherapy","Joint Injection","Bone Density Test"],
    "General":      ["Blood Test","Urine Test","Vaccination","General Checkup","BP Monitoring"],
    "Pediatrics":   ["Growth Assessment","Immunization","Nutrition Counseling","Hearing Test","Vision Test"],
}

STATUSES      = ["Scheduled", "Completed", "Cancelled", "No-Show"]
STATUS_WEIGHTS = [15, 55, 20, 10]          # Completed most common

INV_STATUSES      = ["Paid", "Pending", "Overdue"]
INV_STATUS_WEIGHTS = [60, 25, 15]

# ── schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name     TEXT    NOT NULL,
    last_name      TEXT    NOT NULL,
    email          TEXT,
    phone          TEXT,
    date_of_birth  DATE,
    gender         TEXT,
    city           TEXT,
    registered_date DATE
);

CREATE TABLE IF NOT EXISTS doctors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    specialization  TEXT,
    department      TEXT,
    phone           TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER REFERENCES patients(id),
    doctor_id        INTEGER REFERENCES doctors(id),
    appointment_date DATETIME,
    status           TEXT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS treatments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id   INTEGER REFERENCES appointments(id),
    treatment_name   TEXT,
    cost             REAL,
    duration_minutes INTEGER
);

CREATE TABLE IF NOT EXISTS invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER REFERENCES patients(id),
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT
);
"""

# ── seed functions ────────────────────────────────────────────────────────────

def seed_doctors(cur):
    phones = [f"98{random.randint(10000000,99999999)}" for _ in DOCTOR_DATA]
    rows = [
        (d[0], d[1], d[2], phones[i])
        for i, d in enumerate(DOCTOR_DATA)
    ]
    cur.executemany(
        "INSERT INTO doctors (name, specialization, department, phone) VALUES (?,?,?,?)",
        rows
    )
    return len(rows)


def seed_patients(cur, n=200):
    rows = []
    for i in range(n):
        first  = random.choice(FIRST_NAMES)
        last   = random.choice(LAST_NAMES)
        gender = random.choice(["M", "F"])
        dob    = random_date(datetime(1950, 1, 1), datetime(2005, 12, 31))
        city   = random.choice(CITIES)
        reg    = random_date(ONE_YEAR_AGO, TODAY)

        # Realistic NULLs in optional fields
        email = f"{first.lower()}.{last.lower()}{i}@email.com" if random.random() > 0.15 else None
        phone = f"9{random.randint(100000000,999999999)}"      if random.random() > 0.10 else None

        rows.append((first, last, email, phone, dob, gender, city, reg))

    cur.executemany(
        """INSERT INTO patients
           (first_name,last_name,email,phone,date_of_birth,gender,city,registered_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        rows
    )
    return n


def seed_appointments(cur, n_patients=200, n_doctors=15, n=500):
    # Some patients are repeat visitors (weighted)
    patient_weights = []
    for i in range(1, n_patients + 1):
        # ~20 patients get high weight (repeat visitors)
        patient_weights.append(5 if i <= 20 else 1)

    rows = []
    for _ in range(n):
        pid    = random.choices(range(1, n_patients + 1), weights=patient_weights)[0]
        did    = random.randint(1, n_doctors)
        dt     = random_datetime(ONE_YEAR_AGO, TODAY)
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
        notes  = random.choice([
            "Follow-up required", "First visit", "Referred by GP",
            "Urgent case", "Routine checkup", None, None, None   # NULLs intentional
        ])
        rows.append((pid, did, dt, status, notes))

    cur.executemany(
        "INSERT INTO appointments (patient_id,doctor_id,appointment_date,status,notes) VALUES (?,?,?,?,?)",
        rows
    )
    return n


def seed_treatments(cur, target=350):
    # Only completed appointments get treatments
    cur.execute("SELECT id, doctor_id FROM appointments WHERE status='Completed'")
    completed = cur.fetchall()

    # Fetch doctor specializations
    cur.execute("SELECT id, specialization FROM doctors")
    doc_spec = {row[0]: row[1] for row in cur.fetchall()}

    sample = random.sample(completed, min(target, len(completed)))
    rows = []
    for appt_id, doc_id in sample:
        spec   = doc_spec.get(doc_id, "General")
        t_name = random.choice(TREATMENT_NAMES.get(spec, ["General Checkup"]))
        cost   = round(random.uniform(50, 5000), 2)
        dur    = random.randint(15, 120)
        rows.append((appt_id, t_name, cost, dur))

    cur.executemany(
        "INSERT INTO treatments (appointment_id,treatment_name,cost,duration_minutes) VALUES (?,?,?,?)",
        rows
    )
    return len(rows)


def seed_invoices(cur, n_patients=200, target=300):
    rows = []
    for _ in range(target):
        pid    = random.randint(1, n_patients)
        inv_dt = random_date(ONE_YEAR_AGO, TODAY)
        total  = round(random.uniform(200, 8000), 2)
        status = random.choices(INV_STATUSES, weights=INV_STATUS_WEIGHTS)[0]
        paid   = (
            total                        if status == "Paid"    else
            round(random.uniform(0, total * 0.5), 2) if status == "Pending" else
            0.0
        )
        rows.append((pid, inv_dt, total, paid, status))

    cur.executemany(
        "INSERT INTO invoices (patient_id,invoice_date,total_amount,paid_amount,status) VALUES (?,?,?,?,?)",
        rows
    )
    return len(rows)

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    db_path = "clinic.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(SCHEMA)
    con.commit()

    random.seed(42)          # Reproducible data every run

    n_doc  = seed_doctors(cur);     con.commit()
    n_pat  = seed_patients(cur);    con.commit()
    n_app  = seed_appointments(cur, n_patients=n_pat, n_doctors=n_doc); con.commit()
    n_tre  = seed_treatments(cur);  con.commit()
    n_inv  = seed_invoices(cur);    con.commit()

    con.close()
    print(f"✅ Database created: {db_path}")
    print(f"   Doctors      : {n_doc}")
    print(f"   Patients     : {n_pat}")
    print(f"   Appointments : {n_app}")
    print(f"   Treatments   : {n_tre}")
    print(f"   Invoices     : {n_inv}")

if __name__ == "__main__":
    main()