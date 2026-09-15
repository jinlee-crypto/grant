@echo off
REM Collect on hospital PC and push to the data branch (use when overseas servers are blocked)
cd /d %~dp0
if not exist databranch git worktree add databranch data
cd databranch
git pull --rebase
cd ..
set GRANT_DATA=databranch\data
python collector.py >> collect.log 2>&1
cd databranch
git add data/notices.csv data/runs.csv
git commit -m "collect (hospital PC)"
git push
