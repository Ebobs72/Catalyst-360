#!/usr/bin/env python3
"""
Email module for Bentley Compass 360.

Sends branded assessment invitations and reminders via SMTP.
Works with Microsoft 365 / Outlook, Gmail, or any SMTP provider.
Tracks all sent emails in the database.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime, timedelta
import streamlit as st

from framework import get_logo_data_uri

# Minimum time between reminder emails to the same rater
REMINDER_THROTTLE_HOURS = 48

# REVERTED 2026-08-21, PERMANENTLY - not a temporary toggle. Was briefly
# "Bentley Compass 360" (a recognisable third-party brand name paired with
# an unrelated sending domain), which two of three real corporate recipients
# (Doğuş Otomotiv, Samaco) silently never received - no bounce, email_log
# showed success on our side both times. Consistent with enterprise mail
# security treating a brand/domain mismatch as a phishing signal, exactly
# the pattern those systems are built to catch. A sender identity where the
# display name and the sending domain actually match is the robust fix at
# the scale this system sends at (many independent corporate mail
# environments), not a cosmetic preference. Getting Bentley to align a
# Bentley-owned sending domain isn't practical either, for the same
# scale reason. Still a single hardcoded constant, still no env var/secrets
# override (that override is what caused the ORIGINAL incident this
# constant replaced) - only the value changes, not the one-source-of-truth
# discipline.
SENDER_DISPLAY_NAME = "Ian Moreton-Thickett"


def _email_logo_html():
    """Logo <img> tag for the email header banner, or '' if the asset is missing.

    Uses the negative (white-on-transparent) variant - every email header
    banner has a dark fill (green for invitations, charcoal for reminders),
    and the dark-on-light default logo would be nearly invisible there.

    NB: base64 data: URIs render fine in Gmail, Apple Mail, and mobile clients,
    but Outlook desktop has a long history of NOT rendering inline base64
    images reliably. If dealership recipients are mostly on Outlook, this may
    not always show - see get_logo_data_uri()'s docstring in framework.py.
    """
    logo_uri = get_logo_data_uri(negative=True)
    if not logo_uri:
        return ''
    return f'<img src="{logo_uri}" alt="Bentley Compass 360" style="height: 44px; margin-bottom: 12px;">'

# Last-resort fallback for building rater/portal links. This points at the LIVE
# app, so any other deployment (e.g. the sandbox) MUST set `[app] base_url` in
# its own secrets, or its invitation emails will send raters to the live system.
# It also still carries the pre-white-label name, which is why configuring it
# properly matters: the URL is visible to raters in the link and address bar.
DEFAULT_BASE_URL = "https://catalyst-360-arbncruhflmazjemep8uzh.streamlit.app"


def get_app_base_url():
    """
    Base URL for rater and portal links, so each deployment points at itself.

    Checks APP_BASE_URL in the environment first, then Streamlit secrets,
    matching the same os.environ-first pattern already used for
    ANTHROPIC_API_KEY and the SMTP settings - Render (and most non-Streamlit-
    Cloud hosts) has no st.secrets at all, so that path silently never
    resolved there, and every link fell through to DEFAULT_BASE_URL (the LIVE
    app) regardless of what a [app] base_url entry said in a secrets.toml
    nobody deployed there had.

    Configure per environment as either:
        APP_BASE_URL=https://compass-360.onrender.com   (env var - Render)
    or:
        [app]
        base_url = "https://bentley-compass-360-sandbox.streamlit.app"   (Streamlit Cloud secrets)
    """
    env_url = os.environ.get("APP_BASE_URL")
    if env_url:
        return env_url.rstrip('/')

    try:
        url = st.secrets.get("app", {}).get("base_url")
        if url:
            return str(url).rstrip('/')
    except Exception:
        pass
    return DEFAULT_BASE_URL


def get_admin_notification_email():
    """
    Coordinator/admin address for report-ready milestone notifications
    (self-assessment complete, Full 360 crossed the response threshold).

    Same os.environ-first, st.secrets-fallback pattern as get_app_base_url()
    and get_smtp_config() below - not hardcoded, not Bentley-specific, so
    each deployment configures its own address rather than this project
    picking one deployment's coordinator for everyone.

    Configure per environment as either:
        ADMIN_NOTIFICATION_EMAIL=coordinator@example.com   (env var - Render)
    or:
        [app]
        admin_notification_email = "coordinator@example.com"   (Streamlit Cloud secrets)

    Returns None if unset, so callers can skip sending and log the gap
    rather than raise - a missing address must never block a rater's own
    submission.
    """
    env_value = os.environ.get("ADMIN_NOTIFICATION_EMAIL")
    if env_value:
        return env_value.strip()

    try:
        value = st.secrets.get("app", {}).get("admin_notification_email")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return None


def get_smtp_config():
    """
    Get SMTP configuration - environment variables first, falling back to
    Streamlit secrets per field. Same os.environ-first, st.secrets-fallback
    pattern as report_generator._get_api_key(), extended across SMTP's six
    fields so a deployment (e.g. Render) can supply them as plain env vars
    without needing a secrets.toml at all. Resolution is per-field, not
    per-source - one field can come from the environment while another
    falls back to secrets, so a partially-migrated setup still works.
    """
    try:
        email_config = st.secrets.get("email", {})
    except Exception:
        email_config = {}

    def resolve(env_name, secrets_key, default=""):
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value
        return email_config.get(secrets_key, default)

    smtp_server = resolve("SMTP_SERVER", "smtp_server")
    smtp_port = resolve("SMTP_PORT", "smtp_port", 587)
    username = resolve("SMTP_USERNAME", "username")
    password = resolve("SMTP_PASSWORD", "password")
    # sender_email is the real mailbox (used to authenticate, to send, and as
    # Reply-To) - it stays configurable. There is deliberately no
    # sender_name field here any more: see SENDER_DISPLAY_NAME above.
    sender_email = resolve("SMTP_SENDER_EMAIL", "sender_email", username)

    if smtp_server and username and password:
        return {
            'smtp_server': smtp_server,
            'smtp_port': int(smtp_port),
            'username': username,
            'password': password,
            'sender_email': sender_email,
        }
    return None


def is_email_configured():
    """Check if email sending is properly configured."""
    return get_smtp_config() is not None


def _send_email(to_email, to_name, subject, html_content):
    """Send an email via SMTP. Returns (success, message)."""
    config = get_smtp_config()
    if not config:
        return False, "Email not configured"
    
    msg = MIMEMultipart('alternative')
    # formataddr() RFC 2047-encodes only the display-name portion when it has
    # non-ASCII characters, leaving the address itself as plain, untouched
    # ASCII. Assigning a raw f"{name} <{email}>" string instead lets Python's
    # email library wrap the WHOLE string - name and address together - in
    # one encoded-word, which is invalid (encoded-words must never straddle
    # into the addr-spec) and is what corrupted "Seher Başar Turgut" into an
    # unresolvable recipient at the receiving server.
    msg['From'] = formataddr((SENDER_DISPLAY_NAME, config['sender_email']))
    msg['To'] = formataddr((to_name, to_email)) if to_name else to_email
    msg['Subject'] = subject
    # Reply-To is unaffected by SENDER_DISPLAY_NAME either way: it must be
    # the actual sending mailbox, not a placeholder. It already is -
    # sender_email is the same address used to authenticate and send (see
    # get_smtp_config - sender_email defaults to the SMTP login itself), so
    # a reply lands exactly where the invitation came from regardless of
    # what display name is showing.
    msg['Reply-To'] = config['sender_email']
    
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(config['username'], config['password'])
            server.sendmail(config['sender_email'], to_email, msg.as_string())
        
        return True, f"Sent to {to_email}"
    
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed — check username and app password"
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient refused: {to_email}"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================
# EMAIL TEMPLATES
# ============================================

def _translated(db, locale, key, fallback_text):
    """Shorthand for db.get_translation, safe to call with db=None (some
    callers - e.g. admin_dashboard.py's test-email preview - don't have a
    locale in scope at all, and should just get the current English copy)."""
    if db is None:
        return fallback_text
    return db.get_translation(key, locale, fallback_text=fallback_text)


def _get_rater_invitation_html(rater_name, leader_name, relationship, assessment_url, db=None, locale=None):
    """Generate HTML for rater invitation email.

    db/locale are optional - the email a rater receives should go out in
    whatever locale is on their raters row at send time (see
    send_rater_invitation), but this function still needs to work for
    existing callers that don't have a locale in scope (the admin test-email
    preview), which just get the English fallback throughout.
    """
    greeting = _translated(db, locale, 'email_greeting', "Dear {name},").format(name=rater_name)
    relationship_clause_key = {
        'Boss': 'email_relationship_clause_boss',
        'Peers': 'email_relationship_clause_peers',
        'DRs': 'email_relationship_clause_drs',
    }.get(relationship)
    relationship_clause_fallback = {
        'Boss': 'in your capacity as their line manager',
        'Peers': 'as a peer',
        'DRs': 'as a direct report',
        'Others': ''
    }.get(relationship, '')
    relationship_clause = (
        _translated(db, locale, relationship_clause_key, relationship_clause_fallback)
        if relationship_clause_key else ''
    )

    if relationship == 'Self':
        intro = _translated(
            db, locale, 'email_rater_invitation_intro_self',
            "As part of the Bentley Compass Leadership Programme, you are invited to complete your "
            "leadership self-assessment. Please complete it before Module 1, where you will talk your "
            "report through with your coach."
        )
        cta_text = _translated(db, locale, 'email_rater_invitation_cta_self', "Complete Self-Assessment")
    else:
        suffix = f", {relationship_clause}" if relationship_clause else ""
        intro = _translated(
            db, locale, 'email_rater_invitation_intro_other',
            "You have been invited to provide 360-degree feedback for {leader_name} as part of the "
            "Bentley Compass Leadership Programme{suffix}."
        ).format(leader_name=f"<strong>{leader_name}</strong>", suffix=suffix)
        cta_text = _translated(db, locale, 'email_rater_invitation_cta_other', "Provide Feedback")

    body_note = _translated(
        db, locale, 'email_rater_invitation_body_note',
        "Your feedback is valuable and will be treated confidentially. The assessment takes "
        "approximately 15-20 minutes to complete."
    )

    # Advance notice only - the actual consent capture (a ticked checkbox,
    # blocking entry until confirmed) happens in-app, since HTML email can't
    # reliably submit a checked box back to the system. Self is a genuinely
    # different message, not a shared template with one clause swapped in -
    # there's no anonymity threshold, no "shown to" someone else, and no
    # scores-vs-comments distinction to draw for your own reflection.
    if relationship == 'Self':
        data_protection_note = _translated(
            db, locale, 'email_data_protection_note_self',
            "Before you begin, you'll be asked to confirm you understand how this self-assessment "
            "is used. In short: this is your own reflection, not anonymous feedback, so nothing "
            "here is hidden from you. It forms the basis of your Self-Assessment report and your "
            "first coaching conversation."
        )
    else:
        data_protection_note = _translated(
            db, locale, 'email_data_protection_note_other',
            "Before you begin, you'll be asked to confirm you understand how your feedback is used "
            "and stored. In short: your scores are only ever shown in combination with others, your "
            "name is removed from your response the moment you submit, and any comments you write "
            "are shown to {leader_name} as you've written them, but never attributed to you by name."
        ).format(leader_name=leader_name)

    link_note = _translated(
        db, locale, 'email_link_fallback_note',
        "If the button doesn't work, copy and paste this link into your browser:"
    )
    footer_note = _translated(
        db, locale, 'email_footer_automated_note',
        "This is an automated message from Bentley Compass 360.<br>Please do not reply to this email."
    )

    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: #183319; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                BENTLEY COMPASS 360
                            </h1>
                            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass Leadership Programme
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                {greeting}
                            </p>

                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                {intro}
                            </p>

                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                                {body_note}
                            </p>

                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 0 0 30px 0;">
                                {data_protection_note}
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{assessment_url}"
                                           style="display: inline-block; background: #183319;
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px;
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            {cta_text}
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                {link_note}<br>
                                <a href="{assessment_url}" style="color: #183319; word-break: break-all;">{assessment_url}</a>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                {footer_note}
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _get_reminder_html(rater_name, leader_name, relationship, assessment_url, db=None, locale=None):
    """Generate HTML for reminder email. db/locale optional - see
    _get_rater_invitation_html for why."""

    greeting = _translated(db, locale, 'email_greeting', "Dear {name},").format(name=rater_name)

    if relationship == 'Self':
        intro = _translated(
            db, locale, 'email_rater_reminder_intro_self',
            "This is a friendly reminder to complete your leadership self-assessment for the "
            "Bentley Compass Leadership Programme, ahead of Module 1."
        )
    else:
        intro = _translated(
            db, locale, 'email_rater_reminder_intro_other',
            "This is a friendly reminder to provide your 360-degree feedback for {leader_name}."
        ).format(leader_name=f"<strong>{leader_name}</strong>")

    reminder_header = _translated(db, locale, 'email_reminder_header', "FRIENDLY REMINDER")
    body_note = _translated(
        db, locale, 'email_rater_reminder_body_note',
        "Your input is important and helps support leadership development. The assessment takes "
        "approximately 15-20 minutes."
    )
    cta_text = _translated(db, locale, 'email_rater_reminder_cta', "Complete Now")
    link_note = _translated(
        db, locale, 'email_link_fallback_note',
        "If the button doesn't work, copy and paste this link into your browser:"
    )
    footer_note = _translated(
        db, locale, 'email_footer_automated_note',
        "This is an automated message from Bentley Compass 360.<br>Please do not reply to this email."
    )

    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: #4D4D4F; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                {reminder_header}
                            </h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass 360
                            </p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                {greeting}
                            </p>

                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                {intro}
                            </p>

                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                {body_note}
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{assessment_url}"
                                           style="display: inline-block; background: #183319;
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px;
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            {cta_text}
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                {link_note}<br>
                                <a href="{assessment_url}" style="color: #183319; word-break: break-all;">{assessment_url}</a>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                {footer_note}
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _get_leader_notification_html(leader_name, report_url=None):
    """Generate HTML for leader notification that feedback is ready."""
    
    cta_section = ""
    if report_url:
        cta_section = f"""
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{report_url}" 
                                           style="display: inline-block; background: #183319; 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            View Your Report
                                        </a>
                                    </td>
                                </tr>
                            </table>
        """
    
    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: #183319; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                YOUR FEEDBACK IS READY
                            </h1>
                            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass 360
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                Dear {leader_name},
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                                Great news! Your 360-degree feedback report is now ready for the Bentley Compass Leadership Programme.
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                Your programme coordinator will be in touch to arrange a feedback session where you can discuss your results and create your development plan.
                            </p>
                            
                            {cta_section}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from Bentley Compass 360.<br>
                                Please do not reply to this email.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


# ============================================
# SEND FUNCTIONS
# ============================================

def send_rater_invitation(rater, leader_name, base_url, db):
    """
    Send a rater invitation email.
    
    Args:
        rater: Rater dict with id, email, name, relationship, token
        leader_name: Name of the leader being assessed
        base_url: Base URL for the assessment (e.g., https://app.streamlit.app)
        db: Database instance for logging
    
    Returns:
        (success: bool, message: str)
    """
    if not rater.get('email'):
        return False, "No email address"

    # Goes out in whatever locale is on this rater's row at send time. Almost
    # always None/English here, since the locale picker only appears on the
    # rater's first visit to the FORM, after the invitation has already been
    # sent - see the i18n build instructions, section 6.
    locale = rater.get('locale')

    assessment_url = f"{base_url}?t={rater['token']}"

    if rater['relationship'] == 'Self':
        subject = _translated(db, locale, 'email_rater_invitation_subject_self',
                               "Complete Your Leadership Self-Assessment — Bentley Compass")
    else:
        subject = _translated(db, locale, 'email_rater_invitation_subject_other',
                               "360 Feedback Request for {leader_name} — Bentley Compass"
                               ).format(leader_name=leader_name)

    html = _get_rater_invitation_html(rater.get('name'), leader_name, rater['relationship'], assessment_url, db=db, locale=locale)
    
    success, message = _send_email(
        rater['email'],
        rater.get('name'),
        subject,
        html
    )
    
    # Log the email
    if db:
        db.log_email(
            rater_id=rater['id'],
            email_type='invitation',
            to_email=rater['email'],
            success=success,
            message=message
        )
    
    return success, message


def send_rater_reminder(rater, leader_name, base_url, db):
    """
    Send a reminder email to an incomplete rater.
    
    Args:
        rater: Rater dict with id, email, name, relationship, token
        leader_name: Name of the leader being assessed
        base_url: Base URL for the assessment
        db: Database instance for logging
    
    Returns:
        (success: bool, message: str)
    """
    if not rater.get('email'):
        return False, "No email address"
    
    if rater.get('completed'):
        return False, "Already completed"

    last_sent = rater.get('reminder_sent_at')
    if last_sent:
        try:
            last_sent_dt = datetime.fromisoformat(str(last_sent).replace('Z', '+00:00')).replace(tzinfo=None)
            if datetime.now() - last_sent_dt < timedelta(hours=REMINDER_THROTTLE_HOURS):
                return False, "Reminded recently"
        except (ValueError, TypeError):
            pass

    locale = rater.get('locale')

    assessment_url = f"{base_url}?t={rater['token']}"

    if rater['relationship'] == 'Self':
        subject = _translated(db, locale, 'email_rater_reminder_subject_self',
                               "Reminder: Complete Your Leadership Self-Assessment — Bentley Compass")
    else:
        subject = _translated(db, locale, 'email_rater_reminder_subject_other',
                               "Reminder: 360 Feedback for {leader_name} — Bentley Compass"
                               ).format(leader_name=leader_name)

    html = _get_reminder_html(rater.get('name'), leader_name, rater['relationship'], assessment_url, db=db, locale=locale)
    
    success, message = _send_email(
        rater['email'],
        rater.get('name'),
        subject,
        html
    )
    
    # Log the email and update reminder_sent_at
    if db:
        db.log_email(
            rater_id=rater['id'],
            email_type='reminder',
            to_email=rater['email'],
            success=success,
            message=message
        )
        if success:
            db.update_rater_reminder_sent(rater['id'])
    
    return success, message


def send_leader_notification(leader, db):
    """
    Send notification to leader that their feedback is ready.
    
    Args:
        leader: Leader dict with id, name, email
        db: Database instance for logging
    
    Returns:
        (success: bool, message: str)
    """
    if not leader.get('email'):
        return False, "No email address"
    
    subject = "Your 360 Feedback Report is Ready — Bentley Compass"
    html = _get_leader_notification_html(leader['name'])
    
    success, message = _send_email(
        leader['email'],
        leader['name'],
        subject,
        html
    )
    
    # Log the email
    if db:
        db.log_email(
            leader_id=leader['id'],
            email_type='leader_notification',
            to_email=leader['email'],
            success=success,
            message=message
        )
    
    return success, message


def _get_admin_notification_html(leader_name, milestone_type):
    """Generate HTML for the admin report-ready milestone notice.

    milestone_type selects body copy only ('self_assessment_ready' or
    'full_360_ready') - the caller decides subject and whether/who to send
    to; this just renders the two known bodies."""
    admin_url = f"{get_app_base_url()}?admin=true"

    if milestone_type == 'self_assessment_ready':
        heading = "SELF-ASSESSMENT COMPLETE"
        body = (
            f"<strong>{leader_name}</strong> has completed their leadership "
            f"self-assessment. Their Self-Assessment report can now be generated "
            f"ahead of Module 1."
        )
    else:
        heading = "FULL 360 REPORT READY"
        body = (
            f"<strong>{leader_name}</strong>'s Full 360 has reached enough "
            f"responses to generate a meaningful report."
        )

    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                    <!-- Header -->
                    <tr>
                        <td style="background: #183319; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                {heading}
                            </h1>
                            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass 360
                            </p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                {body}
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 0 0 20px 0;">
                                        <a href="{admin_url}"
                                           style="display: inline-block; background: #183319;
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px;
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            Open Admin Dashboard
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from Bentley Compass 360.
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def send_admin_notification(subject, leader_name, milestone_type, db, leader_id=None):
    """
    Notify the programme coordinator that a leader has reached a report-ready
    milestone - self-assessment complete, or Full 360 just crossed the
    response threshold. Deliberately NOT a per-rater completion notice:
    every individual submission firing an email would be noise, not signal.
    This covers exactly two rare, genuinely actionable events, each meant to
    fire once per leader - the one-time guarantee for the Full 360 case
    lives in database.py's try_claim_full_360_notification, not here; this
    function only sends and logs whatever it's told to.

    Never raises on a missing or failed send - a notification failure must
    not block or error out the rater-facing submission it's triggered from.
    Callers should not need their own try/except around this.

    Args:
        subject: Email subject line (caller's choice, not derived here)
        leader_name: Name of the leader who reached the milestone
        milestone_type: 'self_assessment_ready' or 'full_360_ready' - selects
            body copy only, not who it's sent to
        db: Database instance for logging
        leader_id: Optional, for the email_log FK so the audit trail can be
            traced back to the leader without parsing the message text

    Returns:
        (success: bool, message: str)
    """
    try:
        admin_email = get_admin_notification_email()
        if not admin_email:
            if db:
                db.log_email(
                    leader_id=leader_id,
                    email_type=milestone_type,
                    to_email='[not configured]',
                    success=False,
                    message="ADMIN_NOTIFICATION_EMAIL not configured"
                )
            return False, "ADMIN_NOTIFICATION_EMAIL not configured"

        html = _get_admin_notification_html(leader_name, milestone_type)
        success, message = _send_email(admin_email, None, subject, html)

        if db:
            db.log_email(
                leader_id=leader_id,
                email_type=milestone_type,
                to_email=admin_email,
                success=success,
                message=message
            )

        return success, message
    except Exception as e:
        if db:
            try:
                db.log_email(
                    leader_id=leader_id,
                    email_type=milestone_type,
                    to_email='[error]',
                    success=False,
                    message=str(e)
                )
            except Exception:
                pass
        return False, str(e)


def send_bulk_invitations(raters, leader_name, base_url, db):
    """
    Send invitation emails to multiple raters.
    
    Args:
        raters: List of rater dicts
        leader_name: Name of the leader
        base_url: Base URL for assessments
        db: Database instance
    
    Returns:
        (sent_count, failed_count, results)
    """
    sent = 0
    failed = 0
    results = []
    
    for rater in raters:
        if rater.get('email') and not rater.get('completed'):
            success, message = send_rater_invitation(rater, leader_name, base_url, db)
            results.append({
                'rater': rater.get('name') or rater.get('email'),
                'relationship': rater['relationship'],
                'success': success,
                'message': message
            })
            if success:
                sent += 1
            else:
                failed += 1
    
    return sent, failed, results


def send_bulk_reminders(raters, leader_name, base_url, db):
    """
    Send reminder emails to incomplete raters.
    
    Args:
        raters: List of rater dicts
        leader_name: Name of the leader
        base_url: Base URL for assessments
        db: Database instance
    
    Returns:
        (sent_count, failed_count, results)
    """
    sent = 0
    failed = 0
    results = []
    
    for rater in raters:
        if rater.get('email') and not rater.get('completed'):
            success, message = send_rater_reminder(rater, leader_name, base_url, db)
            results.append({
                'rater': rater.get('name') or rater.get('email'),
                'relationship': rater['relationship'],
                'success': success,
                'message': message
            })
            if success:
                sent += 1
            else:
                failed += 1
    
    return sent, failed, results


# ============================================
# LEADER PORTAL EMAILS
# ============================================

def _get_portal_invitation_html(leader_name, portal_url, db=None, locale=None):
    """Generate HTML for leader portal invitation email (post Module 1).

    db/locale are optional, same reasoning as _get_rater_invitation_html -
    leaders have no locale column of their own today, so this is currently
    always English fallback, but routing it through _translated now means no
    further code change is needed once leader-facing translation is ever
    commissioned.
    """
    data_protection_note = _translated(
        db, locale, 'email_leader_data_protection_note',
        "Before you continue, you'll be asked to confirm you understand how your data and your "
        "raters' feedback are used and stored. In short: your own results are stored against "
        "your name to support your coaching, and any comments your raters write are shown to "
        "you exactly as they've written them."
    )
    # Lets a leader pass this on verbally when they send invitations - added
    # per the consent copy addendum, alongside (not replacing) the note above.
    rater_scrubbing_note = _translated(
        db, locale, 'email_leader_rater_scrubbing_note',
        "Once someone you've nominated submits their feedback, their name and email are "
        "permanently removed from the system. Feel free to let them know this when you invite "
        "them, it often helps people give more candid feedback."
    )
    # FIXED 2026-08-21: previously hardcoded (not routed through _translated
    # like everything else in this function - simply never migrated) and
    # described the OLD immediate-send behaviour ("they will automatically
    # receive an invitation email"). Adding a rater only writes the record;
    # nothing sends until the leader reviews "People You've Nominated" and
    # clicks "Send Invitations" themselves - see the leader-portal section of
    # CLAUDE.md. The stale copy would have set a wrong expectation right in
    # the email that hands the leader their portal.
    raters_flow_note = _translated(
        db, locale, 'email_leader_raters_flow_note',
        "Once you've added your raters, you'll be able to review them and send their "
        "invitations yourself from your portal — where you can also track progress and send "
        "reminders."
    )

    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: #183319; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                YOUR 360 FEEDBACK PORTAL
                            </h1>
                            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass Leadership Programme
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                Dear {leader_name},
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                                Following Module 1, it's now time to set up your 360-degree feedback. This involves 
                                nominating colleagues who will provide feedback on your leadership.
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                                Click the button below to access your personal portal where you can add your raters.
                            </p>

                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 0 0 12px 0;">
                                {data_protection_note}
                            </p>

                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 0 0 20px 0;">
                                {rater_scrubbing_note}
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{portal_url}"
                                           style="display: inline-block; background: #183319; 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            Access Your Portal
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Requirements Box -->
                            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #183319;">
                                <p style="color: #183319; font-weight: 600; margin: 0 0 12px 0;">
                                    Who should you nominate?
                                </p>
                                <table style="width: 100%; color: #666; font-size: 14px; line-height: 1.8;">
                                    <tr>
                                        <td style="padding: 4px 0;"><strong>Line Manager:</strong></td>
                                        <td style="padding: 4px 0;">1 required (max 2 if you have matrix reporting)</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 4px 0;"><strong>Peers:</strong></td>
                                        <td style="padding: 4px 0;">Minimum 3, suggest 5 (colleagues at same level)</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 4px 0;"><strong>Direct Reports:</strong></td>
                                        <td style="padding: 4px 0;">Minimum 3, suggest 5 (if applicable)</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 4px 0;"><strong>Others:</strong></td>
                                        <td style="padding: 4px 0;">Optional (stakeholders, customers, etc.) — if you add any, add at least 3</td>
                                    </tr>
                                </table>
                                <p style="color: #888; font-size: 13px; margin: 12px 0 0 0; font-style: italic;">
                                    We require a minimum of 3 respondents in Peers, Direct Reports, and Others (if used) to ensure anonymity of responses.
                                </p>
                            </div>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 20px 0;">
                                {raters_flow_note}
                            </p>
                            
                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                If the button doesn't work, copy and paste this link into your browser:<br>
                                <a href="{portal_url}" style="color: #183319; word-break: break-all;">{portal_url}</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from Bentley Compass 360.<br>
                                If you have any questions, please contact your programme coordinator.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _get_leader_nomination_reminder_html(leader_name, portal_url, nominated_count):
    """Generate HTML for leader nomination reminder email."""
    
    message = "You haven't added any raters yet." if nominated_count == 0 else f"You've nominated {nominated_count} rater(s) so far, but we recommend at least 8-10 for comprehensive feedback."
    
    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: #4D4D4F; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                REMINDER: NOMINATE YOUR RATERS
                            </h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass Leadership Programme
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                Dear {leader_name},
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                                This is a friendly reminder to nominate your 360-degree feedback raters. 
                                {message}
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                Please add your raters as soon as possible to give them enough time to complete their feedback before Module 2.
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{portal_url}" 
                                           style="display: inline-block; background: #183319; 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            Add Raters Now
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                If the button doesn't work, copy and paste this link into your browser:<br>
                                <a href="{portal_url}" style="color: #183319; word-break: break-all;">{portal_url}</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from Bentley Compass 360.<br>
                                If you have any questions, please contact your programme coordinator.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def send_portal_invitation(leader, base_url, db):
    """
    Send portal invitation email to a leader.
    
    Args:
        leader: Leader dict with id, name, email, portal_token
        base_url: Base URL for the app
        db: Database instance for logging
    
    Returns:
        (success: bool, message: str)
    """
    if not leader.get('email'):
        return False, "No email address"
    
    if not leader.get('portal_token'):
        # Generate token if not exists
        token = db.generate_portal_token(leader['id'])
    else:
        token = leader['portal_token']
    
    portal_url = f"{base_url}?portal={token}"
    
    subject = "Your 360 Feedback Portal — Bentley Compass"
    # locale=None: leaders have no locale column of their own today (i18n is
    # rater-only) - passing db still means no further code change is needed
    # once leader-facing translation is ever commissioned.
    html = _get_portal_invitation_html(leader['name'], portal_url, db=db, locale=None)
    
    success, message = _send_email(
        leader['email'],
        leader['name'],
        subject,
        html
    )
    
    # Log the email and mark as sent
    if db:
        db.log_email(
            leader_id=leader['id'],
            email_type='portal_invitation',
            to_email=leader['email'],
            success=success,
            message=message
        )
        if success:
            db.mark_portal_email_sent(leader['id'])
    
    return success, message


def _get_invitation_failure_html(leader_name, failed_entries, portal_url):
    """Generate HTML for the immediate invitation-failure notice to a leader."""

    rows_html = "".join(
        f"""
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; color: #333; font-size: 14px;">{e.get('name') or 'Unknown'}</td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; color: #666; font-size: 14px;">{e.get('email') or 'No email address'}</td>
                                </tr>"""
        for e in failed_entries
    )
    who = "the following person's" if len(failed_entries) == 1 else "the following people's"

    logo_html = _email_logo_html()
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                    <!-- Header -->
                    <tr>
                        <td style="background: #B00020; padding: 30px 40px; text-align: center;">
                            {logo_html}
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                SOME INVITATIONS DIDN'T SEND
                            </h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                                Bentley Compass 360
                            </p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                Dear {leader_name},
                            </p>

                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                                You recently sent feedback invitations, but {who} invitation could not be delivered:
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 20px 0;">
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 2px solid #183319; color: #183319; font-size: 13px; font-weight: 600;">Name</td>
                                    <td style="padding: 8px 0; border-bottom: 2px solid #183319; color: #183319; font-size: 13px; font-weight: 600;">Email address</td>
                                </tr>{rows_html}
                            </table>

                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                This is usually a mistyped or invalid email address. Please check and correct it on your portal, then send their invitation again.
                            </p>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{portal_url}"
                                           style="display: inline-block; background: #183319;
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px;
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            Go to Your Portal
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                If the button doesn't work, copy and paste this link into your browser:<br>
                                <a href="{portal_url}" style="color: #183319; word-break: break-all;">{portal_url}</a>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from Bentley Compass 360.<br>
                                If you have any questions, please contact your programme coordinator.
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def send_invitation_failure_notice(leader, failed_entries, base_url, db):
    """
    Notify the leader directly, by email, that one or more invitations they
    just triggered failed to send.

    Closes the gap where a leader adds raters, clicks Send, and closes the
    tab before seeing the in-app warning - the portal's own failed-row icon
    (see database.get_failed_invitation_emails) still catches it on their
    next visit, but this reaches them even if they never come back on their
    own initiative.

    Only covers failures our own SMTP call detects immediately (an address
    rejected at send time - see _send_email's SMTPRecipientsRefused handling).
    A message accepted at send time that bounces later is invisible to the
    app entirely, since the bounce is a separate email sent by the
    recipient's mail server straight back to the sending mailbox, with no
    hook into this application. Closing THAT gap needs a bounce-aware
    transactional email provider (e.g. Postmark/SendGrid/SES via webhook),
    not this function - a deliberate later piece of work, not attempted here.

    Args:
        leader: Leader dict with id, name, email, portal_token
        failed_entries: list of dicts with 'name' and 'email', for raters
            whose invitation attempt failed in this batch
        base_url: Base URL for the app
        db: Database instance for logging

    Returns:
        (success: bool, message: str)
    """
    if not leader.get('email') or not failed_entries:
        return False, "No leader email or nothing failed"

    if not leader.get('portal_token'):
        return False, "No portal token"

    portal_url = f"{base_url}?portal={leader['portal_token']}"

    subject = "Some invitations couldn't be sent — Bentley Compass 360"
    html = _get_invitation_failure_html(leader['name'], failed_entries, portal_url)

    success, message = _send_email(
        leader['email'],
        leader['name'],
        subject,
        html
    )

    if db:
        db.log_email(
            leader_id=leader['id'],
            email_type='invitation_failure_notice',
            to_email=leader['email'],
            success=success,
            message=message
        )

    return success, message


def send_leader_nomination_reminder(leader, base_url, db):
    """
    Send nomination reminder email to a leader who hasn't added enough raters.
    
    Args:
        leader: Leader dict with id, name, email, portal_token
        base_url: Base URL for the app
        db: Database instance
    
    Returns:
        (success: bool, message: str)
    """
    if not leader.get('email'):
        return False, "No email address"
    
    if not leader.get('portal_token'):
        return False, "No portal token"
    
    portal_url = f"{base_url}?portal={leader['portal_token']}"
    nominated_count = leader.get('nominated_count', 0)
    
    subject = "Reminder: Nominate Your 360 Raters — Bentley Compass"
    html = _get_leader_nomination_reminder_html(leader['name'], portal_url, nominated_count)
    
    success, message = _send_email(
        leader['email'],
        leader['name'],
        subject,
        html
    )
    
    # Log the email and mark reminder sent
    if db:
        db.log_email(
            leader_id=leader['id'],
            email_type='nomination_reminder',
            to_email=leader['email'],
            success=success,
            message=message
        )
        if success:
            db.mark_nomination_reminder_sent(leader['id'])
    
    return success, message


def send_bulk_portal_invitations(leaders, base_url, db):
    """
    Send portal invitation emails to multiple leaders.
    
    Args:
        leaders: List of leader dicts
        base_url: Base URL for the app
        db: Database instance
    
    Returns:
        (sent_count, failed_count, results)
    """
    sent = 0
    failed = 0
    results = []
    
    for leader in leaders:
        if leader.get('email'):
            success, message = send_portal_invitation(leader, base_url, db)
            results.append({
                'leader': leader['name'],
                'success': success,
                'message': message
            })
            if success:
                sent += 1
            else:
                failed += 1
    
    return sent, failed, results
