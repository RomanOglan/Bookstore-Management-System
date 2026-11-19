[Download the Discord-ready text file](</C:/Users/tahah/Documents/Codex/2026-11-19/ok-i-need-u-to-do/outputs/Discord-Group-Setup-Instructions.txt>)

BOOKSTORE PROJECT — GROUP SETUP

The completed project is now on the main GitHub branch.

FIRST-TIME SETUP

1. Make sure Python, Git, MySQL 8.0, and VS Code are installed.

2. Open PowerShell and run:

cd "$HOME\Documents"
git clone https://github.com/RomanOglan/Bookstore-Management-System.git
cd .\Bookstore-Management-System
code .

3. Create the Python environment:

py -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

4. Create your private MySQL settings:

Copy-Item .env.example .env
notepad .env

Enter your own local MySQL username and password in `.env`. Save it and never upload `.env` to GitHub.

5. Make sure MySQL is running, then run:

python setup_database.py

6. Test and start the website:

python -m unittest -v
python app.py

Open:

http://127.0.0.1:5001
http://127.0.0.1:5001/dbtest

Demo customer:
customer@bookstore.local
Customer123!

Demo staff:
staff@bookstore.local
Staff123!

ALREADY CLONED THE PROJECT?

Open PowerShell in your existing project folder and run:

git status
git pull --ff-only origin main
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_database.py
python -m unittest -v
python app.py

IMPORTANT

- Everyone has a separate local MySQL database.
- Git updates project files, but it does not synchronize live database changes.
- Never commit `.env`, `venv`, database backups, or private user data.
- Check `git status` before pulling. Save unfinished work on your own branch first.
- Do not use the database reset command unless you intentionally want to delete and rebuild your local database.
