"""
Script to generate a realistic PDF bank statement for demoing PDF ingestion.
"""

from pathlib import Path
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUTPUT_PDF = Path(__file__).resolve().parent / "data" / "sample_bank_statement.pdf"


def generate_pdf():
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor("#1e1b4b"),
        spaceAfter=4,
    )

    sub_style = ParagraphStyle(
        'SubStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor("#475569"),
        spaceAfter=15,
    )

    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
    )

    th_style = ParagraphStyle(
        'THCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        textColor=colors.white,
    )

    story = [
        Paragraph("HDFC BANK — ACCOUNT STATEMENT", header_style),
        Paragraph("Account No: 50100234567891 • Period: 01-Jun-2025 to 31-Jul-2025 • Branch: MUMBAI MAIN", sub_style),
    ]

    data = [
        [Paragraph("Txn Date", th_style), Paragraph("Narration / Description", th_style), Paragraph("Withdrawal (Dr)", th_style), Paragraph("Deposit (Cr)", th_style), Paragraph("Balance (INR)", th_style)],
        [Paragraph("01/06/2025", cell_style), Paragraph("UPI-SWIGGY-swiggy@ybl-425678901", cell_style), Paragraph("349.00", cell_style), Paragraph("", cell_style), Paragraph("49,651.00", cell_style)],
        [Paragraph("02/06/2025", cell_style), Paragraph("NEFT-ACME CORP-MONTHLY SALARY", cell_style), Paragraph("", cell_style), Paragraph("75,000.00", cell_style), Paragraph("1,24,651.00", cell_style)],
        [Paragraph("02/06/2025", cell_style), Paragraph("UPI-RENT PAYMENT-landlord@icici", cell_style), Paragraph("32,000.00", cell_style), Paragraph("", cell_style), Paragraph("92,651.00", cell_style)],
        [Paragraph("03/06/2025", cell_style), Paragraph("UPI-ZOMATO-zomato@paytm-523461", cell_style), Paragraph("275.00", cell_style), Paragraph("", cell_style), Paragraph("92,376.00", cell_style)],
        [Paragraph("04/06/2025", cell_style), Paragraph("UPI-NETFLIX-netflix@icici-672345", cell_style), Paragraph("199.00", cell_style), Paragraph("", cell_style), Paragraph("92,177.00", cell_style)],
        [Paragraph("05/06/2025", cell_style), Paragraph("POS 423867*RELIANCE FRESH MUMBAI", cell_style), Paragraph("1,245.00", cell_style), Paragraph("", cell_style), Paragraph("90,932.00", cell_style)],
        [Paragraph("07/06/2025", cell_style), Paragraph("UPI-SPOTIFY INDIA-spotify@ybl", cell_style), Paragraph("119.00", cell_style), Paragraph("", cell_style), Paragraph("90,813.00", cell_style)],
        [Paragraph("11/06/2025", cell_style), Paragraph("BIL/ACT FIBERNET/BROADBAND/JUNE", cell_style), Paragraph("799.00", cell_style), Paragraph("", cell_style), Paragraph("90,014.00", cell_style)],
        [Paragraph("13/06/2025", cell_style), Paragraph("UPI-CULT FIT-cultfit@hdfcbank", cell_style), Paragraph("999.00", cell_style), Paragraph("", cell_style), Paragraph("89,015.00", cell_style)],
        [Paragraph("14/06/2025", cell_style), Paragraph("POS 891234*INDIAN OIL PETROL PUMP", cell_style), Paragraph("2,500.00", cell_style), Paragraph("", cell_style), Paragraph("86,515.00", cell_style)],
        [Paragraph("24/06/2025", cell_style), Paragraph("CC 000381672*CROMA ELECTRONICS", cell_style), Paragraph("45,000.00", cell_style), Paragraph("", cell_style), Paragraph("41,515.00", cell_style)],
        [Paragraph("29/06/2025", cell_style), Paragraph("UPI-AIRTEL-airtel@paytm-767890", cell_style), Paragraph("599.00", cell_style), Paragraph("", cell_style), Paragraph("40,916.00", cell_style)],
        [Paragraph("01/07/2025", cell_style), Paragraph("NEFT-ACME CORP-MONTHLY SALARY", cell_style), Paragraph("", cell_style), Paragraph("75,000.00", cell_style), Paragraph("1,15,916.00", cell_style)],
        [Paragraph("02/07/2025", cell_style), Paragraph("UPI-RENT PAYMENT-landlord@icici", cell_style), Paragraph("32,000.00", cell_style), Paragraph("", cell_style), Paragraph("83,916.00", cell_style)],
        [Paragraph("03/07/2025", cell_style), Paragraph("UPI-NETFLIX-netflix@icici-100123", cell_style), Paragraph("199.00", cell_style), Paragraph("", cell_style), Paragraph("83,717.00", cell_style)],
        [Paragraph("07/07/2025", cell_style), Paragraph("UPI-SPOTIFY INDIA-spotify@ybl", cell_style), Paragraph("119.00", cell_style), Paragraph("", cell_style), Paragraph("83,598.00", cell_style)],
        [Paragraph("11/07/2025", cell_style), Paragraph("BIL/ACT FIBERNET/BROADBAND/JULY", cell_style), Paragraph("799.00", cell_style), Paragraph("", cell_style), Paragraph("82,799.00", cell_style)],
        [Paragraph("12/07/2025", cell_style), Paragraph("UPI-CULT FIT-cultfit@hdfcbank", cell_style), Paragraph("999.00", cell_style), Paragraph("", cell_style), Paragraph("81,800.00", cell_style)],
        [Paragraph("26/07/2025", cell_style), Paragraph("UPI-AIRTEL-airtel@paytm-109012", cell_style), Paragraph("599.00", cell_style), Paragraph("", cell_style), Paragraph("81,201.00", cell_style)],
    ]

    t = Table(data, colWidths=[1.1 * inch, 3.2 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))

    story.append(t)
    doc.build(story)
    print(f"Generated sample bank PDF at: {OUTPUT_PDF}")


if __name__ == "__main__":
    generate_pdf()
