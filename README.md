# 班級知識王積分系統 v1.2

全新獨立的 Flask 班級知識王系統，不連接舊版 class-score-system 或 quiz-battle。

## v1.2 重點
- 學生首頁改為較接近舊版班級積分系統的版面：個人資料、積分/HP、知識王、抽獎、真人房間、榮譽榜。
- AI 對戰：10 題。
- 每答對一題以 10 分為基本分，越快回答速度加分越高。
- AI 難度 65%：每題 AI 有約 65% 機率答對，並以速度產生 AI 得分。
- 玩家勝利：本場總得分 100% 轉成 HP。
- 玩家輸給 AI：本場總得分 50% 轉成 HP。
- HP：每場開始 100 HP；答錯 -10 HP。
- HP 與班級積分：150 HP = 1 分，剩餘 HP 保留。
- 繼續練習：1 班級積分可兌換 10 HP。
- 抽獎：20 分/次，14 種寶物卡及既定權重。
- 真人對戰也採用答題速度計分與 HP 結算規則。
- 包含舊版資料的輕量 schema 升級，不需要連回舊系統。

## Render
Build Command: `pip install -r requirements.txt`
Start Command: `gunicorn app:app`
