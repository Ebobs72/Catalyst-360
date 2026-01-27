#!/usr/bin/env python3
"""
Report generator for the 360 Development Catalyst.
Generates Word documents for Self-Assessment, Full 360, and Progress Reports.
"""

import numpy as np
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from datetime import datetime
import tempfile
import os
from pathlib import Path

from framework import (
    DIMENSIONS, ITEMS, DIMENSION_DESCRIPTIONS,
    COLOURS, GROUP_COLORS, GROUP_DISPLAY,
    HIGH_SCORE_THRESHOLD, SIGNIFICANT_GAP
)

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def set_cell_shading(cell, color):
    """Set background colour of a table cell."""
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shading)


def make_table_borderless(table):
    """Remove all borders from a table."""
    tbl = table._tbl
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'nil')
        tblBorders.append(border)
    tblPr.append(tblBorders)


def categorize_papu_nanu(data):
    """Categorise items into PAPU-NANU quadrants."""
    categories = {
        'agreed_strengths': [],
        'good_news': [],
        'development_areas': [],
        'hidden_talents': [],
    }
    
    for item_num, item_scores in data['by_item'].items():
        if item_num in [41, 42]:
            continue
        
        self_score = item_scores.get('Self')
        combined = item_scores.get('Combined')
        gap = item_scores.get('Gap')
        
        if self_score is None or combined is None:
            continue
        
        no_opp_info = data.get('no_opportunity', {}).get(item_num)
        no_opp_count = no_opp_info['count'] if no_opp_info else 0
        
        item_info = {
            'item_num': item_num,
            'text': item_scores.get('text', ITEMS.get(item_num, '')),
            'self': self_score,
            'combined': combined,
            'gap': gap,
            'no_opp_count': no_opp_count,
        }
        
        if combined >= HIGH_SCORE_THRESHOLD:
            if gap is not None and gap < -SIGNIFICANT_GAP:
                categories['good_news'].append(item_info)
            elif gap is not None and gap > SIGNIFICANT_GAP:
                categories['hidden_talents'].append(item_info)
            else:
                categories['agreed_strengths'].append(item_info)
        else:
            if gap is not None and gap > SIGNIFICANT_GAP:
                categories['hidden_talents'].append(item_info)
            else:
                categories['development_areas'].append(item_info)
    
    for cat in categories:
        if cat in ['agreed_strengths', 'good_news']:
            categories[cat].sort(key=lambda x: x['combined'], reverse=True)
        else:
            categories[cat].sort(key=lambda x: x['combined'])
    
    return categories


def create_radar_chart(dimensions, self_scores, combined_scores, output_path):
    """Create radar chart for dimension overview."""
    labels = list(dimensions.keys())
    num_vars = len(labels)
    
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]
    
    self_values = [self_scores.get(dim, 0) or 0 for dim in labels]
    self_values += self_values[:1]
    
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    
    ax.plot(angles, self_values, 'o-', linewidth=2, label='Self', color=COLOURS['primary_blue'])
    ax.fill(angles, self_values, alpha=0.25, color=COLOURS['primary_blue'])
    
    if combined_scores:
        combined_values = [combined_scores.get(dim, 0) or 0 for dim in labels]
        combined_values += combined_values[:1]
        ax.plot(angles, combined_values, 'o-', linewidth=2, label='Combined Others', color=COLOURS['orange'])
        ax.fill(angles, combined_values, alpha=0.25, color=COLOURS['orange'])
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=9)
    ax.set_ylim(1, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    
    if combined_scores:
        ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def create_item_bar_chart(scores, output_path):
    """Create horizontal bar chart for an item showing all respondent groups plus Combined."""
    groups = []
    values = []
    colors = []
    
    # Add individual groups
    for group in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
        val = scores.get(group)
        if val is not None:
            groups.append(GROUP_DISPLAY[group])
            values.append(val)
            colors.append(GROUP_COLORS[group])
    
    # Add Combined Others bar (if we have Combined score)
    combined = scores.get('Combined')
    if combined is not None:
        groups.append('Combined Others')
        values.append(combined)
        colors.append('#333333')  # Dark grey/black to distinguish from Line Manager
    
    if not values:
        return False
    
    # Reverse for display (Self at top, Combined at bottom)
    groups = groups[::-1]
    values = values[::-1]
    colors = colors[::-1]
    
    fig, ax = plt.subplots(figsize=(4, max(0.8, len(groups) * 0.35)))
    
    y_pos = np.arange(len(groups))
    bars = ax.barh(y_pos, values, color=colors, height=0.55)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(groups, fontsize=8)
    ax.set_xlim(0, 5.5)
    ax.set_xticks([1, 2, 3, 4, 5])
    
    ax.axvline(x=4, color='green', linestyle='--', alpha=0.3, linewidth=1)
    ax.axvline(x=3, color='gray', linestyle=':', alpha=0.3, linewidth=1)
    
    for bar, val in zip(bars, values):
        ax.text(val + 0.08, bar.get_y() + bar.get_height()/2, f'{val:.1f}', va='center', fontsize=8)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=130, bbox_inches='tight', facecolor='white')
    plt.close()
    return True


