#!/usr/bin/env python3
"""
Report generator for the 360 Development Catalyst.
Generates Word documents for Self-Assessment, Full 360, and Progress Reports.

Updated for 9 dimensions (47 items total) with Performance Excellence dimension.
Overall Effectiveness is now Q46-47.
"""

import numpy as np
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn, nsdecls
from docx.oxml import OxmlElement, parse_xml
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from datetime import datetime
import tempfile
import os
import requests
from pathlib import Path

from framework import (
    DIMENSIONS, ITEMS, DIMENSION_DESCRIPTIONS,
    COLOURS, GROUP_COLOURS, GROUP_DISPLAY,
    HIGH_SCORE_THRESHOLD, SIGNIFICANT_GAP
)

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Overall effectiveness questions (now 46 and 47)
OVERALL_ITEMS = [46, 47]

# Colour map for comment source labels (RGB tuples for python-docx)
COMMENT_SOURCE_COLOURS = {
    'Line Manager': RGBColor(0x72, 0x2F, 0x37),   # Burgundy
    'Peers':        RGBColor(0x0A, 0x5E, 0x55),   # Deep Teal
    'Direct Reports': RGBColor(0xB8, 0x86, 0x0B),  # Bentley Gold
    'Others':       RGBColor(0x4A, 0x55, 0x68),    # Slate Grey
    'Self':         RGBColor(0x02, 0x47, 0x31),    # Bentley Green
}


def set_cell_shading(cell, color):
    """Set background colour of a table cell."""
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shading)


def add_section_heading(doc, text, font_size=18):
    """Add a major section heading with larger font."""
    heading = doc.add_heading(text, level=1)
    for run in heading.runs:
        run.font.size = Pt(font_size)
    return heading


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


# ============================================
# CLEAN COMMENT FORMATTING
# ============================================

