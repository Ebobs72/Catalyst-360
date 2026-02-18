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
    COLOURS, GROUP_COLOURS, GROUP_DISPLAY,
    HIGH_SCORE_THRESHOLD, SIGNIFICANT_GAP
)

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Overall effectiveness questions (now 46 and 47)
OVERALL_ITEMS = [46, 47]


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
    add_section_heading(doc, "Response Summary", font_size=16)
    
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
    
    # Radar chart - sized to fit on same page as tables above
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        self_scores = {dim: data['by_dimension'].get(dim, {}).get('Self') for dim in DIMENSIONS}
        combined_scores = {dim: data['by_dimension'].get(dim, {}).get('Combined') for dim in DIMENSIONS}
        create_radar_chart(DIMENSIONS, self_scores, combined_scores, tmp.name)
        
        # Add picture and centre it
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run()
        run.add_picture(tmp.name, width=Inches(5.0))
        os.unlink(tmp.name)
    
    doc.add_page_break()


def add_papu_nanu_section(doc, data):
    """Add strengths and development areas analysis."""
    add_section_heading(doc, "Strengths & Development Analysis", font_size=16)
    
    categories = categorize_papu_nanu(data)
    
    # Helper function to create consistent PAPU-NANU tables
    def keep_table_together(table):
        """Prevent table rows from splitting across pages."""
        for row in table.rows:
            # Set "keep with next" for all rows except the last
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True
        # Last row doesn't need keep_with_next
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
        # Total width ~6.1 inches to match other tables
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
            if i != 1:  # Centre all except Behaviour
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        for item in items:
            row = table.add_row().cells
            for i, cell in enumerate(row):
                cell.width = widths[i]
                # Add vertical padding by setting paragraph spacing
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
        
        # Keep table together on one page
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
    
    # Good News (blue header) - others rate higher than self
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
    
    doc.add_page_break()


def add_dimension_section(doc, dim_name, data, comments, is_self_only=False):
    """Add a dimension section with items displayed side-by-side with bar charts."""
    doc.add_heading(dim_name, level=2)
    
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
        
        # Create 2-column borderless table for side-by-side layout
        layout_table = doc.add_table(rows=1, cols=2)
        make_table_borderless(layout_table)
        layout_table.autofit = False
        
        # Left cell: Question text (~3 inches)
        text_cell = layout_table.rows[0].cells[0]
        text_cell.width = Inches(3.0)
        text_para = text_cell.paragraphs[0]
        text_para.add_run(f"Q{item_num}. ").bold = True
        text_para.add_run(item_text)
        text_para.runs[0].font.size = Pt(10)
        if len(text_para.runs) > 1:
            text_para.runs[1].font.size = Pt(10)
        # Keep statement with its chart
        text_para.paragraph_format.keep_with_next = True
        
        # Right cell: Bar chart (~3 inches)
        chart_cell = layout_table.rows[0].cells[1]
        chart_cell.width = Inches(3.0)
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            if is_self_only:
                create_self_only_bar(item_scores.get('Self'), tmp.name)
            else:
                create_item_bar_chart(item_scores, tmp.name)
            
            chart_para = chart_cell.paragraphs[0]
            chart_para.add_run().add_picture(tmp.name, width=Inches(2.8))
            # Keep chart paragraph together
            chart_para.paragraph_format.keep_together = True
            os.unlink(tmp.name)
        
        doc.add_paragraph()
    
    # Section comments
    section_comments = comments.get('by_section', {}).get(dim_name, [])
    if section_comments:
        comment_heading = doc.add_paragraph()
        run = comment_heading.add_run(f"Comments on {dim_name}")
        run.bold = True
        run.font.size = Pt(11)
        
        # Create comments table with proper widths
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        table.autofit = False
        
        hdr = table.rows[0].cells
        hdr[0].text = "Source"
        hdr[0].width = Inches(1.2)
        hdr[1].text = "Comment"
        hdr[1].width = Inches(5.0)
        
        for cell in hdr:
            set_cell_shading(cell, '024731')
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].runs[0].bold = True
        
        for comment in section_comments:
            row = table.add_row().cells
            row[0].text = GROUP_DISPLAY.get(comment["group"], comment["group"])
            row[0].width = Inches(1.2)
            row[1].text = comment["text"]
            row[1].width = Inches(5.0)
    
    doc.add_page_break()


