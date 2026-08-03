#!/usr/bin/env python3
"""
Rater import and anonymity-severing module for the 360 Development Catalyst.

Two responsibilities:

1. Bulk CSV upload of raters (Model A workflow):
   Ian uploads a CSV of names/emails/relationships/leaders; the system
   creates rater rows and returns tokens so invitations can be sent
   directly from the system.

2. Identity severing at final submission (Model A anonymity):
   When a rater submits, their name and email are permanently removed
   from BOTH the raters table and the email_log table, leaving only
   the relationship type and the opaque token against their responses.
   After severing, the response record cannot be resolved to a person
   by anyone with database access.

This module is deliberately kept separate from database.py so the
severing logic can be reviewed in isolation. It reuses the existing
Database class rather than duplicating connection handling.

NOTE ON RESIDUAL ANONYMITY RISK:
Severing fixes the "link at rest" problem (who does the DB know said
what). It does NOT fix the "inference from shape" problem (who can the
leader deduce from which responses are present or absent, or from a
distinctive verbatim comment in a small group). That is handled in the
reporting layer via minimum-group and comment-suppression rules, not
here. Do not treat severing alone as making the system fully anonymous.
"""

import csv
import io
import re
from database import Database

# Relationship values accepted in the CSV. "Self" is excluded on purpose:
# the leader completes their own self-assessment, they are not an uploaded
# rater. Keep this list aligned with RELATIONSHIP_TYPES in framework.py.
VALID_RELATIONSHIPS = {"Manager", "Peer", "Direct Report", "Other"}

# Accept a few common spellings/casings and normalise them, so Ian doesn't
# have to hand-clean every CSV. Extend this map rather than loosening the
# validation.
RELATIONSHIP_ALIASES = {
    "manager": "Manager",
    "line manager": "Manager",
    "boss": "Manager",
    "peer": "Peer",
    "peers": "Peer",
    "colleague": "Peer",
    "direct report": "Direct Report",
    "direct reports": "Direct Report",
    "report": "Direct Report",
    "dr": "Direct Report",
    "other": "Other",
    "others": "Other",
    "stakeholder": "Other",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalise_relationship(raw):
    """Map a raw relationship string to a valid value, or None if unknown."""
    if raw is None:
        return None
    key = raw.strip().lower()
    if key in RELATIONSHIP_ALIASES:
        return RELATIONSHIP_ALIASES[key]
    # Allow exact valid values through untouched
    if raw.strip() in VALID_RELATIONSHIPS:
        return raw.strip()
    return None


def _build_leader_lookup(db):
    """Return a dict mapping lowercased leader name -> leader_id.

    Names are matched case-insensitively and trimmed. If two active
    leaders share a name this returns the later one and flags nothing;
    dealership disambiguation would need to be added to the CSV if that
    ever happens in practice.
    """
    lookup = {}
    for leader in db.get_all_leaders():
        lookup[leader["name"].strip().lower()] = leader["id"]
    return lookup


def import_raters_from_csv(csv_text, db=None):
    """Import raters from CSV text.

    Expected columns (header row required, case-insensitive):
        leader_name, rater_name, rater_email, relationship

    Returns a summary dict:
        {
            "created": int,
            "skipped": int,
            "created_rows": [ {row, leader_name, rater_name, relationship, token}, ... ],
            "errors": [ {row, reason, data}, ... ],
        }

    Nothing is written until a row passes all validation, and each valid
    row is written independently, so one bad row never blocks the rest.
    """
    if db is None:
        db = Database()

    reader = csv.DictReader(io.StringIO(csv_text))

    # Normalise headers to lowercase stripped keys
    if reader.fieldnames is None:
        return {
            "created": 0,
            "skipped": 0,
            "created_rows": [],
            "errors": [{"row": 0, "reason": "Empty file or no header row.", "data": None}],
        }

    field_map = {name.strip().lower(): name for name in reader.fieldnames}
    required = ["leader_name", "rater_name", "rater_email", "relationship"]
    missing = [c for c in required if c not in field_map]
    if missing:
        return {
            "created": 0,
            "skipped": 0,
            "created_rows": [],
            "errors": [{
                "row": 0,
                "reason": f"Missing required column(s): {', '.join(missing)}. "
                          f"Expected header: {', '.join(required)}.",
                "data": None,
            }],
        }

    leader_lookup = _build_leader_lookup(db)

    # Track (leader_id, email) pairs seen in THIS file to catch in-file
    # duplicates, and also check against emails already live for that leader.
    seen_in_file = set()

    created_rows = []
    errors = []

    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        leader_name = (raw_row.get(field_map["leader_name"]) or "").strip()
        rater_name = (raw_row.get(field_map["rater_name"]) or "").strip()
        rater_email = (raw_row.get(field_map["rater_email"]) or "").strip()
        relationship_raw = (raw_row.get(field_map["relationship"]) or "").strip()

        # Skip blank rows silently. A row carrying only a leader_name (a
        # common spreadsheet artefact where the leader column is filled
        # down) counts as blank: with no rater detail there is nothing to
        # create and it shouldn't surface as an error.
        if not any([rater_name, rater_email, relationship_raw]):
            continue

        row_data = {
            "leader_name": leader_name,
            "rater_name": rater_name,
            "rater_email": rater_email,
            "relationship": relationship_raw,
        }

        # Validate leader
        leader_id = leader_lookup.get(leader_name.lower())
        if leader_id is None:
            errors.append({
                "row": i,
                "reason": f"No matching active leader '{leader_name}'. "
                          f"Add the leader first, or check the spelling.",
                "data": row_data,
            })
            continue

        # Validate relationship
        relationship = _normalise_relationship(relationship_raw)
        if relationship is None:
            errors.append({
                "row": i,
                "reason": f"Unrecognised relationship '{relationship_raw}'. "
                          f"Use one of: Manager, Peer, Direct Report, Other.",
                "data": row_data,
            })
            continue

        # Validate email
        if not EMAIL_RE.match(rater_email):
            errors.append({
                "row": i,
                "reason": f"Invalid email address '{rater_email}'.",
                "data": row_data,
            })
            continue

        # Duplicate within this file
        dup_key = (leader_id, rater_email.lower())
        if dup_key in seen_in_file:
            errors.append({
                "row": i,
                "reason": f"Duplicate: '{rater_email}' already appears for "
                          f"this leader earlier in the file.",
                "data": row_data,
            })
            continue

        # Duplicate against raters already live for this leader
        if _email_already_live_for_leader(db, leader_id, rater_email):
            errors.append({
                "row": i,
                "reason": f"'{rater_email}' is already an active rater for "
                          f"this leader. Not re-added.",
                "data": row_data,
            })
            continue

        # All good, create the rater
        rater_id, token = db.add_rater(
            leader_id=leader_id,
            relationship=relationship,
            rater_email=rater_email,
            rater_name=rater_name,
        )
        seen_in_file.add(dup_key)
        created_rows.append({
            "row": i,
            "rater_id": rater_id,
            "leader_id": leader_id,
            "leader_name": leader_name,
            "rater_name": rater_name,
            "relationship": relationship,
            "rater_email": rater_email,
            "token": token,
        })

    return {
        "created": len(created_rows),
        "skipped": len(errors),
        "created_rows": created_rows,
        "errors": errors,
    }


def _email_already_live_for_leader(db, leader_id, email):
    """True if an un-severed rater with this email already exists for the leader.

    Severed raters have NULL email, so they can never match, which is
    correct: we never want to reconstruct that a severed rater and a new
    upload are the same person.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM raters
        WHERE leader_id = ?
          AND rater_email IS NOT NULL
          AND LOWER(rater_email) = LOWER(?)
        LIMIT 1
        """,
        (leader_id, email),
    )
    hit = cursor.fetchone() is not None
    conn.close()
    return hit


