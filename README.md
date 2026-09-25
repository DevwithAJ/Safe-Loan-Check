# Safe Loan Check

Safe Loan Check is a Flask-based digital loan awareness platform designed to help users understand and verify information related to digital lending applications.

The system does **not** determine whether a loan app is legal, approved, or safe. Instead, it combines multiple independent checks to help users make informed decisions by reviewing app identity, warning signals, public information, and loan-cost details.

---

## Features

* Bilingual Interface (English & Hindi)
* RBI DLA Directory Verification
* Google Play Metadata Analysis
* Experimental Machine Learning Risk Signal
* Loan Cost & Affordability Calculator
* User-Friendly Result Explanations
* Production-Ready Flask Architecture
* Docker & Render Deployment Support
* Security Headers & Rate Limiting
* Health Monitoring Endpoints

---

## Tech Stack

### Backend

* Python
* Flask
* SQLite
* Gunicorn

### Machine Learning

* Scikit-Learn
* Random Forest

### Frontend

* HTML
* CSS
* JavaScript
* Jinja2 Templates

### Deployment

* Docker
* Render

---

## Project Team

### Ajit Kumar

**Team Leader & Full-Stack Integration Lead**

* Project Planning
* Backend Development
* Flask Integration
* Decision Layer Development
* Testing & Deployment
* Team Coordination

### Ajeet Kumar

**Frontend & UI/UX Developer**

* Responsive User Interface
* User Experience Design
* Forms & Result Pages

### Sonu Kumar

**Machine Learning & Data Analysis Lead**

* Data Processing
* Feature Engineering
* Model Training
* Performance Evaluation

### Parnav Kr Mishra

**Data Research, Testing & Documentation Lead**

* RBI DLA Research
* Testing & Validation
* Documentation
* Survey & Pilot Support

---

## Installation

```bash
git clone https://github.com/DevwithAJ/Safe-Loan-Check.git

cd Safe-Loan-Check

python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt

python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## Project Structure

```text
Safe-Loan-Check/
├── app.py
├── config.py
├── requirements.txt
├── services/
├── scripts/
├── models/
├── data/
├── templates/
├── static/
├── docs/
└── tests/
```

---

## Disclaimer

Safe Loan Check is an educational and awareness-focused project.

* Not financial advice
* Not legal advice
* Not a loan approval system
* Not an official RBI service

Users should always verify information through official sources before making financial decisions.

---

## Author

**Ajit Kumar**

B.Tech Computer Science & Engineering
Sandip University, Bihar, India

GitHub: https://github.com/DevwithAJ

---

⭐ If you find this project useful, consider giving it a star on GitHub.