def _add_thin_rule(doc, colour='CCCCCC'):
    """Add a thin horizontal rule (bottom border on an empty paragraph)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    pPr = p._element.get_or_add_pPr()
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'  <w:bottom w:val="single" w:sz="4" w:space="1" w:color="{colour}"/>'
        f'</w:pBdr>'
    )
    pPr.append(pBdr)


def _add_comment_block(doc, group_name, comment_text):
    """
    Add a single comment in the clean style:
    - Source label (bold, coloured) on its own line
    - Comment text below in normal body text
    """
    # Resolve display name
    display_name = GROUP_DISPLAY.get(group_name, group_name)

    # Source label
    source_para = doc.add_paragraph()
    source_para.paragraph_format.space_before = Pt(8)
    source_para.paragraph_format.space_after = Pt(2)
    run = source_para.add_run(display_name)
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = COMMENT_SOURCE_COLOURS.get(
        display_name, RGBColor(0x4A, 0x55, 0x68)
    )

    # Comment text
    comment_para = doc.add_paragraph()
    comment_para.paragraph_format.space_before = Pt(0)
    comment_para.paragraph_format.space_after = Pt(6)
    run = comment_para.add_run(comment_text)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x2D, 0x2D, 0x2D)


def add_clean_comments(doc, comments_list):
    """
    Add a set of comments in the clean rule-separated style.
    comments_list: list of dicts with 'group' and 'text' keys.
    """
    if not comments_list:
        return

    _add_thin_rule(doc)
    for comment in comments_list:
        _add_comment_block(doc, comment['group'], comment['text'])
        _add_thin_rule(doc)


# ============================================
# PAPU-NANU CATEGORISATION
# ============================================

def categorize_papu_nanu(data):
    """Categorise items into PAPU-NANU quadrants."""
    categories = {
        'agreed_strengths': [],
        'good_news': [],
        'development_areas': [],
        'hidden_talents': [],
    }
    
    for item_num, item_scores in data['by_item'].items():
        # Skip overall effectiveness items
        if item_num in OVERALL_ITEMS:
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


# ============================================
# CHARTS
# ============================================

def create_radar_chart(dimensions, self_scores, combined_scores, output_path):
    """Create radar chart for dimension overview - professional style."""
    labels = list(dimensions.keys())
    num_vars = len(labels)
    
    # Calculate angles - start at top and go CLOCKWISE
    # We need to go from 90 degrees (top) decreasing (clockwise)
    angles_deg = [90 - (360 * i / num_vars) for i in range(num_vars)]
    angles = [np.radians(a) for a in angles_deg]
    angles += angles[:1]  # Complete the circle
    
    # Get values
    self_values = [self_scores.get(dim, 0) or 0 for dim in labels]
    self_values += self_values[:1]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12), subplot_kw=dict(polar=True))
    
    # Set theta to start from top and go clockwise
    ax.set_theta_offset(np.pi / 2)  # Start from top
    ax.set_theta_direction(-1)  # Go clockwise
    
    # Recalculate angles for clockwise from top (simpler now with direction set)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]
    
    # Get values again with new angle order
    self_values = [self_scores.get(dim, 0) or 0 for dim in labels]
    self_values += self_values[:1]
    
    # Style the grid
    ax.set_facecolor('white')
    ax.spines['polar'].set_color('#999999')
    ax.spines['polar'].set_linewidth(1.5)
    ax.grid(color='#999999', linestyle='-', linewidth=1, alpha=0.8)
    
    # Plot Self scores
    ax.plot(angles, self_values, 'o-', linewidth=3, label='Self', 
            color=COLOURS['bentley_green'], markersize=10)
    ax.fill(angles, self_values, alpha=0.25, color=COLOURS['bentley_green'])
    
    # Plot Combined scores if available
    if combined_scores and any(combined_scores.get(dim) for dim in labels):
        combined_values = [combined_scores.get(dim, 0) or 0 for dim in labels]
        combined_values += combined_values[:1]
        ax.plot(angles, combined_values, 'o-', linewidth=3, label='Combined Others', 
                color=COLOURS['bentley_gold'], markersize=10)
        ax.fill(angles, combined_values, alpha=0.25, color=COLOURS['bentley_gold'])
    
    # Configure the chart
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(['1', '2', '3', '4', '5'], size=14, color='#333333', fontweight='bold')
    ax.set_rlabel_position(30)
    
    # Set the labels directly using matplotlib's built-in method
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=14, fontweight='bold', color='#333333')
    
    # Adjust label padding - increase to push labels further from chart
    ax.tick_params(axis='x', pad=35)
    
    # Add legend
    if combined_scores and any(combined_scores.get(dim) for dim in labels):
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.15), 
                  ncol=2, fontsize=14, frameon=False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white', pad_inches=0.3)
    plt.close()


def create_item_bar_chart(scores, output_path, include_combined=True):
    """Create horizontal bar chart for an item showing all respondent groups."""
    groups = []
    values = []
    colors = []
    
    for group in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
        val = scores.get(group)
        if val is not None:
            groups.append(GROUP_DISPLAY[group])
            values.append(val)
            colors.append(GROUP_COLOURS[group])
    
    # Add combined bar if requested and available
    if include_combined and scores.get('Combined') is not None:
        groups.append('Combined Others')
        values.append(scores['Combined'])
        colors.append('#333333')  # Black for combined
    
    if not values:
        return False
    
    groups = groups[::-1]
    values = values[::-1]
    colors = colors[::-1]
    
    fig, ax = plt.subplots(figsize=(4.5, max(0.8, len(groups) * 0.5)))
    
    y_pos = np.arange(len(groups))
    bars = ax.barh(y_pos, values, color=colors, height=0.5)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(groups, fontsize=10, fontweight='bold')
    ax.set_xlim(0, 6.0)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.tick_params(axis='x', labelsize=10)
    
    ax.axvline(x=4, color='green', linestyle='--', alpha=0.3, linewidth=1)
    ax.axvline(x=3, color='gray', linestyle=':', alpha=0.3, linewidth=1)
    
    # Place all scores at fixed right-aligned position
    for bar, val in zip(bars, values):
        ax.text(5.7, bar.get_y() + bar.get_height()/2, f'{val:.1f}', 
                va='center', ha='right', fontsize=12, fontweight='bold')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return True


def create_self_only_bar(score, output_path):
    """Create horizontal bar chart for self-assessment only."""
    fig, ax = plt.subplots(figsize=(4.5, 0.8))
    
    if score is not None:
        ax.barh([0], [score], color=COLOURS['bentley_green'], height=0.5)
        # Place score at fixed right-aligned position
        ax.text(5.7, 0, f'{score:.1f}', va='center', ha='right', fontsize=12, fontweight='bold')
    
    ax.set_xlim(0, 6.0)
    ax.set_ylim(-0.5, 0.5)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.tick_params(axis='x', labelsize=10)
    ax.set_yticks([])
    
    ax.axvline(x=4, color='green', linestyle='--', alpha=0.3, linewidth=1)
    ax.axvline(x=3, color='gray', linestyle=':', alpha=0.3, linewidth=1)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


# ============================================
# REPORT SECTIONS
# ============================================

def _add_page_number_footer(section):
    """Add 'Page X of Y' footer to a document section, centre-aligned."""
    footer = section.footer
    footer.is_linked_to_previous = False
    para = footer.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # "Page "
    run = para.add_run("Page ")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Current page number field
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    run1 = para.add_run()
    run1._r.append(fldChar1)

    instrText1 = OxmlElement('w:instrText')
    instrText1.set(qn('xml:space'), 'preserve')
    instrText1.text = ' PAGE '
    run2 = para.add_run()
    run2._r.append(instrText1)

    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    run3 = para.add_run()
    run3._r.append(fldChar2)

    run4 = para.add_run("1")
    run4.font.size = Pt(8)
    run4.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')
    run5 = para.add_run()
    run5._r.append(fldChar3)

    # " of "
    run6 = para.add_run(" of ")
    run6.font.size = Pt(8)
    run6.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Total pages field
    fldChar4 = OxmlElement('w:fldChar')
    fldChar4.set(qn('w:fldCharType'), 'begin')
    run7 = para.add_run()
    run7._r.append(fldChar4)

    instrText2 = OxmlElement('w:instrText')
    instrText2.set(qn('xml:space'), 'preserve')
    instrText2.text = ' NUMPAGES '
    run8 = para.add_run()
    run8._r.append(instrText2)

    fldChar5 = OxmlElement('w:fldChar')
    fldChar5.set(qn('w:fldCharType'), 'separate')
    run9 = para.add_run()
    run9._r.append(fldChar5)

    run10 = para.add_run("1")
    run10.font.size = Pt(8)
    run10.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    fldChar6 = OxmlElement('w:fldChar')
    fldChar6.set(qn('w:fldCharType'), 'end')
    run11 = para.add_run()
    run11._r.append(fldChar6)


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
    
    # Ensure cover page (first section) has NO footer
    first_section = doc.sections[0]
    first_section.different_first_page_header_footer = False
    footer = first_section.footer
    footer.is_linked_to_previous = False
    # Clear any default footer content
    for p in footer.paragraphs:
        p.text = ""
    
    # Add a SECTION BREAK (new page) so the rest of the report is a new section
    from docx.enum.section import WD_ORIENT
    new_section = doc.add_section()
    new_section.start_type = 2  # 2 = new page
    # Copy page dimensions from first section
    new_section.page_width = first_section.page_width
    new_section.page_height = first_section.page_height
    new_section.left_margin = first_section.left_margin
    new_section.right_margin = first_section.right_margin
    new_section.top_margin = first_section.top_margin
    new_section.bottom_margin = first_section.bottom_margin
    
    # Add "Page X of Y" footer to the new section
    _add_page_number_footer(new_section)


def add_table_of_contents(doc):
    """Add a Table of Contents page that auto-updates in Word."""
    heading = add_section_heading(doc, "Contents", font_size=18)

    # Add a TOC field — Word will populate page numbers when user presses F9
    para = doc.add_paragraph()
    run = para.add_run()
    fldChar_begin = OxmlElement('w:fldChar')
    fldChar_begin.set(qn('w:fldCharType'), 'begin')
    run._r.append(fldChar_begin)

    run2 = para.add_run()
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = ' TOC \\o "1-2" \\h \\z \\u '
    run2._r.append(instrText)

    run3 = para.add_run()
    fldChar_separate = OxmlElement('w:fldChar')
    fldChar_separate.set(qn('w:fldCharType'), 'separate')
    run3._r.append(fldChar_separate)

    # Placeholder text (shown before TOC is updated in Word)
    run4 = para.add_run("Right-click and select 'Update Field' to populate contents.")
    run4.font.size = Pt(10)
    run4.font.italic = True
    run4.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    run5 = para.add_run()
    fldChar_end = OxmlElement('w:fldChar')
    fldChar_end.set(qn('w:fldCharType'), 'end')
    run5._r.append(fldChar_end)


def add_response_summary(doc, data):
    """Add response summary table."""
    heading = add_section_heading(doc, "Response Summary", font_size=14)
    heading.paragraph_format.page_break_before = True
    
    response_counts = data.get('response_counts', {})
    hidden_groups = data.get('hidden_groups', [])
    
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    table.autofit = False
    
    # Set consistent widths (total ~6.1 inches to match PAPU-NANU tables)
    widths = [Inches(5.0), Inches(1.1)]
    
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Respondent Group"
    hdr_cells[0].width = widths[0]
    hdr_cells[1].text = "Responses"
    hdr_cells[1].width = widths[1]
    
    for cell in hdr_cells:
        set_cell_shading(cell, '024731')
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        cell.paragraphs[0].runs[0].bold = True
    
    for group in ['Self', 'Boss', 'Peers', 'DRs', 'Others']:
        if group in response_counts and response_counts[group] > 0:
            row = table.add_row().cells
            row[0].text = GROUP_DISPLAY[group]
            row[0].width = widths[0]
            row[1].text = str(response_counts[group])
            row[1].width = widths[1]
            row[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    total = sum(response_counts.values())
    row = table.add_row().cells
    row[0].text = "Total"
    row[0].width = widths[0]
    row[0].paragraphs[0].runs[0].bold = True
    row[1].text = str(total)
    row[1].width = widths[1]
    row[1].paragraphs[0].runs[0].bold = True
    row[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Add anonymity note if groups were hidden (no extra spacing)
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


def add_executive_summary(doc, data):
    """Add executive summary with dimension table and radar chart."""
    add_section_heading(doc, "Executive Summary", font_size=16)
    
    # Dimension table with proper column widths
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    table.autofit = False
    
    # Set column widths to match other tables (total ~6.1 inches)
    widths = [Inches(3.9), Inches(0.7), Inches(1.0), Inches(0.5)]
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            cell.width = widths[i]
    
    hdr = table.rows[0].cells
    hdr[0].text = "Dimension"
    hdr[1].text = "Self"
    hdr[2].text = "Combined"
    hdr[3].text = "Gap"
    
    for cell in hdr:
        set_cell_shading(cell, '024731')
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(10)
    
    for dim_name in DIMENSIONS.keys():
        dim_data = data['by_dimension'].get(dim_name, {})
        row = table.add_row().cells
        
        # Set widths for each new row
        for i, cell in enumerate(row):
            cell.width = widths[i]
        
        row[0].text = dim_name
        row[1].text = f"{dim_data.get('Self', 0):.1f}" if dim_data.get('Self') else "-"
        row[2].text = f"{dim_data.get('Combined', 0):.1f}" if dim_data.get('Combined') else "-"
        
        # Centre-align the score columns
        for i in [1, 2, 3]:
            row[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        gap = dim_data.get('Gap')
        if gap is not None:
            row[3].text = f"{gap:+.1f}"
            if gap > SIGNIFICANT_GAP:
                set_cell_shading(row[3], 'FFF2CC')  # Yellow for over-rating
            elif gap < -SIGNIFICANT_GAP:
                set_cell_shading(row[3], 'C6EFCE')  # Green for under-rating
        else:
            row[3].text = "-"
    
    # Radar chart - sized to fit on same page as table above
    # First, keep the table together with the chart
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.keep_with_next = True

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        self_scores = {dim: data['by_dimension'].get(dim, {}).get('Self') for dim in DIMENSIONS}
        combined_scores = {dim: data['by_dimension'].get(dim, {}).get('Combined') for dim in DIMENSIONS}
        create_radar_chart(DIMENSIONS, self_scores, combined_scores, tmp.name)
        
        # Horizontal rule to separate table from radar
        _add_thin_rule(doc)

        # Add picture and centre it — sized to fit on same page as table above
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run()
        run.add_picture(tmp.name, width=Inches(3.74))  # 9.5cm
        os.unlink(tmp.name)
    
    # No explicit page break — next section uses page_break_before


def add_papu_nanu_section(doc, data):
    """Add strengths and development areas analysis."""
    heading = add_section_heading(doc, "Strengths & Development Analysis", font_size=16)
    heading.paragraph_format.page_break_before = True
    
    categories = categorize_papu_nanu(data)
    
    # Helper function to create consistent PAPU-NANU tables
    def keep_table_together(table):
        """Prevent table rows from splitting across pages."""
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True
        if table.rows:
            last_row = table.rows[-1]
            for cell in last_row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = False
    
    def create_papu_table(doc, items, header_color):
        """Create a PAPU-NANU table with consistent formatting."""
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        table.autofit = False
        
        # Column widths: # | Behaviour | Self | Others | Gap
        widths = [Inches(0.4), Inches(3.9), Inches(0.6), Inches(0.6), Inches(0.6)]
        
        hdr = table.rows[0].cells
        hdr[0].text = "#"
        hdr[1].text = "Behaviour"
        hdr[2].text = "Self"
        hdr[3].text = "Others"
        hdr[4].text = "Gap"
        
        for i, cell in enumerate(hdr):
            cell.width = widths[i]
            set_cell_shading(cell, header_color)
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].runs[0].font.size = Pt(9)
            if i != 1:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        for item in items:
            row = table.add_row().cells
            for i, cell in enumerate(row):
                cell.width = widths[i]
                for para in cell.paragraphs:
                    para.paragraph_format.space_before = Pt(2)
                    para.paragraph_format.space_after = Pt(2)
            
            row[0].text = str(item['item_num'])
            row[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            row[0].paragraphs[0].runs[0].font.size = Pt(9)
            
            row[1].text = item['text']
            row[1].paragraphs[0].runs[0].font.size = Pt(9)
            
            row[2].text = f"{item['self']:.1f}"
            row[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            row[2].paragraphs[0].runs[0].font.size = Pt(9)
            
            row[3].text = f"{item['combined']:.1f}"
            row[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            row[3].paragraphs[0].runs[0].font.size = Pt(9)
            
            gap = item['gap']
            row[4].text = f"{gap:+.1f}" if gap is not None else "-"
            row[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            row[4].paragraphs[0].runs[0].font.size = Pt(9)
        
        keep_table_together(table)
        return table
    
    # Agreed Strengths (green header)
    if categories['agreed_strengths']:
        heading = doc.add_heading("Agreed Strengths", level=2)
        heading.paragraph_format.keep_with_next = True
        desc = doc.add_paragraph("You and others agree these are strengths - keep doing these.")
        desc.paragraph_format.keep_with_next = True
        create_papu_table(doc, categories['agreed_strengths'][:8], '375623')
        doc.add_paragraph()
    
    # Good News (blue header)
    if categories['good_news']:
        heading = doc.add_heading("Good News", level=2)
        heading.paragraph_format.keep_with_next = True
        desc = doc.add_paragraph("Others rate you higher than you rate yourself - you may be underselling yourself.")
        desc.paragraph_format.keep_with_next = True
        create_papu_table(doc, categories['good_news'], '2F5496')
        doc.add_paragraph()
    
    # Development Areas (orange header)
    if categories['development_areas']:
        heading = doc.add_heading("Development Areas", level=2)
        heading.paragraph_format.keep_with_next = True
        desc = doc.add_paragraph("Both you and others see room for growth - priority focus for development.")
        desc.paragraph_format.keep_with_next = True
        create_papu_table(doc, categories['development_areas'][:8], 'C65911')
        doc.add_paragraph()
    
    # Potential Blind Spots / Hidden Talents (purple header)
    if categories['hidden_talents']:
        heading = doc.add_heading("Potential Blind Spots", level=2)
        heading.paragraph_format.keep_with_next = True
        desc = doc.add_paragraph("You rate yourself higher than others do - worth exploring with your coach.")
        desc.paragraph_format.keep_with_next = True
        create_papu_table(doc, categories['hidden_talents'], '7030A0')
        doc.add_paragraph()
    
    # No explicit page break — next section uses page_break_before


def add_dimension_section(doc, dim_name, data, comments, is_self_only=False, is_first_dimension=False):
    """Add a dimension section with items displayed side-by-side with bar charts."""
    heading = doc.add_heading(dim_name, level=2)
    # First dimension flows after the "Detailed Feedback" heading; others start on new page
    if not is_first_dimension:
        heading.paragraph_format.page_break_before = True
    
    # Dimension description
    desc = doc.add_paragraph()
    run = desc.add_run(DIMENSION_DESCRIPTIONS[dim_name])
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    doc.add_paragraph()
    
    start, end = DIMENSIONS[dim_name]
    
    # Each item: side-by-side borderless table (text left, bar chart right)
    for item_num in range(start, end + 1):
        item_scores = data['by_item'].get(item_num, {})
        item_text = item_scores.get('text', ITEMS.get(item_num, ''))
        
        layout_table = doc.add_table(rows=1, cols=2)
        make_table_borderless(layout_table)
        layout_table.autofit = False
        
        text_cell = layout_table.rows[0].cells[0]
        text_cell.width = Inches(3.0)
        text_para = text_cell.paragraphs[0]
        text_para.add_run(f"Q{item_num}. ").bold = True
        text_para.add_run(item_text)
        text_para.runs[0].font.size = Pt(10)
        if len(text_para.runs) > 1:
            text_para.runs[1].font.size = Pt(10)
        text_para.paragraph_format.keep_with_next = True
        
        chart_cell = layout_table.rows[0].cells[1]
        chart_cell.width = Inches(3.0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            if is_self_only:
                create_self_only_bar(item_scores.get('Self'), tmp.name)
            else:
                create_item_bar_chart(item_scores, tmp.name)
            
            chart_para = chart_cell.paragraphs[0]
            chart_para.add_run().add_picture(tmp.name, width=Inches(2.8))
            chart_para.paragraph_format.keep_together = True
            os.unlink(tmp.name)
        
        doc.add_paragraph()
    
    # --- CLEAN COMMENTS (replaces old table style) ---
    section_comments = comments.get('by_section', {}).get(dim_name, [])
    if section_comments:
        comment_heading = doc.add_paragraph()
        run = comment_heading.add_run(f"Comments on {dim_name}")
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x02, 0x47, 0x31)

        add_clean_comments(doc, section_comments)
    
    # No explicit page break here — next section uses page_break_before


def add_overall_effectiveness(doc, data, is_self_only=False):
    """Add Overall Effectiveness section (Q46-47)."""
    heading = add_section_heading(doc, "Overall Effectiveness", font_size=16)
    heading.paragraph_format.page_break_before = True
    
    desc = doc.add_paragraph()
    run = desc.add_run("These two items provide a global assessment of leadership effectiveness.")
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    doc.add_paragraph()
    
    for item_num in OVERALL_ITEMS:
        item_scores = data['by_item'].get(item_num, {})
        item_text = item_scores.get('text', ITEMS.get(item_num, ''))
        
        layout_table = doc.add_table(rows=1, cols=2)
        make_table_borderless(layout_table)
        layout_table.autofit = False
        
        text_cell = layout_table.rows[0].cells[0]
        text_cell.width = Inches(3.0)
        text_para = text_cell.paragraphs[0]
        text_para.add_run(f"Q{item_num}. ").bold = True
        text_para.add_run(item_text)
        text_para.runs[0].font.size = Pt(10)
        if len(text_para.runs) > 1:
            text_para.runs[1].font.size = Pt(10)
        text_para.paragraph_format.keep_with_next = True
        
        chart_cell = layout_table.rows[0].cells[1]
        chart_cell.width = Inches(3.0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            if is_self_only:
                create_self_only_bar(item_scores.get('Self'), tmp.name)
            else:
                create_item_bar_chart(item_scores, tmp.name)
            
            chart_para = chart_cell.paragraphs[0]
            chart_para.add_run().add_picture(tmp.name, width=Inches(2.8))
            chart_para.paragraph_format.keep_together = True
            os.unlink(tmp.name)
        
        doc.add_paragraph()
    
    # No explicit page break — next section uses page_break_before


def add_overall_comments(doc, comments):
    """Add overall qualitative feedback section — clean style."""
    heading = add_section_heading(doc, "Overall Qualitative Feedback", font_size=16)
    heading.paragraph_format.page_break_before = True
    
    # --- STRENGTHS ---
    if comments.get('strengths'):
        heading = doc.add_heading("Greatest Strengths", level=2)
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0x02, 0x47, 0x31)

        add_clean_comments(doc, comments['strengths'])
    
    doc.add_paragraph()
    
    # --- DEVELOPMENT ---
    if comments.get('development'):
        heading = doc.add_heading("Development Suggestions", level=2)
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0x02, 0x47, 0x31)

        add_clean_comments(doc, comments['development'])


def add_reflection_questions(doc):
    """Add reflection questions for coaching preparation."""
    heading = doc.add_heading("Reflection Questions", level=1)
    heading.paragraph_format.page_break_before = True
    
    doc.add_paragraph(
        "Before your coaching session, take some time to reflect on your self-assessment. "
        "Consider the following questions:"
    )
    
    questions = [
        "Which dimensions did you rate yourself highest on? What evidence supports these ratings?",
        "Which dimensions did you rate yourself lowest on? What makes these areas challenging?",
        "Were there any items where you found it difficult to decide on a rating? What made them difficult?",
        "Which 2-3 areas would you most like to develop? Why are these important to you?",
        "What support or resources might help you develop in these areas?",
        "What would success look like for you in your leadership development journey?",
    ]
    
    for i, question in enumerate(questions, 1):
        para = doc.add_paragraph()
        para.add_run(f"{i}. ").bold = True
        para.add_run(question)
        doc.add_paragraph()


def add_what_happens_next(doc):
    """Add What Happens Next section for self-assessment reports."""
    heading = doc.add_heading("What Happens Next", level=1)
    heading.paragraph_format.page_break_before = True
    
    steps = [
        ("Feedback Collection", 
         "Your nominated respondents will receive a link to provide their feedback on your leadership. "
         "This includes your line manager, peers, direct reports, and any others you've nominated."),
        ("Feedback Report", 
         "Once sufficient responses have been received (minimum 5 respondents), your full 360 feedback "
         "report will be generated. This will show how others' perceptions compare with your self-assessment."),
        ("Coaching Session", 
         "You will meet with your coach to explore your feedback in depth. This is an opportunity to "
         "understand the data, identify patterns, and begin planning your development."),
        ("Development Planning", 
         "Working with your coach, you will create a focused development plan targeting 2-3 key areas "
         "for growth over the coming months."),
        ("Ongoing Support", 
         "Your development continues with support from your coach, your line manager, and the resources "
         "available through the Compass programme."),
    ]
    
    for i, (title, description) in enumerate(steps, 1):
        para = doc.add_paragraph()
        para.add_run(f"{i}. {title}: ").bold = True
        para.add_run(description)
        doc.add_paragraph()


def synthesise_feedback_themes(leader_name, comments, data):
    """
    Use the Claude API to synthesise key themes from all verbatim feedback.
    
    Returns a list of theme dicts: [{'title': str, 'narrative': str}, ...]
    Returns None if API call fails or insufficient comments.
    """
    import json
    
    # Collect all comments into a structured prompt
    all_comments = []
    
    # Dimension comments
    for dim_name, dim_comments in comments.get('by_section', {}).items():
        for c in dim_comments:
            all_comments.append({
                'dimension': dim_name,
                'source': c['group'],
                'text': c['text']
            })
    
    # Overall strengths/development comments
    for c in comments.get('strengths', []):
        all_comments.append({
            'dimension': 'Overall Strengths',
            'source': c['group'],
            'text': c['text']
        })
    for c in comments.get('development', []):
        all_comments.append({
            'dimension': 'Overall Development',
            'source': c['group'],
            'text': c['text']
        })
    
    # Need enough comments to synthesise meaningfully
    if len(all_comments) < 5:
        return None
    
    # Build dimension scores context
    scores_context = []
    for dim_name in DIMENSIONS.keys():
        dim_data = data.get('by_dimension', {}).get(dim_name, {})
        self_score = dim_data.get('Self')
        combined = dim_data.get('Combined')
        gap = dim_data.get('Gap')
        if combined:
            scores_context.append(f"{dim_name}: Self={self_score}, Others={combined}, Gap={gap:+.1f}" if gap else f"{dim_name}: Combined={combined}")
    
    prompt = f"""You are writing a section of a 360-degree feedback report for {leader_name}. This section synthesises the key themes from their verbatim feedback. The leader will read this directly, so write in the second person — use "you", "your", "your feedback suggests" etc. Never refer to them as "the leader" or "this leader".

