# 📊 Financial Research Tool

An AI-powered research portal that extracts structured financial data from company reports (PDFs) and exports them to Excel for analysis.

This tool is designed to help analysts quickly convert unstructured financial statements into usable tabular data.

---

## ✨ Features

- 📄 Upload company financial reports (PDF)
- 🔍 Hybrid extraction:
  - Table detection (Camelot)
  - OCR fallback (Tesseract)
- 🤖 AI-powered parsing using Groq LLM
- 📊 Structured preview in browser
- 📥 Export to formatted Excel
- ⚡ Handles scanned and text-based PDFs

---

## 🏗️ System Architecture

```bash
PDF Upload
↓
Table Extraction (Camelot)
↓ (if fails)
OCR (Tesseract)
↓
Text Cleaning
↓
LLM Parsing (Groq)
↓
Data Validation
↓
Preview + Excel Export
```


---

## 🛠️ Tech Stack

- Backend: FastAPI (Python)
- OCR: Tesseract
- Table Extraction: Camelot
- LLM: Groq (llama-3.1-8b-instant)
- Excel: OpenPyXL
- Frontend: HTML + JavaScript
- Deployment: Render

---

## 📁 Project Structure
```bash
finance-research-tool/
│
├── app/
│ ├── api/
│ ├── services/
│ ├── core/
│ └── static/
│
├── requirements.txt
├── start.sh
├── render.yaml
└── README.md
```

---

## 🚀 How to Run Locally

### 1️⃣ Clone Repository

```bash
git clone <your-repo-url>
cd finance-research-tool
```
### 2️⃣ Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```
### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
### 4️⃣ Run Server
```bash
uvicorn app.main:app --reload
```
### 5️⃣ Open in Browser
```bash
http://127.0.0.1:8000
```

---
☁️ Deployment (Render)

The project is deployed using Render.
- Uses render.yaml
- Uses start.sh for startup
- Environment variable required:
 ```bash
  GROQ_KEY = your_api_key_here

```

## 📊 Output Format

The system generates:
- Browser preview of extracted data
- Excel file with:
  - Bold headers
  - Highlighted key rows
  - Auto column width
  - Frozen header

Missing or ambiguous values are marked as:
```bash
MISSING

```
## ⚠️ Limitations

Due to free-tier hosting and OCR limitations:
- Cold start delay (20–40s)
- OCR accuracy depends on scan quality
- Very complex multi-period tables may have partial missing data
- File size limited on free hosting

These are known limitations of automated document processing systems.

## 📌 Future Improvements
- Better multi-row header detection
- Advanced table reconstruction
- Confidence scoring for extracted values
- Support for balance sheets and cash flow statements
- Improved frontend UI

## 👨‍💻 Author

Omkar Tilekar

## 📄 License

This project is for educational and research purposes.

