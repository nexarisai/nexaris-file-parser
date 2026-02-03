from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import pdfplumber
import io
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "nexaris-file-parser"})

@app.route('/parse', methods=['POST'])
def parse_file():
    """Parse Excel or PDF file and return formatted text like pandas df.to_string()"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        filename = file.filename.lower()

        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            # Parse Excel with pandas
            file_content = file.read()
            xlsx = pd.ExcelFile(io.BytesIO(file_content))

            extracted_text = ""
            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(io.BytesIO(file_content), sheet_name=sheet_name)
                # Use pandas to_string() for consistent formatting
                extracted_text += f"\n=== Sheet: {sheet_name} ===\n"
                extracted_text += df.to_string(index=True) + "\n"

            return jsonify({
                "success": True,
                "text": extracted_text.strip(),
                "fileName": file.filename,
                "fileType": "excel",
                "sheets": xlsx.sheet_names
            })

        elif filename.endswith('.pdf'):
            # Parse PDF with pdfplumber
            file_content = file.read()
            extracted_text = ""

            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += f"\n=== Page {i+1} ===\n"
                        extracted_text += page_text + "\n"

            return jsonify({
                "success": True,
                "text": extracted_text.strip(),
                "fileName": file.filename,
                "fileType": "pdf",
                "pages": len(pdf.pages) if pdf else 0
            })

        elif filename.endswith('.csv'):
            # Parse CSV with pandas
            file_content = file.read()
            df = pd.read_csv(io.BytesIO(file_content))
            extracted_text = df.to_string(index=True)

            return jsonify({
                "success": True,
                "text": extracted_text.strip(),
                "fileName": file.filename,
                "fileType": "csv"
            })

        else:
            return jsonify({"error": "Unsupported file type. Use Excel, PDF, or CSV."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
