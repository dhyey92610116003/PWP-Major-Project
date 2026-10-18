import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

class ReportGenerator:
    """
    Generates professional PDF reports for UTM tests.
    """
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_pdf(self, metadata: dict, results: dict, graph_image_path: str = None) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.output_dir, f"UTM_Report_{timestamp}.pdf")
        
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            alignment=1 # Center
        )
        elements.append(Paragraph("Universal Testing Machine - Test Report", title_style))
        elements.append(Spacer(1, 10))
        
        # Test Details Table
        meta_data = [
            ["Test Information", ""],
            ["Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["Operator:", metadata.get("operator", "")],
            ["Customer:", metadata.get("customer", "")],
            ["Material:", metadata.get("material", "")],
            ["Standard:", metadata.get("standard", "")],
            ["Sample ID:", metadata.get("sample", "")],
            ["Dimensions (W x T x G):", f"{metadata.get('width', 0)} x {metadata.get('thickness', 0)} x {metadata.get('gauge_length', 0)} mm"]
        ]
        
        t_meta = Table(meta_data, colWidths=[200, 250])
        t_meta.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (1,0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0,0), (1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.lightgrey)
        ]))
        elements.append(t_meta)
        elements.append(Spacer(1, 20))
        
        # Results Table
        results_data = [
            ["Test Results", ""],
            ["Peak Load:", f"{results.get('peak_load', 0.0):.2f} kN"],
            ["Peak Stress:", f"{results.get('peak_stress', 0.0):.2f} MPa"]
        ]
        
        t_res = Table(results_data, colWidths=[200, 250])
        t_res.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (1,0), colors.HexColor('#28a745')),
            ('TEXTCOLOR', (0,0), (1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.lightgrey)
        ]))
        elements.append(t_res)
        elements.append(Spacer(1, 20))
        
        # Graph
        if graph_image_path and os.path.exists(graph_image_path):
            elements.append(Paragraph("Test Graph:", styles['Heading2']))
            img = Image(graph_image_path, width=450, height=300)
            elements.append(img)
            
        elements.append(Spacer(1, 40))
        
        # Signature
        elements.append(Paragraph("Authorized Signature: _______________________", styles['Normal']))
        
        doc.build(elements)
        return filename
