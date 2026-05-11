import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from openai import OpenAI, OpenAIError
import streamlit as st
from dotenv import load_dotenv
import json, shelve, unicodedata, base64, re, datetime
from fpdf import FPDF

try:
    from prompts.tabler_prompt import TABLER_PROMPT
    from prompts.dictator_prompt import DICTATOR_PROMPT
    from prompts.quizzy_prompt import QUIZZY_PROMPT
except ImportError:
    TABLER_PROMPT = "You are Tabler, an expert curriculum designer. Create a detailed course outline with modules and lessons. Include learning objectives per module, lesson titles (3-5 per module), and assessment strategy. Format with clear headings."
    DICTATOR_PROMPT = 'You are DICTator. Analyze the course outline and return ONLY valid JSON (no markdown, no explanation) like: {"Module 1: Name": ["Lesson 1.1: Name", "Lesson 1.2: Name"], "Module 2: Name": ["Lesson 2.1: Name"]}. Return ONLY the JSON object.'
    QUIZZY_PROMPT = "You are Quizzy. Generate exactly 10 multiple-choice questions from the course content. Format each as:\nQ1. [Question]\nA) [Option]\nB) [Option]\nC) [Option]\nD) [Option]\nAnswer: [Letter]\nExplanation: [Brief reason]\n\nCourse content:\n"

load_dotenv()

st.set_page_config(page_title="AI POWERED DYNAMIC CONTENT GENERATION", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

/* ===== GLOBAL WHITE BACKGROUND ===== */
html, body, .stApp, section.main, .block-container {
    background: #FFFFFF !important;
    color: #1E293B !important;
    font-family: 'Inter', sans-serif !important;
}

/* Remove all internal backgrounds */
div[data-testid="stAppViewContainer"],
div[data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"],
div[data-testid="column"] {
    background: transparent !important;
}

/* ===== BUTTONS (PRIMARY BLUE) ===== */
.stButton > button {
    width: 100%;
    background: linear-gradient(135deg, #5B8DEF, #7DA7FF) !important;
    color: white !important;
    border-radius: 10px !important;
    border: none !important;
    font-weight: 600;
    padding: 10px;
    transition: 0.2s;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(91,141,239,0.35);
}

/* ===== TOP METRICS (COURSES / QUIZZES / LESSONS) ===== */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #DCE8FF, #C7DBFF) !important;
    border: 1px solid #AFC8FF !important;
    border-radius: 14px;
    padding: 15px;
}

/* ===== FEATURE BOXES (BOTTOM CARDS) ===== */
div[data-testid="column"] > div {
    background: linear-gradient(135deg, #EEF4FF, #DCE8FF) !important;
    border: 1px solid #C3D6FF !important;
    border-radius: 16px;
    padding: 20px;
    transition: 0.3s;
}

/* Hover effect */
div[data-testid="column"] > div:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 25px rgba(91,141,239,0.25);
}

/* ===== INPUT FIELDS ===== */
.stTextInput input {
    background: #F5F8FF !important;
    border: 1px solid #C3D6FF !important;
    border-radius: 10px !important;
    padding: 10px !important;
}

/* ===== SIDEBAR ===== */
[data-testid="stSidebar"] {
    background: #F5F8FF !important;
}

/* ===== REMOVE STREAMLIT DEFAULT ===== */
#MainMenu, footer, header {
    visibility: hidden;
}

/* ===== FEATURE BOXES (BOTTOM SECTION) ===== */
div[data-testid="column"] > div {
    border-radius: 16px;
    padding: 20px;
    transition: 0.3s;
    text-align: center;
    font-weight: 600;
}

/* Assign colors by order */
div[data-testid="column"] > div:nth-child(1) {
    background: #E3F2FD !important; /* Soft Blue */
    border: 1px solid #90CAF9 !important;
}

div[data-testid="column"] > div:nth-child(2) {
    background: #E8F5E9 !important; /* Light Green */
    border: 1px solid #A5D6A7 !important;
}

div[data-testid="column"] > div:nth-child(3) {
    background: #FFF8E1 !important; /* Warm Beige */
    border: 1px solid #FFE082 !important;
}

div[data-testid="column"] > div:nth-child(4) {
    background: #F3E5F5 !important; /* Pale Lavender */
    border: 1px solid #CE93D8 !important;
}

/* Hover effect for all boxes */
div[data-testid="column"] > div:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 25px rgba(91,141,239,0.25);
}


