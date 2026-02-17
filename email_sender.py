#!/usr/bin/env python3
"""
Email module for the 360 Development Catalyst.

Sends branded assessment invitations and reminders via SMTP.
Works with Microsoft 365 / Outlook, Gmail, or any SMTP provider.
Tracks all sent emails in the database.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import streamlit as st


def get_smtp_config():
    """Get SMTP configuration from Streamlit secrets."""
    try:
        email_config = st.secrets.get("email", {})
        smtp_server = email_config.get("smtp_server", "")
        smtp_port = email_config.get("smtp_port", 587)
        username = email_config.get("username", "")
        password = email_config.get("password", "")
        sender_email = email_config.get("sender_email", username)
        sender_name = email_config.get("sender_name", "The Development Catalyst")
        
        if smtp_server and username and password:
            return {
                'smtp_server': smtp_server,
                'smtp_port': int(smtp_port),
                'username': username,
                'password': password,
                'sender_email': sender_email,
                'sender_name': sender_name
            }
    except Exception:
        pass
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
    msg['From'] = f"{config['sender_name']} <{config['sender_email']}>"
    msg['To'] = f"{to_name} <{to_email}>" if to_name else to_email
    msg['Subject'] = subject
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

def _get_rater_invitation_html(leader_name, relationship, assessment_url):
    """Generate HTML for rater invitation email."""
    
    relationship_text = {
        'Self': 'complete your self-assessment',
        'Boss': 'provide feedback as their line manager',
        'Peers': 'provide feedback as a peer',
        'DRs': 'provide feedback as a direct report',
        'Others': 'provide feedback'
    }.get(relationship, 'provide feedback')
    
    if relationship == 'Self':
        intro = f"As part of the Bentley Compass Leadership Programme, you are invited to complete your 360-degree self-assessment."
        cta_text = "Complete Self-Assessment"
    else:
        intro = f"You have been invited to provide 360-degree feedback for <strong>{leader_name}</strong> as part of the Bentley Compass Leadership Programme."
        cta_text = "Provide Feedback"
    
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
                        <td style="background: linear-gradient(135deg, #024731 0%, #035D40 100%); padding: 30px 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                THE 360 DEVELOPMENT CATALYST
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
                                {intro}
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                Your feedback is valuable and will be treated confidentially. The assessment takes approximately 15-20 minutes to complete.
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{assessment_url}" 
                                           style="display: inline-block; background: linear-gradient(135deg, #024731 0%, #035D40 100%); 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            {cta_text}
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                If the button doesn't work, copy and paste this link into your browser:<br>
                                <a href="{assessment_url}" style="color: #024731; word-break: break-all;">{assessment_url}</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from The Development Catalyst.<br>
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


def _get_reminder_html(leader_name, relationship, assessment_url):
    """Generate HTML for reminder email."""
    
    if relationship == 'Self':
        intro = f"This is a friendly reminder to complete your 360-degree self-assessment for the Bentley Compass Leadership Programme."
    else:
        intro = f"This is a friendly reminder to provide your 360-degree feedback for <strong>{leader_name}</strong>."
    
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
                        <td style="background: linear-gradient(135deg, #B8860B 0%, #D4A017 100%); padding: 30px 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                FRIENDLY REMINDER
                            </h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                                The 360 Development Catalyst
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                {intro}
                            </p>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">
                                Your input is important and helps support leadership development. The assessment takes approximately 15-20 minutes.
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{assessment_url}" 
                                           style="display: inline-block; background: linear-gradient(135deg, #024731 0%, #035D40 100%); 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            Complete Now
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                If the button doesn't work, copy and paste this link into your browser:<br>
                                <a href="{assessment_url}" style="color: #024731; word-break: break-all;">{assessment_url}</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from The Development Catalyst.<br>
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
                                           style="display: inline-block; background: linear-gradient(135deg, #024731 0%, #035D40 100%); 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            View Your Report
                                        </a>
                                    </td>
                                </tr>
                            </table>
        """
    
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
                        <td style="background: linear-gradient(135deg, #024731 0%, #035D40 100%); padding: 30px 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                                YOUR FEEDBACK IS READY
                            </h1>
                            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">
                                The 360 Development Catalyst
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
                                This is an automated message from The Development Catalyst.<br>
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
    
    assessment_url = f"{base_url}?t={rater['token']}"
    
    if rater['relationship'] == 'Self':
        subject = "Complete Your 360 Self-Assessment — Bentley Compass"
    else:
        subject = f"360 Feedback Request for {leader_name} — Bentley Compass"
    
    html = _get_rater_invitation_html(leader_name, rater['relationship'], assessment_url)
    
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
    
    assessment_url = f"{base_url}?t={rater['token']}"
    
    subject = f"Reminder: 360 Feedback for {leader_name} — Bentley Compass"
    if rater['relationship'] == 'Self':
        subject = "Reminder: Complete Your 360 Self-Assessment — Bentley Compass"
    
    html = _get_reminder_html(leader_name, rater['relationship'], assessment_url)
    
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

def _get_portal_invitation_html(leader_name, portal_url):
    """Generate HTML for leader portal invitation email (post Module 1)."""
    
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
                        <td style="background: linear-gradient(135deg, #024731 0%, #035D40 100%); padding: 30px 40px; text-align: center;">
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
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{portal_url}" 
                                           style="display: inline-block; background: linear-gradient(135deg, #024731 0%, #035D40 100%); 
                                                  color: #ffffff; text-decoration: none; padding: 16px 40px; 
                                                  border-radius: 6px; font-size: 16px; font-weight: 600;
                                                  letter-spacing: 0.5px;">
                                            Access Your Portal
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Requirements Box -->
                            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #024731;">
                                <p style="color: #024731; font-weight: 600; margin: 0 0 12px 0;">
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
                                        <td style="padding: 4px 0;">Optional (stakeholders, customers, etc.)</td>
                                    </tr>
                                </table>
                                <p style="color: #888; font-size: 13px; margin: 12px 0 0 0; font-style: italic;">
                                    We require minimum 3 in Peers and Direct Reports to ensure anonymity of responses.
                                </p>
                            </div>
                            
                            <p style="color: #666; font-size: 15px; line-height: 1.6; margin: 20px 0;">
                                Once you've added your raters, they will automatically receive an invitation email 
                                with a link to complete their feedback. You can track progress and send reminders 
                                from your portal.
                            </p>
                            
                            <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; padding-top: 20px; border-top: 1px solid #eee;">
                                If the button doesn't work, copy and paste this link into your browser:<br>
                                <a href="{portal_url}" style="color: #024731; word-break: break-all;">{portal_url}</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from The Development Catalyst.<br>
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
                        <td style="background: linear-gradient(135deg, #B8860B 0%, #D4A017 100%); padding: 30px 40px; text-align: center;">
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
                                           style="display: inline-block; background: linear-gradient(135deg, #024731 0%, #035D40 100%); 
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
                                <a href="{portal_url}" style="color: #024731; word-break: break-all;">{portal_url}</a>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 40px; text-align: center; border-top: 1px solid #eee;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                This is an automated message from The Development Catalyst.<br>
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
    html = _get_portal_invitation_html(leader['name'], portal_url)
    
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
