📘 Project Management Phases
🟢 1. Initiation Phase:
Deciding what to build and why

🔍 Identify the Problem / Idea

The Lebanese official journal Al Jarida Al Rasmiya contains critical legal and governmental information. However:
-Published mainly as long PDF documents
-Difficult to search or filter information
-Not automatically organized
-Users must read manually to find relevant updates

💡 Proposed Solution:
Develop a smart web application “AljaridaAlrasmiya” that:
-Automatically reads official journal documents
-Extracts Arabic text directly from PDF files
-Uses AI models to classify and filter topics
-Displays organized and searchable content

This system will make official information accessible, structured, and searchable.


🎯 Project Goals and Objectives

Main Goal:
Develop an intelligent web-based system that extracts, analyzes, and manages information from Al Jarida Al Rasmiya using PDF text extraction and AI

Objectives:
-Upload and process official journal PDFs
-Extract Arabic text directly from PDF files
-Detect topics (laws, jobs, tenders, announcements…)
-Store data in structured database
-Use AI/NLP for classification
-Provide searchable web interface


📊 Feasibility Study

⏱ Time Feasibility
Project divided into phases:
-PDF text extraction module
-AI classification
-Web dashboard and automation

Estimated duration: 3–4 months.

💰 Cost Feasibility
Low-cost implementation using open-source tools:
-Python
-Free AI/NLP models
-Local hosting

Optional: domain and hosting.

🧠 Technical Feasibility
Technologies available:
-PDF processing: pdfplumber or PyPDF
-AI/NLP: Python & Transformers
-Backend: Flask (Python)
-Database: MySQL
-Frontend: HTML/CSS/JS
Challenges include OCR accuracy and Arabic NLP processing, but both are manageable.

👥 Stakeholders
-Developers: Salah Al Jardali/Daniel Ghazaly
-Academic Supervisor: Project guidance and evaluation
-End Users: Citizens, researchers, job seekers
-Data Source: Al Jarida Al Rasmiya
-Future Admin: System maintenance

🟣 2. Planning Phase
Figuring out how the project will be done

🧩 Define Tasks and Activities

Main development tasks include:
-Collect official journal datasets
-Implement PDF text extraction module
-Clean and preprocess text
-Build AI classification model
-Design and implement database
-Develop web dashboard
-Testing and evaluation
-Documentation and presentation

📅 Project Timeline

Estimated timeline:

February:
-Project setup (GitHub, Jira)
-Data collection
-PDF text extraction testing

March:

-Text extraction module development
-Database design
-Start AI classification

April:

-Web dashboard development
-AI model improvement
-System integration

May:

-Testing and evaluation
-Final documentation
-Presentation and defense

💰 Cost & Resources

Resources required:
-Laptop/PC
-Python and open-source libraries
-Internet access
-GitHub & Jira tools

Most tools are free and open-source.

⚠ Risk Management
| Risk                  | Solution                        |
| --------------------- | ------------------------------- |
| Inconsistent PDF text |   Apply text cleaning and 
                           preprocessing

|    formatting         |     
| Arabic NLP complexity | Use pretrained models (AraBERT) |
| Time constraints      | Divide tasks across team        |
| Integration issues    | Test modules separately         |

🏗 System Architecture
Overall Architecture
The system is designed to automatically extract and classify information from Al Jarida Al Rasmiya using OCR and AI.

Official Journal PDF
        ↓
PDF Text Extraction
        ↓
Text Preprocessing & Cleaning
        ↓
AI Classification Model (NLP)
        ↓
MySQL Database Storage
        ↓
Flask Web Application
        ↓
Search & User Dashboard

Components
-AI Model: Classify extracted text into topics
-Database: Store structured information
-Web Dashboard: Display searchable content

🤖AI Model Methodology
Objective

Automatically classify extracted text into predefined categories:
-Laws and decrees
-Job announcements
-Tenders
-Official decisions
-Public announcements

Approach

1-Extract Arabic text from PDF files
2-Clean and preprocess text
3-Apply NLP classification model
4-Store predicted category in database

Model Options:

-AraBERT (recommended for Arabic NLP)
-TF-IDF + Machine Learning classifier
-Keyword-based classification (baseline)

Evaluation Metrics:

-Accuracy
-Precision
-Recall
-F1-score

💻Installation & Run Guide

Requirements:

-Python 3.10+
-MySQL
-Git

Install dependencies:
pip install flask  pillow transformers torch scikit-learn mysql-connector-python

Run project:python app.py
Open browser:http://127.0.0.1:5000

🔬Research Methodology

This project follows an applied research methodology combining OCR and AI techniques.

Step 1: Data Collection
Official journal PDFs collected and stored locally.

Step 2: Data Processing
System extracts Arabic text directly from PDF files

Step 3: Text Preprocessing

-Remove noise
-Normalize Arabic text
-Tokenization

Step 4: AI Classification
NLP model classifies content into categories.

Step 5: System Implementation
Web application developed to manage and display extracted data.

Step 6: Evaluation

System tested for:
-OCR accuracy
-Classification accuracy
-Usability