</style>
""", unsafe_allow_html=True)



# ── AI client ──────────────────────────────────────────────────────────────
try:
    client = OpenAI(api_key="YOUR API KEY", base_url="https://api.groq.com/openai/v1")
except: client = None

MODEL = "openai/gpt-oss-20b"

def call_llm(system, user=""):
    msgs = [{"role":"system","content":system}]
    if user: msgs.append({"role":"user","content":user})
    r = client.chat.completions.create(model=MODEL, messages=msgs, max_tokens=4096)
    return r.choices[0].message.content

# ── DB helpers ─────────────────────────────────────────────────────────────
DB="ls_db"
def db_get(k,d=None):
    with shelve.open(DB) as db: return db.get(k,d)
def db_set(k,v):
    with shelve.open(DB) as db: db[k]=v
def get_users(): return db_get("users",{})
def save_users(u): db_set("users",u)
def get_courses(): return db_get("courses",[])
def save_courses(c): db_set("courses",c)
def get_qh(u): return db_get(f"qh_{u}",[])
def add_qh(u,mod,sc,tot):
    h=get_qh(u); h.append({"module":mod,"score":sc,"total":tot,"pct":round(sc/tot*100) if tot else 0,"date":str(datetime.date.today())}); db_set(f"qh_{u}",h)
def get_fb(): return db_get("fb",[])
def add_fb(u,name,msg,rating):
    f=get_fb(); f.append({"user":u,"name":name,"message":msg,"rating":rating,"date":str(datetime.date.today())}); db_set("fb",f)

# ── Session ────────────────────────────────────────────────────────────────
DEFS={"logged_in":False,"current_user":None,"user_role":None,"page":"🏠 Dashboard","chat_history":[],"course_outline":None,"gen_modules":{},"quiz_data":{},"course_meta":{},"pdf_b64":None,"pdf_ready":False,"quiz_answers":{},"quiz_score":None,"active_quiz":None}
for k,v in DEFS.items():
    if k not in st.session_state: st.session_state[k]=v

# ── Auth helpers ───────────────────────────────────────────────────────────
def register(un,pw,name,email,role="user"):
    u=get_users()
    if un in u: return False,"Username exists."
    u[un]={"password":pw,"name":name,"email":email,"role":role,"joined":str(datetime.date.today()),"bio":"","avatar":"🧑‍🎓"}
    save_users(u); return True,"Registered!"

def login(un,pw):
    u=get_users()
    if un not in u: return False,"User not found."
    if u[un]["password"]!=pw: return False,"Wrong password."
    return True,u[un]

# ── PDF helper ─────────────────────────────────────────────────────────────
def make_pdf(content):
    content=unicodedata.normalize('NFKD',content).encode('ascii','ignore').decode('ascii')
    pdf=FPDF(); pdf.add_page(); pdf.set_font('Arial','B',11)
    pdf.multi_cell(0,8,content); return pdf

# ── Quiz parser ────────────────────────────────────────────────────────────
def parse_quiz(text):
    qs=[]
    for block in re.split(r'\nQ\d+\.','\n'+(text or "")):
        block=block.strip()
        if not block: continue
        lines=block.split('\n'); q=lines[0].strip(); opts={}; ans=""; exp=""
        for ln in lines[1:]:
            ln=ln.strip()
            if ln.startswith('A)'): opts['A']=ln[2:].strip()
            elif ln.startswith('B)'): opts['B']=ln[2:].strip()
            elif ln.startswith('C)'): opts['C']=ln[2:].strip()
            elif ln.startswith('D)'): opts['D']=ln[2:].strip()
            elif ln.startswith('Answer:'): ans=ln.replace('Answer:','').strip().upper()
            elif ln.startswith('Explanation:'): exp=ln.replace('Explanation:','').strip()
        if q and opts and ans: qs.append({"question":q,"options":opts,"answer":ans,"explanation":exp})
    return qs

# ══════════════════════════════════════════════════════════════════════════
# AUTH PAGE
# ══════════════════════════════════════════════════════════════════════════
def page_auth():
    st.markdown("""<div style="text-align:center;padding:36px 0 22px;">
        <div style="font-size:3.2rem;">🎓</div>
        <div style="font-family:'Sora',sans-serif;font-size:2.6rem;font-weight:800;
             background:linear-gradient(135deg,#E8EAFF,#A89EFF 50%,#FF6584);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;">LearnSphere</div>
        <div style="color:#7B80A0;font-size:.95rem;margin-top:5px;">AI-Powered E-Learning · Learn Anything, Anytime</div>
    </div>""", unsafe_allow_html=True)
    _,mid,_=st.columns([1,1.3,1])
    with mid:
        t1,t2=st.tabs(["🔐 Login","✨ Sign Up"])
        with t1:
            st.markdown("<br>",unsafe_allow_html=True)
            u=st.text_input("Username",key="li_u",placeholder="Your username")
            p=st.text_input("Password",type="password",key="li_p",placeholder="Your password")
            c1,c2=st.columns(2)
            with c1:
                if st.button("Login →",use_container_width=True):
                    ok,res=login(u,p)
                    if ok:
                        st.session_state.logged_in=True; st.session_state.current_user=u
                        st.session_state.user_role=res["role"]; st.rerun()
                    else: st.error(res)
            with c2:
                if st.button("Demo Login",use_container_width=True):
                    us=get_users()
                    if "demo" not in us: register("demo","demo123","Alex Demo","alex@demo.com","user")
                    if "admin" not in us: register("admin","admin123","Admin User","admin@demo.com","admin")
                    st.session_state.logged_in=True; st.session_state.current_user="demo"
                    st.session_state.user_role="user"; st.rerun()
        with t2:
            st.markdown("<br>",unsafe_allow_html=True)
            n=st.text_input("Full Name",key="su_n",placeholder="Your name")
            e=st.text_input("Email",key="su_e",placeholder="your@email.com")
            un=st.text_input("Username",key="su_u",placeholder="Choose username")
            pw=st.text_input("Password",type="password",key="su_p",placeholder="Create password")
            if st.button("Create Account →",use_container_width=True):
                if all([n,e,un,pw]):
                    ok,msg=register(un,pw,n,e,"user")
                    st.success(msg) if ok else st.error(msg)
                else: st.error("Fill all fields.")
    st.markdown("<br><br>",unsafe_allow_html=True)
    cols=st.columns(4)
    for col,(ic,ti,de) in zip(cols,[("🤖","AI Course Generator","Enter requirements, AI builds full course"),("📦","Smart Modules","Complete lessons following Bloom's Taxonomy"),("📝","Auto Quizzes","10 MCQs per module with instant scoring"),("📄","PDF Export","Download full course as formatted PDF")]):
        with col:
            st.markdown(f'<div class="card" style="text-align:center;"><div style="font-size:1.8rem;margin-bottom:7px;">{ic}</div><div style="font-weight:700;font-size:.86rem;margin-bottom:4px;">{ti}</div><div style="color:var(--muted);font-size:.77rem;">{de}</div></div>',unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════
def sidebar():
    with st.sidebar:
        st.markdown("""<div style="text-align:center;padding:16px 0 6px;">
            <div style="font-size:1.8rem;">🎓</div>
            <div style="font-family:'Sora',sans-serif;font-size:1.2rem;font-weight:800;
                 background:linear-gradient(135deg,#A89EFF,#FF6584);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">LearnSphere</div>
        </div>""", unsafe_allow_html=True)
        u=get_users().get(st.session_state.current_user,{})
        st.markdown(f"""<div style="background:rgba(108,99,255,.1);border:1px solid rgba(108,99,255,.2);
             border-radius:12px;padding:10px;margin:7px 0;text-align:center;">
            <div style="font-size:1.3rem;">{u.get('avatar','🧑‍🎓')}</div>
            <div style="font-weight:700;font-size:.86rem;">{u.get('name','User')}</div>
            <div style="color:var(--muted);font-size:.71rem;">{st.session_state.user_role.capitalize()}</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("<div style='color:var(--muted);font-size:.71rem;padding:0 4px;margin-bottom:4px;'>MENU</div>",unsafe_allow_html=True)
        all_pages=["🏠 Dashboard","🚀 Generate Course","📦 My Modules","📝 Take Quiz","💬 AI Tutor","📊 My Progress","💬 Feedback","👤 Profile"]
        if st.session_state.user_role=="admin":
            all_pages+=["👑 Admin Panel","👥 Manage Users","📈 All Performance","💌 All Feedback"]
        sel=st.radio("",all_pages,key="nav",label_visibility="collapsed")
        st.session_state.page=sel
        st.markdown("---")
        if st.button("🚪 Logout",use_container_width=True):
            for k,v in DEFS.items(): st.session_state[k]=v
            st.rerun()
        st.markdown("<div style='text-align:center;color:var(--muted);font-size:.66rem;margin-top:14px;'>LearnSphere v2.0 · AI-Powered</div>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
def page_dashboard():
    u = get_users().get(st.session_state.current_user, {})
    qh = get_qh(st.session_state.current_user)
    avg = round(sum(q['pct'] for q in qh) / len(qh)) if qh else 0
    courses = get_courses()

    # ✅ Fix: count modules from session OR saved courses
    my_modules_count = len(st.session_state.gen_modules) or sum(
        len(c.get("modules", {}))
        for c in courses
        if c.get("created_by") == st.session_state.current_user
    )

    st.markdown(f"""<div style="margin-bottom:20px;">
        <div style="font-family:'Sora',sans-serif;font-size:1.65rem;font-weight:800;">
            Welcome back, {u.get('name','User')}! 👋
        </div>
        <div style="color:var(--muted);">Ready to learn something new today?</div>
    </div>""", unsafe_allow_html=True)

    s1, s2, s3, s4 = st.columns(4)
    for col, (v, l, c) in zip([s1, s2, s3, s4], [
        (str(len(courses)), "Courses Available", "var(--primary)"),
        (str(len(qh)), "Quizzes Taken", "var(--acc)"),
        (f"{avg}%", "Avg Score", "var(--warn)"),
        (str(my_modules_count), "My Modules", "var(--sec)"),
    ]):
        with col:
            st.markdown(
                f'<div class="stat"><div class="stn" style="color:{c};">{v}</div>'
                f'<div class="stl">{l}</div></div>',
                unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)
    ca, cb = st.columns([2, 1])

    with ca:
        st.markdown('<div class="sec">Recent Activity</div>', unsafe_allow_html=True)
        if qh:
            for q in reversed(qh[-5:]):
                c = "var(--ok)" if q['pct'] >= 70 else "var(--warn)" if q['pct'] >= 50 else "var(--sec)"
                st.markdown(f"""<div class="card" style="display:flex;justify-content:space-between;align-items:center;padding:13px 17px;">
                    <div><div style="font-weight:600;font-size:.86rem;">📝 {q['module']}</div>
                    <div style="color:var(--muted);font-size:.74rem;">{q['date']}</div></div>
                    <div style="font-family:'Sora',sans-serif;font-size:1.15rem;font-weight:800;color:{c};">{q['pct']}%</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="card" style="text-align:center;padding:26px;"><div style="font-size:2rem;">📖</div><div style="color:var(--muted);margin-top:7px;font-size:.86rem;">No activity yet. Generate a course and start learning!</div></div>', unsafe_allow_html=True)

    with cb:
        st.markdown('<div class="sec">Quick Start</div>', unsafe_allow_html=True)
        for lbl, pg in [
            ("🚀 Generate a Course", "🚀 Generate Course"),
            ("📝 Take a Quiz", "📝 Take Quiz"),
            ("💬 Chat with AI Tutor", "💬 AI Tutor")
        ]:
            if st.button(lbl, use_container_width=True, key=f"qs_{lbl}"):
                st.session_state.page = pg
                st.rerun()

        if courses:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div style="font-weight:700;font-size:.86rem;margin-bottom:7px;">📚 Available Courses</div>', unsafe_allow_html=True)
            for c in courses[-3:]:
                st.markdown(
                    f'<div class="card" style="padding:9px 13px;">'
                    f'<div style="font-weight:600;font-size:.8rem;">📘 {c.get("name","")}</div>'
                    f'<div style="color:var(--muted);font-size:.72rem;">{c.get("meta",{}).get("level","")} · {len(c.get("modules",{}))} modules</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

# ══════════════════════════════════════════════════════════════════════════
# GENERATE COURSE  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_generate():
    st.markdown('<div class="sec">🚀 Generate My Course</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Tell the AI what you want to learn — it builds the full course automatically</div>',unsafe_allow_html=True)
    st.markdown('<div class="sb"><div style="font-weight:700;font-size:.93rem;">📋 Step 1 — Enter Your Requirements</div></div>',unsafe_allow_html=True)
    cl,cr=st.columns(2)
    with cl:
        cn=st.text_input("1️⃣ Course Name *",placeholder="e.g., Introduction to Data Science",key="gc_cn")
        el=st.selectbox("2️⃣ Your Education Level",["Primary","High School","Diploma","Bachelors","Masters"],key="gc_el")
        dl=st.selectbox("3️⃣ Difficulty Level",["Beginner","Intermediate","Advanced"],key="gc_dl")
    with cr:
        nm=st.number_input("4️⃣ Number of Modules",1,15,4,key="gc_nm")
        dur=st.text_input("5️⃣ Course Duration",placeholder="e.g., 6 weeks",key="gc_dur")
        crd=st.text_input("6️⃣ Credits / Hours",placeholder="e.g., 3 credit hours",key="gc_crd")
    st.markdown("<br>",unsafe_allow_html=True)
    b1,b2=st.columns([2,1])
    with b1: gen=st.button("🤖 Generate Course Outline",use_container_width=True)
    with b2: rst=st.button("🔁 Reset",use_container_width=True)
    if rst:
        st.session_state.course_outline=None; st.session_state.gen_modules={}
        st.session_state.quiz_data={}; st.session_state.pdf_ready=False; st.session_state.pdf_b64=None; st.rerun()
    if gen:
        if not cn.strip(): st.error("⚠️ Please enter a Course Name."); st.stop()
        meta={"name":cn,"level":dl,"modules":nm,"duration":dur,"credit":crd,"audience":el}
        st.session_state.course_meta=meta
        PROMPTER=f"""You are Prompter, the world's best Prompt Engineer. Generate a comprehensive prompt for Tabler (a course outline tool) using ONLY these inputs:
1) Course Name: {cn}
2) Target Audience Edu Level: {el}
3) Course Difficulty Level: {dl}
4) No. of Modules: {nm}
5) Course Duration: {dur}
6) Course Credit: {crd}
Mention all 6 inputs explicitly. Verify course name is appropriate and not gibberish."""
        with st.spinner("🤖 Crafting smart prompt from your requirements..."):
            gp=call_llm(PROMPTER)
        with st.spinner("📚 Building course outline..."):
            outline=call_llm(TABLER_PROMPT,gp)
        st.session_state.course_outline=outline
        st.session_state.gen_modules={}; st.session_state.quiz_data={}
        st.session_state.pdf_ready=False; st.session_state.pdf_b64=None
        st.success("✅ Course outline generated!")

    if st.session_state.course_outline:
        meta=st.session_state.course_meta
        st.markdown(f"""<div class="cg">
            <div style="font-weight:700;font-size:.98rem;">📘 {meta.get('name','')}
                <span class="badge bp" style="margin-left:8px;">{meta.get('level','')}</span>
                <span class="badge bw" style="margin-left:5px;">{meta.get('duration','')}</span>
                <span class="badge bs" style="margin-left:5px;">{meta.get('audience','')}</span>
            </div>
            <div style="color:var(--muted);font-size:.78rem;margin-top:4px;">{meta.get('modules','')} modules · {meta.get('credit','')}</div>
        </div>""",unsafe_allow_html=True)
        with st.expander("📋 View Course Outline",expanded=True):
            st.write(st.session_state.course_outline)
        with st.expander("✏️ Need changes? Modify the outline"):
            mods=st.text_area("Describe changes:",placeholder="e.g., Add an ethics module, make module 2 more advanced...",height=80,key="mod_txt")
            if st.button("✅ Apply Modifications",key="apply_mods"):
                if mods.strip():
                    mp=f"Modify this course outline using the changes described and return the complete updated outline.\nChanges: {mods}\nCurrent outline: {st.session_state.course_outline}"
                    with st.spinner("✏️ Applying changes..."):
                        updated=call_llm(TABLER_PROMPT,mp)
                    st.session_state.course_outline=updated
                    st.session_state.gen_modules={}; st.session_state.quiz_data={}
                    st.success("✅ Outline updated!"); st.rerun()
        st.markdown("---")
        st.markdown('<div class="sb"><div style="font-weight:700;font-size:.93rem;">⚡ Step 2 — Auto-Generate Full Course (Modules + Quizzes + PDF)</div><div style="color:var(--muted);font-size:.79rem;margin-top:3px;">AI writes every lesson, generates 10 quiz questions per module, then bundles into a downloadable PDF.</div></div>',unsafe_allow_html=True)
        lbl="🔄 Re-Generate" if st.session_state.gen_modules else "🚀 Generate Full Course Now!"
        if st.button(lbl,use_container_width=True,key="run_gen"):
            run_generation(meta)
        if st.session_state.pdf_ready and st.session_state.pdf_b64:
            st.markdown("---")
            st.markdown('<div style="background:rgba(67,232,160,.08);border:1px solid rgba(67,232,160,.25);border-radius:12px;padding:13px 17px;margin-bottom:11px;"><span style="font-size:1.3rem;">📄</span><span style="font-weight:700;margin-left:9px;">Your course PDF is ready!</span></div>',unsafe_allow_html=True)
            d1,d2=st.columns(2)
            with d1:
                st.download_button("📥 Download Full Course PDF",data=st.session_state.pdf_b64,
                    file_name=f"{meta.get('name','course').replace(' ','_')}.pdf",mime="application/pdf",use_container_width=True)
            with d2:
                if st.button("📝 Go Take the Quiz!",use_container_width=True,key="goto_quiz"):
                    st.session_state.page="📝 Take Quiz"; st.rerun()

def run_generation(meta):
    cn=meta.get("name","Course")
    with st.spinner("📖 Extracting module structure..."):
        dr=call_llm(DICTATOR_PROMPT,st.session_state.course_outline)
        ml=None
        try: ml=json.loads(dr)
        except:
            m=re.search(r'\{.*\}',dr,re.DOTALL)
            if m:
                try: ml=json.loads(m.group())
                except: pass
        if not ml: st.error("❌ Could not parse module structure. Try regenerating."); st.stop()
    all_pdf=(f"COURSE: {cn}\nLevel: {meta.get('level','')} | Audience: {meta.get('audience','')} | Duration: {meta.get('duration','')} | Credits: {meta.get('credit','')}\n"+"="*60+"\n\n")
    st.session_state.gen_modules={}; st.session_state.quiz_data={}
    for mod,lessons in ml.items():
        st.markdown(f'<div class="mh"><div style="font-weight:700;font-size:.93rem;">📦 {mod}</div></div>',unsafe_allow_html=True)
        mc=""
        for les in lessons:
            lp=f"""You are Coursify, expert educational content creator.
