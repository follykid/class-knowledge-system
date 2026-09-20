# 全新系統 v1 部署說明

## 原系統完全不動
本專案是獨立的新專案，不連接舊 `class-score-system`、舊 `quiz-battle`、舊 Firebase。

## 本機測試
1. `pip install -r requirements.txt`
2. `python app.py`
3. 開啟 `http://127.0.0.1:5000/`

## GitHub + Render
- 建立全新的 GitHub Repository，例如 `class-knowledge-system`
- 將本資料夾全部上傳到新 Repository 根目錄
- Render 建立新的 Web Service，連到新 Repository
- Build Command：`pip install -r requirements.txt`
- Start Command：`gunicorn app:app`
- 建議新增 `SECRET_KEY`
- 若使用 Render PostgreSQL，新增 `DATABASE_URL`

## 帳號
- teacher / 1930：管理員
- teacher01 / 1930：一般玩家「小明」
- 26 位學生：504 資料中的學號 + 四碼密碼

## v1 積分規則
- AI 對戰：答對每題 +1，完成 +1，勝利再 +3
- 真人對戰：答對每題 +1，完成 +1，勝利再 +5
- 教師可手動 +1 / -1
- 每場遊戲使用唯一 event_id，避免重複計分
