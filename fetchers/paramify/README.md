# Paramify FedRAMP Report Fetchers

Generates FedRAMP 20x machine-readable report JSON directly from Paramify issue data,
and validates each report against the official FedRAMP schema before writing it.

Unlike the other fetchers in this repository (which pull evidence *from* third-party
source systems *into* Paramify), these fetchers read *from* Paramify and produce the
FedRAMP Consolidated Rules 2026 vulnerability reporting artifacts. They plug into the
standard pipeline like any other fetcher: stage 3 runs them, stage 4 uploads their
output to the Evidence records identified by `EVD-PARAMIFY-VER-RPT-AVI` / `EVD-PARAMIFY-VER-RPT-VDT`.

## Reports Produced

| Report | Rule | Fetcher | Evidence referenceId | Covers |
|---|---|---|---|---|
| Accepted Vulnerability Info | VER-RPT-AVI | `paramify_accepted_vulnerabilities.py` | `EVD-PARAMIFY-VER-RPT-AVI` | Accepted vulnerabilities only |
| Vulnerability Detail Report | VER-RPT-VDT | `paramify_vulnerability_detail_report.py` | `EVD-PARAMIFY-VER-RPT-VDT` | Non-accepted vulnerabilities only |
| Historical VER Activity | VER-TFR-MRH | `paramify_historical_ver_activity.py` | `EVD-PARAMIFY-VER-TFR-MRH` | Point-in-time snapshot: both arrays in one document |

The two reports partition the project's vulnerabilities: every issue is reported by
exactly one of them, using a shared definition of "accepted." No evidence UUIDs are
configured anywhere; the pipeline resolves (or creates) the Evidence records at
runtime from the stable referenceIds above.

## Prerequisites

- Python 3.9 or higher (developed and tested on 3.14)
- `requests` and `jsonschema` (see repo-level dependencies)
- A Paramify account and an API token with read access to the target project
  (the pipeline's upload stage additionally needs evidence write permission)
- The project (program) UUID you want to report on

## Quick Start (standalone)

```bash
# 1. Clone the repository
git clone https://github.com/paramify/evidence-fetchers.git
cd evidence-fetchers

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Paramify token, project UUID, cert package URI, and report start
chmod 600 .env

# 3. Run a report (writes JSON locally; upload happens in pipeline stage 4)
python fetchers/paramify/paramify_accepted_vulnerabilities.py --output-dir ./evidence
python fetchers/paramify/paramify_vulnerability_detail_report.py --output-dir ./evidence
```

Or run through the standard pipeline (`main.py`): select the `paramify` category in
stage 1, create the evidence sets in stage 2, run in stage 3, upload in stage 4.

See [API_KEY_SETUP.md](./API_KEY_SETUP.md) for the full list of environment variables.

## How "Accepted" Is Determined

An issue is treated as an **accepted vulnerability** (and therefore reported under
VER-RPT-AVI, not VER-RPT-VDT) if either:

1. It has an accepted deviation of type `OPERATIONAL_REQUIREMENT`, `VENDOR_DEPENDENCY`,
   or `RISK_ADJUSTMENT`; or
2. It is open and its **real completed evaluation** is at least **192 days** old
   (VER-TFR-MAV: a vulnerability not fully mitigated within 192 days of evaluation
   is an accepted vulnerability).

**Missing / sentinel evaluation dates:** Paramify records a Unix-epoch timestamp
(`1970-01-01T00:00:00.000Z`) as `evaluationDate` for issues that were never actually
evaluated. Such sentinel (pre-2000) or missing dates mean the evaluation never
happened, so the VER-TFR-MAV clock has not started: these issues are **excluded from
time-based acceptance**, reported in the VDT report **without** an
`evaluationCompletedAt` field, and counted in a run warning (per VER-TFR-EVU,
Class C providers should evaluate vulnerabilities within 5 days of detection, so an
unevaluated backlog is surfaced rather than silently mis-accepted).

`FALSE_POSITIVE` deviations are **not** acceptances. They are surfaced in the VDT report
as a `finalDisposition` of `"False Positive"`.

## Vulnerability Detail Report Fields

The VDT fetcher derives two report-specific fields from Paramify data. These derivations
are **interim** and should be confirmed with the FedRAMP package owner before production
reporting:

- **`finalDisposition`** — `"Fully Mitigated"` when the issue is closed;
  `"Partially Mitigated"` when the issue is open and has either a risk-adjustment
  deviation or a remediation-activity milestone; `"False Positive"` for an accepted
  false-positive deviation; omitted while the issue is still active with no progress.
- **`overdueStatus`** — `isOverdue: true` (with a required explanation) when the issue
  is open and past its due date; `isOverdue: false` otherwise.

## Historical VER Activity Snapshot

`paramify_historical_ver_activity.py` produces the VER-TFR-MRH snapshot: one
document with `activeVulnerabilities` (VDT fields) and `acceptedVulnerabilities`
(AVI fields), plus a `generatedAt` timestamp. It contains no acceptance logic of
its own -- it imports the AVI and VDT fetchers and partitions a single issue
fetch with their shared accepted definition, so the snapshot can never disagree
with the individual reports. Data is always fetched fresh from the Paramify API,
never reassembled from previously generated evidence. Per VER-TFR-MRH, Class C
providers should refresh this at least every 14 days (scheduling is operational,
outside the fetcher).

## Schema Validation

Each report is validated against the vendored FedRAMP schema in `_fedramp/schemas/`
before it is written and reported as valid evidence. The schemas are the official
`2026-06-24` releases; `_fedramp/schema_validator.py` handles FedRAMP's cross-file
`$ref` format without modifying the vendored files.

## Performance

The VDT fetcher makes one milestones call per open, non-partially-mitigated issue, so
large projects take several minutes. The per-request HTTP timeout defaults to 90
seconds and can be tuned with `PARAMIFY_HTTP_TIMEOUT`.