Generate detailed lesson content for: '{les}' in module '{mod}', course '{cn}'.
Audience: {meta.get('audience','')} | Difficulty: {meta.get('level','')}
Follow Bloom's Taxonomy. Include:
1) Introduction and context
2) Key terms with definitions and analogies
3) Step-by-step explanations with real-world examples
4) Real-world applications and case studies
5) Reflective questions and exercises
6) Summary and key takeaways
Use Markdown. Be comprehensive and engaging."""
            with st.spinner(f"✍️ Writing: {les}..."):
                content=call_llm(lp)
            with st.expander(f"📄 {les}"): st.write(content)
            mc+=f"## {les}\n\n{content}\n\n---\n\n"
        with st.spinner(f"🧪 Generating quiz for {mod}..."):
            qr=call_llm(QUIZZY_PROMPT+mc)
        st.session_state.quiz_data[mod]=qr
        st.session_state.gen_modules[mod]=mc
        qs=parse_quiz(qr)
        st.success(f"✅ {mod} — {len(lessons)} lessons + {len(qs)} quiz questions")
        with st.expander(f"📝 Quiz preview: {mod}"): st.write(qr)
        all_pdf+=f"# {mod}\n\n{mc}\n\n## Quiz — {mod}\n\n{qr}\n\n"+"="*60+"\n\n"
    with st.spinner("📄 Building PDF..."):
        pdf=make_pdf(all_pdf)
        b64=base64.b64encode(pdf.output(dest="S").encode('latin1')).decode()
        st.session_state.pdf_b64=b64; st.session_state.pdf_ready=True
    rec={"name":cn,"meta":meta,"outline":st.session_state.course_outline,"modules":st.session_state.gen_modules,"quizzes":st.session_state.quiz_data,"created_by":st.session_state.current_user,"created_date":str(datetime.date.today())}
    courses=[c for c in get_courses() if not(c.get("created_by")==st.session_state.current_user and c.get("name")==cn)]
    courses.append(rec); save_courses(courses)
    st.success("🎉 Full course generated and published!"); st.balloons()
    
    save_courses(courses)
    st.success("🎉 Full course generated and published!")
    st.balloons()
    st.rerun()   # <— ensures dashboard reloads with updated courses

# ══════════════════════════════════════════════════════════════════════════
# MY MODULES  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_modules():
    st.markdown('<div class="sec">📦 My Modules</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Browse your course modules and content</div>',unsafe_allow_html=True)
    courses=get_courses()
    if not st.session_state.gen_modules and not courses:
        st.markdown('<div class="card" style="text-align:center;padding:40px;"><div style="font-size:2.3rem;">📭</div><div style="font-weight:700;margin:9px 0 5px;">No Modules Yet</div><div style="color:var(--muted);font-size:.83rem;">Generate a course to see modules here.</div></div>',unsafe_allow_html=True)
        if st.button("🚀 Generate a Course"): st.session_state.page="🚀 Generate Course"; st.rerun()
        return
    if courses:
        names=[f"📘 {c.get('name','')}  (by {c.get('created_by','?')} · {c.get('created_date','')})" for c in courses]
        ch=st.selectbox("📚 Load a course:",["(Use current session)"] + names)
        if ch!="(Use current session)" and st.button("📂 Load This Course",key="load_c"):
            idx=names.index(ch); c=courses[idx]
            st.session_state.gen_modules=c.get("modules",{}); st.session_state.quiz_data=c.get("quizzes",{})
            st.session_state.course_outline=c.get("outline"); st.session_state.course_meta=c.get("meta",{})
            st.session_state.pdf_ready=False; st.success(f"Loaded: {c.get('name')}"); st.rerun()
    if not st.session_state.gen_modules: st.info("Generate a course or load one above."); return
    meta=st.session_state.course_meta
    st.markdown(f"""<div class="cg"><div style="font-weight:700;font-size:.96rem;">📘 {meta.get('name','Current Course')}</div>
        <div style="color:var(--muted);font-size:.78rem;margin-top:4px;">{meta.get('level','')} · {meta.get('audience','')} · {meta.get('duration','')}</div></div>""",unsafe_allow_html=True)
    for mod,content in st.session_state.gen_modules.items():
        qc=len(parse_quiz(st.session_state.quiz_data.get(mod,"")))
        with st.expander(f"📦 {mod}  ·  📝 {qc} quiz questions"):
            st.markdown(content[:4000]+"\n\n*[Truncated — download PDF for full]*" if len(content)>4000 else content)
            if st.button(f"📝 Take Quiz for this Module",key=f"mq_{mod}"):
                st.session_state.active_quiz=mod; st.session_state.quiz_answers={}; st.session_state.quiz_score=None
                st.session_state.page="📝 Take Quiz"; st.rerun()
    if st.session_state.pdf_ready and st.session_state.pdf_b64:
        st.markdown("---")
        st.download_button("📥 Download Full Course PDF",data=st.session_state.pdf_b64,
            file_name=f"{meta.get('name','course').replace(' ','_')}.pdf",mime="application/pdf")

# ══════════════════════════════════════════════════════════════════════════
# TAKE QUIZ  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_quiz():
    st.markdown('<div class="sec">📝 Take Quiz</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Test your knowledge with AI-generated questions</div>',unsafe_allow_html=True)
    qd=st.session_state.quiz_data
    if not qd:
        courses=get_courses()
        if courses:
            st.info("Load a course to take its quiz:")
            for i,c in enumerate(courses):
                if st.button(f"📘 Load: {c.get('name','')}",key=f"lq_{i}"):
                    st.session_state.gen_modules=c.get("modules",{}); st.session_state.quiz_data=c.get("quizzes",{})
                    st.session_state.course_meta=c.get("meta",{}); st.rerun()
        else:
            st.info("No quizzes available. Generate a course first.")
            if st.button("🚀 Generate Course"): st.session_state.page="🚀 Generate Course"; st.rerun()
        return
    mods=list(qd.keys())
    active=st.session_state.active_quiz or mods[0]
    if active not in mods: active=mods[0]
    sel=st.selectbox("Select Module",mods,index=mods.index(active))
    if sel!=st.session_state.active_quiz:
        st.session_state.active_quiz=sel; st.session_state.quiz_answers={}; st.session_state.quiz_score=None
    qs=parse_quiz(qd[sel])
    if not qs: st.warning("Could not parse quiz."); st.text(qd[sel]); return
    st.markdown(f'<div class="cg" style="margin-bottom:16px;"><div style="font-weight:700;">📝 {sel}</div><div style="color:var(--muted);font-size:.8rem;margin-top:3px;">{len(qs)} questions · Multiple choice · Instant scoring</div></div>',unsafe_allow_html=True)
    ans=st.session_state.quiz_answers
    done=st.session_state.quiz_score is not None
    for i,q in enumerate(qs):
        st.markdown(f'<div style="font-weight:600;margin:16px 0 7px;font-size:.9rem;">Q{i+1}. {q["question"]}</div>',unsafe_allow_html=True)
        opts=q["options"]
        if done:
            ua=ans.get(i,"")
            for k,v in opts.items():
                ir=k==q["answer"]; iu=k==ua
                bg="rgba(67,232,160,.15)" if ir else ("rgba(255,101,132,.15)" if iu else "transparent")
                bc="#43E8A0" if ir else ("#FF6584" if iu else "var(--border)")
                ic="✅" if ir else ("❌" if iu else "○")
                st.markdown(f'<div style="background:{bg};border:2px solid {bc};border-radius:10px;padding:10px 14px;margin:4px 0;font-size:.86rem;">{ic} {k}) {v}</div>',unsafe_allow_html=True)
            if q.get("explanation"):
                st.markdown(f'<div style="background:rgba(67,232,200,.07);border-left:3px solid var(--acc);padding:8px 12px;border-radius:0 8px 8px 0;margin-top:4px;font-size:.8rem;color:var(--muted);">💡 {q["explanation"]}</div>',unsafe_allow_html=True)
        else:
            ol=[f"{k}) {v}" for k,v in opts.items()]
            ch=st.radio("",ol,key=f"q_{sel}_{i}",label_visibility="collapsed")
            if ch: ans[i]=ch[0]
    st.session_state.quiz_answers=ans
    if not done:
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("🎯 Submit Answers",use_container_width=True):
            sc=sum(1 for i,q in enumerate(qs) if ans.get(i)==q["answer"])
            st.session_state.quiz_score=sc
            add_qh(st.session_state.current_user,sel,sc,len(qs)); st.rerun()
    else:
        sc=st.session_state.quiz_score; tot=len(qs); pct=round(sc/tot*100)
        c="var(--ok)" if pct>=70 else "var(--warn)" if pct>=50 else "var(--sec)"
        g="Excellent! 🏆" if pct>=90 else "Great Job! 🎉" if pct>=70 else "Keep Practicing! 💪"
        st.markdown(f"""<div style="text-align:center;padding:26px;background:var(--card);border-radius:16px;border:2px solid {c};margin:18px 0;">
            <div style="font-family:'Sora',sans-serif;font-size:2.3rem;font-weight:800;color:{c};">{pct}%</div>
            <div style="font-weight:700;font-size:.98rem;margin:5px 0;">{g}</div>
            <div style="color:var(--muted);">{sc} / {tot} correct</div>
        </div>""",unsafe_allow_html=True)
        if st.button("🔄 Retake Quiz",use_container_width=True):
            st.session_state.quiz_answers={}; st.session_state.quiz_score=None; st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# AI TUTOR  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_tutor():
    st.markdown('<div class="sec">💬 AI Tutor</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Ask anything — your AI tutor is always here</div>',unsafe_allow_html=True)
    meta=st.session_state.course_meta
    ctx=f"Current course: {meta.get('name','')}" if meta.get("name") else "General learning assistant"
    cc,cs=st.columns([3,1])
    with cs:
        st.markdown(f'<div class="card"><div style="font-size:.76rem;color:var(--muted);margin-bottom:5px;">CONTEXT</div><div style="font-size:.8rem;font-weight:600;">{ctx}</div></div>',unsafe_allow_html=True)
        st.markdown('<div style="font-size:.76rem;color:var(--muted);margin-bottom:7px;">QUICK PROMPTS</div>',unsafe_allow_html=True)
        for s in ["Explain key concepts","Give a real example","Summarize my learning","What to study next?","Quiz me!"]:
            if st.button(s,key=f"qp_{s}",use_container_width=True): _chat(s); st.rerun()
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("🗑️ Clear",use_container_width=True): st.session_state.chat_history=[]; st.rerun()
    with cc:
        if not st.session_state.chat_history:
            st.markdown('<div style="text-align:center;padding:40px;color:var(--muted);"><div style="font-size:2.3rem;margin-bottom:9px;">🤖</div><div style="font-weight:600;margin-bottom:4px;">Your AI Tutor is Ready!</div><div style="font-size:.81rem;">Ask anything about your course or any topic.</div></div>',unsafe_allow_html=True)
        else:
            for msg in st.session_state.chat_history:
                cls="umsg" if msg["role"]=="user" else "cmsg"
                who="YOU" if msg["role"]=="user" else "🤖 TUTOR"
                wc="var(--pl)" if msg["role"]=="user" else "var(--acc)"
                st.markdown(f'<div class="{cls}"><div style="font-size:.7rem;color:{wc};margin-bottom:3px;font-weight:600;">{who}</div><div style="font-size:.86rem;">{msg["content"]}</div></div>',unsafe_allow_html=True)
        prompt=st.chat_input("Ask your AI tutor anything...")
        if prompt: _chat(prompt); st.rerun()

def _chat(prompt):
    st.session_state.chat_history.append({"role":"user","content":prompt})
    meta=st.session_state.course_meta
    sys=f"""You are an expert AI tutor. {('Course: '+meta.get('name','')) if meta.get('name') else 'General learning assistant'}.