def create_self_only_bar(score, output_path):
    """Create horizontal bar chart for self-assessment only."""
    fig, ax = plt.subplots(figsize=(4, 0.8))
    
    if score is not None:
        ax.barh([0], [score], color=COLOURS['primary_blue'], height=0.5)
        ax.text(score + 0.15, 0, f'{score:.1f}', va='center', fontsize=9, fontweight='bold')
    
    ax.set_xlim(0, 5.8)
    ax.set_ylim(-0.5, 0.5)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(['1', '2', '3', '4', '5'], fontsize=8)
    ax.set_yticks([])
    
    ax.axvline(x=4, color='green', linestyle='--', alpha=0.3, linewidth=1)
    ax.axvline(x=3, color='gray', linestyle=':', alpha=0.3, linewidth=1)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=130, bbox_inches='tight', facecolor='white')
    plt.close()


def create_cover_page(doc, leader_name, report_type, dealership=None, cohort=None):
    """Create the cover page."""
    for _ in range(6):
        doc.add_paragraph()
    
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("THE 360 DEVELOPMENT CATALYST")
    run.bold = True
    run.font.size = Pt(28)
    run.font.color.rgb = RGBColor(0x02, 0x47, 0x31)
    
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(report_type)
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    doc.add_paragraph()
    
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = name_para.add_run(leader_name)
    run.bold = True
    run.font.size = Pt(24)
    run.font.color.rgb = RGBColor(0x02, 0x47, 0x31)
    
    if dealership:
        detail = doc.add_paragraph()
        detail.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = detail.add_run(dealership)
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    if cohort:
        detail = doc.add_paragraph()
        detail.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = detail.add_run(f"Cohort: {cohort}")
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    doc.add_paragraph()
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_para.add_run(datetime.now().strftime("%B %Y"))
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    for _ in range(4):
        doc.add_paragraph()
    
    prog = doc.add_paragraph()
    prog.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = prog.add_run("Bentley Compass Leadership Programme")
    run.font.size = Pt(11)
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    doc.add_page_break()


def add_response_summary(doc, data):
    """Add response summary table."""
    doc.add_heading("Response Summary", level=2)
    
    response_counts = data.get('response_counts', {})
    hidden_groups = data.get('hidden_groups', [])
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Respondent Group"
    hdr_cells[1].text = "Responses"
    
    for cell in hdr_cells:
        set_cell_shading(cell, '024731')
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        cell.paragraphs[0].runs[0].bold = True
    
    for group in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
        if group in response_counts and response_counts[group] > 0:
            row = table.add_row().cells
            row[0].text = GROUP_DISPLAY[group]
            row[1].text = str(response_counts[group])
    
    total = sum(response_counts.values())
    row = table.add_row().cells
    row[0].text = "Total"
    row[0].paragraphs[0].runs[0].bold = True
    row[1].text = str(total)
    row[1].paragraphs[0].runs[0].bold = True
    
    doc.add_paragraph()
    
    # Add anonymity note if groups were hidden
    if hidden_groups:
        from framework import ANONYMITY_THRESHOLD
        note = doc.add_paragraph()
        note_text = (
            f"Note: To protect anonymity, respondent groups with fewer than {ANONYMITY_THRESHOLD} "
            f"responses have been combined into 'Others'. "
            f"Groups combined: {', '.join(GROUP_DISPLAY.get(g, g) for g in hidden_groups)}."
        )
        run = note.add_run(note_text)
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    doc.add_paragraph()