The tone should be warm, constructive, and developmental — as if a skilled coach were talking them through their feedback. Be direct but supportive.

Below are all the verbatim comments from their feedback, organised by dimension and source group, followed by their dimension scores.

VERBATIM COMMENTS:
{json.dumps(all_comments, indent=2)}

DIMENSION SCORES:
{chr(10).join(scores_context)}

Please identify 4-6 key themes that emerge from this feedback. For each theme:
1. Give it a clear, concise title (e.g., "Building Trust Through Authenticity" or "Balancing Operational Focus with Strategic Thinking")
2. Write a 2-3 sentence narrative that synthesises the evidence — reference what respondents said without quoting them verbatim, connect to the quantitative scores where relevant, and speak directly to {leader_name} using "you" and "your".

Respond ONLY with a JSON array of objects, each with "title" and "narrative" keys. No preamble, no markdown formatting, just the JSON array."""

    try:
        import requests
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": _get_api_key(),
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result['content'][0]['text'].strip()
            # Clean any markdown fencing
            text = text.replace('```json', '').replace('```', '').strip()
            themes = json.loads(text)
            return themes
        else:
            print(f"API returned status {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"Theme synthesis failed: {e}")
        return None


def _get_api_key():
    """Get the Anthropic API key from environment or Streamlit secrets."""
    # Try Streamlit secrets first
    try:
        import streamlit as st
        key = st.secrets.get("anthropic", {}).get("api_key")
        if key:
            return key
    except Exception:
        pass
    
    # Fall back to environment variable
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    
    raise ValueError("No Anthropic API key found. Set ANTHROPIC_API_KEY or add to Streamlit secrets.")


def add_theme_synthesis(doc, leader_name, comments, data):
    """
    Add the AI-generated theme synthesis section to the report.
    
    Falls back gracefully if the API is unavailable — the report still generates
    without the synthesis section.
    """
    themes = synthesise_feedback_themes(leader_name, comments, data)
    
    if not themes:
        return  # Silently skip if synthesis unavailable
    
    heading = add_section_heading(doc, "Key Themes in Your Feedback", font_size=16)
    heading.paragraph_format.page_break_before = True
    
    intro = doc.add_paragraph(
        "The following themes have been identified from the qualitative feedback provided by your "
        "respondents. These represent the patterns and consistent messages that emerge when all "
        "comments are considered together."
    )
    intro.paragraph_format.space_after = Pt(12)
    
    for i, theme in enumerate(themes):
        # Theme title
        title_para = doc.add_paragraph()
        title_para.paragraph_format.space_before = Pt(12) if i > 0 else Pt(6)
        title_para.paragraph_format.space_after = Pt(4)
        run = title_para.add_run(f"{i + 1}. {theme['title']}")
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x02, 0x47, 0x31)  # Bentley green
        
        # Theme narrative
        narrative_para = doc.add_paragraph(theme['narrative'])
        narrative_para.paragraph_format.space_after = Pt(8)
        for run in narrative_para.runs:
            run.font.size = Pt(10)
    
    # Closing note
    _add_thin_rule(doc)
    note = doc.add_paragraph()
    run = note.add_run(
        "Note: This synthesis has been generated to help identify patterns in your feedback. "
        "It should be explored in your coaching session alongside the detailed verbatim comments above."
    )
    run.font.size = Pt(9)
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)


def add_next_steps(doc):
    """Add next steps section for full 360 reports."""
    heading = add_section_heading(doc, "Next Steps", font_size=16)
    heading.paragraph_format.page_break_before = True
    
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


# ============================================
# MAIN GENERATION
# ============================================

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
        
        # About This Report — styled heading, its own page
        about_heading = add_section_heading(doc, "About This Report", font_size=16)
        doc.add_paragraph(
            "This self-assessment report captures your own view of your leadership effectiveness "
            "across the nine dimensions of the Compass framework. It forms the starting point for "
            "your 360-degree feedback process."
        )
        doc.add_paragraph()
        doc.add_paragraph(
            "The report is structured as follows:"
        )
        sections_list = [
            "Your Self-Assessment Overview — your dimension scores at a glance with a radar chart",
            "Detailed Self-Assessment by Dimension — item-level scores with bar charts for each of the nine dimensions",
            "Overall Effectiveness — two global leadership effectiveness items",
            "Reflection Questions — prompts to help you prepare for your coaching session",
            "What Happens Next — the next steps in the 360 feedback process",
        ]
        for item in sections_list:
            para = doc.add_paragraph(item, style='List Bullet')
        
        # Contents page
        add_table_of_contents(doc)
        
        # Overview — dimension table + radar on one page
        heading = add_section_heading(doc, "Your Self-Assessment Overview", font_size=16)
        heading.paragraph_format.page_break_before = True
        
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        table.autofit = False
        
        widths = [Inches(4.6), Inches(1.5)]
        
        hdr = table.rows[0].cells
        hdr[0].text = "Dimension"
        hdr[1].text = "Your Score"
        for i, cell in enumerate(hdr):
            cell.width = widths[i]
            set_cell_shading(cell, '024731')
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].runs[0].font.size = Pt(10)
        if len(hdr) > 1:
            hdr[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        for dim_name in DIMENSIONS.keys():
            row = table.add_row().cells
            for i, cell in enumerate(row):
                cell.width = widths[i]
            row[0].text = dim_name
            self_score = data['by_dimension'].get(dim_name, {}).get('Self')
            row[1].text = f"{self_score:.1f}" if self_score else "-"
            row[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Keep table with radar
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True
        
        # Horizontal rule + radar chart
        _add_thin_rule(doc)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            self_scores = {dim: data['by_dimension'].get(dim, {}).get('Self') for dim in DIMENSIONS}
            create_radar_chart(DIMENSIONS, self_scores, None, tmp.name)
            
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run()
            run.add_picture(tmp.name, width=Inches(3.74))  # 9.5cm
            os.unlink(tmp.name)
        
        # Detailed sections — with parent heading that flows into first dimension
        detail_heading = add_section_heading(doc, "Detailed Self-Assessment by Dimension", font_size=18)
        detail_heading.paragraph_format.page_break_before = True
        detail_heading.paragraph_format.keep_with_next = True
        
        for i, dim_name in enumerate(DIMENSIONS.keys()):
            add_dimension_section(doc, dim_name, data, comments, is_self_only=True,
                                  is_first_dimension=(i == 0))
        
        # Overall Effectiveness
        add_overall_effectiveness(doc, data, is_self_only=True)
        
        # Reflection Questions
        add_reflection_questions(doc)
        
        # What Happens Next
        add_what_happens_next(doc)
        
    elif report_type == 'Full 360':
        create_cover_page(doc, leader_name, "Feedback Report", dealership, cohort)
        
        # About This Report — its own page (cover page already has a page break)
        about_heading = add_section_heading(doc, "About This Report", font_size=16)
        doc.add_paragraph(
            "This 360-degree feedback report brings together perspectives from your line manager, "
            "peers, direct reports, and others, alongside your self-assessment. The comparison "
            "helps identify areas of alignment and potential blind spots."
        )
        doc.add_paragraph()
        doc.add_paragraph(
            "The report is structured as follows:"
        )
        sections_list = [
            "Response Summary & Executive Summary — who responded and your dimension scores at a glance",
            "Strengths & Development Analysis — where you and others agree, and where perceptions differ",
            "Detailed Feedback by Dimension — item-level scores with bar charts for each of the nine dimensions",
            "Overall Effectiveness — two global leadership effectiveness items",
            "Overall Qualitative Feedback — verbatim comments on your greatest strengths and development areas",
            "Key Themes in Your Feedback — patterns and consistent messages identified across all your feedback",
            "Next Steps — guidance for making the most of your feedback",
        ]
        for item in sections_list:
            para = doc.add_paragraph(item, style='List Bullet')
        
        # Contents page
        add_table_of_contents(doc)
        
        # Response Summary + Executive Summary + Radar — all on one page
        add_response_summary(doc, data)
        add_executive_summary(doc, data)
        
        add_papu_nanu_section(doc, data)
        
        # Detailed Feedback by Dimension
        # The section title is added before the first dimension only
        detail_heading = add_section_heading(doc, "Detailed Feedback by Dimension", font_size=18)
        detail_heading.paragraph_format.page_break_before = True
        # keep_with_next ensures heading stays with first dimension
        detail_heading.paragraph_format.keep_with_next = True
        
        for i, dim_name in enumerate(DIMENSIONS.keys()):
            add_dimension_section(doc, dim_name, data, comments, is_self_only=False,
                                  is_first_dimension=(i == 0))
        
        # Overall effectiveness (now Q46-47)
        add_overall_effectiveness(doc, data, is_self_only=False)
        
        add_overall_comments(doc, comments)
        add_theme_synthesis(doc, leader_name, comments, data)
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