Be helpful, clear, encouraging, educational. Use examples."""
    msgs=[{"role":"system","content":sys}]+st.session_state.chat_history[-12:]
    try:
        r=client.chat.completions.create(model=MODEL,messages=msgs,max_tokens=1024)
        reply=r.choices[0].message.content
    except Exception as e: reply=f"Error: {e}"
    st.session_state.chat_history.append({"role":"assistant","content":reply})

# ══════════════════════════════════════════════════════════════════════════
# PROGRESS  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_progress():
    st.markdown('<div class="sec">📊 My Progress</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Track your learning journey</div>',unsafe_allow_html=True)
    qh=get_qh(st.session_state.current_user)
    if not qh:
        st.markdown('<div class="card" style="text-align:center;padding:40px;"><div style="font-size:2.3rem;">📊</div><div style="font-weight:700;margin:9px 0 5px;">No Data Yet</div><div style="color:var(--muted);font-size:.83rem;">Take some quizzes to track progress!</div></div>',unsafe_allow_html=True); return
    scores=[q['pct'] for q in qh]
    avg=round(sum(scores)/len(scores)); best=max(scores)
    s1,s2,s3,s4=st.columns(4)
    for col,(v,l,c) in zip([s1,s2,s3,s4],[(f"{avg}%","Average","var(--primary)"),(f"{best}%","Best Score","var(--ok)"),(str(len(qh)),"Quizzes Done","var(--acc)"),(str(sum(q['total'] for q in qh)),"Total Questions","var(--warn)")]):
        with col: st.markdown(f'<div class="stat"><div class="stn" style="color:{c};">{v}</div><div class="stl">{l}</div></div>',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    for q in reversed(qh):
        c="#43E8A0" if q['pct']>=70 else "#FFB347" if q['pct']>=50 else "#FF6584"
        st.markdown(f"""<div class="card" style="padding:13px 17px;margin-bottom:7px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div><div style="font-weight:600;font-size:.86rem;">📝 {q['module']}</div>
                <div style="color:var(--muted);font-size:.74rem;">{q['date']} · {q['score']}/{q['total']}</div></div>
                <div style="font-family:'Sora',sans-serif;font-size:1.25rem;font-weight:800;color:{c};">{q['pct']}%</div>
            </div>
            <div style="background:var(--card2);border-radius:8px;height:5px;overflow:hidden;">
                <div style="width:{q['pct']}%;height:100%;background:{c};border-radius:8px;"></div>
            </div></div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# FEEDBACK  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_feedback():
    st.markdown('<div class="sec">💬 Feedback</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Share your experience and help us improve</div>',unsafe_allow_html=True)
    u=get_users().get(st.session_state.current_user,{})
    with st.form("fb"):
        rating=st.select_slider("Rate your experience:",options=[1,2,3,4,5],value=5,format_func=lambda x:"⭐"*x)
        msg=st.text_area("Your feedback *",placeholder="Tell us what you think...",height=110)
        if st.form_submit_button("📨 Submit Feedback",use_container_width=True):
            if msg.strip(): add_fb(st.session_state.current_user,u.get("name",""),msg,rating); st.success("✅ Thank you for your feedback!")
            else: st.error("Please write your feedback.")
    fb=[f for f in get_fb() if f.get("user")==st.session_state.current_user]
    if fb:
        st.markdown("---")
        st.markdown('<div style="font-weight:700;margin-bottom:9px;">Your Previous Feedback</div>',unsafe_allow_html=True)
        for f in reversed(fb[-3:]):
            st.markdown(f'<div class="card" style="padding:13px 17px;"><div style="display:flex;justify-content:space-between;"><span style="color:var(--muted);font-size:.78rem;">{f.get("date","")}</span><span>{"⭐"*f.get("rating",5)}</span></div><div style="font-size:.86rem;margin-top:6px;">{f.get("message","")}</div></div>',unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# PROFILE  ← ALL USERS
# ══════════════════════════════════════════════════════════════════════════
def page_profile():
    st.markdown('<div class="sec">👤 My Profile</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Manage your account</div>',unsafe_allow_html=True)
    users=get_users(); u=users.get(st.session_state.current_user,{})
    avs=["🧑‍🎓","👨‍💻","👩‍🏫","🧑‍🔬","👨‍🎨","🦸","🧙","🧑‍💼","👩‍💻","🧑‍🚀"]
    ca,cf=st.columns([1,2.5])
    with ca:
        st.markdown(f'<div class="card" style="text-align:center;padding:20px;"><div style="font-size:3.2rem;margin-bottom:9px;">{u.get("avatar","🧑‍🎓")}</div><div style="font-weight:700;">{u.get("name","")}</div><div style="color:var(--muted);font-size:.76rem;">{st.session_state.user_role.capitalize()}</div><div style="color:var(--muted);font-size:.71rem;margin-top:2px;">Joined {u.get("joined","")}</div></div>',unsafe_allow_html=True)
        av=st.selectbox("Avatar",avs,index=avs.index(u.get("avatar","🧑‍🎓")) if u.get("avatar") in avs else 0)
    with cf:
        with st.form("prof"):
            nn=st.text_input("Full Name",value=u.get("name",""))
            ne=st.text_input("Email",value=u.get("email",""))
            nb=st.text_area("Bio",value=u.get("bio",""),placeholder="Tell us about yourself...",height=85)
            np=st.text_input("New Password (blank=keep)",type="password")
            if st.form_submit_button("💾 Save",use_container_width=True):
                users[st.session_state.current_user].update({"name":nn,"email":ne,"bio":nb,"avatar":av})
                if np: users[st.session_state.current_user]["password"]=np
                save_users(users); st.success("✅ Saved!"); st.rerun()
    qh=get_qh(st.session_state.current_user); avg=round(sum(q['pct'] for q in qh)/len(qh)) if qh else 0
    st.markdown("<br>",unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    for col,(v,l,c) in zip([c1,c2,c3],[(str(len(qh)),"Quizzes Taken","var(--primary)"),(f"{avg}%","Avg Score","var(--ok)"),(str(len(get_courses())),"Courses Available","var(--warn)")]):
        with col: st.markdown(f'<div class="stat"><div class="stn" style="color:{c};">{v}</div><div class="stl">{l}</div></div>',unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════
def page_admin():
    st.markdown('<div class="sec">👑 Admin Panel</div>',unsafe_allow_html=True)
    users=get_users(); courses=get_courses(); fb=get_fb()
    all_qh=[q for un in users for q in get_qh(un)]
    s1,s2,s3,s4=st.columns(4)
    for col,(v,l,c) in zip([s1,s2,s3,s4],[(str(len(users)),"Total Users","var(--primary)"),(str(len(courses)),"Courses Created","var(--acc)"),(str(len(all_qh)),"Quiz Attempts","var(--warn)"),(str(len(fb)),"Feedback","var(--ok)")]):
        with col: st.markdown(f'<div class="stat"><div class="stn" style="color:{c};">{v}</div><div class="stl">{l}</div></div>',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    st.markdown('<div class="cg"><div style="font-weight:700;">Platform Health</div><div style="color:var(--muted);font-size:.8rem;margin-top:4px;">All systems operational · AI model active</div></div>',unsafe_allow_html=True)
    if courses:
        st.markdown('<div style="font-weight:700;margin:14px 0 9px;">Recently Created Courses</div>',unsafe_allow_html=True)
        for c in reversed(courses[-5:]):
            st.markdown(f'<div class="card" style="padding:12px 16px;"><div style="font-weight:600;font-size:.88rem;">📘 {c.get("name","")}</div><div style="color:var(--muted);font-size:.76rem;">by {c.get("created_by","?")} · {c.get("created_date","")} · {len(c.get("modules",{}))} modules</div></div>',unsafe_allow_html=True)

def page_manage_users():
    st.markdown('<div class="sec">👥 Manage Users</div>',unsafe_allow_html=True)
    st.markdown('<div class="sub">Add, edit or remove user accounts</div>',unsafe_allow_html=True)
    users=get_users()
    with st.expander("➕ Add New User"):
        with st.form("add_u"):
            a1,a2=st.columns(2)
            with a1: nn=st.text_input("Full Name"); ne=st.text_input("Email"); nu=st.text_input("Username")
            with a2: np=st.text_input("Password",type="password"); nr=st.selectbox("Role",["user","admin"])
            if st.form_submit_button("✅ Create User",use_container_width=True):
                if all([nn,ne,nu,np]):
                    ok,msg=register(nu,np,nn,ne,nr)
                    st.success(msg) if ok else st.error(msg); st.rerun()
                else: st.error("Fill all fields.")
    st.markdown(f"---\n**{len(users)} registered users:**")
    for un,ud in users.items():
        qh=get_qh(un); avg=round(sum(q['pct'] for q in qh)/len(qh)) if qh else 0
        c="#43E8A0" if avg>=70 else "#FFB347" if avg>=50 else "#7B80A0"
        ci,ca2=st.columns([3,1])
        with ci:
            rb=f'<span class="badge br">Admin</span>' if ud.get("role")=="admin" else f'<span class="badge bp">User</span>'
            st.markdown(f"""<div class="card" style="padding:13px 17px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="display:flex;align-items:center;gap:11px;">
                        <div style="font-size:1.7rem;">{ud.get('avatar','🧑‍🎓')}</div>
                        <div><div style="font-weight:700;font-size:.88rem;">{ud.get('name','')} {rb}</div>
                        <div style="color:var(--muted);font-size:.74rem;">{un} · {ud.get('email','')} · {ud.get('joined','')}</div></div>
                    </div>
                    <div style="text-align:right;"><div style="font-family:'Sora',sans-serif;font-size:1.15rem;font-weight:800;color:{c};">{avg}%</div>
                    <div style="color:var(--muted);font-size:.72rem;">{len(qh)} quizzes</div></div>
                </div></div>""",unsafe_allow_html=True)
        with ca2:
            st.markdown("<br>",unsafe_allow_html=True)
            if un!=st.session_state.current_user:
                if st.button("🗑️ Delete",key=f"del_{un}",use_container_width=True):
                    del users[un]; save_users(users); st.success(f"Deleted {un}"); st.rerun()
            nr2="user" if ud.get("role")=="admin" else "admin"
            if st.button(f"→ {nr2.capitalize()}",key=f"role_{un}",use_container_width=True):
                users[un]["role"]=nr2; save_users(users); st.rerun()

def page_all_performance():
    st.markdown('<div class="sec">📈 All Performance</div>',unsafe_allow_html=True)
    users=get_users()
    for un,ud in users.items():
        qh=get_qh(un); avg=round(sum(q['pct'] for q in qh)/len(qh)) if qh else 0; best=max((q['pct'] for q in qh),default=0)
        c="#43E8A0" if avg>=70 else "#FFB347" if avg>=50 else "#7B80A0"
        with st.expander(f"{ud.get('avatar','🧑‍🎓')} {ud.get('name',un)}  ·  Avg: {avg}%  ·  {len(qh)} quizzes"):
            if not qh: st.markdown('<div style="color:var(--muted);font-size:.83rem;">No activity yet.</div>',unsafe_allow_html=True)
            else:
                sm1,sm2,sm3=st.columns(3)
                for col,(v,l,cl) in zip([sm1,sm2,sm3],[(f"{avg}%","Average",c),(f"{best}%","Best","var(--ok)"),(str(len(qh)),"Quizzes","var(--primary)")]):
                    with col: st.markdown(f'<div class="stat"><div class="stn" style="color:{cl};">{v}</div><div class="stl">{l}</div></div>',unsafe_allow_html=True)
                st.markdown("<br>",unsafe_allow_html=True)
                for q in reversed(qh[-6:]):
                    qc="#43E8A0" if q['pct']>=70 else "#FFB347" if q['pct']>=50 else "#FF6584"
                    st.markdown(f'<div style="display:flex;justify-content:space-between;padding:7px 11px;background:var(--card2);border-radius:8px;margin:3px 0;font-size:.8rem;"><span>📝 {q["module"]} · {q["date"]}</span><span style="font-weight:700;color:{qc};">{q["pct"]}% ({q["score"]}/{q["total"]})</span></div>',unsafe_allow_html=True)

def page_all_feedback():
    st.markdown('<div class="sec">💌 All Feedback</div>',unsafe_allow_html=True)
    fb=get_fb()
    if not fb: st.info("No feedback yet."); return
    avg_r=round(sum(f.get('rating',5) for f in fb)/len(fb),1)
    f1,f2,f3=st.columns(3)
    for col,(v,l,c) in zip([f1,f2,f3],[(str(len(fb)),"Total","var(--primary)"),(f"{avg_r}/5","Avg Rating","var(--warn)"),(str(len([f for f in fb if f.get('rating',5)>=4])),"Positive","var(--ok)")]):
        with col: st.markdown(f'<div class="stat"><div class="stn" style="color:{c};">{v}</div><div class="stl">{l}</div></div>',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    for f in reversed(fb):
        st.markdown(f"""<div class="card" style="padding:13px 17px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
                <div style="font-weight:600;font-size:.86rem;">{f.get('name','User')} <span style="color:var(--muted);font-weight:400;">@{f.get('user','')}</span></div>
                <div style="display:flex;gap:9px;align-items:center;"><span>{"⭐"*f.get('rating',5)}</span><span style="color:var(--muted);font-size:.74rem;">{f.get('date','')}</span></div>
            </div>
            <div style="font-size:.84rem;">{f.get('message','')}</div>
        </div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    page_auth()
else:
    sidebar()
    p=st.session_state.page; r=st.session_state.user_role
    if   p=="🏠 Dashboard":       page_dashboard()
    elif p=="🚀 Generate Course":  page_generate()
    elif p=="📦 My Modules":       page_modules()
    elif p=="📝 Take Quiz":        page_quiz()
    elif p=="💬 AI Tutor":         page_tutor()
    elif p=="📊 My Progress":      page_progress()
    elif p=="💬 Feedback":         page_feedback()
    elif p=="👤 Profile":          page_profile()
    elif p=="👑 Admin Panel"  and r=="admin": page_admin()
    elif p=="👥 Manage Users" and r=="admin": page_manage_users()
    elif p=="📈 All Performance" and r=="admin": page_all_performance()
    elif p=="💌 All Feedback" and r=="admin": page_all_feedback()
    else: page_dashboard()