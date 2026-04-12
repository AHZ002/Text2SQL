import requests
import json

URL = "http://localhost:8000/chat"

QUESTIONS = [
    "How many patients do we have?",
    "List all doctors and their specializations",
    "Show me appointments for last month",
    "Which doctor has the most appointments?",
    "What is the total revenue?",
    "Show revenue by doctor",
    "How many cancelled appointments last quarter?",
    "Top 5 patients by spending",
    "Average treatment cost by specialization",
    "Show monthly appointment count for the past 6 months",
    "Which city has the most patients?",
    "List patients who visited more than 3 times",
    "Show unpaid invoices",
    "What percentage of appointments are no-shows?",
    "Show the busiest day of the week for appointments",
    "Revenue trend by month",
    "Average appointment duration by doctor",
    "List patients with overdue invoices",
    "Compare revenue between departments",
    "Show patient registration trend by month",
]

print("=" * 70)
print("NL2SQL — 20 Question Test")
print("=" * 70)

passed = 0
failed = 0

for i, question in enumerate(QUESTIONS, 1):
    try:
        resp = requests.post(URL, json={"question": question}, timeout=30)
        data = resp.json()

        has_sql  = bool(data.get("sql_query"))
        has_rows = data.get("row_count") is not None
        has_err  = bool(data.get("error"))

        status = "✅ PASS" if (has_sql and has_rows and not has_err) else "❌ FAIL"
        if has_sql and has_rows and not has_err:
            passed += 1
        else:
            failed += 1

        print(f"\n[{i:02d}] {status} | {question}")
        print(f"      SQL     : {(data.get('sql_query') or '')[:80]}")
        print(f"      Rows    : {data.get('row_count')} | Error: {data.get('error')}")

    except Exception as e:
        failed += 1
        print(f"\n[{i:02d}] ❌ FAIL | {question}")
        print(f"      Exception: {e}")

print("\n" + "=" * 70)
print(f"RESULTS: {passed}/20 passed | {failed}/20 failed")
print("=" * 70)