import os
import io
from datetime import datetime

from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
COVER_FOLDER = os.path.join(UPLOAD_FOLDER, 'covers')
EXPORT_FOLDER = os.path.join(UPLOAD_FOLDER, 'exports')
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COVER_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)

# Brand colours
BRAND_BLUE = os.environ.get('BRAND_BLUE', '#0084a9')
ORANGE = os.environ.get('BRAND_ORANGE', '#fc9a2d')
GREY = os.environ.get('BRAND_GREY', '#f7f7f7')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max per upload


def list_modules():
    """Return a list of existing PDF modules in the upload folder."""
    files = []
    for fname in sorted(os.listdir(UPLOAD_FOLDER)):
        if fname.lower().endswith('.pdf'):
            files.append(fname)
    return files


def generate_cover_pdf(title: str, client_name: str, created_by: str, date_str: str) -> str:
    """Generate a cover PDF with brand styling and save to the covers folder.

    Returns the filename of the generated cover.
    """
    # Create unique filename
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    filename = f"cover_{timestamp}.pdf"
    path = os.path.join(COVER_FOLDER, filename)

    # Prepare canvas
    c = pdfcanvas.Canvas(path, pagesize=letter)
    width, height = letter

    # Draw background image (construction photo) covering upper half of the page
    bg_path = os.path.join(STATIC_FOLDER, 'background.png')
    if os.path.exists(bg_path):
        # scale background to width of page and half the height
        bg = ImageReader(bg_path)
        img_width, img_height = bg.getSize()
        aspect = img_height / img_width
        # Fit width to page width
        draw_height = height * 0.65  # cover about 65% of the page
        draw_width = draw_height / aspect
        if draw_width < width:
            draw_width = width
            draw_height = draw_width * aspect
        # center crop vertically and horizontally by drawing bigger and clipping automatically
        c.drawImage(bg, 0, height - draw_height, width=draw_width, height=draw_height, mask='auto')
    else:
        # Fill grey if no background
        c.setFillColor(colors.HexColor(GREY))
        c.rect(0, height * 0.5, width, height * 0.5, stroke=0, fill=1)

    # Blue angled header bar
    c.setFillColor(colors.HexColor(BRAND_BLUE))
    # Draw a polygon (trapezoid) across the top left corner
    c.saveState()
    # Points: top-left, top-right, diagonal midline
    c.beginPath()
    c.moveTo(0, height)
    c.lineTo(width, height)
    c.lineTo(width, height - height * 0.25)
    c.lineTo(0, height - height * 0.35)
    c.close()
    c.fill()
    c.restoreState()

    # Bottom-left orange accent bar
    c.setFillColor(colors.HexColor(ORANGE))
    c.saveState()
    c.beginPath()
    c.moveTo(0, 0)
    c.lineTo(width * 0.3, 0)
    c.lineTo(0, height * 0.12)
    c.close()
    c.fill()
    c.restoreState()

    # Logo on top left
    logo_path = os.path.join(STATIC_FOLDER, 'logo.png')
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        logo_width, logo_height = logo.getSize()
        # define maximum width and height for logo
        max_w = width * 0.2
        max_h = height * 0.15
        scale = min(max_w / logo_width, max_h / logo_height)
        lw = logo_width * scale
        lh = logo_height * scale
        c.drawImage(logo, inch * 0.5, height - lh - inch * 0.5, width=lw, height=lh, mask='auto')

    # Title text
    c.setFillColor(colors.white)
    title_font_size = 36
    c.setFont('Helvetica-Bold', title_font_size)
    # wrap title if necessary
    max_title_width = width * 0.8
    lines = []
    current_line = ''
    for word in title.split():
        test = f"{current_line} {word}".strip()
        if c.stringWidth(test, 'Helvetica-Bold', title_font_size) < max_title_width:
            current_line = test
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    y_pos = height - inch * 2.5
    for line in lines:
        c.drawString(inch * 0.5, y_pos, line)
        y_pos -= title_font_size * 1.2

    # Prepared for subtitle (client name)
    c.setFont('Helvetica', 18)
    c.setFillColor(colors.white)
    if client_name:
        prepared_text = f"Prepared for {client_name}"
        c.drawString(inch * 0.5, y_pos - 10, prepared_text)
        y_pos -= 28

    # Date on right side
    if date_str:
        c.setFont('Helvetica', 16)
        c.setFillColor(colors.HexColor(BRAND_BLUE))
        # Extract month and year from date
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            month_year = date_obj.strftime('%B %Y')
        except Exception:
            month_year = date_str
        # Place at right side
        c.drawRightString(width - inch * 0.5, height * 0.3, month_year)

    # Presented to / by at bottom
    c.setFont('Helvetica', 12)
    c.setFillColor(colors.HexColor(BRAND_BLUE))
    # Presented to
    if client_name:
        c.drawString(inch * 0.5, inch * 0.7, 'Presented to')
        c.setFont('Helvetica-Bold', 16)
        c.setFillColor(colors.black)
        c.drawString(inch * 0.5, inch * 0.5, client_name)
    # Presented by
    if created_by:
        c.setFont('Helvetica', 12)
        c.setFillColor(colors.HexColor(BRAND_BLUE))
        c.drawRightString(width - inch * 0.5, inch * 0.7, 'Presented by')
        c.setFont('Helvetica-Bold', 16)
        c.setFillColor(colors.black)
        c.drawRightString(width - inch * 0.5, inch * 0.5, created_by)

    c.showPage()
    c.save()
    return filename