def add_overall_effectiveness(doc, data, is_self_only=False):
    """Add Overall Effectiveness section (Q46-47)."""
    add_section_heading(doc, "Overall Effectiveness", font_size=16)
    
    desc = doc.add_paragraph()
    run = desc.add_run("These two items provide a global assessment of leadership effectiveness.")
    run.font.italic = True
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    doc.add_paragraph()
    
    for item_num in OVERALL_ITEMS:
        item_scores = data['by_item'].get(item_num, {})
        item_text = item_scores.get('text', ITEMS.get(item_num, ''))
        
        # Create 2-column borderless table for side-by-side layout (same as dimensions)
        layout_table = doc.add_table(rows=1, cols=2)
        make_table_borderless(layout_table)
        layout_table.autofit = False
        
        # Left cell: Question text (~3 inches)
        text_cell = layout_table.rows[0].cells[0]
        text_cell.width = Inches(3.0)
        text_para = text_cell.paragraphs[0]
        text_para.add_run(f"Q{item_num}. ").bold = True
        text_para.add_run(item_text)
        text_para.runs[0].font.size = Pt(10)
        if len(text_para.runs) > 1:
            text_para.runs[1].font.size = Pt(10)
        # Keep statement with its chart
        text_para.paragraph_format.keep_with_next = True
        
        # Right cell: Bar chart (~3 inches)
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
    
    doc.add_page_break()


def add_overall_comments(doc, comments):
    """Add overall qualitative feedback section."""
    add_section_heading(doc, "Overall Qualitative Feedback", font_size=16)
    
    if comments.get('strengths'):
        doc.add_heading("Greatest Strengths", level=2)
        
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = "Source"
        hdr[1].text = "Comment"
        for cell in hdr:
            set_cell_shading(cell, '375623')
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].runs[0].bold = True
        
        for comment in comments['strengths']:
            row = table.add_row().cells
            row[0].text = GROUP_DISPLAY.get(comment["group"], comment["group"])
            row[1].text = comment["text"]
    
    doc.add_paragraph()
    
    if comments.get('development'):
        doc.add_heading("Development Suggestions", level=2)
        
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = "Source"
        hdr[1].text = "Comment"
        for cell in hdr:
            set_cell_shading(cell, 'C65911')
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].runs[0].bold = True
        
        for comment in comments['development']:
            row = table.add_row().cells
            row[0].text = GROUP_DISPLAY.get(comment["group"], comment["group"])
            row[1].text = comment["text"]
    
    doc.add_page_break()


def add_reflection_questions(doc):
    """Add reflection questions for coaching preparation."""
    doc.add_heading("Reflection Questions", level=1)
    
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
        doc.add_paragraph()  # Space for notes
    
    doc.add_page_break()


def add_what_happens_next(doc):
    """Add What Happens Next section for self-assessment reports."""
    doc.add_heading("What Happens Next", level=1)
    
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


def add_next_steps(doc):
    """Add next steps section for full 360 reports."""
    add_section_heading(doc, "Next Steps", font_size=16)
    
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
            "across the nine dimensions of the Compass framework. It forms the starting point for "
            "your 360-degree feedback process."
        )
        doc.add_page_break()
        
        # Overview table
        doc.add_heading("Your Self-Assessment Overview", level=1)
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = "Dimension"
        hdr[1].text = "Your Score"
        for cell in hdr:
            set_cell_shading(cell, '024731')
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        
        for dim_name in DIMENSIONS.keys():
            row = table.add_row().cells
            row[0].text = dim_name
            self_score = data['by_dimension'].get(dim_name, {}).get('Self')
            row[1].text = f"{self_score:.2f}" if self_score else "-"
        
        doc.add_paragraph()
        
        # Radar - larger and centred
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            self_scores = {dim: data['by_dimension'].get(dim, {}).get('Self') for dim in DIMENSIONS}
            create_radar_chart(DIMENSIONS, self_scores, None, tmp.name)
            
            # Add picture and centre it
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run()
            run.add_picture(tmp.name, width=Inches(6))
            os.unlink(tmp.name)
        
        doc.add_page_break()
        
        # Detailed sections
        for dim_name in DIMENSIONS.keys():
            add_dimension_section(doc, dim_name, data, comments, is_self_only=True)
        
        # Overall Effectiveness
        add_overall_effectiveness(doc, data, is_self_only=True)
        
        # Reflection Questions
        add_reflection_questions(doc)
        
        # What Happens Next
        add_what_happens_next(doc)
        
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
        
        # Detailed Feedback section - heading flows into first dimension
        add_section_heading(doc, "Detailed Feedback by Dimension", font_size=18)
        
        for dim_name in DIMENSIONS.keys():
            add_dimension_section(doc, dim_name, data, comments, is_self_only=False)
        
        # Overall effectiveness (now Q46-47)
        add_overall_effectiveness(doc, data, is_self_only=False)
        
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
