# Financial PDF Retrieval-Augmented Generation (RAG) System

## Overview
This project is a **Financial PDF Retrieval-Augmented Generation (RAG) System**, a web application designed to process financial PDFs (e.g., quarterly earnings reports) and extract both structured and unstructured data. Users can upload PDFs, extract key financial metrics (like Revenue, EBITDA, or PAT), manage metrics to extract, and query the data for insights. The system supports structured queries (e.g., "What is the revenue trend?") and unstructured queries (e.g., "What does the company do?") using semantic search.

## Features

- **PDF Upload**: Upload financial PDFs for automatic processing.
- **Structured Data Extraction**: Extracts metrics like Revenue, EBITDA, and expenses using regex patterns and stores them in a SQLite database.
- **Unstructured Data Storage**: Chunks PDF text, embeds it using SentenceTransformer, and stores it in a FAISS vector store for semantic search.
- **Metric Management**: View extracted metrics and add, edit, or delete regex patterns for extraction.
- **Query System**: Ask structured questions (e.g., "Show me the expense breakdown") or unstructured questions (e.g., "What does the company do?"), with responses formatted in Markdown.

## Technologies Used

- **Python**: Core programming language.
- **Flask**: Web framework for building the application.
- **SQLite**: Lightweight database for storing structured metrics.
- **pdfplumber**: Library for extracting text from PDFs.
- **SentenceTransformer (all-MiniLM-L6-v2)**: For embedding text chunks for semantic search.
- **FAISS**: Efficient vector store for similarity search.
- **markdown2**: For formatting query results in Markdown.
- **Bootstrap**: For responsive frontend styling.
- **Jinja2**: Templating engine for dynamic HTML rendering.
- **numpy**: For numerical operations with embeddings.
- **pytesseract and Pillow**: Included in dependencies but not used in the current code (potentially for future OCR functionality).
- **pandas**: Included in dependencies but not used in the current code (potentially for future data analysis).

## Prerequisites
Before running the project, ensure you have the following installed:

- **Python**: The project is built with Python.
- **pip**: Python package manager for installing dependencies.
- **Tesseract-OCR**: Required for pytesseract. Install it on your system:
  - Windows: Download and install from [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki).
  - Ubuntu: `sudo apt-get install tesseract-ocr`.
  - macOS: `brew install tesseract`.

## Setup Instructions

### Clone the Repository:
```
git clone https://github.com/your-username/financial-pdf-rag-system.git
cd financial-pdf-rag-system
```


```
## Setup

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate

# On Windows:
.\venv\Scripts\activate

```


### Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt

The requirements.txt should include:
flask
pdfplumber 
pytesseract
pillow
sentence-transformers
faiss-cpu
numpy
pandas
markdown

```



## Directory Structure
The application automatically creates the following directory structure:
```
uploads/: For storing uploaded PDFs.
database/: For the SQLite database (metrics.db).
vectors/: For the FAISS vector store (vector_store.faiss).
static/css/: For the styles.css file (ensure styles.css is placed in static/css/).
```

## Running the Application

1. Start the Flask server:
```bash
python app.py

The app will run at http://127.0.0.1:5000/.
```

## Quick Start

Access the web interface at:  
[http://127.0.0.1:5000/](http://127.0.0.1:5000/)

## Usage Guide

### 1. Uploading Documents
- Navigate to the homepage
- Upload financial PDFs (e.g., `Q1FY24.pdf`)
- System automatically processes and extracts metrics

### 2. Viewing Metrics
After upload, you'll see:
- **Extracted values**: Revenue, EBITDA Margin, etc.
- **Source page references**
- **Option** to add new extraction patterns

### 3. Adding Custom Metrics
Example pattern for "Other Income":
```regex
Other Income\s*₹?(\d+\.\d+)\s*(Cr\.|INR Cr\.)
```


## Querying Data

On the Query page, you can ask both structured and unstructured questions:

### Structured Queries
```python
"What is the revenue trend?"
(Structured query showing revenue over quarters, e.g., "Q1FY23: 18.4 INR Cr., Q1FY24: 19.8 INR Cr.").
```

### Unstructured Queries
```
"What does Tracxn do?"
(Unstructured query retrieving relevant text, e.g., "Tracxn is a Data & Software platform for the Private Markets globally…").
```

Project Structure

```
financial-pdf-rag-system/
│
├── app.py 
├── requirements.txt 
├── static/
│ └── css/
│ └── styles.css 
├── templates/
│ ├── index.html 
│ ├── metrics.html
│ └── query.html 
├── uploads/ 
├── database/ 
│ └── metrics.db
└── vectors/
└── vector_store.faiss

```

## Development Process
This project was developed in the following steps:

## Initial Setup:

Chose Flask for its simplicity and Python for its rich ecosystem.
Set up a basic web app with routes for uploading PDFs, viewing metrics, and querying data using app.py.

## Structured Data Extraction:

Used pdfplumber to extract text from PDFs in extract_structured_data.
Defined regex patterns in init_db to capture financial metrics (e.g., Revenue, PAT) and stored them in SQLite (metric_table and user_metrics tables).
Added source page tracking and categorization (e.g., Financial, Expense) for better organization.

## Unstructured Data Handling:

Implemented store_unstructured_data to chunk PDF text, embed it using SentenceTransformer, and store it in a FAISS vector store for semantic search.
Used query_unstructured_data to retrieve relevant text chunks for unstructured queries.

## Query System:

Developed query_structured_data to handle structured queries (e.g., "revenue trend") by fetching data from the SQLite database.
Used FAISS for unstructured queries to retrieve relevant text chunks, formatted with markdown2.

## Frontend:

Created index.html for PDF uploads, metrics.html for metric management, and query.html for querying, using Bootstrap for styling and Jinja2 for dynamic rendering.
Added custom styles in styles.css to enhance the UI, such as formatting query results with the result-content class.