@app.route('/')
def index():
    # Render a simple interface
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', files=list_modules(), brand_blue=BRAND_BLUE, today=today)


@app.route('/list_modules')
def list_modules_api():
    return jsonify(list_modules())


@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')
    saved = []
    for f in files:
        if not f.filename.lower().endswith('.pdf'):
            continue
        filename = secure_filename(f.filename)
        # avoid overwriting existing by appending timestamp
        base, ext = os.path.splitext(filename)
        counter = 1
        unique = filename
        while os.path.exists(os.path.join(UPLOAD_FOLDER, unique)):
            unique = f"{base}_{counter}{ext}"
            counter += 1
        f.save(os.path.join(UPLOAD_FOLDER, unique))
        saved.append(unique)
    return jsonify({'saved': saved, 'all': list_modules()})


@app.route('/generate_cover', methods=['POST'])
def generate_cover():
    data = request.json
    title = data.get('title', 'Proposal')
    client_name = data.get('client_name', '')
    created_by = data.get('created_by', '')
    date_str = data.get('date', '')
    filename = generate_cover_pdf(title, client_name, created_by, date_str)
    # return relative path for builder
    return jsonify({'cover': filename})


@app.route('/export', methods=['POST'])
def export_pdf():
    data = request.json
    files = data.get('files', [])  # list of filenames in order
    cover = data.get('cover', None)
    writer = PdfWriter()
    if cover:
        cover_path = os.path.join(COVER_FOLDER, cover)
        if os.path.exists(cover_path):
            try:
                reader = PdfReader(cover_path)
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                print(f"Error adding cover: {e}")
    for filename in files:
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(path) and filename.lower().endswith('.pdf'):
            try:
                reader = PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                print(f"Error merging {filename}: {e}")
    # Save exported file
    export_name = f"proposal_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.pdf"
    export_path = os.path.join(EXPORT_FOLDER, export_name)
    with open(export_path, 'wb') as f:
        writer.write(f)
    return jsonify({'export': export_name})


@app.route('/download/<folder>/<filename>')
def download_file(folder, filename):
    # allow downloading from covers or exports or root uploads
    if folder == 'covers':
        directory = COVER_FOLDER
    elif folder == 'exports':
        directory = EXPORT_FOLDER
    else:
        directory = UPLOAD_FOLDER
    return send_from_directory(directory, filename, as_attachment=True)


if __name__ == '__main__':
    # For local testing
    app.run(debug=True, host='0.0.0.0', port=5000)