def add_executive_summary(doc, data):
    """Add executive summary with dimension table and radar chart."""
    doc.add_heading("Executive Summary", level=1)
    
    # Dimension table
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    
    hdr = table.rows[0].cells
    hdr[0].text = "Dimension"
    hdr[1].text = "Self"
    hdr[2].text = "Combined"
    hdr[3].text = "Gap"
    
    for cell in hdr:
        set_cell_shading(cell, '024731')
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        cell.paragraphs[0].runs[0].bold = True
    
    for dim_name in DIMENSIONS.keys():
        dim_data = data['by_dimension'].get(dim_name, {})
        row = table.add_row().cells
        row[0].text = dim_name
        row[1].text = f"{dim_data.get('Self', 0):.2f}" if dim_data.get('Self') else "-"
        row[2].text = f"{dim_data.get('Combined', 0):.2f}" if dim_data.get('Combined') else "-"
        gap = dim_data.get('Gap')
        if gap is not None:
            row[3].text = f"{gap:+.2f}"
            if gap > SIGNIFICANT_GAP:
                set_cell_shading(row[3], 'FFF2CC')
            elif gap < -SIGNIFICANT_GAP:
                set_cell_shading(row[3], 'C6EFCE')
    
    doc.add_paragraph()
    
    # Radar chart
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        self_scores = {dim: data['by_dimension'].get(dim, {}).get('Self') for dim in DIMENSIONS}
        combined_scores = {dim: data['by_dimension'].get(dim, {}).get('Combined') for dim in DIMENSIONS}
        create_radar_chart(DIMENSIONS, self_scores, combined_scores, tmp.name)
        doc.add_picture(tmp.name, width=Inches(5))
        os.unlink(tmp.name)
    
    doc.add_page_break()


def set_column_widths(table, widths_inches):
    """Set column widths for a table."""
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths_inches):
                cell.width = Inches(widths_inches[i])


def create_papu_table(doc, items, header_color, title, description, include_not_seen=False):
    """Create a consistent PAPU-NANU table."""
    # Title as styled paragraph (not heading)
    title_para = doc.add_paragraph()
    title_run = title_para.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(12)
    title_run.font.color.rgb = RGBColor(
        int(header_color[0:2], 16),
        int(header_color[2:4], 16),
        int(header_color[4:6], 16)
    )
    
    # Description
    desc_para = doc.add_paragraph(description)
    desc_para.runs[0].font.size = Pt(10)
    desc_para.runs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    if not items:
        doc.add_paragraph("No items currently fall into this category.")
        doc.add_paragraph()
        return
    
    # Determine columns
    if include_not_seen:
        cols = 6
        headers = ['#', 'Behaviour', 'Self', 'Others', 'Gap', 'Not Seen']
        widths = [0.4, 4.0, 0.55, 0.65, 0.55, 0.75]
    else:
        cols = 5
        headers = ['#', 'Behaviour', 'Self', 'Others', 'Gap']
        widths = [0.47, 4.0, 0.69, 0.69, 0.69]
    
    table = doc.add_table(rows=1, cols=cols)
    table.style = 'Table Grid'
    
    # Header row
    hdr = table.rows[0].cells
    for i, header_text in enumerate(headers):
        hdr[i].text = header_text
        set_cell_shading(hdr[i], header_color)
        hdr[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        hdr[i].paragraphs[0].runs[0].font.size = Pt(9)
        hdr[i].paragraphs[0].runs[0].bold = True
    
    # Data rows
    for item in items:
        row = table.add_row().cells
        row[0].text = str(item['item_num'])
        row[1].text = item['text']
        row[2].text = f"{item['self']:.1f}"
        row[3].text = f"{item['combined']:.1f}"
        row[4].text = f"{item['gap']:+.1f}" if item.get('gap') is not None else "-"
        
        if include_not_seen:
            row[5].text = str(item['no_opp_count']) if item.get('no_opp_count') else "-"
        
        # Set font size for all cells
        for cell in row:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)
    
    set_column_widths(table, widths)
    doc.add_paragraph()


