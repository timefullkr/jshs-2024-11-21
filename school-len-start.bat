
@echo off
chcp 65001
title todays-menu

cd /d d:\app\todays-menu
call venv\Scripts\activate

echo 서버를 시작합니다...
python main.py 

pause
