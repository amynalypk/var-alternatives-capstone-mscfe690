"""Word primitives for the Module 6 deliverable.

This is `Module 4 Design/build_m4_deliverable.py` with four additions and nothing
removed, so the reviewer who has seen the proposal sees the same typefaces, the same
table rules and the same tinted equation boxes in the draft report. The additions are
`add_equation` (the house form for a displayed formula), `add_table_caption`,
`add_page_number_footer` and `add_styled_paragraph_block`.

Content does not live here. Every number and every table in
`generate_m6_final_docx.py` comes out of data/module6_metrics_manifest.json.
"""

import os
import re
import subprocess
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def set_table_borders(table, color="B0C4DE", sz="6"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideV w:val="none"/>
            <w:left w:val="none"/>
            <w:right w:val="none"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)

def add_styled_paragraph(doc, text="", space_after=5, space_before=0, line_spacing=1.15, bold_prefix=None, italic=False, align=WD_ALIGN_PARAGRAPH.LEFT):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.line_spacing = line_spacing
    
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = 'Calibri'
        r_pre.font.size = Pt(10.5)
        r_pre.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
        
    if text:
        parts = re.split(r'(\*\*.*?\*\*)', text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                run = p.add_run(part[2:-2])
                run.bold = True
            elif part.startswith('*') and part.endswith('*'):
                run = p.add_run(part[1:-1])
                run.italic = True
            else:
                run = p.add_run(part)
            run.font.name = 'Calibri'
            run.font.size = Pt(10.5)
            if italic:
                run.italic = True
    return p

def add_heading_1(doc, text):
    h = doc.add_paragraph(style="Heading 1")
    h.paragraph_format.space_before = Pt(16)
    h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True
    run = h.add_run(text)
    run.font.name = 'Calibri Light'
    run.font.size = Pt(15)
    run.bold = True
    run.font.color.rgb = RGBColor(0x2F, 0x54, 0x96)
    return h

def add_heading_2(doc, text):
    h = doc.add_paragraph(style="Heading 2")
    h.paragraph_format.space_before = Pt(12)
    h.paragraph_format.space_after = Pt(4)
    h.paragraph_format.keep_with_next = True
    run = h.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(12.5)
    run.bold = True
    run.font.color.rgb = RGBColor(0x2F, 0x54, 0x96)
    return h

def add_heading_3(doc, text):
    h = doc.add_paragraph(style="Heading 3")
    h.paragraph_format.space_before = Pt(8)
    h.paragraph_format.space_after = Pt(2)
    h.paragraph_format.keep_with_next = True
    run = h.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(11)
    run.bold = True
    run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    return h

def add_bullet_point(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.line_spacing = 1.15
    
    r_bullet = p.add_run("•  ")
    r_bullet.bold = True
    r_bullet.font.color.rgb = RGBColor(0x2F, 0x54, 0x96)
    
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = 'Calibri'
        r_pre.font.size = Pt(10.5)
        
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = p.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*'):
            run = p.add_run(part[1:-1])
            run.italic = True
        else:
            run = p.add_run(part)
        run.font.name = 'Calibri'
        run.font.size = Pt(10.5)
    return p

def add_callout_box(doc, text, title=None):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]
    cell.width = Inches(6.5)
    set_cell_background(cell, "F0F4F8")
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="2F5496"/>
            <w:top w:val="none"/>
            <w:right w:val="none"/>
            <w:bottom w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    
    if title:
        r_t = p.add_run(title + "\n")
        r_t.bold = True
        r_t.font.name = 'Calibri'
        r_t.font.size = Pt(10)
        r_t.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
        
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = p.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*'):
            run = p.add_run(part[1:-1])
            run.italic = True
        else:
            run = p.add_run(part)
        run.font.name = 'Calibri'
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return tbl

def add_table_data(doc, headers, rows_data, col_widths=None):
    if len(headers) > 5:
        first_table = None
        for start in range(1, len(headers), 4):
            columns = [0] + list(range(start, min(start + 4, len(headers))))
            if start > 1:
                add_styled_paragraph(doc, "Continued metrics (same row labels).", italic=True)
            panel = add_table_data(
                doc, [headers[i] for i in columns],
                [[row[i] for i in columns] for row in rows_data])
            if first_table is None:
                first_table = panel
        return first_table

    available = (doc.sections[-1].page_width - doc.sections[-1].left_margin
                 - doc.sections[-1].right_margin) / Inches(1)
    numeric = []
    desired = []
    for i, header in enumerate(headers):
        values = [str(row[i]) for row in rows_data]
        is_numeric = bool(values) and all(
            re.fullmatch(r"[\d\s.,%$+−\-\[\]()/<>–]+|n/a|yes|no", value)
            for value in values)
        numeric.append(is_numeric)
        longest = max((len(value) for value in values), default=0)
        # A text column has to hold its longest unbreakable word, not just the width
        # of its heading: "Minimum variance (Ledoit-Wolf)" is a strategy name, and a
        # column sized by the word "Book" breaks that name in the middle.
        word = max([len(part) for value in values for part in value.split()]
                   + [len(part) for part in str(header).split()], default=0)
        desired.append(max(0.8, min(2.3, longest * 0.065 + 0.22))
                       if is_numeric else max(1.35, min(2.9, word * 0.11 + longest * 0.02)))
    if not col_widths:
        widths = [available * value / sum(desired) for value in desired]
    else:
        widths = [available * value / sum(col_widths) for value in col_widths]

    tbl = doc.add_table(rows=len(rows_data) + 1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    for column, width in zip(tbl.columns, widths):
        column.width = Inches(width)
    for row in tbl.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width)
    set_table_borders(tbl, color="B0C4DE", sz="6")
    
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "2F5496")
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = 'Calibri'
            r.font.bold = True
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            
    trPr = tbl.rows[0]._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))

    for r_idx, row in enumerate(rows_data):
        row_cells = tbl.rows[r_idx + 1].cells
        bg_color = "F2F5F9" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row):
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=120, right=120)
            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.space_after = Pt(1.5)
            p.paragraph_format.space_before = Pt(1.5)
            p.paragraph_format.line_spacing = 1.1
            word_wrap = OxmlElement("w:wordWrap")
            # "1" keeps a word intact and lets a long label take a second line at a
            # space; "0" lets Word snap names like "Ledoit-Wolf" in half instead.
            word_wrap.set(qn("w:val"), "1")
            p._p.get_or_add_pPr().append(word_wrap)
            if numeric[c_idx]:
                row_cells[c_idx]._tc.get_or_add_tcPr().append(OxmlElement("w:noWrap"))
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

            lines = str(val).split("\n")
            for l_idx, line in enumerate(lines):
                if l_idx > 0:
                    p = row_cells[c_idx].add_paragraph()
                    p.paragraph_format.space_after = Pt(1.5)
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.line_spacing = 1.1
                parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        run = p.add_run(part[2:-2])
                        run.bold = True
                    elif part.startswith('*') and part.endswith('*'):
                        run = p.add_run(part[1:-1])
                        run.italic = True
                    else:
                        run = p.add_run(part)
                    run.font.name = 'Calibri'
                    run.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return tbl

