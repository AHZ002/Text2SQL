# Test Results — 20 Question Evaluation

**Score: 20/20 passed**
**LLM Provider:** Groq (llama-3.3-70b-versatile)
**Database:** clinic.db (SQLite)
**Date Tested:** April 2026

---

## Results Table

| # | Question | Rows Returned | Status |
|---|---|---|---|
| 1 | How many patients do we have? | 1 (count=200) | PASS |
| 2 | List all doctors and their specializations | 15 | PASS |
| 3 | Show me appointments for last month | 49 | PASS |
| 4 | Which doctor has the most appointments? | 1 | PASS |
| 5 | What is the total revenue? | 1 | PASS |
| 6 | Show revenue by doctor | 15 | PASS |
| 7 | How many cancelled appointments last quarter? | 1 | PASS |
| 8 | Top 5 patients by spending | 5 | PASS |
| 9 | Average treatment cost by specialization | 5 | PASS |
| 10 | Show monthly appointment count for the past 6 months | 7 | PASS |
| 11 | Which city has the most patients? | 1 | PASS |
| 12 | List patients who visited more than 3 times | 41 | PASS |
| 13 | Show unpaid invoices | 124 | PASS |
| 14 | What percentage of appointments are no-shows? | 1 | PASS |
| 15 | Show the busiest day of the week for appointments | 1 | PASS |
| 16 | Revenue trend by month | 13 | PASS |
| 17 | Average appointment duration by doctor | 15 | PASS |
| 18 | List patients with overdue invoices | 39 | PASS |
| 19 | Compare revenue between departments | 5 | PASS |
| 20 | Show patient registration trend by month | 13 | PASS |

---

## Issues Encountered and How They Were Fixed

### Issue 1 — Agent not calling RunSqlTool (missing schema context)

**Problem:**
The LLM responded with "I will execute a query..." but never actually ran any
SQL. It had no knowledge of our database tables or columns because nothing was
telling it what the database looked like.

**Fix:**
Injected the full live database schema into the system prompt using
DefaultSystemPromptBuilder with a custom base_prompt. The schema is read
directly from clinic.db at startup using SQLite's PRAGMA table_info() so it
always reflects the real database structure.

---

### Issue 2 — SQL extractor grabbed tool call syntax as SQL (Question 8)

**Problem:**
The agent correctly called search_saved_correct_tool_uses() to check memory
before running SQL. But our regex extracted that tool call as if it were SQL,
producing:

    SELECT * FROM search_saved_correct_tool_uses()

This crashed with "no such table: search_saved_correct_tool_uses".

**Fix:**
Added a validation rule to reject any SQL where a function call appears as a
table source:

    if re.search(r"FROM\s+\w+\s*\(", sql, re.IGNORECASE):
        return False, "Invalid SQL — function calls not allowed as table sources."

---

### Issue 3 — Wrong status values in generated SQL (Questions 13 and 18)

**Problem:**
The LLM guessed status = 'unpaid' and status = 'overdue' (lowercase) instead
of the exact values stored in our data which are 'Pending', 'Overdue', and
'No-Show'. SQLite string comparison is case-sensitive so queries returned 0 rows
even though the SQL ran without errors.

**Fix:**
Added explicit enum value hints to the system prompt so the LLM always uses
the correct exact values:

    Invoice status values are exactly: 'Paid', 'Pending', 'Overdue'
    Appointment status values are exactly: 'Scheduled', 'Completed', 'Cancelled', 'No-Show'
    For unpaid invoices use: status IN ('Pending', 'Overdue')
    For no-show appointments use: status = 'No-Show'

---

### Issue 4 — async UserResolver TypeError

**Problem:**
Vanna's agent internally uses await resolver.resolve_user() but our
implementation was a regular synchronous function. Python threw:

    TypeError: object User can't be used in 'await' expression

**Fix:**
Added the async keyword to resolve_user() so it can be properly awaited.

---

## Bonus Features Implemented

- 📊 Chart generation — Plotly bar and line charts returned for all multi-row responses
- 🛡️ Input validation — empty questions and questions over 500 characters are rejected
- ⏱️ Rate limiting — 20 requests per minute per IP address via SlowAPI
- 📝 Structured logging — every processing step logged with timestamp and severity level