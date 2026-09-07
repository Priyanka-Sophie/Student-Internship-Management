# INTERN — Student Internship Recommendation Management System

SIMS is a Flask-based college project for helping students discover internships that fit their academic profile and resume skills. Administrators review every imported role before it is visible to students.

## Features

- Student registration and secure login with hashed passwords
- Student profile with qualification, specialization, study year and skills
- PDF resume upload and rule-based skill extraction
- Database-backed student dashboard, internship search, details, recommendations and application tracker
- Resume-based, explainable recommendation scores
- Protected admin portal for internship review, approval, rejection, expiry, source sync, student directory and reports
- External internship importer using OpenIntern employer-application links
- Approval safeguard: imported internships start as **Pending** and are only visible after an administrator changes them to **Active**

## Technology

- Python 3
- Flask, Flask-Login and Flask-SQLAlchemy
- SQLite
- pypdf
- HTML and CSS

## Local setup

1. Clone the repository and open it in VS Code.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Create an administrator account (run this once):

   ```powershell
   .\.venv\Scripts\python.exe create_admin.py
   ```

5. Start the app:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

6. Open `http://127.0.0.1:5000/`.

## Using SIMS

### Student

1. Register a student account and sign in.
2. Complete qualification, specialization and year on **My Profile**.
3. Upload a PDF resume from **My Resume**.
4. SIMS extracts known skills and uses them for recommendations.
5. Search approved internships, open the original employer application link, then optionally mark the role as applied in the local SIMS tracker.

### Administrator

1. Go to `http://127.0.0.1:5000/admin/login`.
2. Open **Sources** and select **Sync Live Internships** to import current roles.
3. Open **Review internships** and verify the employer link for each item.
4. Select **Approve** to make a role visible to students. Select **Reject**, **Pending**, or **Expire** when appropriate.

## Data and privacy

- `internship.db` and the `uploads/` directory are local runtime data and are intentionally ignored by Git.
- The app does not upload student resumes or personal details to GitHub.
- Internship records are retained locally; on a new clone, use the Admin **Sources** page to sync new roles.
- Students apply on the original employer website. SIMS only stores an optional local tracker entry.

## Project structure

```text
app.py                  Flask routes and application logic
models.py               SQLite database models
resume_tools.py         Resume skill extraction and scoring
live_internships.py     OpenIntern sync service
create_admin.py         Safe local administrator-account setup
templates/              Student and admin pages
static/css/style.css    Application styling
```

## Notes for evaluation

The matching feature is intentionally rule-based and explainable for a B.Sc. project. When an external listing does not publish required skills through its source API, SIMS labels the result as resume relevance rather than claiming an employer-stated skill match.
