# PulseTime

Basic attendance management system built with Python (Flask), HTML/CSS/JavaScript, and SQLite.

PulseTime helps a small office track employees, daily check-in/check-out, late arrivals, absences, and simple attendance reports.

## Features

- Dashboard with present, late, and absent counts
- Employee directory with add-employee form
- Daily attendance register with check-in, check-out, and mark-absent actions
- Date-range reports by employee and by day
- SQLite database created automatically on first run
- Sample employees and attendance records for a quick demo

## Tech stack

- Backend: Python 3 and Flask
- Database: SQLite (`attendance.db`)
- Frontend: HTML, CSS, and vanilla JavaScript
- API prefix: `/api`

## Run locally

```bash
pip install -r requirements.txt
python3 app.py
