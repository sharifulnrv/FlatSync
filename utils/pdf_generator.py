import re
from xhtml2pdf import pisa
from io import BytesIO
from flask import render_template

def render_to_pdf(template_src, context_dict):
    """
    Renders a Jinja2 template into a PDF file in-memory.
    Uses a minimalistic PDF-specific layout for a professional outcome.
    """
    from datetime import datetime
    from flask import current_app
    
    # 2. Add PDF-specific flags and metadata to the context
    context_dict['is_pdf'] = True
    context_dict['now_date'] = datetime.now().strftime('%B %d, %Y')
    context_dict['config'] = context_dict.get('config', {
        'COMPANY_NAME': current_app.config.get('COMPANY_NAME', 'FlatSync Administrative Hub'),
        'COMPANY_ADDRESS': current_app.config.get('COMPANY_ADDRESS', 'Association Office')
    })
    
    html = render_template(template_src, **context_dict)
    
    # 3. Targeted removal of interactive elements (Scripts/Buttons/Links)
    html = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<button\b[^<]*(?:(?!<\/button>)<[^<]*)*<\/button>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<a\b[^<]*(?:(?!<\/a>)<[^<]*)*<\/a>', '', html, flags=re.IGNORECASE | re.DOTALL)
    
    # 4. Inject PDF-safe Global Styles while RESERVING template-level styles
    pdf_styles = r"""
    <style>
        /* Hide UI boilerplate */
        aside, nav, footer, header, .no-print, button, .print\:hidden, #notification-container { display: none !important; }
        
        main { display: block !important; width: 100% !important; }
        
        /* Pisa basic layouts */
        table { width: 100%; border-collapse: collapse; margin-bottom: 10pt; table-layout: fixed; }
        th, td { padding: 8pt 4pt; text-align: left; vertical-align: top; border: 0 !important; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        
        /* Premium Core (Ensure these survive) */
        .premium-container { border: 2pt solid #0f172a; border-radius: 40pt; padding: 30pt; }
        .pill-header { background-color: #0f172a; color: #ffffff; padding: 8pt 20pt; border-radius: 12pt; display: inline-block; font-weight: bold; }
        .dotted-line { border-bottom: 1pt dotted #94a3b8; }
        .amount-box-pdf { border: 2pt solid #0f172a; border-radius: 20pt; background-color: #f8fafc; padding: 15pt; width: 200pt; }
    </style>
    """
    html = html.replace('</head>', f'{pdf_styles}</head>')

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None
