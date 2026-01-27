#!/usr/bin/env python3
"""
Database module for the 360 Development Catalyst.

Handles all data persistence using SQLite.
"""

import sqlite3
import secrets
import hashlib
from datetime import datetime
from pathlib import Path
import json

class Database:
    def __init__(self, db_path="compass_360.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
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
                status TEXT DEFAULT 'active'
            )
        """)
        
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
        
        # Cohorts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cohorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        
        conn.commit()
        conn.close()
    
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
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
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
        
        leaders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return leaders
    
    def get_leader(self, leader_id):
        """Get a specific leader by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM leaders WHERE id = ?", (leader_id,))
        leader = cursor.fetchone()
        conn.close()
        
        return dict(leader) if leader else None
    
    def update_leader(self, leader_id, **kwargs):
        """Update leader details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        valid_fields = ['name', 'email', 'dealership', 'cohort', 'assessment_year', 'status']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if updates:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [leader_id]
            
            cursor.execute(f"UPDATE leaders SET {set_clause} WHERE id = ?", values)
            conn.commit()
        
        conn.close()
    
    def delete_leader(self, leader_id):
        """Soft delete a leader (set status to inactive)."""
        self.update_leader(leader_id, status='inactive')
    
    # ==========================================
    # RATER MANAGEMENT
    # ==========================================
    
    def generate_token(self):
        """Generate a unique, URL-safe token."""
        return secrets.token_urlsafe(6)  # Generates 8 characters
    
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
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                r.*,
                l.name as leader_name,
                l.dealership as leader_dealership,
                CASE WHEN r.completed_at IS NOT NULL THEN 1 ELSE 0 END as completed
            FROM raters r
            JOIN leaders l ON r.leader_id = l.id
            WHERE r.token = ?
        """, (token,))
        
        rater = cursor.fetchone()
        conn.close()
        
        return dict(rater) if rater else None
    
    def get_raters_for_leader(self, leader_id):
        """Get all raters for a specific leader."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT *,
                CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END as completed
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
        
        raters = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return raters
    
    def mark_rater_complete(self, rater_id):
        """Mark a rater as having completed their feedback."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE raters SET completed_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (rater_id,))
        
        conn.commit()
        conn.close()
    
    def delete_rater(self, rater_id):
        """Delete a rater and their responses."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM ratings WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM comments WHERE rater_id = ?", (rater_id,))
        cursor.execute("DELETE FROM raters WHERE id = ?", (rater_id,))
        
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
            ratings: Dict of {item_number: score} where score is 1-5, 'NO' for no opportunity, or 'NA' for not applicable
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for item_num, score in ratings.items():
            no_opp = score == 'NO'
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
        """Submit complete feedback (ratings + comments) and mark as complete."""
        self.submit_ratings(rater_id, ratings)
        self.submit_comments(rater_id, comments)
        self.mark_rater_complete(rater_id)
    
    # ==========================================
    # DATA RETRIEVAL FOR REPORTS
    # ==========================================
    
    def get_leader_feedback_data(self, leader_id):
        """
        Get all feedback data for a leader in the format needed for report generation.
        
        Applies anonymity threshold - groups with fewer than ANONYMITY_THRESHOLD
        respondents have their data folded into 'Others' category.
        Boss and Self are exempt from this threshold.
        
        Returns:
            Tuple of (data_dict, comments_dict) matching the report generator format
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        from framework import ITEMS, DIMENSIONS, ANONYMITY_THRESHOLD
        
        # Get response counts by relationship
        cursor.execute("""
            SELECT relationship, COUNT(*) as count
            FROM raters
            WHERE leader_id = ? AND completed_at IS NOT NULL
            GROUP BY relationship
        """, (leader_id,))
        
        raw_response_counts = {}
        relationship_map = {'Self': 'Self', 'Boss': 'Boss', 'Peers': 'Peers', 
                          'DRs': 'DRs', 'Others': 'Others'}
        for row in cursor.fetchall():
            raw_response_counts[relationship_map.get(row['relationship'], row['relationship'])] = row['count']
        
        # Determine which groups meet the anonymity threshold
        # Self and Boss are always shown; others need >= ANONYMITY_THRESHOLD
        visible_groups = ['Self', 'Boss']  # Always visible
        hidden_groups = []  # Groups that will be folded into Others
        
        for group in ['Peers', 'DRs', 'Others']:
            count = raw_response_counts.get(group, 0)
            if count >= ANONYMITY_THRESHOLD:
                visible_groups.append(group)
            elif count > 0:
                hidden_groups.append(group)
        
        # Build response_counts for visible groups only
        # Hidden groups get added to Others count
        response_counts = {}
        others_count = raw_response_counts.get('Others', 0)
        
        for group in ['Self', 'Boss', 'Peers', 'DRs']:
            if group in visible_groups:
                response_counts[group] = raw_response_counts.get(group, 0)
            elif group in hidden_groups:
                others_count += raw_response_counts.get(group, 0)
        
        if others_count > 0 or 'Others' in visible_groups:
            response_counts['Others'] = others_count
        
        # Create a mapping for hidden groups -> Others
        def map_group(group):
            if group in hidden_groups:
                return 'Others'
            return group
        
        # Get all ratings grouped by item and relationship
        cursor.execute("""
            SELECT 
                rt.item_number,
                r.relationship,
                rt.score,
                rt.no_opportunity
            FROM ratings rt
            JOIN raters r ON rt.rater_id = r.id
            WHERE r.leader_id = ? AND r.completed_at IS NOT NULL
        """, (leader_id,))
        
        # Build the by_item structure with anonymity applied
        by_item = {}
        no_opportunity = {}
        
        for item_num in range(1, 43):
            by_item[item_num] = {'text': ITEMS.get(item_num, '')}
        
        # Collect scores by item and mapped group
        item_scores = {}  # {item_num: {group: [scores]}}
        item_no_opp = {}  # {item_num: {group: count}}
        
        for row in cursor.fetchall():
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
        for item_num in range(1, 43):
            if item_num in item_scores:
                for group, scores in item_scores[item_num].items():
                    if scores:
                        by_item[item_num][group] = round(sum(scores) / len(scores), 1)
            
            # Track no opportunity
            if item_num in item_no_opp:
                total_no_opp = sum(item_no_opp[item_num].values())
                if total_no_opp > 0:
                    no_opportunity[item_num] = {
                        'count': total_no_opp,
                        'groups': [],
                        'text': ITEMS.get(item_num, '')
                    }
                    for group, count in item_no_opp[item_num].items():
                        no_opportunity[item_num]['groups'].extend([group] * count)
        
        # Calculate combined scores and gaps
        for item_num in by_item:
            item = by_item[item_num]
            # Only include visible groups in Combined (excluding Self)
            other_scores = []
            for g in ['Boss', 'Peers', 'DRs', 'Others']:
                if g in visible_groups or g == 'Others':
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
                if scores and (g in visible_groups or g in ['Self', 'Combined', 'Others']):
                    by_dimension[dim_name][g] = round(sum(scores) / len(scores), 2)
            
            if 'Self' in by_dimension[dim_name] and 'Combined' in by_dimension[dim_name]:
                by_dimension[dim_name]['Gap'] = round(
                    by_dimension[dim_name]['Self'] - by_dimension[dim_name]['Combined'], 2
                )
        
        # Build overall items
        overall = {}
        for item_num in [41, 42]:
            overall[item_num] = by_item.get(item_num, {})
        
        # Store info about hidden groups for reporting
        data = {
            'by_item': by_item,
            'by_dimension': by_dimension,
            'overall': overall,
            'response_counts': response_counts,
            'raw_response_counts': raw_response_counts,
            'no_opportunity': no_opportunity,
            'visible_groups': visible_groups,
            'hidden_groups': hidden_groups,
            'anonymity_applied': len(hidden_groups) > 0
        }
        
        # Get comments - also apply anonymity mapping
        cursor.execute("""
            SELECT c.section, c.comment_text, r.relationship
            FROM comments c
            JOIN raters r ON c.rater_id = r.id
            WHERE r.leader_id = ? AND r.completed_at IS NOT NULL
        """, (leader_id,))
        
        comments = {
            'by_section': {},
            'strengths': [],
            'development': []
        }
        
        for row in cursor.fetchall():
            section = row['section']
            raw_group = row['relationship']
            mapped_group = map_group(raw_group)
            
            comment = {'group': mapped_group, 'text': row['comment_text']}
            
            if section == 'strengths':
                comments['strengths'].append(comment)
            elif section == 'development':
                comments['development'].append(comment)
            else:
                if section not in comments['by_section']:
                    comments['by_section'][section] = []
                comments['by_section'][section].append(comment)
        
        conn.close()
        
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
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT data_json FROM historical_scores
            WHERE leader_id = ? AND assessment_year = ?
            ORDER BY created_at DESC LIMIT 1
        """, (leader_id, year))
        
        row = cursor.fetchone()
        conn.close()
        
        return json.loads(row['data_json']) if row else None
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    def get_dashboard_stats(self):
        """Get overall statistics for the admin dashboard."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM leaders WHERE status = 'active') as total_leaders,
                (SELECT COUNT(*) FROM raters) as total_raters,
                (SELECT COUNT(*) FROM raters WHERE completed_at IS NOT NULL) as completed_responses,
                (SELECT COUNT(DISTINCT leader_id) FROM raters r 
                 WHERE (SELECT COUNT(*) FROM raters r2 
                        WHERE r2.leader_id = r.leader_id AND r2.completed_at IS NOT NULL) >= 5) as ready_for_report
        """)
        
        stats = dict(cursor.fetchone())
        conn.close()
        
        return stats
    
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
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM cohorts ORDER BY name")
        cohorts = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return cohorts
    
    def delete_cohort(self, cohort_id):
        """Delete a cohort (doesn't affect leaders assigned to it)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM cohorts WHERE id = ?", (cohort_id,))
        
        conn.commit()
        conn.close()
    
    def get_leaders_by_cohort(self, cohort_name):
        """Get all active leaders in a specific cohort."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT l.*,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id) as total_raters,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.completed_at IS NOT NULL) as completed_raters,
                   (SELECT COUNT(*) FROM raters r WHERE r.leader_id = l.id AND r.relationship = 'Self' AND r.completed_at IS NOT NULL) as self_completed
            FROM leaders l
            WHERE l.status = 'active' AND l.cohort = ?
            ORDER BY l.name
        """, (cohort_name,))
        
        leaders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return leaders
