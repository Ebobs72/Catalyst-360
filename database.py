#!/usr/bin/env python3
"""
Database module for Bentley Compass 360.

Handles all data persistence using Turso (libSQL) for cloud hosting,
with fallback to local SQLite for development.
"""

import secrets
from datetime import datetime
from pathlib import Path
import json
import os

# Try to import libsql for Turso, fall back to sqlite3 for local dev
import sqlite3

try:
    import libsql
    USING_TURSO = True
except ImportError:
    USING_TURSO = False

class Database:
    def __init__(self, db_path="compass_360.db"):
        """
        Initialize database connection.
        
        If Turso credentials are available (via environment or Streamlit secrets),
        connects to Turso cloud database. Otherwise falls back to local SQLite.
        """
        self.db_path = db_path
        self.turso_url = None
        self.turso_token = None
        
        # Try to get Turso credentials
        self._load_turso_credentials()
        
        self.init_database()
    
    def _load_turso_credentials(self):
        """Load Turso credentials from environment or Streamlit secrets."""
        # Try Streamlit secrets first
        try:
            import streamlit as st
            self.turso_url = st.secrets.get("turso", {}).get("url")
            self.turso_token = st.secrets.get("turso", {}).get("token")
        except:
            pass
        
        # Fall back to environment variables
        if not self.turso_url:
            self.turso_url = os.environ.get("TURSO_DATABASE_URL")
        if not self.turso_token:
            self.turso_token = os.environ.get("TURSO_AUTH_TOKEN")
    
    def get_connection(self):
        """Get a database connection."""
        if self.turso_url and self.turso_token and USING_TURSO:
            # Connect to Turso cloud database
            conn = libsql.connect(
                database=self.turso_url,
                auth_token=self.turso_token
            )
            return conn
        else:
            # Fall back to local SQLite
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
    
    def _execute(self, query, params=None):
        """Execute a query and return the cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return conn, cursor
    
    def _fetchall(self, query, params=None):
        """Execute a query and fetch all results as list of dicts."""
        conn, cursor = self._execute(query, params)
        
        if USING_TURSO and self.turso_url and self.turso_token:
            rows = cursor.fetchall()
            if rows and len(rows) > 0:
                columns = [desc[0] for desc in cursor.description]
                result = [dict(zip(columns, row)) for row in rows]
            else:
                result = []
        else:
            result = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return result
    
    def _fetchone(self, query, params=None):
        """Execute a query and fetch one result as dict."""
        conn, cursor = self._execute(query, params)
        row = cursor.fetchone()
        
        if row:
            if USING_TURSO and self.turso_url and self.turso_token:
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row))
            else:
                result = dict(row)
        else:
            result = None
        
        conn.close()
        return result
    
    def _safe_add_column(self, table, column, col_type):
        """Safely add a column to a table if it doesn't exist."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    def init_database(self):
        """Initialize the database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Leaders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                dealership TEXT,
                cohort TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assessment_year INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                portal_token TEXT,
                portal_email_sent_at TIMESTAMP,
                nomination_reminder_sent_at TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Migration: Add columns if they don't exist (for existing databases)
        self._safe_add_column("leaders", "portal_token", "TEXT")
        self._safe_add_column("leaders", "portal_email_sent_at", "TIMESTAMP")
        self._safe_add_column("leaders", "nomination_reminder_sent_at", "TIMESTAMP")
        # The leader's own record of who they nominated. Deliberately stored on
        # the LEADER, not on `raters`: identity severing nulls raters.name and
        # raters.email at submission, so a roster held there would be destroyed
        # for exactly the people who responded (and the blank rows would leak
        # per-person response status). Held here it survives severing, and the
        # only link back to a rater row is the email address, which severing
        # removes as a side effect. See CLAUDE.md section 5.
        self._safe_add_column("leaders", "nomination_roster", "TEXT")
        # Self-identified development priorities, captured at self-assessment.
        # Stored on the LEADER rather than the Self rater row because they are
        # the leader's own development intent, not anonymous feedback, and they
        # need to outlive any change to how self-assessment rows are handled.
        self._safe_add_column("leaders", "development_priorities", "TEXT")
        
        # Continue with rest of schema
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Raters table (people providing feedback)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                leader_id INTEGER NOT NULL,
                name TEXT,
                email TEXT,
                relationship TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                reminder_sent_at TIMESTAMP,
                draft_ratings TEXT,
                draft_comments TEXT,
                draft_saved_at TIMESTAMP,
                FOREIGN KEY (leader_id) REFERENCES leaders(id)
            )
        """)
        
        # Ratings table (individual item scores)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rater_id INTEGER NOT NULL,
                item_number INTEGER NOT NULL,
                score INTEGER,
                no_opportunity BOOLEAN DEFAULT FALSE,
                not_applicable BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rater_id) REFERENCES raters(id),
                UNIQUE(rater_id, item_number)
            )
        """)
        
        # Comments table (qualitative feedback)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rater_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                comment_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rater_id) REFERENCES raters(id)
            )
        """)
        
        # Generated reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                leader_id INTEGER NOT NULL,
                report_type TEXT NOT NULL,
                file_path TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assessment_year INTEGER,
                FOREIGN KEY (leader_id) REFERENCES leaders(id)
            )
        """)
        
        # Historical data for progress reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                leader_id INTEGER NOT NULL,
                assessment_year INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (leader_id) REFERENCES leaders(id)
            )
        """)
        
        # Cohorts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cohorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Email log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rater_id INTEGER,
                leader_id INTEGER,
                email_type TEXT NOT NULL,
                to_email TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rater_id) REFERENCES raters(id),
                FOREIGN KEY (leader_id) REFERENCES leaders(id)
            )
        """)

        # i18n foundation (round-two rater nomination, October cohort): stores
        # translated strings keyed by string_key + locale, looked up at render
        # time via get_translation(). Not used for scores - only item text, UI
        # copy, and email copy get translated. A missing row for a given
        # key/locale is not an error: get_translation() falls back to the
        # current English string, which is what ships until real translations
        # are commissioned. See CLAUDE.md/the i18n build instructions for the
        # full string_key conventions.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                string_key TEXT NOT NULL,
                locale TEXT NOT NULL,
                string_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(string_key, locale)
            )
        """)

        conn.commit()
        conn.close()

        # Migration: Add draft columns to raters table for existing databases
        self._safe_add_column("raters", "draft_ratings", "TEXT")
        self._safe_add_column("raters", "draft_comments", "TEXT")
        self._safe_add_column("raters", "draft_saved_at", "TIMESTAMP")
        # Rater's chosen UI/form language (e.g. 'en', 'ar', 'de'...). NULL until
        # they actively pick one on first visit to the feedback form - treated
        # identically to 'en' at every read site (see get_translation), never
        # backfilled for existing rows.
        self._safe_add_column("raters", "locale", "TEXT")
    
    # ==========================================
    # LEADER MANAGEMENT
    # ==========================================
    
    def add_leader(self, name, email=None, dealership=None, cohort=None):
        """Add a new leader to the system."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO leaders (name, email, dealership, cohort)
            VALUES (?, ?, ?, ?)
        """, (name, email, dealership, cohort))
        
        leader_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return leader_id
    
    def get_all_leaders(self):
        """Get all leaders with their response counts."""
        return self._fetchall("""
            SELECT 
                l.*,
                COUNT(DISTINCT r.id) as total_raters,
                COUNT(DISTINCT CASE WHEN r.completed_at IS NOT NULL THEN r.id END) as completed_raters,
                COUNT(DISTINCT CASE WHEN r.relationship = 'Self' AND r.completed_at IS NOT NULL THEN r.id END) as self_completed
            FROM leaders l
            LEFT JOIN raters r ON l.id = r.leader_id
            WHERE l.status = 'active'
            GROUP BY l.id
            ORDER BY l.name
        """)
    
    def get_leader(self, leader_id):
        """Get a specific leader by ID."""
        return self._fetchone("SELECT * FROM leaders WHERE id = ?", (leader_id,))
    
    def update_leader(self, leader_id, **kwargs):
        """Update leader details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        valid_fields = ['name', 'email', 'dealership', 'cohort', 'assessment_year', 'status', 
                       'portal_token', 'portal_email_sent_at', 'nomination_reminder_sent_at']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if updates:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = tuple(list(updates.values()) + [leader_id])
            
            cursor.execute(f"UPDATE leaders SET {set_clause} WHERE id = ?", values)
            conn.commit()
        
        conn.close()
    
    def delete_leader(self, leader_id):
        """Soft delete a leader (set status to inactive)."""
        self.update_leader(leader_id, status='inactive')
    
    def get_leaders_by_cohort(self, cohort_name):
        """Get all active leaders in a specific cohort."""
        return self._fetchall("""
            SELECT l.*,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id) as total_raters,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.completed_at IS NOT NULL) as completed_raters,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.relationship = 'Self' AND r.completed_at IS NOT NULL) as self_completed
            FROM leaders l
            WHERE l.status = 'active' AND l.cohort = ?
            ORDER BY l.name
        """, (cohort_name,))
    
    def generate_portal_token(self, leader_id):
        """Generate a unique portal token for a leader."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        token = secrets.token_urlsafe(8)
        
        try:
            cursor.execute("""
                UPDATE leaders SET portal_token = ? WHERE id = ?
            """, (token, leader_id))
            
            conn.commit()
        except Exception as e:
            conn.close()
            raise Exception(f"Failed to set portal token: {str(e)}. The portal_token column may not exist.")
        
        conn.close()
        
        return token
    
    def get_leader_by_portal_token(self, token):
        """Get leader information by their portal token."""
        return self._fetchone("""
            SELECT 
                l.*,
                (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id) as total_raters,
                (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.completed_at IS NOT NULL) as completed_raters,
                (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.relationship = 'Self' AND r.completed_at IS NOT NULL) as self_completed
            FROM leaders l
            WHERE l.portal_token = ? AND l.status = 'active'
        """, (token,))
    
    def mark_portal_email_sent(self, leader_id):
        """Mark that the portal invitation email has been sent."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE leaders SET portal_email_sent_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (leader_id,))
        
        conn.commit()
        conn.close()
    
    def mark_nomination_reminder_sent(self, leader_id):
        """Mark that a nomination reminder has been sent."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE leaders SET nomination_reminder_sent_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (leader_id,))
        
        conn.commit()
        conn.close()
    
    def get_leaders_needing_portal_email(self):
        """Get leaders who have completed self-assessment but haven't received portal email."""
        return self._fetchall("""
            SELECT l.*
            FROM leaders l
            JOIN raters r ON l.id = r.leader_id
            WHERE l.status = 'active'
              AND l.portal_email_sent_at IS NULL
              AND r.relationship = 'Self'
              AND r.completed_at IS NOT NULL
        """)
    
    def get_leaders_needing_nomination_reminder(self, days_since_portal_email=7):
        """Get leaders who received portal email but haven't nominated minimum raters."""
        return self._fetchall("""
            SELECT l.*,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.relationship != 'Self') as nominated_count
            FROM leaders l
            WHERE l.status = 'active'
              AND l.portal_email_sent_at IS NOT NULL
              AND (l.nomination_reminder_sent_at IS NULL 
                   OR julianday('now') - julianday(l.nomination_reminder_sent_at) > ?)
              AND (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.relationship != 'Self') < 5
        """, (days_since_portal_email,))
    
    # ==========================================
    # NOMINATION ROSTER
    # ==========================================
    #
    # The leader's own durable record of who they nominated. Survives identity
    # severing because it lives on the `leaders` row, not on `raters`. Used for
    # display and for email correction only — never for scoring, and never
    # joined to responses.

    def get_nomination_roster(self, leader_id):
        """
        Return the leader's nomination roster as a list of dicts
        ({'name', 'email', 'relationship'}).

        Falls back to building the roster from the current `raters` rows if the
        column is empty (i.e. a leader nominated before this column existed).
        That backfill is only accurate for raters not yet severed, which is
        correct: severed rows carry no identity to recover.
        """
        row = self._fetchone(
            "SELECT nomination_roster FROM leaders WHERE id = ?", (leader_id,)
        )
        if row and row.get('nomination_roster'):
            try:
                return json.loads(row['nomination_roster'])
            except (ValueError, TypeError):
                pass

        # Backfill from raters for pre-existing data
        backfilled = [
            {
                'name': r.get('name'),
                'email': r.get('email'),
                'relationship': r['relationship'],
            }
            for r in self.get_raters_for_leader(leader_id)
            if r['relationship'] != 'Self' and (r.get('name') or r.get('email'))
        ]
        if backfilled:
            self._save_nomination_roster(leader_id, backfilled)
        return backfilled

    def _save_nomination_roster(self, leader_id, roster):
        """Persist the roster list back to the leader row."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE leaders SET nomination_roster = ? WHERE id = ?",
            (json.dumps(roster), leader_id)
        )
        conn.commit()
        conn.close()

    def add_to_nomination_roster(self, leader_id, name, email, relationship):
        """
        Append a nominee to the leader's roster, if not already present.

        The dedupe matters: callers add the rater row first, so on a leader whose
        roster column is still empty the backfill in get_nomination_roster
        already picks up the rater that is about to be appended here. Matching is
        by email where there is one, since that is the link to the rater row,
        and by name plus relationship otherwise.
        """
        roster = self.get_nomination_roster(leader_id)

        for entry in roster:
            if email and entry.get('email') == email:
                return
            if not email and entry.get('name') == name \
                    and entry.get('relationship') == relationship:
                return

        roster.append({'name': name, 'email': email, 'relationship': relationship})
        self._save_nomination_roster(leader_id, roster)

    def update_nomination_entry(self, leader_id, old_email,
                                new_email=None, new_relationship=None):
        """
        Correct a nominee's email address and/or relationship on the roster.

        Returns True if a roster entry was updated. Matching is by the old
        address, which is also the only link back to the `raters` row — once a
        rater is severed their email is NULL, so no match exists and the
        response cannot be re-identified by writing an address back.
        """
        roster = self.get_nomination_roster(leader_id)
        updated = False
        for entry in roster:
            if entry.get('email') == old_email:
                if new_email:
                    entry['email'] = new_email
                if new_relationship:
                    entry['relationship'] = new_relationship
                updated = True
                break
        if updated:
            self._save_nomination_roster(leader_id, roster)
        return updated

    def get_unsevered_rater_by_email(self, leader_id, email):
        """
        Find a rater row for this leader still carrying the given email.

        Returns None once the rater has been severed, which is how the email
        correction path stays safe: there is nothing to write an address onto.
        """
        if not email:
            return None
        return self._fetchone("""
            SELECT *,
                CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END as completed
            FROM raters
            WHERE leader_id = ? AND email = ?
        """, (leader_id, email))

    # ==========================================
    # SELF-IDENTIFIED DEVELOPMENT PRIORITIES
    # ==========================================

    def get_development_priorities(self, leader_id):
        """
        Return the leader's ranked development priorities as a list of dicts
        ({'rank', 'dimension', 'actions'}), lowest rank first. Empty list if none.
        """
        row = self._fetchone(
            "SELECT development_priorities FROM leaders WHERE id = ?", (leader_id,)
        )
        if not row or not row.get('development_priorities'):
            return []
        try:
            priorities = json.loads(row['development_priorities'])
        except (ValueError, TypeError):
            return []
        return sorted(priorities, key=lambda p: p.get('rank', 0))

    def save_development_priorities(self, leader_id, priorities):
        """
        Replace the leader's development priorities.

        Args:
            leader_id: The leader's ID
            priorities: List of {'rank': int, 'dimension': str, 'actions': str}.
                Entries with no dimension are dropped, so a partially filled
                form saves only what was actually chosen.
        """
        cleaned = [
            {
                'rank': p.get('rank'),
                'dimension': p.get('dimension'),
                'actions': (p.get('actions') or '').strip(),
            }
            for p in priorities
            if p.get('dimension')
        ]

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE leaders SET development_priorities = ? WHERE id = ?",
            (json.dumps(cleaned), leader_id)
        )
        conn.commit()
        conn.close()

    # ==========================================
    # RATER MANAGEMENT
    # ==========================================

    def generate_token(self):
        """Generate a unique, URL-safe token."""
        return secrets.token_urlsafe(6)
    
    def add_rater(self, leader_id, relationship, name=None, email=None):
        """Add a rater for a leader and generate their unique link."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        token = self.generate_token()
        
        cursor.execute("""
            INSERT INTO raters (leader_id, name, email, relationship, token)
            VALUES (?, ?, ?, ?, ?)
        """, (leader_id, name, email, relationship, token))
        
        rater_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return rater_id, token
    
    def get_rater_by_token(self, token):
        """Get rater information by their unique token."""
        return self._fetchone("""
            SELECT 
                r.*,
                l.name as leader_name,
                l.dealership as leader_dealership,
                CASE WHEN r.completed_at IS NOT NULL THEN 1 ELSE 0 END as completed
            FROM raters r
            JOIN leaders l ON r.leader_id = l.id
            WHERE r.token = ?
        """, (token,))
    
    def get_rater(self, rater_id):
        """Get a specific rater by ID."""
        return self._fetchone("""
            SELECT 
                r.*,
                l.name as leader_name,
                CASE WHEN r.completed_at IS NOT NULL THEN 1 ELSE 0 END as completed
            FROM raters r
            JOIN leaders l ON r.leader_id = l.id
            WHERE r.id = ?
        """, (rater_id,))
    
    def get_raters_for_leader(self, leader_id):
        """Get all raters for a specific leader."""
        return self._fetchall("""
            SELECT *,
                CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END as completed,
                CASE WHEN draft_saved_at IS NOT NULL AND completed_at IS NULL THEN 1 ELSE 0 END as has_draft
            FROM raters
            WHERE leader_id = ?
            ORDER BY 
                CASE relationship 
                    WHEN 'Self' THEN 1 
                    WHEN 'Boss' THEN 2 
                    WHEN 'Peers' THEN 3 
                    WHEN 'DRs' THEN 4 
                    ELSE 5 
                END
        """, (leader_id,))
    
    def update_rater(self, rater_id, **kwargs):
        """
        Update rater details (name, email, relationship).

        CALLERS MUST NOT change `relationship` on a rater who has already
        submitted. Their answers were given in the context of the relationship
        they were invited under, so recategorising them afterwards would
        misrepresent their input, and moving anonymous responses between groups
        would let someone probe which group a given response sits in. The portal
        enforces this by only ever resolving the rater through
        get_unsevered_rater_by_email, which finds nothing once they have
        submitted.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        valid_fields = ['name', 'email', 'relationship']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if updates:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = tuple(list(updates.values()) + [rater_id])
            
            cursor.execute(f"UPDATE raters SET {set_clause} WHERE id = ?", values)
            conn.commit()
        
        conn.close()
    
    def update_rater_reminder_sent(self, rater_id):
        """Update the reminder_sent_at timestamp for a rater."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE raters SET reminder_sent_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (rater_id,))
        
        conn.commit()
        conn.close()
    
    def reset_rater_response(self, rater_id):
        """
        Testing helper: clear a rater's submitted response (ratings, comments,
        completed_at) so the same rater row and token can be resubmitted or
        re-simulated from a clean slate.

        Does NOT restore identity. Real or simulated, a completed rater has
        already been through sever_rater_identity, which nulls name and email
        irreversibly by design — this only clears response content and reopens
        completed_at, it never touches identity. Not for use on a genuinely
        completed real rater outside testing: it discards their actual
        feedback with no way to recover it.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM ratings WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM comments WHERE rater_id = ?", (rater_id,))
        cursor.execute("""
            UPDATE raters
            SET completed_at = NULL,
                draft_ratings = NULL,
                draft_comments = NULL,
                draft_saved_at = NULL
            WHERE id = ?
        """, (rater_id,))

        conn.commit()
        conn.close()

    def mark_rater_complete(self, rater_id):
        """Mark a rater as having completed their feedback and clear draft."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE raters
            SET completed_at = CURRENT_TIMESTAMP,
                draft_ratings = NULL,
                draft_comments = NULL,
                draft_saved_at = NULL
            WHERE id = ?
        """, (rater_id,))

        conn.commit()
        conn.close()

    def sever_rater_identity(self, rater_id):
        """
        Irreversibly detach a submitted response from the person who gave it
        (anonymity severing, Model A).

        Nulls `raters.name` AND `raters.email`, and overwrites
        `email_log.to_email` with a placeholder (that column is NOT NULL, so it
        cannot be set to NULL). Token, relationship and all responses are
        preserved, so scoring and group attribution are unaffected, but the
        response can no longer be resolved to a named individual.

        Both identifiers must go: the name is the stronger of the two, so
        nulling only the email would sever nothing meaningful.

        The leader's own record of who they nominated is unaffected, because it
        lives on `leaders.nomination_roster` rather than on this row.

        IRREVERSIBLE BY DESIGN. Called from submit_feedback after the completion
        commit. Never call it on a rater who has not submitted.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE raters SET name = NULL, email = NULL WHERE id = ?",
            (rater_id,)
        )
        cursor.execute(
            "UPDATE email_log SET to_email = '[severed]' WHERE rater_id = ?",
            (rater_id,)
        )

        conn.commit()
        conn.close()
    
    def delete_rater(self, rater_id):
        """
        Delete a rater and their responses.

        Refuses to delete a rater who has already responded — this is the
        DB-level guard behind the UI's "only remove raters who haven't
        responded yet" rule, so it holds even if the UI check is bypassed.

        Returns:
            True if deleted, False if refused because the rater has already completed.
        """
        row = self._fetchone("SELECT completed_at FROM raters WHERE id = ?", (rater_id,))
        if row is None or row['completed_at'] is not None:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM ratings WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM comments WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM raters WHERE id = ?", (rater_id,))

        conn.commit()
        conn.close()
        return True

    # ==========================================
    # TRANSLATIONS (i18n)
    # ==========================================

    def get_translation(self, string_key, locale, fallback_text=""):
        """Return the translated string, or fallback_text if none exists.

        Falls back (never raises, never returns a blank string) when locale is
        None, 'en', or there's simply no row yet for this key/locale - which is
        the expected state for every key until real translations are
        commissioned. fallback_text is always the current English string
        already hardcoded at the call site, so a report/form with zero
        translation rows renders identically to today's English version.
        """
        if not locale or locale == 'en':
            return fallback_text

        row = self._fetchone(
            "SELECT string_value FROM translations WHERE string_key = ? AND locale = ?",
            (string_key, locale),
        )
        if row is None or not row['string_value']:
            return fallback_text
        return row['string_value']

    def set_rater_locale(self, rater_id, locale):
        """Update raters.locale - the language a rater chose for the form."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE raters SET locale = ? WHERE id = ?", (locale, rater_id))
        conn.commit()
        conn.close()

    # ==========================================
    # DRAFT SAVE & RESUME
    # ==========================================
    
    def save_draft(self, rater_id, ratings, comments):
        """
        Save partial feedback as a draft for later resumption.
        
        Args:
            rater_id: The rater's ID
            ratings: Dict of {item_number: rating_value} (only answered items)
            comments: Dict of {section: comment_text}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert int keys to strings for JSON serialisation.
        # NB: "no opportunity to observe" is a real, meaningful answer of 0/"0" —
        # must not be filtered out as falsy alongside genuinely unanswered items.
        ratings_json = json.dumps({str(k): v for k, v in ratings.items() if v != '' and v is not None})
        comments_json = json.dumps({k: v for k, v in comments.items() if v and v.strip()})
        
        cursor.execute("""
            UPDATE raters 
            SET draft_ratings = ?,
                draft_comments = ?,
                draft_saved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (ratings_json, comments_json, rater_id))
        
        conn.commit()
        conn.close()
    
    def get_draft(self, rater_id):
        """
        Retrieve a saved draft for a rater.
        
        Returns:
            Tuple of (ratings_dict, comments_dict, saved_at) or (None, None, None)
        """
        row = self._fetchone("""
            SELECT draft_ratings, draft_comments, draft_saved_at
            FROM raters
            WHERE id = ? AND draft_saved_at IS NOT NULL AND completed_at IS NULL
        """, (rater_id,))
        
        if row and row.get('draft_ratings'):
            ratings = json.loads(row['draft_ratings'])
            # Convert string keys back to ints
            ratings = {int(k): v for k, v in ratings.items()}
            
            comments = json.loads(row['draft_comments']) if row.get('draft_comments') else {}
            saved_at = row['draft_saved_at']
            
            return ratings, comments, saved_at
        
        return None, None, None
    
    def clear_draft(self, rater_id):
        """Clear a saved draft (e.g., after successful submission)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE raters 
            SET draft_ratings = NULL, draft_comments = NULL, draft_saved_at = NULL
            WHERE id = ?
        """, (rater_id,))
        
        conn.commit()
        conn.close()
    
    # ==========================================
    # FEEDBACK SUBMISSION
    # ==========================================
    
    def submit_ratings(self, rater_id, ratings):
        """
        Submit ratings for a rater.
        
        Args:
            rater_id: The rater's ID
            ratings: Dict of {item_number: score} where score is 1-5 on the frequency
                scale, or 0 / 'NO' for "no opportunity to observe" (excluded from
                averages, not counted as a low score). 'NA' is accepted for
                backward compatibility with older callers.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        for item_num, score in ratings.items():
            no_opp = score == 'NO' or score == 0 or score == '0'
            not_applicable = score == 'NA'
            actual_score = None if (no_opp or not_applicable) else int(score)
            
            cursor.execute("""
                INSERT OR REPLACE INTO ratings (rater_id, item_number, score, no_opportunity, not_applicable)
                VALUES (?, ?, ?, ?, ?)
            """, (rater_id, item_num, actual_score, no_opp, not_applicable))
        
        conn.commit()
        conn.close()
    
    def submit_comments(self, rater_id, comments):
        """
        Submit comments for a rater.
        
        Args:
            rater_id: The rater's ID
            comments: Dict of {section: comment_text}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for section, text in comments.items():
            if text and text.strip():
                cursor.execute("""
                    INSERT INTO comments (rater_id, section, comment_text)
                    VALUES (?, ?, ?)
                """, (rater_id, section, text.strip()))
        
        conn.commit()
        conn.close()
    
    def submit_feedback(self, rater_id, ratings, comments):
        """
        Submit complete feedback (ratings + comments), mark as complete, and
        sever the responder's identity.

        Severing runs AFTER the completion commit so a failure part-way through
        cannot leave a severed rater with no recorded response. It is
        irreversible: see sever_rater_identity.
        """
        self.submit_ratings(rater_id, ratings)
        self.submit_comments(rater_id, comments)
        self.mark_rater_complete(rater_id)
        self.sever_rater_identity(rater_id)
    
    # ==========================================
    # EMAIL LOGGING
    # ==========================================
    
    def log_email(self, email_type, to_email, success, message=None, rater_id=None, leader_id=None):
        """Log an email send attempt."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO email_log (rater_id, leader_id, email_type, to_email, success, message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (rater_id, leader_id, email_type, to_email, success, message))
        
        conn.commit()
        conn.close()
    
    def get_email_log_for_leader(self, leader_id, limit=50):
        """Get email log entries for a leader's raters."""
        return self._fetchall("""
            SELECT 
                el.*,
                r.name as rater_name,
                r.relationship
            FROM email_log el
            LEFT JOIN raters r ON el.rater_id = r.id
            WHERE el.leader_id = ? OR r.leader_id = ?
            ORDER BY el.sent_at DESC
            LIMIT ?
        """, (leader_id, leader_id, limit))
    
    def get_last_email_for_rater(self, rater_id):
        """Get the most recent email sent to a rater."""
        return self._fetchone("""
            SELECT * FROM email_log
            WHERE rater_id = ?
            ORDER BY sent_at DESC
            LIMIT 1
        """, (rater_id,))
    
    def get_raters_pending_invitation(self, leader_id):
        """
        Raters for this leader who haven't yet been sent an invitation email.

        Adding a rater (single form or CSV import) no longer sends the
        invitation itself - that's a separate, deliberate action the leader
        triggers after reviewing the roster, so a typo'd name/email/
        relationship can be caught and corrected first rather than mailed out
        immediately. Excludes Self (never invited via this path) and anyone
        who has already completed their response (can't happen without a
        prior invitation in practice, but excluded defensively either way).

        Also requires a non-null email. Found via testing: a handful of old
        rows on this leader predate the roster/name/email being required
        together, so they carry no email at all - send_rater_invitation can
        never do anything with those, and they don't appear in
        get_nomination_roster either (its own backfill requires a name or
        email), so without this filter they inflated the pending count with
        raters the leader has no way to see or act on.
        """
        return self._fetchall("""
            SELECT * FROM raters
            WHERE leader_id = ?
              AND relationship != 'Self'
              AND completed_at IS NULL
              AND email IS NOT NULL
              AND id NOT IN (
                  SELECT rater_id FROM email_log
                  WHERE email_type = 'invitation' AND success = 1 AND rater_id IS NOT NULL
              )
            ORDER BY created_at
        """, (leader_id,))

    def get_failed_invitation_emails(self, leader_id):
        """
        Email addresses among this leader's raters that failed to send on
        their last invitation attempt and have never succeeded since.

        Used to flag a specific row as needing attention on the portal's
        nomination list, distinct from a row that just hasn't been sent yet -
        a bulk send can partially fail, and without this there's no way to
        tell which of several pending people actually needs a fixed email
        address rather than just a resend. Matched on email (email_log.to_email)
        rather than rater_id, since that's what the roster itself is keyed on.
        """
        rows = self._fetchall("""
            SELECT DISTINCT el.to_email
            FROM email_log el
            JOIN raters r ON r.id = el.rater_id
            WHERE r.leader_id = ?
              AND el.email_type = 'invitation'
              AND el.success = 0
              AND el.rater_id NOT IN (
                  SELECT rater_id FROM email_log
                  WHERE email_type = 'invitation' AND success = 1 AND rater_id IS NOT NULL
              )
        """, (leader_id,))
        return {row['to_email'].strip().lower() for row in rows if row.get('to_email')}

    def get_email_stats_for_leader(self, leader_id):
        """Get email statistics for a leader's assessment."""
        return self._fetchone("""
            SELECT 
                COUNT(DISTINCT CASE WHEN el.email_type = 'invitation' AND el.success = 1 THEN el.rater_id END) as invitations_sent,
                COUNT(DISTINCT CASE WHEN el.email_type = 'reminder' AND el.success = 1 THEN el.rater_id END) as reminders_sent,
                (SELECT COUNT(*) FROM raters WHERE leader_id = ? AND email IS NOT NULL) as raters_with_email
            FROM email_log el
            JOIN raters r ON el.rater_id = r.id
            WHERE r.leader_id = ?
        """, (leader_id, leader_id))
    
    # ==========================================
    # DATA RETRIEVAL FOR REPORTS
    # ==========================================
    
    def get_leader_feedback_data(self, leader_id):
        """
        Get all feedback data for a leader in the format needed for report generation.
        
        Applies anonymity threshold - groups with fewer than ANONYMITY_THRESHOLD
        respondents have their data folded into 'Others' category. If 'Others'
        itself is still thin after absorbing them, it folds again into whichever
        of Peers/DRs is still standing on its own (see the fold cascade below).
        Boss and Self are exempt from this threshold.
        
        Returns:
            Tuple of (data_dict, comments_dict) matching the report generator format
        """
        from framework import DIMENSIONS, ANONYMITY_THRESHOLD, get_item_text
        
        # Get response counts by relationship
        rows = self._fetchall("""
            SELECT relationship, COUNT(*) as count
            FROM raters
            WHERE leader_id = ? AND completed_at IS NOT NULL
            GROUP BY relationship
        """, (leader_id,))
        
        raw_response_counts = {}
        relationship_map = {'Self': 'Self', 'Boss': 'Boss', 'Peers': 'Peers', 
                          'DRs': 'DRs', 'Others': 'Others'}
        for row in rows:
            raw_response_counts[relationship_map.get(row['relationship'], row['relationship'])] = row['count']
        
        # Determine which groups meet the anonymity threshold.
        #
        # TIER 1 — Peers and DRs below the threshold FOLD INTO Others, which is
        # safe because merging hides the split: you cannot recover a folded
        # group's mean from a combined one.
        #
        # TIER 2 — 'Others' used to have nothing to fold into if it was STILL thin
        # after absorbing tier 1. It was whitelisted as always-visible, which meant
        # a single "Other" respondent was published as a group of one with their
        # own score. That broke the hard floor. The fix folded it the other way:
        # if Others (after absorbing tier 1) is still below the threshold, it
        # folds INTO whichever of Peers/DRs is still standing on its own (prefer
        # Peers; fall back to DRs). This preserves those responses inside a
        # standing group's average and comments instead of throwing them away.
        #
        # Tier 2 can only fail to find a home when NEITHER Peers nor DRs stands —
        # i.e. every non-Boss/Self group is thin. Given MIN_RESPONSES_FOR_REPORT
        # (5) and Boss's 2-person cap, at least 3 non-Boss responses always exist
        # by the time a report is generated, so folding every thin group together
        # always clears ANONYMITY_THRESHOLD (3) on its own — this branch is
        # unreachable today. SUPPRESSION below is kept as a defensive fallback in
        # case that gate ever changes, not as the expected path.
        #
        # Suppression, when it does fire, has to come out of Combined too, not
        # just the per-group display. Combined is the mean of the group means, so
        # if every other group is shown then a suppressed group's mean is
        # recoverable by simple subtraction. Suppression that leaves the number
        # derivable is not suppression.
        visible_groups = ['Self', 'Boss']
        hidden_groups = []

        for group in ['Peers', 'DRs']:
            count = raw_response_counts.get(group, 0)
            if count >= ANONYMITY_THRESHOLD:
                visible_groups.append(group)
            elif count > 0:
                hidden_groups.append(group)

        # What Others will hold once the tier 1 groups are folded in
        others_count = raw_response_counts.get('Others', 0)
        for group in hidden_groups:
            others_count += raw_response_counts.get(group, 0)

        others_suppressed = False
        suppressed_groups = []
        others_fold_target = None

        if others_count >= ANONYMITY_THRESHOLD:
            visible_groups.append('Others')
        elif others_count > 0:
            for candidate in ['Peers', 'DRs']:
                if candidate in visible_groups:
                    others_fold_target = candidate
                    break
            if others_fold_target is None:
                # Nowhere left to fold into — every non-Boss group is thin.
                others_suppressed = True
                suppressed_groups = sorted(
                    set(hidden_groups) |
                    ({'Others'} if raw_response_counts.get('Others', 0) else set())
                )

        # Build response_counts for the groups that are actually reportable
        response_counts = {}
        for group in ['Self', 'Boss', 'Peers', 'DRs']:
            if group in visible_groups:
                response_counts[group] = raw_response_counts.get(group, 0)
                if group == others_fold_target:
                    response_counts[group] += others_count

        if 'Others' in visible_groups:
            response_counts['Others'] = others_count

        def map_group(group):
            if group in hidden_groups:
                return others_fold_target or 'Others'
            if group == 'Others' and others_fold_target:
                return others_fold_target
            return group
        
        # Get all ratings
        rating_rows = self._fetchall("""
            SELECT 
                rt.item_number,
                r.relationship,
                rt.score,
                rt.no_opportunity
            FROM ratings rt
            JOIN raters r ON rt.rater_id = r.id
            WHERE r.leader_id = ? AND r.completed_at IS NOT NULL
        """, (leader_id,))
        
        # Build the by_item structure (45 items)
        by_item = {}
        no_opportunity = {}

        # NB: 'text' is always the They-form. It suits the Full 360, where the item
        # was put to others that way. The Self-Assessment report must NOT use it:
        # that report's only rater was the leader, who answered the I-form, so
        # add_dimension_section resolves the wording itself via get_item_text.
        for item_num in range(1, 46):
            by_item[item_num] = {'text': get_item_text(item_num, 'Others')}
        
        # Collect scores by item and mapped group
        item_scores = {}
        item_no_opp = {}
        
        for row in rating_rows:
            item_num = row['item_number']
            raw_group = relationship_map.get(row['relationship'], row['relationship'])
            mapped_group = map_group(raw_group)
            
            if item_num not in item_scores:
                item_scores[item_num] = {}
                item_no_opp[item_num] = {}
            
            if mapped_group not in item_scores[item_num]:
                item_scores[item_num][mapped_group] = []
                item_no_opp[item_num][mapped_group] = 0
            
            if row['no_opportunity']:
                item_no_opp[item_num][mapped_group] += 1
            elif row['score'] is not None:
                item_scores[item_num][mapped_group].append(row['score'])
        
        # Calculate averages per item per group
        for item_num in range(1, 46):
            if item_num in item_scores:
                for group, scores in item_scores[item_num].items():
                    if scores:
                        by_item[item_num][group] = round(sum(scores) / len(scores), 1)

            if item_num in item_no_opp:
                total_no_opp = sum(item_no_opp[item_num].values())
                if total_no_opp > 0:
                    no_opportunity[item_num] = {
                        'count': total_no_opp,
                        'groups': [],
                        'text': get_item_text(item_num, 'Others')
                    }
                    for group, count in item_no_opp[item_num].items():
                        no_opportunity[item_num]['groups'].extend([group] * count)
        
        # Drop a suppressed Others group from the per-item scores before anything
        # is averaged, so it cannot reach Combined or the dimension rollups
        if others_suppressed:
            for item in by_item.values():
                item.pop('Others', None)

        # Calculate combined scores and gaps
        for item_num in by_item:
            item = by_item[item_num]
            other_scores = []
            for g in ['Boss', 'Peers', 'DRs', 'Others']:
                if g in visible_groups:
                    if item.get(g) is not None:
                        other_scores.append(item[g])

            if other_scores:
                item['Combined'] = round(sum(other_scores) / len(other_scores), 2)
                if item.get('Self') is not None:
                    item['Gap'] = round(item['Self'] - item['Combined'], 2)
        
        # Calculate dimension averages
        by_dimension = {}
        for dim_name, (start, end) in DIMENSIONS.items():
            dim_scores = {g: [] for g in ['Self', 'Boss', 'Peers', 'DRs', 'Others', 'Combined']}
            
            for item_num in range(start, end + 1):
                item = by_item.get(item_num, {})
                for g in dim_scores.keys():
                    if item.get(g) is not None:
                        dim_scores[g].append(item[g])
            
            by_dimension[dim_name] = {}
            for g, scores in dim_scores.items():
                if scores and (g in visible_groups or g in ['Self', 'Combined']):
                    by_dimension[dim_name][g] = round(sum(scores) / len(scores), 2)
            
            if 'Self' in by_dimension[dim_name] and 'Combined' in by_dimension[dim_name]:
                by_dimension[dim_name]['Gap'] = round(
                    by_dimension[dim_name]['Self'] - by_dimension[dim_name]['Combined'], 2
                )
        
        data = {
            'by_item': by_item,
            'by_dimension': by_dimension,
            'development_priorities': self.get_development_priorities(leader_id),
            'response_counts': response_counts,
            'raw_response_counts': raw_response_counts,
            'no_opportunity': no_opportunity,
            'visible_groups': visible_groups,
            'hidden_groups': hidden_groups,
            'suppressed_groups': suppressed_groups,
            'suppressed_count': others_count if others_suppressed else 0,
            'others_fold_target': others_fold_target,
            # True whenever ANY tier of the fold cascade actually fired — tier 1
            # (hidden_groups non-empty), tier 2 (others_fold_target set), or the
            # dormant suppression fallback. Checking hidden_groups alone missed
            # the tier-2-only case (Others thin on its own while Peers/DRs are
            # both healthy), which folds silently with hidden_groups still empty.
            'anonymity_applied': len(hidden_groups) > 0 or bool(suppressed_groups) or bool(others_fold_target)
        }
        
        # Get comments
        comment_rows = self._fetchall("""
            SELECT c.section, c.comment_text, r.relationship
            FROM comments c
            JOIN raters r ON c.rater_id = r.id
            WHERE r.leader_id = ? AND r.completed_at IS NOT NULL
        """, (leader_id,))
        
        comments = {
            'by_section': {},
            'keep': [],
            'change': []
        }

        for row in comment_rows:
            section = row['section']
            raw_group = row['relationship']
            mapped_group = map_group(raw_group)

            # A suppressed group's verbatims are held back too. Showing them, even
            # unlabelled, would tell the leader they came from the two or three
            # people in that group, since every other comment carries its group.
            if others_suppressed and mapped_group == 'Others':
                continue

            comment = {'group': mapped_group, 'text': row['comment_text']}

            if section == 'keep':
                comments['keep'].append(comment)
            elif section == 'change':
                comments['change'].append(comment)
            else:
                if section not in comments['by_section']:
                    comments['by_section'][section] = []
                comments['by_section'][section].append(comment)
        
        return data, comments
    
    def save_historical_data(self, leader_id, year, data):
        """Save a snapshot of feedback data for historical comparison."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO historical_scores (leader_id, assessment_year, data_json)
            VALUES (?, ?, ?)
        """, (leader_id, year, json.dumps(data)))
        
        conn.commit()
        conn.close()
    
    def get_historical_data(self, leader_id, year):
        """Retrieve historical feedback data for a specific year."""
        row = self._fetchone("""
            SELECT data_json FROM historical_scores
            WHERE leader_id = ? AND assessment_year = ?
            ORDER BY created_at DESC LIMIT 1
        """, (leader_id, year))
        
        return json.loads(row['data_json']) if row else None
    
    # ==========================================
    # COHORT MANAGEMENT
    # ==========================================
    
    def add_cohort(self, name):
        """Add a new cohort."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO cohorts (name) VALUES (?)",
                (name,)
            )
            conn.commit()
            cohort_id = cursor.lastrowid
        except:
            cohort_id = None
        
        conn.close()
        return cohort_id
    
    def get_all_cohorts(self):
        """Get all cohorts."""
        return self._fetchall("SELECT * FROM cohorts ORDER BY name")
    
    def delete_cohort(self, cohort_id):
        """Delete a cohort (doesn't affect leaders assigned to it)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM cohorts WHERE id = ?", (cohort_id,))
        
        conn.commit()
        conn.close()
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    def get_dashboard_stats(self):
        """Get overall statistics for the admin dashboard."""
        return self._fetchone("""
            SELECT 
                (SELECT COUNT(*) FROM leaders WHERE status = 'active') as total_leaders,
                (SELECT COUNT(*) FROM raters) as total_raters,
                (SELECT COUNT(*) FROM raters WHERE completed_at IS NOT NULL) as completed_responses,
                (SELECT COUNT(DISTINCT leader_id) FROM raters r 
                 WHERE (SELECT COUNT(*) FROM raters r2 
                        WHERE r2.leader_id = r.leader_id AND r2.completed_at IS NOT NULL) >= 5) as ready_for_report
        """)
    
    def get_connection_info(self):
        """Return info about the current database connection."""
        if self.turso_url and self.turso_token and USING_TURSO:
            return {
                'type': 'Turso Cloud',
                'url': self.turso_url,
                'status': 'Connected'
            }
        else:
            return {
                'type': 'Local SQLite',
                'path': self.db_path,
                'status': 'Connected'
            }
