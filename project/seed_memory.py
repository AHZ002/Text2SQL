import asyncio
from vanna_setup import agent_memory

# ── 15 known good question-SQL pairs ─────────────────────────────────────────
SEED_PAIRS = [
    # ── Patient queries ───────────────────────────────────────────────────────
    (
        "How many patients do we have?",
        "SELECT COUNT(*) AS total_patients FROM patients"
    ),
    (
        "List all patients with their city and gender",
        "SELECT first_name, last_name, city, gender FROM patients ORDER BY last_name"
    ),
    (
        "Which city has the most patients?",
        """SELECT city, COUNT(*) AS patient_count
           FROM patients
           GROUP BY city
           ORDER BY patient_count DESC
           LIMIT 1"""
    ),
    (
        "Show patient registration trend by month",
        """SELECT strftime('%Y-%m', registered_date) AS month,
                  COUNT(*) AS new_patients
           FROM patients
           GROUP BY month
           ORDER BY month"""
    ),
    (
        "List patients who visited more than 3 times",
        """SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
           FROM patients p
           JOIN appointments a ON a.patient_id = p.id
           GROUP BY p.id
           HAVING visit_count > 3
           ORDER BY visit_count DESC"""
    ),

    # ── Doctor queries ────────────────────────────────────────────────────────
    (
        "List all doctors and their specializations",
        "SELECT name, specialization, department FROM doctors ORDER BY specialization"
    ),
    (
        "Which doctor has the most appointments?",
        """SELECT d.name, COUNT(a.id) AS appointment_count
           FROM doctors d
           JOIN appointments a ON a.doctor_id = d.id
           GROUP BY d.id
           ORDER BY appointment_count DESC
           LIMIT 1"""
    ),
    (
        "Average appointment duration by doctor",
        """SELECT d.name, AVG(t.duration_minutes) AS avg_duration
           FROM doctors d
           JOIN appointments a ON a.doctor_id = d.id
           JOIN treatments t ON t.appointment_id = a.id
           GROUP BY d.id
           ORDER BY avg_duration DESC"""
    ),

    # ── Appointment queries ───────────────────────────────────────────────────
    (
        "Show me appointments for last month",
        """SELECT a.id, p.first_name, p.last_name, d.name AS doctor,
                  a.appointment_date, a.status
           FROM appointments a
           JOIN patients p ON p.id = a.patient_id
           JOIN doctors d ON d.id = a.doctor_id
           WHERE strftime('%Y-%m', a.appointment_date)
               = strftime('%Y-%m', date('now', '-1 month'))
           ORDER BY a.appointment_date"""
    ),
    (
        "How many cancelled appointments are there in the last quarter?",
        """SELECT COUNT(*) AS cancelled_count
           FROM appointments
           WHERE status = 'Cancelled'
           AND appointment_date >= date('now', '-3 months')"""
    ),
    (
        "Show monthly appointment count for the past 6 months",
        """SELECT strftime('%Y-%m', appointment_date) AS month,
                  COUNT(*) AS appointment_count
           FROM appointments
           WHERE appointment_date >= date('now', '-6 months')
           GROUP BY month
           ORDER BY month"""
    ),
    (
        "What percentage of appointments are no-shows?",
        """SELECT
               ROUND(100.0 * SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END)
               / COUNT(*), 2) AS no_show_percentage
           FROM appointments"""
    ),

    # ── Financial queries ─────────────────────────────────────────────────────
    (
        "What is the total revenue?",
        "SELECT SUM(total_amount) AS total_revenue FROM invoices"
    ),
    (
        "Show revenue by doctor",
        """SELECT d.name, SUM(i.total_amount) AS total_revenue
           FROM invoices i
           JOIN appointments a ON a.patient_id = i.patient_id
           JOIN doctors d ON d.id = a.doctor_id
           GROUP BY d.id
           ORDER BY total_revenue DESC"""
    ),
    (
        "Show unpaid invoices",
        """SELECT p.first_name, p.last_name, i.invoice_date,
                  i.total_amount, i.paid_amount, i.status
           FROM invoices i
           JOIN patients p ON p.id = i.patient_id
           WHERE i.status IN ('Pending', 'Overdue')
           ORDER BY i.invoice_date"""
    ),
]


async def seed():
    print(f"Seeding {len(SEED_PAIRS)} question-SQL pairs into agent memory...")
    for i, (question, sql) in enumerate(SEED_PAIRS, 1):
        await agent_memory.save_tool_usage(
            question=question,
            tool_name="run_sql",
            args={"sql": sql},
            context=None,
            success=True,
        )
        print(f"  [{i:02d}/{len(SEED_PAIRS)}] ✅ {question[:60]}")
    print(f"\nDone. {len(SEED_PAIRS)} pairs seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())