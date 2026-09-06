@echo off
setlocal

echo [1/2] Fetching repository list...
if not exist "data\interim" mkdir data\interim

gh repo list --limit 150 --json name,description,updatedAt > data\interim\repos.json
if %errorlevel% neq 0 (
    echo Error fetching repositories from GitHub CLI.
    exit /b %errorlevel%
)

echo Converting repos.json to repos.csv...
python -c "import json, csv; data = json.load(open('data/interim/repos.json', encoding='utf-8')); keys = ['name', 'description', 'updatedAt']; writer = csv.DictWriter(open('data/interim/repos.csv', 'w', encoding='utf-8', newline=''), fieldnames=keys); writer.writeheader(); writer.writerows(data)"
if %errorlevel% neq 0 (
    echo Error converting repos.json to CSV.
    exit /b %errorlevel%
)

echo [2/3] Running issue fetch script...
uv run code/src/fetch_issues.py
if %errorlevel% neq 0 (
    echo Error running fetch_issues.py.
    exit /b %errorlevel%
)

echo [3/3] Compiling dashboard dataset and updating index.html...
uv run code/src/build_dashboard.py
if %errorlevel% neq 0 (
    echo Error running build_dashboard.py.
    exit /b %errorlevel%
)

echo Pipeline complete! View at index.html or data/final/dashboard_data.json.
endlocal
