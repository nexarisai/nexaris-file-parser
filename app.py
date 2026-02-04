from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import pdfplumber
import io
import os
import gc

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Max rows per sheet to prevent memory issues (adjust as needed)
MAX_ROWS_PER_SHEET = 5000

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
            # Parse Excel with pandas - memory efficient approach
            file_stream = io.BytesIO(file.read())

            # Use ExcelFile to read sheets efficiently
            with pd.ExcelFile(file_stream, engine='openpyxl') as xlsx:
                sheet_names = xlsx.sheet_names
                extracted_text = ""
                truncated = False

                for sheet_name in sheet_names:
                    # Read sheet with row limit to prevent memory issues
                    df = pd.read_excel(xlsx, sheet_name=sheet_name, nrows=MAX_ROWS_PER_SHEET)

                    extracted_text += f"\n=== Sheet: {sheet_name} ===\n"
                    extracted_text += df.to_string(index=True) + "\n"

                    # Check if we hit the row limit
                    if len(df) >= MAX_ROWS_PER_SHEET:
                        truncated = True
                        extracted_text += f"\n[Note: Sheet truncated at {MAX_ROWS_PER_SHEET} rows]\n"

                    # Free memory
                    del df
                    gc.collect()

            # Clean up
            file_stream.close()
            gc.collect()

            return jsonify({
                "success": True,
                "text": extracted_text.strip(),
                "fileName": file.filename,
                "fileType": "excel",
                "sheets": sheet_names,
                "truncated": truncated
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
