#!/usr/bin/env python3
"""
Test script for cross-reference comparison logic.

Uses the real rippling_current_employees.json already fetched, then generates
mock Okta and KnowBe4 data in the exact format observed from Paramify evidence,
with deliberate gaps to verify the comparison logic works correctly.

Run from the rippling_fetchers directory:
    python test_cross_reference.py --output-dir ./test_output
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup path
# ---------------------------------------------------------------------------
OUTPUT_DIR = "./test_output"
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--output-dir" and i + 1 < len(sys.argv[1:]):
        OUTPUT_DIR = sys.argv[i + 2]

evidence_dir = Path(OUTPUT_DIR)
evidence_dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Step 1: Load real Rippling data
# ---------------------------------------------------------------------------
rippling_path = evidence_dir / "rippling_current_employees.json"
if not rippling_path.exists():
    print(f"ERROR: {rippling_path} not found. Run rippling_current_employees.py first.")
    sys.exit(1)

with rippling_path.open(encoding="utf-8") as f:
    rippling_data = json.load(f)

employees = rippling_data.get("results", [])
print(f"Loaded {len(employees)} Rippling employees from {rippling_path}")

# Extract emails
rippling_emails = []
for emp in employees:
    email = (emp.get("workEmail") or emp.get("work_email") or emp.get("email") or "").strip().lower()
    if email:
        rippling_emails.append(email)

print(f"  Found {len(rippling_emails)} employees with email addresses")

# ---------------------------------------------------------------------------
# Step 2: Generate mock Okta data (exact format from Paramify evidence)
# Format observed: admin_users[].email, regular_users[].email
# ---------------------------------------------------------------------------

# Use first 10 Rippling employees as Okta regular users (simulating most but not all are in Okta)
# Plus 2 "stale" accounts not in Rippling
okta_regular_emails = rippling_emails[:10]
okta_stale_emails = ["former.employee@paramify.com", "contractor.old@paramify.com"]

okta_data = {
    "admin_users": [
        {"id": "00ut001", "login": rippling_emails[0], "email": rippling_emails[0],
         "name": employees[0].get("firstName", "Admin") + " " + employees[0].get("lastName", "User"),
         "is_super_admin": True, "admin_type": "SUPER_ADMIN"},
    ],
    "regular_users": [
        {"email": e, "name": "Okta User", "status": "ACTIVE"}
        for e in okta_regular_emails[1:]  # skip first (already in admin)
    ] + [
        {"email": e, "name": "Stale Account", "status": "ACTIVE"}
        for e in okta_stale_emails
    ],
    "group_memberships": []
}

total_okta = 1 + len(okta_data["regular_users"])
print(f"\nGenerated mock Okta data:")
print(f"  {len(okta_data['admin_users'])} admin users")
print(f"  {len(okta_data['regular_users'])} regular users ({len(okta_stale_emails)} are stale/not in Rippling)")
print(f"  {len(rippling_emails) - len(okta_regular_emails)} Rippling employees intentionally missing from Okta")

# ---------------------------------------------------------------------------
# Step 3: Generate mock KnowBe4 data (exact format from Paramify evidence)
# Format: results.users[].email, results.enrollments[].user.email + .status
# ---------------------------------------------------------------------------

# Use first 20 Rippling employees in KnowBe4
# Leave rest out to simulate employees not in KnowBe4
kb4_user_emails = rippling_emails[:20]

# Of those 20: first 17 passed training, 2 not started, 1 in progress
kb4_users = [{"id": 100000 + i, "email": e, "status": "active"} for i, e in enumerate(kb4_user_emails)]

kb4_enrollments = []
for i, email in enumerate(kb4_user_emails):
    if i < 17:
        status = "Passed"
        completion_date = "2025-03-01T10:00:00.000Z"
    elif i < 19:
        status = "Not Started"
        completion_date = None
    else:
        status = "In Progress"
        completion_date = None

    kb4_enrollments.append({
        "enrollment_id": 800000 + i,
        "module_name": "Security Awareness Training 2025",
        "user": {"id": 100000 + i, "email": email},
        "campaign_id": 2491845,
        "campaign_name": "Annual Security Awareness Training",
        "enrollment_date": "2025-01-01T00:00:00.000Z",
        "completion_date": completion_date,
        "status": status,
    })

kb4_data = {
    "users": kb4_users,
    "enrollments": kb4_enrollments,
    "user_training_status": [],
    "summary": {
        "total_users": len(kb4_users),
        "completed_training": 17,
        "in_progress": 1,
        "not_started": 2,
        "completion_rate": round(17 / len(kb4_users) * 100),
    }
}

print(f"\nGenerated mock KnowBe4 data:")
print(f"  {len(kb4_users)} users in KnowBe4")
print(f"  17 passed, 2 not started, 1 in progress")
print(f"  {len(rippling_emails) - len(kb4_user_emails)} Rippling employees NOT in KnowBe4 at all")

# ---------------------------------------------------------------------------
# Step 4: Run cross-reference comparison
# ---------------------------------------------------------------------------

def cross_ref_okta(rippling_employees, okta_admin, okta_regular):
    """Compare Rippling vs Okta."""
    rippling_by_email = {}
    for emp in rippling_employees:
        email = (emp.get("workEmail") or emp.get("work_email") or emp.get("email") or "").strip().lower()
        if email:
            rippling_by_email[email] = emp

    # Combine all Okta users
    okta_emails = set()
    for u in okta_admin + okta_regular:
        email = (u.get("email") or u.get("login") or "").strip().lower()
        if email:
            okta_emails.add(email)

    rippling_set = set(rippling_by_email.keys())

    in_okta_not_rippling = sorted(okta_emails - rippling_set)
    in_rippling_not_okta = sorted(rippling_set - okta_emails)
    matched = sorted(rippling_set & okta_emails)

    return {
        "source": "rippling_vs_okta",
        "summary": {
            "rippling_active_employees": len(rippling_set),
            "okta_active_users": len(okta_emails),
            "matched_both_systems": len(matched),
            "in_okta_not_in_rippling": len(in_okta_not_rippling),
            "in_rippling_not_in_okta": len(in_rippling_not_okta),
        },
        "in_okta_not_in_rippling": [{"email": e} for e in in_okta_not_rippling],
        "in_rippling_not_in_okta": [
            {"email": e, "name": rippling_by_email[e].get("firstName", "") + " " + rippling_by_email[e].get("lastName", "")}
            for e in in_rippling_not_okta
        ],
        "matched_emails": matched,
    }


def cross_ref_knowbe4(rippling_employees, kb4_users, kb4_enrollments):
    """Compare Rippling vs KnowBe4 training."""
    rippling_by_email = {}
    for emp in rippling_employees:
        email = (emp.get("workEmail") or emp.get("work_email") or emp.get("email") or "").strip().lower()
        if email:
            rippling_by_email[email] = emp

    kb4_email_set = {u["email"].strip().lower() for u in kb4_users if u.get("email")}

    # Build enrollment status per email (best status wins: Passed > In Progress > Not Started)
    STATUS_RANK = {"passed": 3, "in progress": 2, "not started": 1}
    enrolled_status = {}
    for enr in kb4_enrollments:
        email = (enr.get("user", {}).get("email") or enr.get("email") or "").strip().lower()
        status = enr.get("status", "").strip()
        if email:
            current_rank = STATUS_RANK.get(enrolled_status.get(email, "").lower(), 0)
            new_rank = STATUS_RANK.get(status.lower(), 0)
            if new_rank > current_rank:
                enrolled_status[email] = status

    rippling_set = set(rippling_by_email.keys())

    not_in_kb4 = sorted(rippling_set - kb4_email_set)
    in_kb4_not_enrolled = sorted((rippling_set & kb4_email_set) - set(enrolled_status.keys()))
    enrolled_not_passed = sorted([
        e for e in rippling_set & set(enrolled_status.keys())
        if enrolled_status[e].lower() not in ("passed", "completed")
    ])
    passed = sorted([
        e for e in rippling_set & set(enrolled_status.keys())
        if enrolled_status[e].lower() in ("passed", "completed")
    ])

    return {
        "source": "rippling_vs_knowbe4",
        "summary": {
            "rippling_active_employees": len(rippling_set),
            "knowbe4_users": len(kb4_email_set),
            "not_in_knowbe4_at_all": len(not_in_kb4),
            "in_knowbe4_not_enrolled": len(in_kb4_not_enrolled),
            "enrolled_but_not_passed": len(enrolled_not_passed),
            "passed": len(passed),
        },
        "not_in_knowbe4_at_all": [
            {"email": e, "name": rippling_by_email[e].get("firstName","") + " " + rippling_by_email[e].get("lastName","")}
            for e in not_in_kb4
        ],
        "in_knowbe4_not_enrolled": [{"email": e} for e in in_kb4_not_enrolled],
        "enrolled_but_not_passed": [
            {"email": e, "enrollment_status": enrolled_status[e]}
            for e in enrolled_not_passed
        ],
        "passed_emails": passed,
    }


# ---------------------------------------------------------------------------
# Step 5: Run comparisons and save outputs
# ---------------------------------------------------------------------------

print("\n" + "="*60)
print("RUNNING CROSS-REFERENCE COMPARISONS")
print("="*60)

# --- Okta gap ---
okta_gap = cross_ref_okta(employees, okta_data["admin_users"], okta_data["regular_users"])
okta_gap_path = evidence_dir / "rippling_vs_okta_gap.json"
with okta_gap_path.open("w", encoding="utf-8") as f:
    json.dump(okta_gap, f, indent=2)

# Avoid printing potentially sensitive summary data directly
print(f"\n[Rippling vs Okta]")
print("  Comparison complete.")
print(f"  Detailed results saved to: {okta_gap_path}")

# --- KnowBe4 gap ---
kb4_gap = cross_ref_knowbe4(employees, kb4_data["users"], kb4_data["enrollments"])
kb4_gap_path = evidence_dir / "rippling_vs_knowbe4_gap.json"
with kb4_gap_path.open("w", encoding="utf-8") as f:
    json.dump(kb4_gap, f, indent=2)

s = kb4_gap["summary"]
print(f"\n[Rippling vs KnowBe4]")
print(f"  Rippling employees     : {s['rippling_active_employees']}")
print(f"  KnowBe4 users          : {s['knowbe4_users']}")
print(f"  Not in KnowBe4 at all  : {s['not_in_knowbe4_at_all']}")
print(f"  In KB4 but not enrolled: {s['in_knowbe4_not_enrolled']}")
print(f"  Enrolled but not passed: {s['enrolled_but_not_passed']}")
print(f"  Passed                 : {s['passed']}")
print(f"  -> Saved: {kb4_gap_path}")

# ---------------------------------------------------------------------------
# Step 6: Validate the logic is correct
# ---------------------------------------------------------------------------
print("\n" + "="*60)
print("VALIDATION CHECKS")
print("="*60)

errors = []

# Okta checks
s_okta = okta_gap["summary"]
if s_okta["in_okta_not_in_rippling"] != len(okta_stale_emails):
    errors.append(f"FAIL: expected {len(okta_stale_emails)} stale Okta accounts, got {s_okta['in_okta_not_in_rippling']}")
else:
    print(f"PASS: Detected {len(okta_stale_emails)} stale Okta accounts correctly")

expected_missing_okta = len(rippling_emails) - len(okta_regular_emails)
if s_okta["in_rippling_not_in_okta"] != expected_missing_okta:
    errors.append(f"FAIL: expected {expected_missing_okta} Rippling employees missing from Okta, got {s_okta['in_rippling_not_in_okta']}")
else:
    print(f"PASS: Detected {expected_missing_okta} Rippling employees missing from Okta correctly")

# KnowBe4 checks
s_kb4 = kb4_gap["summary"]
expected_not_in_kb4 = len(rippling_emails) - len(kb4_user_emails)
if s_kb4["not_in_knowbe4_at_all"] != expected_not_in_kb4:
    errors.append(f"FAIL: expected {expected_not_in_kb4} employees not in KnowBe4, got {s_kb4['not_in_knowbe4_at_all']}")
else:
    print(f"PASS: Detected {expected_not_in_kb4} employees not in KnowBe4 correctly")

if s_kb4["enrolled_but_not_passed"] != 3:  # 2 not started + 1 in progress
    errors.append(f"FAIL: expected 3 enrolled-but-not-passed, got {s_kb4['enrolled_but_not_passed']}")
else:
    print(f"PASS: Detected 3 enrolled-but-not-passed (2 not started + 1 in progress) correctly")

print()
if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("All checks passed! Cross-reference logic is working correctly.")
    print(f"\nOutput files in {evidence_dir}:")
    print(f"  rippling_vs_okta_gap.json")
    print(f"  rippling_vs_knowbe4_gap.json")
