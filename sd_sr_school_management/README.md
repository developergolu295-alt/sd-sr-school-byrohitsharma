# S.D S.R S.E.C School Management Portal

A Flask + SQLAlchemy school portal with SQLite for local use and PostgreSQL support for online hosting.

## Included
- Teacher registration/login with hashed passwords; administrator can approve/disable teacher accounts.
- Class-wise student records, daily attendance, library catalogue, issue/return tracking.
- English/Hindi language selector (the current build switches the page language setting; some detailed page labels remain English).
- Printable student profile.
- Excel `.xlsx` import/export for each class.
- Alphabetical (A-Z) student sorting view. This sorts names; it does **not** overwrite official roll numbers.
- Master portal lock, configurable with `PORTAL_PASSWORD`.
- Cute elephant theme and "Developer Rohit" footer.
- SQLAlchemy database designed to support thousands of student records and many concurrent teachers when deployed with PostgreSQL and suitable hosting.

## Run on Windows
1. Extract the ZIP.
2. Open Command Prompt in the extracted folder.
3. Create and activate a virtual environment:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install packages:
   ```bat
   pip install -r requirements.txt
   ```
5. Copy `.env.example` to `.env` and set `SECRET_KEY` and `PORTAL_PASSWORD`. (For local quick start, the default portal password is `@sd!kmpur`.)
6. Start:
   ```bat
   python app.py
   ```
7. Open `http://127.0.0.1:5000`.

## First setup
- Enter the portal master password.
- Visit `/admin/bootstrap` to create the first administrator account. This URL disappears after the first account exists.
- Sign in as administrator, add classes, then create teacher accounts using **Teacher registration**. Teachers select their assigned class during registration.
- The administrator can enable/disable teacher accounts and can see teacher IDs, class assignments, student records and class names in the portal/database.
- Teachers can change their own class password from their class page. Passwords are stored as secure hashes, not readable plaintext.

## Excel import format
Use `.xlsx` with a header row. `Name` is required. Optional headers:
`Roll No`, `Admission No`, `Guardian`, `Phone`, `Address`.
Export a class roster first to get a ready-made template.

## Put it online
This ZIP is a deployable application, but it is **not already hosted online**. To publish it:
1. Choose a Python hosting provider that supports persistent PostgreSQL (for example Render, Railway, or a VPS).
2. Push this folder to a private Git repository and create a web service with build command `pip install -r requirements.txt` and start command `gunicorn app:app`.
3. Set environment variables `SECRET_KEY`, `PORTAL_PASSWORD`, and `DATABASE_URL` to your hosted PostgreSQL connection string.
4. Enable HTTPS, restrict database access, configure backups, and create the first administrator at `/admin/bootstrap`.

Do not use the default portal password or development secret on a public deployment. Keep student data private and provide access only to authorized school staff. Have the school administration approve the portal and its data-handling arrangements before entering real student information.