def add_papu_nanu_section(doc, data):
    """Add strengths and development areas analysis."""
    doc.add_heading("Strengths & Development Analysis", level=1)
    
    intro = doc.add_paragraph(
        "This analysis compares your self-ratings with how others see you, "
        "revealing patterns of agreement and potential blind spots."
    )
    doc.add_paragraph()
    
    categories = categorize_papu_nanu(data)
    
    # Agreed Strengths (dark green)
    create_papu_table(
        doc,
        categories['agreed_strengths'][:8],
        '375623',
        'AGREED STRENGTHS',
        "You and others agree these are strengths - keep doing these."
    )
    
    # Good News (blue)
    create_papu_table(
        doc,
        categories['good_news'],
        '2F5496',
        'GOOD NEWS',
        "Others see these as strengths but you rate yourself lower - you're doing better than you think!"
    )
    
    # Development Areas (orange)
    create_papu_table(
        doc,
        categories['development_areas'][:8],
        'C65911',
        'DEVELOPMENT AREAS',
        "Both you and others see room for growth - priority focus for development."
    )
    
    # Hidden Talents (purple) - includes Not Seen column
    if categories['hidden_talents']:
        # Add explanatory note before Hidden Talents table
        note = doc.add_paragraph()
        note_run = note.add_run(
            "'Not Seen' shows how many respondents selected 'No Opportunity' to observe this behaviour. "
            "A high number may indicate a visibility issue rather than a genuine gap."
        )
        note_run.font.size = Pt(9)
        note_run.font.italic = True
        note_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    create_papu_table(
        doc,
        categories['hidden_talents'],
        '7030A0',
        'HIDDEN TALENTS',
        "You rate yourself higher than others do. These may be genuine talents that aren't visible to others, or potential blind spots.",
        include_not_seen=True
    )
    
    doc.add_page_break()


def add_comments_table(doc, comments_list, title=None):
    """Add a comments table with Source/Comment columns matching sample format."""
    if not comments_list:
        return
    
    if title:
        heading = doc.add_paragraph()
        run = heading.add_run(title)
        run.bold = True
        run.font.size = Pt(11)
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    
    # Header row
    hdr = table.rows[0].cells
    hdr[0].text = "Source"
    hdr[1].text = "Comment"
    
    for cell in hdr:
        set_cell_shading(cell, 'D9D9D9')
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9)
    
    # Data rows
    for comment in comments_list:
        row = table.add_row().cells
        row[0].text = GROUP_DISPLAY.get(comment['group'], comment['group'])
        row[1].text = comment['text']
        
        for cell in row:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)
    
    # Set column widths (narrow source, wide comment)
    set_column_widths(table, [1.1, 5.4])
    
    doc.add_paragraph()


