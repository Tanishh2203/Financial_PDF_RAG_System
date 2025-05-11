import os
import re
import sqlite3
import pdfplumber
import numpy as np
from flask import Flask, render_template, request, redirect, url_for
from sentence_transformers import SentenceTransformer
import faiss
import markdown2  

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['DATABASE'] = 'database/metrics.db'
app.config['VECTOR_STORE'] = 'vectors/vector_store.faiss'

#folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('database', exist_ok=True)
os.makedirs('vectors', exist_ok=True)

embedder = SentenceTransformer('all-MiniLM-L6-v2')
dimension = 384
index = None  
chunks = []

def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metric_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quarter TEXT,
            metric_name TEXT,
            value REAL,
            unit TEXT,
            year INTEGER,
            source_page INTEGER,  -- Added to track source page
            category TEXT  -- Added to categorize metrics (e.g., Financial, Operational)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT UNIQUE,
            pattern TEXT,
            category TEXT  -- Added to categorize metrics
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM user_metrics')
    if cursor.fetchone()[0] == 0:
        default_metrics = [
            ("Revenue from Operations", r"Revenue from Operations\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Financial"),
            ("Total Income", r"Total Income\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Financial"),
            ("EBITDA", r"EBITDA\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Financial"),
            ("PAT", r"PAT\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Financial"),
            ("Free Cash Flow", r"Free Cash Flow\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Financial"),
            ("Cash & Cash Equivalents", r"Cash & Cash Equivalents\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Financial"),
            ("EBITDA Margin", r"EBITDA Margin\s*(\d+\.\d+)%", "Financial"),
            ("PAT Margin", r"PAT Margin\s*(\d+\.\d+)%", "Financial"),
            ("Employee Benefit Expenses", r"Employee Benefit Expenses\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("Salaries, Wages & Bonus", r"Salaries, Wages & Bonus\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("Employee Stock Option Expense", r"Employee Stock Option Expense\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("Depreciation Expense", r"Depreciation Expense\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("Other Expenses", r"Other Expenses\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("Cloud Hosting Charges", r"Cloud Hosting Charges\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("Rent for Building", r"Rent for Building\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)", "Expense"),
            ("International Revenue Share", r"International Revenue\s*~\s*(\d+\.\d+)%", "Operational"),
            ("Global Tech Funding", r"Global Tech Funding.*?(\d+\.\d+)\s*(USD Bn\.)", "Market"),
            ("India Tech Funding", r"India Tech Funding.*?(\d+\.\d+)\s*(USD Bn\.)", "Market"),
        ]
        cursor.executemany('INSERT INTO user_metrics (metric_name, pattern, category) VALUES (?, ?, ?)', default_metrics)
    conn.commit()
    conn.close()

def load_or_create_index():
    global index, chunks
    if os.path.exists(app.config['VECTOR_STORE']):
        index = faiss.read_index(app.config['VECTOR_STORE'])
        chunks = []  # In a production app, you'd persist chunks separately
    else:
        index = faiss.IndexFlatL2(dimension)
        chunks = []

def chunk_text(text):
    if not text:
        return []
    chunks = [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]
    return chunks

def store_unstructured_data(pdf_path, quarter):
    global chunks, index
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    page_chunks = chunk_text(page_text)
                    chunks.extend([(chunk, quarter, page_num) for chunk in page_chunks])
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return

    embeddings = embedder.encode([chunk[0] for chunk in chunks])
    embeddings = np.array(embeddings, dtype=np.float32)

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    faiss.write_index(index, app.config['VECTOR_STORE'])

def extract_structured_data(pdf_path, quarter):
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT metric_name, pattern, category FROM user_metrics')
    metrics_to_extract = [{"name": row[0], "pattern": row[1], "category": row[2]} for row in cursor.fetchall()]

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            pages_text = []
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
                    pages_text.append((page_num, page_text))
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        conn.close()
        return []

    year_match = re.search(r"FY(\d{2})", quarter)
    year = int(f"20{year_match.group(1)}") if year_match else 2023

    cursor.execute('DELETE FROM metric_table WHERE quarter = ?', (quarter,))
    extracted_metrics = []

    for metric in metrics_to_extract:
        for page_num, page_text in pages_text:
            match = re.search(metric["pattern"], page_text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    unit = match.group(2) if len(match.groups()) > 1 and "Cr." in metric["pattern"] else "%" if "%" in metric["pattern"] else "USD Bn."
                    cursor.execute('''
                        INSERT INTO metric_table (quarter, metric_name, value, unit, year, source_page, category)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (quarter, metric["name"], value, unit, year, page_num, metric["category"]))
                    extracted_metrics.append({
                        "quarter": quarter,
                        "metric_name": metric["name"],
                        "value": value,
                        "unit": unit,
                        "year": year,
                        "source_page": page_num,
                        "category": metric["category"]
                    })
                except (ValueError, IndexError) as e:
                    print(f"Error extracting metric {metric['name']}: {e}")
    conn.commit()
    conn.close()

    return extracted_metrics

def query_structured_data(query):
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    query_lower = query.lower()

    # Net Profit (PAT) Trend
    if "trend" in query_lower and "net profit" in query_lower:
        cursor.execute('SELECT quarter, value, unit, source_page FROM metric_table WHERE metric_name = "PAT" ORDER BY year, quarter')
        results = cursor.fetchall()
        if results:
            trend = "# Net Profit (PAT) Trend\n"
            for row in results:
                trend += f"- {row[0]}: {row[1]} {row[2]} (Source: Page {row[3]})\n"
            return trend, []
    
    # EBITDA Margin Evolution
    elif "margin" in query_lower and "evolved" in query_lower:
        cursor.execute('SELECT quarter, value, unit, source_page FROM metric_table WHERE metric_name = "EBITDA Margin" ORDER BY year, quarter')
        results = cursor.fetchall()
        if results:
            evolution = "# EBITDA Margin Evolution\n"
            for row in results:
                evolution += f"- {row[0]}: {row[1]}{row[2]} (Source: Page {row[3]})\n"
            return evolution, []
    
    # EBITDA Margin Decrease with Follow-up
    elif "ebitda margin decrease" in query_lower:
        cursor.execute('SELECT quarter, value, unit, source_page FROM metric_table WHERE metric_name = "EBITDA Margin" ORDER BY year, quarter')
        results = cursor.fetchall()
        if results and len(results) >= 2:
            latest = results[-1]
            previous = results[-2]
            if latest[1] < previous[1]:
                structured_result = f"# EBITDA Margin Decrease\nEBITDA Margin decreased from {previous[1]}{previous[2]} in {previous[0]} to {latest[1]}{latest[2]} in {latest[0]}.\n**Source**: Pages {previous[3]} and {latest[3]}"
                return structured_result, [f"why {latest[0]}"]
    
    # Revenue Trend
    elif "revenue trend" in query_lower:
        cursor.execute('SELECT quarter, value, unit, source_page FROM metric_table WHERE metric_name = "Revenue from Operations" ORDER BY year, quarter')
        results = cursor.fetchall()
        if results:
            trend = "# Revenue Trend\n"
            for row in results:
                trend += f"- {row[0]}: {row[1]} {row[2]} (Source: Page {row[3]})\n"
            return trend, []
    
    # Expense Breakdown
    elif "expense breakdown" in query_lower:
        cursor.execute('SELECT metric_name, value, unit, source_page FROM metric_table WHERE category = "Expense" AND quarter = (SELECT MAX(quarter) FROM metric_table)')
        results = cursor.fetchall()
        if results:
            breakdown = "# Expense Breakdown (Latest Quarter)\n"
            for row in results:
                breakdown += f"- {row[0]}: {row[1]} {row[2]} (Source: Page {row[3]})\n"
            return breakdown, []
    
    # International Revenue Share
    elif "international revenue" in query_lower:
        cursor.execute('SELECT quarter, value, unit, source_page FROM metric_table WHERE metric_name = "International Revenue Share" ORDER BY year, quarter')
        results = cursor.fetchall()
        if results:
            share = "# International Revenue Share\n"
            for row in results:
                share += f"- {row[0]}: {row[1]}{row[2]} (Source: Page {row[3]})\n"
            return share, []

    conn.close()
    return None, []

def query_unstructured_data(query):
    global chunks, index
    if index is None or index.ntotal == 0:
        return "# No Data Available\nNo data available to query. Please upload a PDF first."
    query_embedding = embedder.encode([query]).astype(np.float32)
    D, I = index.search(query_embedding, k=3)
    results = []
    for idx in I[0]:
        if idx != -1 and idx < len(chunks):
            chunk_text, chunk_quarter, page_num = chunks[idx]
            results.append(f"**From {chunk_quarter} (Page {page_num})**:\n{chunk_text}")
    return "# Relevant Information\n" + "\n\n".join(results) if results else "# No Relevant Information\nNo relevant information found."

@app.route('/')
def index():
    return render_template('index.html', message="")

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        return render_template('index.html', message="No file part")
    file = request.files['pdf_file']
    if file.filename == '':
        return render_template('index.html', message="No selected file")
    if file and file.filename.endswith('.pdf'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        quarter = file.filename.replace('.pdf', '')
        extracted_metrics = extract_structured_data(filepath, quarter)
        store_unstructured_data(filepath, quarter)
        return redirect(url_for('metrics', message="File uploaded and processed successfully!"))
    return render_template('index.html', message="Please upload a PDF file")

@app.route('/metrics')
def metrics():
    message = request.args.get('message', "")
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT quarter, metric_name, value, unit, year, source_page, category FROM metric_table')
    metrics = [{"quarter": row[0], "metric_name": row[1], "value": row[2], "unit": row[3], "year": row[4], "source_page": row[5], "category": row[6]} for row in cursor.fetchall()]
    cursor.execute('SELECT id, metric_name, pattern, category FROM user_metrics')
    user_metrics = [{"id": row[0], "metric_name": row[1], "pattern": row[2], "category": row[3]} for row in cursor.fetchall()]
    conn.close()
    return render_template('metrics.html', metrics=metrics, user_metrics=user_metrics, message=message)

@app.route('/add_metric', methods=['POST'])
def add_metric():
    metric_name = request.form['metric_name']
    pattern = request.form['pattern']
    category = request.form['category']  # Added category input
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO user_metrics (metric_name, pattern, category) VALUES (?, ?, ?)', (metric_name, pattern, category))
        conn.commit()
        message = "Metric added successfully!"
    except sqlite3.IntegrityError:
        message = "Metric name already exists!"
    finally:
        conn.close()
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT quarter, metric_name, value, unit, year, source_page, category FROM metric_table')
    metrics = [{"quarter": row[0], "metric_name": row[1], "value": row[2], "unit": row[3], "year": row[4], "source_page": row[5], "category": row[6]} for row in cursor.fetchall()]
    cursor.execute('SELECT id, metric_name, pattern, category FROM user_metrics')
    user_metrics = [{"id": row[0], "metric_name": row[1], "pattern": row[2], "category": row[3]} for row in cursor.fetchall()]
    conn.close()
    return render_template('metrics.html', metrics=metrics, user_metrics=user_metrics, message=message)

@app.route('/edit_metric/<int:metric_id>', methods=['POST'])
def edit_metric(metric_id):
    metric_name = request.form['metric_name']
    pattern = request.form['pattern']
    category = request.form['category']  # Added category input
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('UPDATE user_metrics SET metric_name = ?, pattern = ?, category = ? WHERE id = ?', (metric_name, pattern, category, metric_id))
    conn.commit()
    conn.close()
    message = "Metric updated successfully!"
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT quarter, metric_name, value, unit, year, source_page, category FROM metric_table')
    metrics = [{"quarter": row[0], "metric_name": row[1], "value": row[2], "unit": row[3], "year": row[4], "source_page": row[5], "category": row[6]} for row in cursor.fetchall()]
    cursor.execute('SELECT id, metric_name, pattern, category FROM user_metrics')
    user_metrics = [{"id": row[0], "metric_name": row[1], "pattern": row[2], "category": row[3]} for row in cursor.fetchall()]
    conn.close()
    return render_template('metrics.html', metrics=metrics, user_metrics=user_metrics, message=message)

@app.route('/delete_metric/<int:metric_id>')
def delete_metric(metric_id):
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_metrics WHERE id = ?', (metric_id,))
    conn.commit()
    conn.close()
    message = "Metric deleted successfully!"
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT quarter, metric_name, value, unit, year, source_page, category FROM metric_table')
    metrics = [{"quarter": row[0], "metric_name": row[1], "value": row[2], "unit": row[3], "year": row[4], "source_page": row[5], "category": row[6]} for row in cursor.fetchall()]
    cursor.execute('SELECT id, metric_name, pattern, category FROM user_metrics')
    user_metrics = [{"id": row[0], "metric_name": row[1], "pattern": row[2], "category": row[3]} for row in cursor.fetchall()]
    conn.close()
    return render_template('metrics.html', metrics=metrics, user_metrics=user_metrics, message=message)

@app.route('/query', methods=['GET', 'POST'])
def query():
    if request.method == 'POST':
        query_text = request.form['query']
        structured_result, followups = query_structured_data(query_text)
        if structured_result:
            result = structured_result
            for followup in followups:
                unstructured_result = query_unstructured_data(followup)
                result += "\n\n## Possible Reason\n" + unstructured_result
        else:
            result = query_unstructured_data(query_text)
        # Convert Markdown to HTML
        result_html = markdown2.markdown(result)
        return render_template('query.html', query=query_text, result_html=result_html, message="")
    return render_template('query.html', query="", result_html="", message="")

if __name__ == '__main__':
    init_db()
    load_or_create_index()
    app.run(debug=True)