def format_import_summary(result):
    """Human-readable summary string for the admin UI."""
    lines = []
    lines.append(f"{result['created']} rater(s) created, {result['skipped']} row(s) skipped.")
    if result["created_rows"]:
        by_leader = {}
        for r in result["created_rows"]:
            by_leader.setdefault(r["leader_name"], []).append(r["relationship"])
        lines.append("")
        lines.append("Created:")
        for leader_name, rels in by_leader.items():
            counts = {}
            for rel in rels:
                counts[rel] = counts.get(rel, 0) + 1
            breakdown = ", ".join(f"{n} {rel}" for rel, n in counts.items())
            lines.append(f"  {leader_name}: {breakdown}")
    if result["errors"]:
        lines.append("")
        lines.append("Skipped:")
        for e in result["errors"]:
            row_ref = f"row {e['row']}" if e["row"] else "file"
            lines.append(f"  {row_ref}: {e['reason']}")
    return "\n".join(lines)


# ==============================================================================
# MODEL A SEVERING
# ==============================================================================

def sever_rater_identity(db, rater_id):
    """Permanently remove identifying data for a single rater.

    Called at FINAL submission (not draft save). After this runs:
      - raters.rater_name and raters.rater_email are NULL
      - email_log.recipient_email for this rater is NULL
      - the token, relationship, and all responses remain intact but
        can no longer be resolved to a person via the database.

    This is irreversible by design. Once severed, the rater cannot be
    re-contacted or re-identified, which is the point of Model A.
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    # Null the identity fields on the rater row. Keep token + relationship.
    cursor.execute(
        """
        UPDATE raters
        SET rater_name = NULL,
            rater_email = NULL
        WHERE id = ?
        """,
        (rater_id,),
    )

    # Null the email trail in the log so it can't be joined back.
    # We keep the log row itself (for send-success auditing) but strip
    # the address, which is the only identifying field there.
    cursor.execute(
        """
        UPDATE email_log
        SET recipient_email = NULL
        WHERE rater_id = ?
        """,
        (rater_id,),
    )

    conn.commit()
    conn.close()


def verify_no_residual_identity(db, leader_id):
    """Audit helper: confirm that every SUBMITTED rater for a leader has
    been severed. Returns a list of rater_ids that submitted but still
    carry a name or email (should always be empty if the submit hook is
    wired correctly). Use this before handing a report to the client, or
    as a scheduled integrity check.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM raters
        WHERE leader_id = ?
          AND completed_at IS NOT NULL
          AND (rater_name IS NOT NULL OR rater_email IS NOT NULL)
        """,
        (leader_id,),
    )
    offenders = [row[0] for row in cursor.fetchall()]
    conn.close()
    return offenders
