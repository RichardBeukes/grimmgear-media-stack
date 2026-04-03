@echo off
cd /d D:\grimmgear-media-stack\backend
"C:\Users\richa\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 7777
