import os, json, random, string, uuid, csv, io
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__)
app.config['SECRET_KEY']=os.environ.get('SECRET_KEY','fresh-v1-change-me')
db_url=os.environ.get('DATABASE_URL','sqlite:///'+os.path.join(BASE_DIR,'data.db'))
if db_url.startswith('postgres://'): db_url=db_url.replace('postgres://','postgresql+psycopg://',1)
elif db_url.startswith('postgresql://'): db_url=db_url.replace('postgresql://','postgresql+psycopg://',1)
app.config['SQLALCHEMY_DATABASE_URI']=db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
db=SQLAlchemy(app)

class Student(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    account=db.Column(db.String(32),unique=True,nullable=False)
    name=db.Column(db.String(50),nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    seat=db.Column(db.Integer,default=0)
    role=db.Column(db.String(20),default='student')
    score=db.Column(db.Integer,default=0)
    hp=db.Column(db.Integer,default=100)
    battle_score=db.Column(db.Integer,default=0)
    wins=db.Column(db.Integer,default=0)
    losses=db.Column(db.Integer,default=0)
    online=db.Column(db.Boolean,default=False)

class ScoreEvent(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    event_id=db.Column(db.String(80),unique=True,nullable=False)
    student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    delta=db.Column(db.Integer,nullable=False)
    reason=db.Column(db.String(120),nullable=False)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

class Message(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    user_name=db.Column(db.String(50),nullable=False)
    text=db.Column(db.String(300),nullable=False)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

class QuestionBank(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    qtype=db.Column(db.String(20),nullable=False,default='選擇題')
    category=db.Column(db.String(80),nullable=False,default='未分類')
    seconds=db.Column(db.Integer,nullable=False,default=60)
    question=db.Column(db.Text,nullable=False)
    options_json=db.Column(db.Text,nullable=False,default='[]')
    correct=db.Column(db.Integer,nullable=False,default=1)
    active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
    updated_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))

class AnswerRecord(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    question_id=db.Column(db.Integer,nullable=False)
    category=db.Column(db.String(50),nullable=False)
    question=db.Column(db.Text,nullable=False)
    selected_choice=db.Column(db.Integer,nullable=False)
    correct_choice=db.Column(db.Integer,nullable=False)
    is_correct=db.Column(db.Boolean,nullable=False)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

class Room(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(8),unique=True,nullable=False)
    host_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    status=db.Column(db.String(20),default='waiting')
    question_ids=db.Column(db.Text,default='[]')
    current_index=db.Column(db.Integer,default=0)
    started_at=db.Column(db.DateTime)
    question_started_at=db.Column(db.DateTime)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

class RoomPlayer(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    room_id=db.Column(db.Integer,db.ForeignKey('room.id'),nullable=False)
    student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    answered_index=db.Column(db.Integer,default=-1)
    correct_count=db.Column(db.Integer,default=0)
    battle_score=db.Column(db.Integer,default=0)
    joined_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
    __table_args__=(db.UniqueConstraint('room_id','student_id',name='uq_room_student'),)

class PrizeCard(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(80),unique=True,nullable=False)
    weight=db.Column(db.Float,nullable=False)
    description=db.Column(db.String(200),default='')

class PrizeDraw(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    card_id=db.Column(db.Integer,db.ForeignKey('prize_card.id'),nullable=False)
    status=db.Column(db.String(20),default='pending')
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

PRIZE_CARDS=[
    ('造型文具',1.0,'抽中後可向老師兌換。'),
    ('限量商品',1.0,'抽中後可向老師兌換。'),
    ('功課減量',0.6,'依老師班級規則兌換。'),
    ('使用電腦',4.0,'依老師班級規則兌換。'),
    ('值日生跳過',0.5,'依老師班級規則兌換。'),
    ('免睡卡',2.0,'依老師班級規則兌換。'),
    ('點數加倍',0.4,'依老師班級規則兌換。'),
    ('免罰金牌',1.0,'依老師班級規則兌換。'),
    ('V I P',0.2,'依老師班級規則兌換。'),
    ('珍珠奶茶',2.0,'依老師班級規則兌換。'),
    ('我想跟他坐',1.0,'依老師班級規則兌換。'),
    ('銘謝惠顧',2.0,'本次未抽中獎品。'),
    ('禮物卡',1.0,'抽中後可向老師兌換。'),
    ('手工冰淇淋',2.0,'抽中後可向老師兌換。'),
]

with open(os.path.join(BASE_DIR,'quiz.json'),encoding='utf-8') as f: QUESTIONS=json.load(f)

ROSTER=[(1, '黃聰', '111061', '0924'), (2, '昱綸', '111201', '1031'), (3, '靖喬', '111095', '1118'), (4, '侑辰', '111038', '0107'), (5, '楷欣', '111039', '0111'), (6, '芸霆', '111128', '0126'), (7, '俊賀', '111040', '0129'), (8, '品睿', '111070', '0201'), (9, '柏甫', '111071', '0227'), (10, '威碩', '111164', '0502'), (11, '雋書', '111074', '0612'), (12, '莫凡', '111166', '0703'), (13, '祐廷', '111137', '0723'), (14, '詠琂', '111139', '0818'), (15, '可荺', '111019', '0924'), (16, '張惟', '111079', '1015'), (17, '品真', '111112', '1108'), (18, '彥伃', '111115', '1223'), (19, '羽芯', '111052', '0125'), (20, '紫瑜', '111053', '0205'), (21, '翊榛', '111117', '0217'), (22, '侑璇', '111054', '0218'), (23, '芷軒', '111143', '0310'), (24, '芯妤', '111057', '0402'), (25, '毓琳', '111147', '0520'), (26, '予甯', '111150', '0710')]

def question_dict(q):
    return {
        'id': q.id,
        'qtype': q.qtype,
        'category': q.category,
        'seconds': q.seconds,
        'question': q.question,
        'options': json.loads(q.options_json or '[]'),
        'correct': q.correct,
        'active': bool(q.active),
    }

def active_questions():
    rows=QuestionBank.query.filter_by(active=True).order_by(QuestionBank.id).all()
    return [question_dict(q) for q in rows]

def next_question_id():
    last=db.session.query(db.func.max(QuestionBank.id)).scalar()
    return int(last or 0)+1

def normalize_question_input(data):
    qtype=str(data.get('qtype',data.get('題型','選擇題'))).strip() or '選擇題'
    category=str(data.get('category',data.get('分類','未分類'))).strip() or '未分類'
    question=str(data.get('question',data.get('題目',''))).strip()
    try: seconds=max(1,min(600,int(data.get('seconds',data.get('秒數',60)))))
    except Exception: seconds=60
    if 'options' in data and isinstance(data.get('options'),list):
        options=[str(x).strip() for x in data.get('options')]
    else:
        options=[str(data.get(f'option{i}',data.get(f'選項{i}',''))).strip() for i in range(1,5)]
    if qtype in ('是非題','是非','OX','O/X'):
        qtype='是非題'; options=['O','X']
    else:
        qtype='選擇題'
        options=options[:4]
        while len(options)<4: options.append('')
    options=[x for x in options if x!='']
    try: correct=int(data.get('correct',data.get('正確答案',1)))
    except Exception: correct=1
    if not question: raise ValueError('題目不能是空白')
    if qtype=='是非題':
        correct=1 if correct not in (1,2) else correct
    elif not (1 <= correct <= len(options) <= 4):
        raise ValueError('正確答案編號或選項數量不正確')
    return qtype,category,seconds,question,options,correct

def seed():
    db.create_all()
    # v1.1 -> v1.2 的輕量資料庫升級：Render 若已有舊 SQLite/Postgres，補上新欄位。
    inspector=db.inspect(db.engine) if hasattr(db,'inspect') else None
    # SQLAlchemy 的 inspect 位於 sqlalchemy.inspect，避免依賴舊資料庫 schema。
    from sqlalchemy import inspect, text
    insp=inspect(db.engine)
    upgrades={
        'student': [('battle_score','INTEGER DEFAULT 0')],
        'room': [('question_started_at','TIMESTAMP NULL')],
        'room_player': [('battle_score','INTEGER DEFAULT 0')],
    }
    for table, cols in upgrades.items():
        existing={c['name'] for c in inspect(db.engine).get_columns(table)}
        for col, definition in cols:
            if col not in existing:
                db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {definition}'))
    db.session.commit()
    if Student.query.count()==0:
        for seat,name,account,pwd in ROSTER:
            db.session.add(Student(account=account,name=name,password_hash=generate_password_hash(pwd),seat=seat,role='student'))
        db.session.add(Student(account='teacher',name='老師',password_hash=generate_password_hash('1930'),seat=0,role='teacher'))
        db.session.add(Student(account='teacher01',name='小明',password_hash=generate_password_hash('1930'),seat=0,role='student'))
    for _s in Student.query.all():
        if _s.role in ('student','teacher') and _s.hp == 20: _s.hp=100
        if _s.battle_score is None: _s.battle_score=0
    if PrizeCard.query.count()==0:
        for name,weight,desc in PRIZE_CARDS:
            db.session.add(PrizeCard(name=name,weight=weight,description=desc))
    if QuestionBank.query.count()==0:
        for q in QUESTIONS:
            db.session.add(QuestionBank(
                id=int(q['id']), qtype='選擇題' if len(q.get('options',[]))>=3 else '是非題',
                category=str(q.get('category','未分類')), seconds=60,
                question=str(q.get('question','')), options_json=json.dumps(q.get('options',[]),ensure_ascii=False),
                correct=int(q.get('correct',1)), active=True))
    db.session.commit()

def current_user():
    sid=session.get('student_id')
    return db.session.get(Student,sid) if sid else None

def login_required(fn):
    @wraps(fn)
    def wrap(*a,**kw):
        if not current_user(): return jsonify({'ok':False,'error':'請先登入'}),401
        return fn(*a,**kw)
    return wrap

def add_score(student,delta,reason,event_id):
    if not event_id: return False
    if ScoreEvent.query.filter_by(event_id=event_id).first(): return False
    student.score += int(delta)
    db.session.add(ScoreEvent(event_id=event_id,student_id=student.id,delta=int(delta),reason=reason))
    return True

def leaderboard_data():
    rows=Student.query.filter(Student.role=='student').order_by(Student.score.desc(),Student.seat.asc()).all()
    return [{'rank':i+1,'account':s.account,'name':s.name,'seat':s.seat,'score':s.score,'hp':s.hp,'battle_score':s.battle_score,'wins':s.wins,'losses':s.losses,'online':bool(s.online)} for i,s in enumerate(rows)]

def room_state(room):
    players=RoomPlayer.query.filter_by(room_id=room.id).all()
    return {'code':room.code,'status':room.status,'host_id':room.host_id,'current_index':room.current_index,'question_count':len(json.loads(room.question_ids or '[]')),'players':[{'student_id':p.student_id,'name':db.session.get(Student,p.student_id).name,'seat':db.session.get(Student,p.student_id).seat,'answered_index':p.answered_index,'correct_count':p.correct_count,'battle_score':p.battle_score,'hp':db.session.get(Student,p.student_id).hp} for p in players]}

@app.route('/')
def index(): return render_template('index.html')
@app.route('/student')
def student(): return render_template('student.html')
@app.route('/teacher')
def teacher(): return render_template('teacher.html')
@app.route('/game')
def game(): return render_template('game.html')
@app.route('/display')
def display(): return render_template('display.html')
@app.post('/api/login')
def api_login():
    data=request.get_json() or {}; account=str(data.get('account','')).strip(); pwd=str(data.get('password',''))
    u=Student.query.filter_by(account=account).first()
    if not u or not check_password_hash(u.password_hash,pwd): return jsonify({'ok':False,'error':'帳號或密碼錯誤'}),401
    session['student_id']=u.id; u.online=True; db.session.commit()
    return jsonify({'ok':True,'user':{'account':u.account,'name':u.name,'seat':u.seat,'role':u.role,'score':u.score,'hp':u.hp,'battle_score':u.battle_score,'wins':u.wins,'losses':u.losses}})
@app.post('/api/logout')
def logout():
    u=current_user()
    if u: u.online=False; db.session.commit()
    session.clear(); return jsonify({'ok':True})
@app.get('/api/me')
def me():
    u=current_user();
    if not u: return jsonify({'ok':False}),401
    return jsonify({'ok':True,'user':{'account':u.account,'name':u.name,'seat':u.seat,'role':u.role,'score':u.score,'hp':u.hp,'battle_score':u.battle_score,'wins':u.wins,'losses':u.losses}})
@app.get('/api/leaderboard')
def leaderboard(): return jsonify({'ok':True,'items':leaderboard_data()})
@app.get('/api/messages')
@login_required
def messages():
    rows=Message.query.order_by(Message.created_at.desc(),Message.id.desc()).limit(100).all()
    return jsonify({'ok':True,'items':[
        {'id':m.id,'user':m.user_name,'text':m.text,'timestamp':int(m.created_at.timestamp()*1000) if m.created_at else 0}
        for m in rows
    ]})

@app.post('/api/messages')
@login_required
def post_message():
    u=current_user()
    data=request.get_json() or {}
    text=str(data.get('text','')).strip()
    if not text: return jsonify({'ok':False,'error':'留言不能是空白'}),400
    if len(text)>300: return jsonify({'ok':False,'error':'留言最多 300 字'}),400
    m=Message(student_id=u.id,user_name=u.name,text=text)
    db.session.add(m); db.session.commit()
    return jsonify({'ok':True,'item':{'id':m.id,'user':m.user_name,'text':m.text,'timestamp':int(m.created_at.timestamp()*1000)}})

@app.get('/api/admin/messages')
def admin_messages():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    rows=Message.query.order_by(Message.created_at.desc(),Message.id.desc()).limit(500).all()
    return jsonify({'ok':True,'items':[
        {'id':m.id,'student_id':m.student_id,'user':m.user_name,'text':m.text,'timestamp':int(m.created_at.timestamp()*1000) if m.created_at else 0}
        for m in rows
    ]})

@app.delete('/api/admin/messages/<int:message_id>')
def admin_delete_message(message_id):
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    m=db.session.get(Message,message_id)
    if not m: return jsonify({'ok':False,'error':'留言不存在'}),404
    db.session.delete(m); db.session.commit()
    return jsonify({'ok':True})

@app.post('/api/admin/messages/clear')
def admin_clear_messages():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    count=Message.query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'ok':True,'deleted':count})

@app.get('/api/display/leaderboard')
def display_leaderboard():
    # 大螢幕專用資料：排名、座號、積分與尚未兌換的寶物卡。
    rows=Student.query.filter(Student.role=='student').order_by(Student.score.desc(),Student.seat.asc()).all()
    items=[]
    for i, student in enumerate(rows, 1):
        owned=(db.session.query(PrizeDraw, PrizeCard)
               .join(PrizeCard, PrizeDraw.card_id==PrizeCard.id)
               .filter(PrizeDraw.student_id==student.id, PrizeDraw.status=='pending')
               .order_by(PrizeDraw.created_at.desc()).all())
        items.append({
            'rank':i, 'account':student.account, 'name':student.name, 'seat':student.seat,
            'score':student.score, 'hp':student.hp, 'wins':student.wins, 'losses':student.losses,
            'cards':[{'id':draw.id, 'name':card.name, 'description':card.description} for draw,card in owned]
        })
    return jsonify({'ok':True,'items':items})
@app.get('/api/questions')
@login_required
def questions():
    n=min(max(int(request.args.get('count',10)),1),20)
    bank=active_questions()
    chosen=random.sample(bank,min(n,len(bank))) if bank else []
    return jsonify({'ok':True,'questions':[{k:q[k] for k in ('id','qtype','category','seconds','question','options')} for q in chosen]})

@app.post('/api/hp/exchange')
@login_required
def hp_exchange():
    u=current_user(); data=request.get_json() or {}; points=max(0,int(data.get('points',1)))
    if points<1 or u.score<points: return jsonify({'ok':False,'error':'積分不足，無法兌換 HP'}),400
    u.score-=points
    u.hp=u.hp+points*10
    db.session.add(ScoreEvent(event_id='hp-exchange:'+str(uuid.uuid4()),student_id=u.id,delta=-points,reason='積分兌換HP'))
    db.session.commit()
    return jsonify({'ok':True,'score':u.score,'hp':u.hp,'added_hp':points*10})

@app.post('/api/hp/to_score')
@login_required
def hp_to_score():
    u=current_user()
    hp_points=max(0,int(u.hp)//1000)
    if hp_points < 1:
        return jsonify({'ok':False,'error':'HP 不足 1000，無法兌換 1 分'}),400
    u.hp -= hp_points * 1000
    add_score(u, hp_points, f'HP 兌換積分（{hp_points} 分）', 'hp-to-score:'+str(uuid.uuid4()))
    db.session.commit()
    return jsonify({'ok':True,'score':u.score,'hp':u.hp,'added_score':hp_points})

@app.post('/api/quiz/start')
@login_required
def quiz_start():
    u=current_user()
    u.hp=100
    u.battle_score=0
    db.session.commit()
    return jsonify({'ok':True,'hp':u.hp,'battle_score':u.battle_score})

@app.post('/api/quiz/finish')
@login_required
def quiz_finish():
    u=current_user(); data=request.get_json() or {}; event_id=str(data.get('event_id','')).strip(); mode=str(data.get('mode','ai'))
    if mode not in ('ai','real'): mode='ai'
    battle_score=max(0,int(data.get('battle_score',0)))
    won=bool(data.get('win'))
    # 勝者：本場總得分 100% 轉成 HP；敗者：總得分 50% 轉成 HP。
    earned_hp=battle_score if won else battle_score//2
    u.battle_score=battle_score
    u.hp=max(0,u.hp)+earned_hp
    # 不自動把 HP 換成班級積分；玩家必須在學生頁手動兌換。
    points_from_hp=0
    if add_score(u,0,f'知識王{("AI" if mode=="ai" else "真人")}對戰紀錄',event_id):
        if won: u.wins+=1
        else: u.losses+=1
    db.session.commit()
    return jsonify({'ok':True,'battle_score':battle_score,'earned_hp':earned_hp,'score':u.score,'hp':u.hp,'points_from_hp':points_from_hp,'win':won})

def speed_points(elapsed):
    # 10 分為基本分；越快答對，速度加分越高。超過 12 秒仍保留基本 10 分。
    try: t=max(0.0,float(elapsed))
    except Exception: t=12.0
    bonus=max(0,min(10,round((12.0-t)*10/12.0)))
    return 10+bonus

@app.post('/api/validate')
@login_required
def validate_answer():
    u=current_user(); data=request.get_json() or {}; qid=int(data.get('id',0)); choice=int(data.get('choice',0))
    qobj=db.session.get(QuestionBank,qid)
    q=question_dict(qobj) if qobj and qobj.active else None
    if not q: return jsonify({'ok':False,'error':'題目不存在'}),404
    is_correct=choice==q['correct']
    elapsed=data.get('elapsed',12)
    gained=speed_points(elapsed) if is_correct else 0
    if not is_correct: u.hp=max(0,u.hp-10)
    db.session.add(AnswerRecord(student_id=u.id,question_id=q['id'],category=q['category'],question=q['question'],selected_choice=choice,correct_choice=q['correct'],is_correct=is_correct))
    db.session.commit()
    return jsonify({'ok':True,'correct':is_correct,'hp':u.hp,'gained':gained,'elapsed':float(elapsed) if str(elapsed).replace('.','',1).isdigit() else 12})

@app.post('/api/rooms')
@login_required
def create_room():
    u=current_user();
    if u.role=='teacher': return jsonify({'ok':False,'error':'教師管理帳號不能建立對戰房間'}),403
    for _ in range(20):
        code=''.join(random.choices(string.ascii_uppercase+string.digits,k=5))
        if not Room.query.filter_by(code=code).first(): break
    bank=active_questions(); qs=random.sample(bank,min(10,len(bank)))
    room=Room(code=code,host_id=u.id,question_ids=json.dumps([q['id'] for q in qs]),status='waiting')
    db.session.add(room); db.session.flush(); db.session.add(RoomPlayer(room_id=room.id,student_id=u.id)); db.session.commit()
    return jsonify({'ok':True,'room':room_state(room)})
@app.get('/api/rooms')
@login_required
def rooms():
    rs=Room.query.filter_by(status='waiting').order_by(Room.created_at.desc()).limit(15).all()
    return jsonify({'ok':True,'rooms':[room_state(r) for r in rs]})
@app.post('/api/rooms/<code>/join')
@login_required
def join_room(code):
    u=current_user(); r=Room.query.filter_by(code=code.upper()).first()
    if not r or r.status!='waiting': return jsonify({'ok':False,'error':'房間不存在或已開始'}),404
    existing=RoomPlayer.query.filter_by(room_id=r.id,student_id=u.id).first()
    if existing is None:
        if RoomPlayer.query.filter_by(room_id=r.id).count()>=2: return jsonify({'ok':False,'error':'房間已滿'}),400
        db.session.add(RoomPlayer(room_id=r.id,student_id=u.id))
        db.session.flush()
    # 第二位玩家加入後立即開戰，不再需要房主另外按「開始對戰」。
    players=RoomPlayer.query.filter_by(room_id=r.id).all()
    if len(players)>=2:
        r.status='playing'; r.current_index=0
        r.started_at=datetime.now(timezone.utc); r.question_started_at=datetime.now(timezone.utc)
        for p in players:
            st=db.session.get(Student,p.student_id)
            st.hp=100; p.answered_index=-1; p.correct_count=0; p.battle_score=0
    db.session.commit()
    return jsonify({'ok':True,'room':room_state(r)})
@app.post('/api/rooms/<code>/leave')
@login_required
def leave_room(code):
    u=current_user(); r=Room.query.filter_by(code=code.upper()).first()
    if not r:
        return jsonify({'ok':True,'gone':True})
    p=RoomPlayer.query.filter_by(room_id=r.id,student_id=u.id).first()
    if not p:
        return jsonify({'ok':True,'room':room_state(r)})
    db.session.delete(p); db.session.flush()
    remaining=RoomPlayer.query.filter_by(room_id=r.id).all()
    # 離開後沒有玩家：直接刪除空房間。
    if not remaining:
        db.session.delete(r)
        db.session.commit()
        return jsonify({'ok':True,'gone':True})
    # 對戰中有人離開：剩下玩家的房間也結束，避免幽靈房間。
    if r.status=='playing':
        r.status='finished'
    db.session.commit()
    return jsonify({'ok':True,'gone':False,'room':room_state(r)})

@app.get('/api/rooms/<code>')
@login_required
def get_room(code):
    r=Room.query.filter_by(code=code.upper()).first()
    if not r: return jsonify({'ok':False,'error':'找不到房間'}),404
    return jsonify({'ok':True,'room':room_state(r)})
@app.post('/api/rooms/<code>/start')
@login_required
def start_room(code):
    u=current_user(); r=Room.query.filter_by(code=code.upper()).first()
    if not r or r.host_id!=u.id: return jsonify({'ok':False,'error':'只有房主可以開始'}),403
    if RoomPlayer.query.filter_by(room_id=r.id).count()<2: return jsonify({'ok':False,'error':'至少需要兩位玩家'}),400
    r.status='playing'; r.current_index=0; r.started_at=datetime.now(timezone.utc); r.question_started_at=datetime.now(timezone.utc)
    for p in RoomPlayer.query.filter_by(room_id=r.id).all():
        s=db.session.get(Student,p.student_id); s.hp=100; p.answered_index=-1; p.correct_count=0; p.battle_score=0
    db.session.commit()
    return jsonify({'ok':True,'room':room_state(r)})
@app.get('/api/rooms/<code>/question')
@login_required
def room_question(code):
    r=Room.query.filter_by(code=code.upper()).first();
    if not r: return jsonify({'ok':False,'error':'找不到房間'}),404
    ids=json.loads(r.question_ids or '[]')
    if r.current_index>=len(ids): return jsonify({'ok':True,'done':True})
    qobj=db.session.get(QuestionBank,ids[r.current_index]); q=question_dict(qobj) if qobj and qobj.active else None
    return jsonify({'ok':True,'index':r.current_index,'question':{'id':q['id'],'category':q['category'],'question':q['question'],'options':q['options']}})
@app.post('/api/rooms/<code>/answer')
@login_required
def room_answer(code):
    u=current_user(); r=Room.query.filter_by(code=code.upper()).first()
    if not r or r.status!='playing': return jsonify({'ok':False,'error':'對戰尚未開始'}),400
    p=RoomPlayer.query.filter_by(room_id=r.id,student_id=u.id).first()
    if not p: return jsonify({'ok':False,'error':'你不在此房間'}),403
    data=request.get_json() or {}; idx=int(data.get('index',-1)); choice=int(data.get('choice',0)); ids=json.loads(r.question_ids or '[]')
    if idx!=r.current_index: return jsonify({'ok':False,'error':'題目已切換'}),409
    if p.answered_index==idx: return jsonify({'ok':True,'duplicate':True,'correct_count':p.correct_count})
    qobj=db.session.get(QuestionBank,ids[idx]); q=question_dict(qobj) if qobj and qobj.active else None
    correct=(choice==q['correct'])
    elapsed=(datetime.now(timezone.utc)- (r.question_started_at or datetime.now(timezone.utc))).total_seconds()
    gained=speed_points(elapsed) if correct else 0
    if not correct: u.hp=max(0,u.hp-10)
    if correct: p.correct_count+=1; p.battle_score+=gained
    p.answered_index=idx; db.session.commit()
    # advance when all players answered
    players=RoomPlayer.query.filter_by(room_id=r.id).all()
    if all(x.answered_index==idx for x in players):
        r.current_index+=1
        if r.current_index>=len(ids):
            r.status='finished'
            # 真人對戰：以本場 battle_score 判定勝負；勝者獲得 100% 本場分數的 HP，
            # 敗者獲得 50%。HP 不自動換成班級積分，必須手動兌換。
            scores=[x.battle_score for x in players]
            top=max(scores) if scores else 0
            for x in players:
                s=db.session.get(Student,x.student_id)
                won=(x.battle_score==top and top>0)
                earned=x.battle_score if won else x.battle_score//2
                s.hp += earned
                if won: s.wins += 1
                else: s.losses += 1
            db.session.commit()
        else: db.session.commit()
    return jsonify({'ok':True,'correct':correct,'correct_count':p.correct_count,'battle_score':p.battle_score,'hp':u.hp,'room':room_state(r)})

@app.get('/api/prizes')
@login_required
def prizes():
    u=current_user()
    cards=PrizeCard.query.order_by(PrizeCard.id).all()
    owned=(db.session.query(PrizeDraw,PrizeCard).join(PrizeCard,PrizeDraw.card_id==PrizeCard.id).filter(PrizeDraw.student_id==u.id,PrizeDraw.status=='pending').order_by(PrizeDraw.created_at.desc()).all())
    return jsonify({'ok':True,'cost':20,'cards':[{'id':c.id,'name':c.name,'weight':c.weight,'description':c.description} for c in cards], 'owned':[{'id':d.id,'name':c.name,'description':c.description,'status':d.status,'created_at':d.created_at.isoformat()} for d,c in owned]})

@app.post('/api/prizes/draw')
@login_required
def prize_draw():
    u=current_user(); cost=20
    if u.score < cost: return jsonify({'ok':False,'error':f'點數不足 {cost} 分','score':u.score}),400
    cards=PrizeCard.query.all()
    if not cards: return jsonify({'ok':False,'error':'目前沒有抽獎卡設定'}),500
    chosen=random.choices(cards,weights=[c.weight for c in cards],k=1)[0]
    event_id='draw:'+str(uuid.uuid4())
    if not add_score(u,-cost,'幸運抽獎',event_id): return jsonify({'ok':False,'error':'抽獎失敗，請再試一次'}),500
    draw=PrizeDraw(student_id=u.id,card_id=chosen.id,status='pending')
    db.session.add(draw); db.session.commit()
    return jsonify({'ok':True,'card':{'id':chosen.id,'name':chosen.name,'description':chosen.description},'score':u.score,'draw_id':draw.id})

@app.post('/api/admin/prizes/<int:draw_id>/redeem')
def redeem_prize(draw_id):
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    d=db.session.get(PrizeDraw,draw_id)
    if not d or d.status!='pending': return jsonify({'ok':False,'error':'卡片不存在或已核銷'}),404
    d.status='redeemed'; db.session.commit(); return jsonify({'ok':True})

@app.get('/api/admin/prizes')
def admin_prizes():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    rows=(db.session.query(PrizeDraw,PrizeCard,Student).join(PrizeCard,PrizeDraw.card_id==PrizeCard.id).join(Student,PrizeDraw.student_id==Student.id).filter(PrizeDraw.status=='pending').order_by(PrizeDraw.created_at.desc()).all())
    return jsonify({'ok':True,'items':[{'id':d.id,'student_id':s.id,'name':s.name,'account':s.account,'seat':s.seat,'card':c.name,'description':c.description,'created_at':d.created_at.isoformat()} for d,c,s in rows]})

@app.post('/api/admin/score')
def admin_score():
    u=current_user();
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    data=request.get_json() or {}; sid=int(data.get('student_id')); delta=int(data.get('delta',0)); reason=str(data.get('reason','教師調整'))[:120]
    s=db.session.get(Student,sid)
    if not s or s.role!='student': return jsonify({'ok':False,'error':'學生不存在'}),404
    add_score(s,delta,reason,'admin:'+str(uuid.uuid4())); db.session.commit(); return jsonify({'ok':True,'score':s.score})
@app.get('/api/admin/students')
def admin_students():
    u=current_user();
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    return jsonify({'ok':True,'items':[{'id':s.id,'account':s.account,'name':s.name,'seat':s.seat,'score':s.score,'wins':s.wins,'losses':s.losses} for s in Student.query.filter_by(role='student').order_by(Student.seat).all()]})

@app.get('/api/admin/questions')
def admin_questions():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    category=str(request.args.get('category','')).strip()
    keyword=str(request.args.get('q','')).strip()
    query=QuestionBank.query.filter_by(active=True)
    if category: query=query.filter(QuestionBank.category==category)
    if keyword: query=query.filter(QuestionBank.question.ilike(f'%{keyword}%'))
    rows=query.order_by(QuestionBank.id.desc()).limit(500).all()
    return jsonify({'ok':True,'count':QuestionBank.query.filter_by(active=True).count(),'items':[question_dict(q) for q in rows], 'categories':[x[0] for x in db.session.query(QuestionBank.category).filter_by(active=True).distinct().order_by(QuestionBank.category).all()]})

@app.post('/api/admin/questions')
def admin_add_question():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    try:
        qtype,category,seconds,question,options,correct=normalize_question_input(request.get_json() or {})
    except ValueError as e:
        return jsonify({'ok':False,'error':str(e)}),400
    q=QuestionBank(id=next_question_id(),qtype=qtype,category=category,seconds=seconds,question=question,options_json=json.dumps(options,ensure_ascii=False),correct=correct,active=True)
    db.session.add(q); db.session.commit()
    return jsonify({'ok':True,'question':question_dict(q)})

@app.post('/api/admin/questions/import')
def admin_import_questions():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    if 'file' not in request.files: return jsonify({'ok':False,'error':'請選擇 CSV 檔案'}),400
    file=request.files['file']
    if not file.filename.lower().endswith('.csv'): return jsonify({'ok':False,'error':'只接受 CSV 檔案'}),400
    raw=file.read()
    text=None
    for enc in ('utf-8-sig','utf-8','cp950','big5'):
        try: text=raw.decode(enc); break
        except UnicodeDecodeError: continue
    if text is None: return jsonify({'ok':False,'error':'CSV 編碼無法辨識，請使用 UTF-8'}),400
    reader=csv.DictReader(io.StringIO(text))
    required={'題目','選項一','選項二','正確答案'}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        return jsonify({'ok':False,'error':'CSV 欄位需至少包含：題目、選項一、選項二、正確答案；建議使用系統提供的完整格式'}),400
    imported=[]; skipped=[]; errors=[]
    existing={(q.category.strip(),q.question.strip()) for q in QuestionBank.query.filter_by(active=True).all()}
    nid=next_question_id()
    for lineno,row in enumerate(reader,start=2):
        try:
            data={
                '題型':row.get('題型','選擇題'), '分類':row.get('分類','未分類'), '秒數':row.get('秒數','60'),
                '題目':row.get('題目',''), '選項一':row.get('選項一',''), '選項二':row.get('選項二',''),
                '選項三':row.get('選項三',''), '選項四':row.get('選項四',''), '正確答案':row.get('正確答案','1')
            }
            qtype,category,seconds,question,options,correct=normalize_question_input(data)
            key=(category,question)
            if key in existing:
                skipped.append({'line':lineno,'reason':'已有相同分類與題目','question':question})
                continue
            q=QuestionBank(id=nid,qtype=qtype,category=category,seconds=seconds,question=question,options_json=json.dumps(options,ensure_ascii=False),correct=correct,active=True)
            db.session.add(q); imported.append(q); existing.add(key); nid+=1
        except Exception as e:
            errors.append({'line':lineno,'error':str(e)})
    if errors and not imported:
        db.session.rollback()
        return jsonify({'ok':False,'error':'沒有成功匯入任何題目','imported':0,'skipped':len(skipped),'errors':errors[:20]}),400
    db.session.commit()
    return jsonify({'ok':True,'imported':len(imported),'skipped':len(skipped),'errors':errors[:20],'total':QuestionBank.query.filter_by(active=True).count()})

@app.delete('/api/admin/questions/<int:q_id>')
def admin_delete_question(q_id):
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    q=db.session.get(QuestionBank,q_id)
    if not q or not q.active: return jsonify({'ok':False,'error':'題目不存在'}),404
    q.active=False; db.session.commit()
    return jsonify({'ok':True})

@app.get('/api/admin/questions/export')
def admin_export_questions():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    rows=QuestionBank.query.filter_by(active=True).order_by(QuestionBank.id).all()
    output=io.StringIO(newline='')
    writer=csv.writer(output)
    writer.writerow(['題型','分類','秒數','題目','選項一','選項二','選項三','選項四','正確答案'])
    for q in rows:
        opts=json.loads(q.options_json or '[]')
        opts=(opts+['','','',''])[:4]
        writer.writerow([q.qtype,q.category,q.seconds,q.question,*opts,q.correct])
    from flask import Response
    resp=Response('﻿'+output.getvalue(),mimetype='text/csv; charset=utf-8')
    resp.headers['Content-Disposition']='attachment; filename=class_knowledge_question_bank.csv'
    return resp

@app.get('/api/admin/errors')
def admin_errors():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    rows=(db.session.query(AnswerRecord.question_id,AnswerRecord.question,AnswerRecord.category,db.func.count(AnswerRecord.id).label('total'),db.func.sum(db.case((AnswerRecord.is_correct==False,1),else_=0)).label('wrong')).group_by(AnswerRecord.question_id,AnswerRecord.question,AnswerRecord.category).order_by(db.desc('wrong'),db.desc('total')).limit(30).all())
    return jsonify({'ok':True,'items':[{'question_id':r[0],'question':r[1],'category':r[2],'attempts':int(r[3] or 0),'wrong':int(r[4] or 0)} for r in rows if int(r[4] or 0)>0]})

@app.get('/api/health')
def health(): return jsonify({'status':'ok','system':'class-knowledge-system-v1.3'})

@app.context_processor
def ctx(): return {'year':datetime.now().year}

with app.app_context(): seed()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