def add_dimension_section(doc, dim_name, data, comments, is_self_only=False):
    """Add a dimension section with items and charts."""
    doc.add_heading(dim_name, level=1)
    
    desc = doc.add_paragraph()
    run = desc.add_run(DIMENSION_DESCRIPTIONS[dim_name])
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    doc.add_paragraph()
    
    start, end = DIMENSIONS[dim_name]
    
    for item_num in range(start, end + 1):
        item_scores = data['by_item'].get(item_num, {})
        item_text = item_scores.get('text', ITEMS.get(item_num, ''))
        
        layout_table = doc.add_table(rows=1, cols=2)
        make_table_borderless(layout_table)
        
        text_cell = layout_table.rows[0].cells[0]
        text_cell.width = Inches(3.5)
        text_para = text_cell.paragraphs[0]
        text_para.add_run(f"Q{item_num}. {item_text}")
        
        chart_cell = layout_table.rows[0].cells[1]
        chart_cell.width = Inches(3.0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            if is_self_only:
                create_self_only_bar(item_scores.get('Self'), tmp.name)
            else:
                create_item_bar_chart(item_scores, tmp.name)
            
            chart_para = chart_cell.paragraphs[0]
            chart_para.add_run().add_picture(tmp.name, width=Inches(2.8))
            os.unlink(tmp.name)
        
        doc.add_paragraph()
    
    # Comments table for this section
    section_comments = comments.get('by_section', {}).get(dim_name, [])
    if section_comments:
        add_comments_table(doc, section_comments, f"Comments on {dim_name}")
    
    doc.add_page_break()


def add_overall_comments(doc, comments):
    """Add overall qualitative feedback section matching sample format."""
    doc.add_heading("Overall Qualitative Feedback", level=1)
    
    # Strengths section
    strengths_heading = doc.add_paragraph()
    run = strengths_heading.add_run("What does this leader do particularly well?")
    run.bold = True
    run.font.size = Pt(11)
    
    if comments.get('strengths'):
        add_comments_table(doc, comments['strengths'])
    else:
        doc.add_paragraph("No comments provided.")
        doc.add_paragraph()
    
    # Development section
    dev_heading = doc.add_paragraph()
    run = dev_heading.add_run("What could this leader do differently or develop further?")
    run.bold = True
    run.font.size = Pt(11)
    
    if comments.get('development'):
        add_comments_table(doc, comments['development'])
    else:
        doc.add_paragraph("No comments provided.")
        doc.add_paragraph()
    
    doc.add_page_break()


def add_next_steps(doc):
    """Add next steps section."""
    doc.add_heading("Next Steps", level=1)
    
    doc.add_paragraph(
        "This feedback provides a foundation for your ongoing leadership development. "
        "Consider the following as you reflect on your results:"
    )
    
    steps = [
        "Review your Agreed Strengths - how can you leverage these more deliberately?",
        "Consider the Good News items - are you being too hard on yourself in these areas?",
        "Focus on 2-3 Development Areas - what specific actions could you take?",
        "Explore any Hidden Talents - is this a visibility issue or a genuine gap?",
        "Discuss your results with your coach to create a focused development plan.",
    ]
    
    for step in steps:
        para = doc.add_paragraph(step, style='List Bullet')
    
    doc.add_paragraph()
    doc.add_paragraph(
        "Remember: this feedback represents perceptions at a point in time. "
        "Use it as data to inform your development, not as a definitive judgement."
    )


def generate_report(leader_name, report_type, data, comments, dealership=None, cohort=None):
    """
    Main entry point for report generation.
    
    Args:
        leader_name: Name of the leader
        report_type: 'Self-Assessment', 'Full 360', or 'Progress Report'
        data: Feedback data dictionary
        comments: Comments dictionary
        dealership: Optional dealership name
        cohort: Optional cohort name
    
    Returns:
        Path to generated report file
    """
    doc = Document()
    
    if report_type == 'Self-Assessment':
        create_cover_page(doc, leader_name, "Self-Assessment Report", dealership, cohort)
        
        doc.add_heading("About This Report", level=1)
        doc.add_paragraph(
            "This self-assessment report captures your own view of your leadership effectiveness "
            "across the eight dimensions of the Compass framework. It forms the starting point for "
            "your 360-degree feedback process."
        )
        doc.add_page_break()
        
        # Overview table
        doc.add_heading("Your Self-Assessment Overview", level=1)
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = "Dimension"
        hdr[1].text = "Self"
        for cell in hdr:
            set_cell_shading(cell, '024731')
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        
        for dim_name in DIMENSIONS.keys():
            row = table.add_row().cells
            row[0].text = dim_name
            self_score = data['by_dimension'].get(dim_name, {}).get('Self')
            row[1].text = f"{self_score:.2f}" if self_score else "-"
        
        doc.add_paragraph()
        
        # Radar
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            self_scores = {dim: data['by_dimension'].get(dim, {}).get('Self') for dim in DIMENSIONS}
            create_radar_chart(DIMENSIONS, self_scores, None, tmp.name)
            doc.add_picture(tmp.name, width=Inches(5))
            os.unlink(tmp.name)
        
        doc.add_page_break()
        
        # Detailed sections
        for dim_name in DIMENSIONS.keys():
            add_dimension_section(doc, dim_name, data, comments, is_self_only=True)
        
        # Overall Effectiveness
        doc.add_heading("Overall Effectiveness", level=1)
        for item_num in [41, 42]:
            item_scores = data['by_item'].get(item_num, {})
            item_text = item_scores.get('text', ITEMS.get(item_num, ''))
            # Adjust for self-assessment
            item_text = item_text.replace("this person", "myself")
            
            layout_table = doc.add_table(rows=1, cols=2)
            make_table_borderless(layout_table)
            
            text_cell = layout_table.rows[0].cells[0]
            text_cell.width = Inches(3.5)
            text_para = text_cell.paragraphs[0]
            text_para.add_run(f"Q{item_num}. {item_text}")
            
            chart_cell = layout_table.rows[0].cells[1]
            chart_cell.width = Inches(3.0)
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                create_self_only_bar(item_scores.get('Self'), tmp.name)
                chart_para = chart_cell.paragraphs[0]
                chart_para.add_run().add_picture(tmp.name, width=Inches(2.8))
                os.unlink(tmp.name)
            
            doc.add_paragraph()
        
        doc.add_page_break()
        
        # Reflection Questions
        doc.add_heading("Reflection Questions", level=1)
        doc.add_paragraph(
            "Use these questions to prepare for your coaching conversation:"
        )
        
        reflection_questions = [
            "Looking at your highest-rated dimensions, what specific behaviours or habits contribute to these strengths?",
            "Which areas did you rate lowest, and what factors might be contributing to this?",
            "Are there any dimensions where you feel uncertain about your rating? What would help you get clearer?",
            "What patterns do you notice across your self-assessment?",
            "If you were to focus on developing one area over the next three months, which would have the biggest impact?",
            "What support or resources would help you develop in your chosen area?",
        ]
        
        for i, question in enumerate(reflection_questions, 1):
            para = doc.add_paragraph()
            para.add_run(f"{i}. ").bold = True
            para.add_run(question)
        
        doc.add_page_break()
        
        # What Happens Next
        doc.add_heading("What Happens Next", level=1)
        doc.add_paragraph(
            "This self-assessment is the first step in your 360-degree feedback process. Here's what comes next:"
        )
        
        next_steps = [
            ("Feedback Collection", "Your line manager, peers, and direct reports will be invited to provide their perspective on your leadership using the same framework."),
            ("Full 360 Report", "Once feedback is collected, you'll receive a comprehensive report comparing your self-assessment with how others see you."),
            ("Coaching Conversation", "You'll discuss your results with your coach to identify key insights and development priorities."),
            ("Development Planning", "Together with your coach, you'll create a focused development plan for the coming months."),
        ]
        
        for title, description in next_steps:
            para = doc.add_paragraph()
            para.add_run(f"{title}: ").bold = True
            para.add_run(description)
            doc.add_paragraph()
        
    elif report_type == 'Full 360':
        create_cover_page(doc, leader_name, "Feedback Report", dealership, cohort)
        
        doc.add_heading("About This Report", level=1)
        doc.add_paragraph(
            "This 360-degree feedback report brings together perspectives from your line manager, "
            "peers, direct reports, and others, alongside your self-assessment. The comparison "
            "helps identify areas of alignment and potential blind spots."
        )
        doc.add_page_break()
        
        add_response_summary(doc, data)
        add_executive_summary(doc, data)
        add_papu_nanu_section(doc, data)
        
        doc.add_heading("Detailed Feedback by Dimension", level=1)
        doc.add_page_break()
        
        for dim_name in DIMENSIONS.keys():
            add_dimension_section(doc, dim_name, data, comments, is_self_only=False)
        
        # Overall effectiveness
        doc.add_heading("Overall Effectiveness", level=1)
        for item_num in [41, 42]:
            item_scores = data['by_item'].get(item_num, {})
            item_text = item_scores.get('text', ITEMS.get(item_num, ''))
            
            para = doc.add_paragraph()
            para.add_run(f"{item_num}. {item_text}").bold = True
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                create_item_bar_chart(item_scores, tmp.name)
                doc.add_picture(tmp.name, width=Inches(4))
                os.unlink(tmp.name)
            
            doc.add_paragraph()
        
        doc.add_page_break()
        
        add_overall_comments(doc, comments)
        add_next_steps(doc)
    
    else:  # Progress Report
        create_cover_page(doc, leader_name, "Progress Report", dealership, cohort)
        doc.add_paragraph("Progress report generation coming soon...")
    
    # Save
    filename = f"{leader_name.replace(' ', '_')}_{report_type.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.docx"
    output_path = REPORTS_DIR / filename
    doc.save(output_path)
    
    return str(output_path)


def generate_all_reports(db, leader_ids=None):
    """Generate reports for multiple leaders."""
    from database import Database
    
    if leader_ids is None:
        leaders = db.get_all_leaders()
        leader_ids = [l['id'] for l in leaders if l['completed_raters'] >= 5]
    
    generated = []
    for leader_id in leader_ids:
        leader = db.get_leader(leader_id)
        data, comments = db.get_leader_feedback_data(leader_id)
        
        output_path = generate_report(
            leader['name'],
            'Full 360',
            data,
            comments,
            leader.get('dealership'),
            leader.get('cohort')
        )
        generated.append(output_path)
    
    return generated
