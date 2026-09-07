import os, json, random, string, uuid
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__)
app.config['SECRET_KEY']=os.environ.get('SECRET_KEY','fresh-v1-change-me')
db_url=os.environ.get('DATABASE_URL','sqlite:///'+os.path.join(BASE_DIR,'data.db'))
if db_url.startswith('postgres://'): db_url=db_url.replace('postgres://','postgresql://',1)
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
    hp=db.Column(db.Integer,default=20)
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
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

class RoomPlayer(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    room_id=db.Column(db.Integer,db.ForeignKey('room.id'),nullable=False)
    student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False)
    answered_index=db.Column(db.Integer,default=-1)
    correct_count=db.Column(db.Integer,default=0)
    joined_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
    __table_args__=(db.UniqueConstraint('room_id','student_id',name='uq_room_student'),)

with open(os.path.join(BASE_DIR,'quiz.json'),encoding='utf-8') as f: QUESTIONS=json.load(f)

ROSTER=[(1, '黃聰', '111061', '0924'), (2, '昱綸', '111201', '1031'), (3, '靖喬', '111095', '1118'), (4, '侑辰', '111038', '0107'), (5, '楷欣', '111039', '0111'), (6, '芸霆', '111128', '0126'), (7, '俊賀', '111040', '0129'), (8, '品睿', '111070', '0201'), (9, '柏甫', '111071', '0227'), (10, '威碩', '111164', '0502'), (11, '雋書', '111074', '0612'), (12, '莫凡', '111166', '0703'), (13, '祐廷', '111137', '0723'), (14, '詠琂', '111139', '0818'), (15, '可荺', '111019', '0924'), (16, '張惟', '111079', '1015'), (17, '品真', '111112', '1108'), (18, '彥伃', '111115', '1223'), (19, '羽芯', '111052', '0125'), (20, '紫瑜', '111053', '0205'), (21, '翊榛', '111117', '0217'), (22, '侑璇', '111054', '0218'), (23, '芷軒', '111143', '0310'), (24, '芯妤', '111057', '0402'), (25, '毓琳', '111147', '0520'), (26, '予甯', '111150', '0710')]

def seed():
    db.create_all()
    if Student.query.count()==0:
        for seat,name,account,pwd in ROSTER:
            db.session.add(Student(account=account,name=name,password_hash=generate_password_hash(pwd),seat=seat,role='student'))
        db.session.add(Student(account='teacher',name='老師',password_hash=generate_password_hash('1930'),seat=0,role='teacher'))
        db.session.add(Student(account='teacher01',name='小明',password_hash=generate_password_hash('1930'),seat=0,role='student'))
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
    return [{'rank':i+1,'account':s.account,'name':s.name,'seat':s.seat,'score':s.score,'hp':s.hp,'wins':s.wins,'losses':s.losses,'online':bool(s.online)} for i,s in enumerate(rows)]

def room_state(room):
    players=RoomPlayer.query.filter_by(room_id=room.id).all()
    return {'code':room.code,'status':room.status,'host_id':room.host_id,'current_index':room.current_index,'question_count':len(json.loads(room.question_ids or '[]')),'players':[{'student_id':p.student_id,'name':db.session.get(Student,p.student_id).name,'seat':db.session.get(Student,p.student_id).seat,'answered_index':p.answered_index,'correct_count':p.correct_count} for p in players]}

@app.route('/')
def index(): return render_template('index.html')
@app.route('/student')
def student(): return render_template('student.html')
@app.route('/teacher')
def teacher(): return render_template('teacher.html')
@app.route('/display')
def display(): return render_template('display.html')
@app.post('/api/login')
def api_login():
    data=request.get_json() or {}; account=str(data.get('account','')).strip(); pwd=str(data.get('password',''))
    u=Student.query.filter_by(account=account).first()
    if not u or not check_password_hash(u.password_hash,pwd): return jsonify({'ok':False,'error':'帳號或密碼錯誤'}),401
    session['student_id']=u.id; u.online=True; db.session.commit()
    return jsonify({'ok':True,'user':{'account':u.account,'name':u.name,'seat':u.seat,'role':u.role,'score':u.score,'hp':u.hp,'wins':u.wins,'losses':u.losses}})
@app.post('/api/logout')
def logout():
    u=current_user()
    if u: u.online=False; db.session.commit()
    session.clear(); return jsonify({'ok':True})
@app.get('/api/me')
def me():
    u=current_user();
    if not u: return jsonify({'ok':False}),401
    return jsonify({'ok':True,'user':{'account':u.account,'name':u.name,'seat':u.seat,'role':u.role,'score':u.score,'hp':u.hp,'wins':u.wins,'losses':u.losses}})
@app.get('/api/leaderboard')
def leaderboard(): return jsonify({'ok':True,'items':leaderboard_data()})
@app.get('/api/questions')
@login_required
def questions():
    n=min(max(int(request.args.get('count',10)),1),20)
    chosen=random.sample(QUESTIONS,min(n,len(QUESTIONS)))
    # never expose answer before submission
    return jsonify({'ok':True,'questions':[{'id':q['id'],'category':q['category'],'question':q['question'],'options':q['options']} for q in chosen]})
