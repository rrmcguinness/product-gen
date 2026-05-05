from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from typing import List, Dict, Any

def generate_pdf_report(output_path: Path, stats: Dict[str, Any]):
    """
    Generates a premium PDF report summarizing the pipeline execution.
    """
    doc = SimpleDocTemplate(str(output_path), pagesize=(1224, 792))
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles for a premium feel
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0071dc"), # Walmart Blue
        spaceAfter=20
    )
    
    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#2e2f32"),
        spaceAfter=10,
        spaceBefore=15
    )
    
    body_style = styles['Normal']
    
    # Title
    story.append(Paragraph("Product Generation Pipeline Report", title_style))
    story.append(Spacer(1, 10))
    
    # Summary Stats
    story.append(Paragraph("Summary Statistics", h2_style))
    
    total_processed = stats.get("total_processed", 0)
    avg_tokens = stats.get("total_tokens", 0) / total_processed if total_processed > 0 else 0
    
    data = [
        ["Metric", "Value"],
        ["Total Products Processed", str(total_processed)],
        ["Successful Images", str(stats.get("success_count", 0))],
        ["Failed Images", str(stats.get("fail_count", 0))],
        ["Total Retries", str(stats.get("total_retries", 0))],
        ["Total Input Tokens", str(stats.get("total_input_tokens", 0))],
        ["Total Output Tokens", str(stats.get("total_output_tokens", 0))],
        ["Total Tokens Used", str(stats.get("total_tokens", 0))],
        ["Average Tokens per Run", f"{avg_tokens:.2f}"],
        ["Total Time (s)", f"{stats.get('total_time', 0.0):.2f}"],
        ["Input Cost ($)", f"${stats.get('total_input_cost', 0.0):.4f}"],
        ["Output Cost ($)", f"${stats.get('total_output_cost', 0.0):.4f}"],
        ["Total Cost ($)", f"${stats.get('total_cost', 0.0):.4f}"],
    ]
    
    t = Table(data, colWidths=[200, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#f2f8fd")),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.HexColor("#0071dc")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e3e4e5")),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("Note: Cost analysis assumes Gemini 2.5 Pro rates ($1.25/M input, $10/M output for <=200k tokens) with a 10% discount.", body_style))
    story.append(Spacer(1, 20))
    
    # Detailed Results or Errors
    if stats.get("errors"):
        story.append(Paragraph("Errors Encountered", h2_style))
        for err in stats["errors"]:
            story.append(Paragraph(f"• {err}", body_style))
            story.append(Spacer(1, 5))
            
    # Detailed Product Breakdown
    if "product_details" in stats and stats["product_details"]:
        from reportlab.platypus import PageBreak
        story.append(PageBreak()) # Start on a new page as requested
        story.append(Paragraph("Detailed Product Breakdown", h2_style))
        
        detail_data = [
            ["Product ID", "Category", "Success", "Fail", "Retries", "Enrich", "Desc", "Img1", "Judge", "Total", "Time", "Cost"]
        ]
        
        for detail in stats["product_details"]:
            detail_data.append([
                str(detail.get("id", "")),
                str(detail.get("category", "")),
                str(detail.get("success", 0)),
                str(detail.get("fail", 0)),
                str(detail.get("retries", 0)),
                str(detail.get("enrich_tokens", 0)),
                str(detail.get("desc_tokens", 0)),
                str(detail.get("img1_tokens", 0)),
                str(detail.get("judge_tokens", 0)),
                str(detail.get("tokens", 0)),
                f"{detail.get('time', 0.0):.2f}",
                f"${detail.get('cost', 0.0):.4f}"
            ])
            
        dt = Table(detail_data, colWidths=[60, 200, 40, 40, 40, 60, 60, 60, 60, 60, 50, 50])
        dt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f8fd")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0071dc")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e3e4e5")),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        story.append(dt)
            
    doc.build(story)
    print(f"PDF report generated at: {output_path}")
