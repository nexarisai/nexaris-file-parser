from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import pdfplumber
import io
import os
import gc

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Limits to prevent memory issues on Render free tier (512MB)
MAX_FILE_SIZE_MB = 5  # Max file size in MB
MAX_ROWS_PER_SHEET = 2000  # Reduced from 5000
MAX_COLS = 50  # Max columns to read

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

        # Check file size first
        file.seek(0, 2)  # Seek to end
        file_size_mb = file.tell() / (1024 * 1024)
        file.seek(0)  # Reset to beginning

        if file_size_mb > MAX_FILE_SIZE_MB:
            return jsonify({
                "error": f"File too large ({file_size_mb:.1f}MB). Max size is {MAX_FILE_SIZE_MB}MB. Please split the file or reduce data."
            }), 400

        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            # Parse Excel with pandas - memory efficient approach
            file_content = file.read()
            file_stream = io.BytesIO(file_content)
            del file_content  # Free the raw bytes immediately
            gc.collect()

            # Use ExcelFile to read sheets efficiently
            try:
                xlsx = pd.ExcelFile(file_stream, engine='openpyxl')
                sheet_names = xlsx.sheet_names
                extracted_text = ""
                truncated = False

                # Process all sheets (up to 15 max for memory safety)
                for sheet_name in sheet_names[:15]:
                    # Read sheet with row and column limits
                    df = pd.read_excel(
                        xlsx,
                        sheet_name=sheet_name,
                        nrows=MAX_ROWS_PER_SHEET,
                        usecols=lambda x: x < MAX_COLS if isinstance(x, int) else True
                    )

                    # Limit columns if too many
                    if len(df.columns) > MAX_COLS:
                        df = df.iloc[:, :MAX_COLS]
                        truncated = True

                    extracted_text += f"\n=== Sheet: {sheet_name} ===\n"
                    extracted_text += df.to_string(index=True) + "\n"

                    # Check if we hit the row limit
                    if len(df) >= MAX_ROWS_PER_SHEET:
                        truncated = True
                        extracted_text += f"\n[Note: Sheet truncated at {MAX_ROWS_PER_SHEET} rows]\n"

                    # Free memory aggressively
                    del df
                    gc.collect()

                if len(sheet_names) > 15:
                    truncated = True
                    extracted_text += f"\n[Note: Only processed first 15 of {len(sheet_names)} sheets]\n"

                xlsx.close()
            finally:
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