def add_figure_with_caption(doc, img_path, fig_title, fig_caption, width=Inches(6.4)):
    if not os.path.exists(img_path):
        print(f"Warning: Image file not found: {img_path}")
        return None
        
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=width)
    
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(10)
    p_cap.paragraph_format.left_indent = Inches(0.4)
    p_cap.paragraph_format.right_indent = Inches(0.4)
    
    r_title = p_cap.add_run(fig_title + ": ")
    r_title.bold = True
    r_title.font.name = 'Calibri'
    r_title.font.size = Pt(9)
    r_title.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    
    r_desc = p_cap.add_run(fig_caption)
    r_desc.italic = True
    r_desc.font.name = 'Calibri'
    r_desc.font.size = Pt(8.5)
    r_desc.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    
    return p_img

def add_equation(doc, text, label=None, title=None):
    """A displayed formula in the house style: a tinted box with a small-caps title.

    Module 4 set its equations this way, so the reviewer sees one convention across
    both documents rather than a new one invented for the second deliverable.
    """
    head = title or (f"EQUATION {label}" if label else None)
    return add_callout_box(doc, text, title=head)


def add_table_caption(doc, label, caption):
    """Caption above the table, which is where a reader looks for it first."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(f"{label}. ")
    r.bold = True
    r.font.name = 'Calibri'
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    r2 = p.add_run(caption)
    r2.italic = True
    r2.font.name = 'Calibri'
    r2.font.size = Pt(8.5)
    r2.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    return p


def _append_page_field(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement('w:fldChar')
    begin.set(qn('w:fldCharType'), 'begin')
    instruction = OxmlElement('w:instrText')
    instruction.set(qn('xml:space'), 'preserve')
    instruction.text = 'PAGE'
    end = OxmlElement('w:fldChar')
    end.set(qn('w:fldCharType'), 'end')
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(end)
    run.font.name = 'Calibri'
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
    return run


def add_page_number_footer(doc, prefix="MScFE 690 Capstone  |  Draft Project Report  |  Page "):
    """A real Word PAGE field, so the number is the rendered page and not a guess."""
    for section in doc.sections:
        footer = section.footer
        paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        for run in list(paragraph.runs):
            run._r.getparent().remove(run._r)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lead = paragraph.add_run(prefix)
        lead.font.name = 'Calibri'
        lead.font.size = Pt(8.5)
        lead.font.color.rgb = RGBColor(0x77, 0x77, 0x77)
        _append_page_field(paragraph)


def add_styled_paragraph_block(doc, paragraphs, space_after=6):
    """Write several body paragraphs, so a section's prose stays readable in source."""
    return [add_styled_paragraph(doc, text, space_after=space_after)
            for text in paragraphs]