@app.post('/api/quiz/finish')
@login_required
def quiz_finish():
    u=current_user(); data=request.get_json() or {}; event_id=str(data.get('event_id','')).strip(); mode=str(data.get('mode','ai'))
    correct=max(0,min(20,int(data.get('correct',0))));
    if mode not in ('ai','real'): mode='ai'
    bonus=(3 if mode=='ai' else 5) if bool(data.get('win')) else 0
    participation=1
    earned=correct+bonus+participation
    if add_score(u,earned,f'知識王{("AI" if mode=="ai" else "真人")}對戰',event_id):
        if bool(data.get('win')): u.wins+=1
        else: u.losses+=1
        db.session.commit()
        return jsonify({'ok':True,'earned':earned,'score':u.score})
    return jsonify({'ok':True,'earned':0,'score':u.score,'duplicate':True})

@app.post('/api/validate')
@login_required
def validate_answer():
    u=current_user(); data=request.get_json() or {}; qid=int(data.get('id',0)); choice=int(data.get('choice',0))
    q=next((x for x in QUESTIONS if x['id']==qid),None)
    if not q: return jsonify({'ok':False,'error':'題目不存在'}),404
    is_correct=choice==q['correct']
    db.session.add(AnswerRecord(student_id=u.id,question_id=q['id'],category=q['category'],question=q['question'],selected_choice=choice,correct_choice=q['correct'],is_correct=is_correct))
    db.session.commit()
    return jsonify({'ok':True,'correct':is_correct})

@app.post('/api/rooms')
@login_required
def create_room():
    u=current_user();
    if u.role=='teacher': return jsonify({'ok':False,'error':'教師管理帳號不能建立對戰房間'}),403
    for _ in range(20):
        code=''.join(random.choices(string.ascii_uppercase+string.digits,k=5))
        if not Room.query.filter_by(code=code).first(): break
    qs=random.sample(QUESTIONS,min(10,len(QUESTIONS)))
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
    if RoomPlayer.query.filter_by(room_id=r.id,student_id=u.id).first() is None:
        if RoomPlayer.query.filter_by(room_id=r.id).count()>=2: return jsonify({'ok':False,'error':'房間已滿'}),400
        db.session.add(RoomPlayer(room_id=r.id,student_id=u.id)); db.session.commit()
    return jsonify({'ok':True,'room':room_state(r)})
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
    r.status='playing'; r.current_index=0; r.started_at=datetime.now(timezone.utc); db.session.commit()
    return jsonify({'ok':True,'room':room_state(r)})
@app.get('/api/rooms/<code>/question')
@login_required
def room_question(code):
    r=Room.query.filter_by(code=code.upper()).first();
    if not r: return jsonify({'ok':False,'error':'找不到房間'}),404
    ids=json.loads(r.question_ids or '[]')
    if r.current_index>=len(ids): return jsonify({'ok':True,'done':True})
    q=next((x for x in QUESTIONS if x['id']==ids[r.current_index]),None)
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
    q=next((x for x in QUESTIONS if x['id']==ids[idx]),None)
    correct=(choice==q['correct'])
    if correct: p.correct_count+=1
    p.answered_index=idx; db.session.commit()
    # advance when all players answered
    players=RoomPlayer.query.filter_by(room_id=r.id).all()
    if all(x.answered_index==idx for x in players):
        r.current_index+=1
        if r.current_index>=len(ids):
            r.status='finished'
            for x in players:
                s=db.session.get(Student,x.student_id); win=x.correct_count>=(sum(y.correct_count for y in players)-x.correct_count) if len(players)==2 else False
                # v1: each participant gets correct + participation; winner gets bonus
                event=f'room:{r.id}:player:{x.student_id}'
                bonus=5 if (len(players)==2 and x.correct_count>next(y.correct_count for y in players if y.student_id!=x.student_id)) else 0
                add_score(s,x.correct_count+1+bonus,'知識王真人對戰',event)
                if bonus: s.wins+=1
                else: s.losses+=1
            db.session.commit()
        else: db.session.commit()
    return jsonify({'ok':True,'correct':correct,'correct_count':p.correct_count,'room':room_state(r)})

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

@app.get('/api/admin/errors')
def admin_errors():
    u=current_user()
    if not u or u.role!='teacher': return jsonify({'ok':False,'error':'需要教師權限'}),403
    rows=(db.session.query(AnswerRecord.question_id,AnswerRecord.question,AnswerRecord.category,db.func.count(AnswerRecord.id).label('total'),db.func.sum(db.case((AnswerRecord.is_correct==False,1),else_=0)).label('wrong')).group_by(AnswerRecord.question_id,AnswerRecord.question,AnswerRecord.category).order_by(db.desc('wrong'),db.desc('total')).limit(30).all())
    return jsonify({'ok':True,'items':[{'question_id':r[0],'question':r[1],'category':r[2],'attempts':int(r[3] or 0),'wrong':int(r[4] or 0)} for r in rows if int(r[4] or 0)>0]})

@app.get('/api/health')
def health(): return jsonify({'status':'ok','system':'class-knowledge-system-v1'})

@app.context_processor
def ctx(): return {'year':datetime.now().year}

with app.app_context(): seed()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
