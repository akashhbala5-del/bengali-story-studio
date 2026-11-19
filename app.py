import streamlit as st
import requests, json, re, io, zipfile
from datetime import datetime


st.set_page_config(page_title="Bengali Story Studio", page_icon="🎬", layout="wide")

STAGES = [
    ("idea", "01 · Story Ideas", "Create original story concepts and select one."),
    ("outline", "02 · Story Architect", "Build the plot, clue chain, escalation, reveal and ending."),
    ("script", "03 · Bengali Scriptwriter", "Write the narration and dialogue in natural Bengali."),
    ("script_review", "04 · Script Critic", "Review logic, continuity, pacing, language and suspense."),
    ("scene_breakdown", "05 · Film Director", "Turn the approved script into scenes and shots."),
    ("visual_bible", "06 · Visual Continuity", "Lock characters, locations, props and reusable visual prompts."),
    ("audio_plan", "07 · Audio Producer", "Plan Bengali voice delivery, ambience, music and sound effects."),
    ("edit_plan", "08 · Video Editor", "Create timeline, subtitle and assembly instructions."),
    ("qc", "09 · Quality Control", "Check story, language, continuity, audio, export and rights."),
    ("youtube_pack", "10 · YouTube Packaging", "Titles, thumbnails, description, tags, pinned comment and Shorts."),
    ("analytics", "11 · Analytics & Learning", "Analyze metrics and turn findings into next-episode experiments."),
]
PROMPTS = {
"idea": "You are a Bengali YouTube supernatural mystery/horror story ideation agent. Generate 8 original concepts in natural West Bengal Bengali. For each: title, premise, 20-second hook, central mystery, twist, visual potential, estimated runtime. Avoid clichés and ensure production with narrated visuals is feasible. Score originality, curiosity, visual potential and audience fit 1-5. Recommend a shortlist.",
"outline": "You are a story architect for cinematic Bengali supernatural mystery. Based on the chosen concept, create a detailed 8-12 minute outline: hook, protagonist, setting, mystery rules, clue sequence, escalating incidents, midpoint, reveal, climax, ending, unresolved question if appropriate. Internal logic must hold; foreshadow fairly. Write in Bengali.",
"script": "You are a professional Bengali screenwriter. Write a production-ready 8-12 minute narration script based on the approved outline. Use natural West Bengal Bengali, oral storytelling rhythm, suspense, restrained dialogue and intentional pauses. Include [visual] and [sound] cues sparingly. Avoid filler/repetition. Output narration first, then voice/pronunciation notes.",
"script_review": "Act as a strict Bengali story editor. Review hook, logic, continuity, pacing, repetitiveness, natural spoken Bengali, pronunciation, motivations, clue fairness and ending. Rank issues by severity. Give improved passages or a revised script only where worthwhile. End with PASS/REVISE and reasons.",
"scene_breakdown": "Act as film director and storyboard supervisor. Convert approved script to scene/shot breakdown. Suggested cuts every 5-12 seconds where useful. Table columns: Scene ID, estimated time, narration excerpt, visual action, characters, location, shot size, angle, motion (Ken Burns/parallax), lighting, image prompt, transition, sound cue. Cinematic 16:9 continuity.",
"visual_bible": "Act as visual continuity designer. Build character sheets (age, facial traits, hair, clothing, body language, palette, continuity rules), locations, props, motifs and reusable image prompt templates. Bengali setting, cinematic realism, 16:9. Add negative prompts to prevent face/clothing drift, extra limbs, text, logos, watermarks and artifacts.",
"audio_plan": "Act as sound designer for Bengali suspense. Create a cue sheet by scene/time with narration emotion/speed/pause, ambience, music texture, SFX, cue in/out, intensity. Specify natural West Bengal Bengali voice direction. Narration must be foreground; audio must not overpower it. Include licensing reminders.",
"edit_plan": "Act as video editor/post supervisor. Create an edit blueprint with timeline, duration, filenames, image motion, transitions, subtitle placement, audio cues, pacing and export settings for an 8-12 minute narrated YouTube story. Provide repeatable file naming.",
"qc": "Act as release quality-control lead. Checklist: story, Bengali language, continuity, visual quality, audio, subtitles, editing, export, copyright/license, YouTube metadata and audience settings. Mark PASS/FAIL/NEEDS REVIEW. Do not claim to inspect a rendered video unless it was provided. Give release recommendation and blockers.",
"youtube_pack": "Act as YouTube packaging editor for Bengali supernatural storytelling. Generate 5 compelling but honest title options, 2 thumbnail concepts with short Bengali text, Bengali description, search phrases, hashtags, pinned comment, playlist suggestion and 3 Shorts concepts with hook/end. No keyword stuffing.",
"analytics": "Act as YouTube analyst. Analyze metrics/comments supplied. Separate evidence from hypotheses. Diagnose packaging, hook, retention, pacing and satisfaction. Give 5 next-episode experiments and a learning log: repeat/stop/test. If metrics absent, provide a collection template instead of inventing results."
}

def blank_project(title="Untitled Episode"):
    now = datetime.now().isoformat(timespec="seconds")
    return {"episode_id":"EP01", "name":title, "created":now, "updated":now, "genre":"Bengali supernatural mystery / horror", "runtime":"8–12 minutes", "language":"Natural West Bengal Bengali", "style":"Cinematic realism, atmospheric, suspense, 16:9", "notes":"", "metrics":"", "approved":{}, "drafts":{}, "status":{k:"Not Started" for k,_,_ in STAGES}}

def project_json(project):
    project["updated"] = datetime.now().isoformat(timespec="seconds")
    return json.dumps(project, ensure_ascii=False, indent=2)

def make_pack(project):
    lines=[f"# {project.get('episode_id','EP')} — {project.get('name','Episode')}", "", f"**Genre:** {project.get('genre')}  ", f"**Runtime:** {project.get('runtime')}  ", f"**Language:** {project.get('language')}  ", f"**Visual style:** {project.get('style')}", "", "## Creator notes", project.get("notes", "")]
    for key,title,_ in STAGES:
        content=project.get("approved",{}).get(key) or project.get("drafts",{}).get(key)
        if content: lines.extend(["",f"## {title}","",content])
    return "\n".join(lines)

def generate_cloud(prompt, context, endpoint, model, api_key):
    endpoint=endpoint.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    payload={"model":model,"temperature":0.75,"messages":[
        {"role":"system","content":prompt+"\n\nUse approved outputs as source of truth. Preserve continuity. Do not invent production approvals or metrics."},
        {"role":"user","content":context}
    ]}
    response=requests.post(endpoint,headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json=payload,timeout=180)
    response.raise_for_status()
    data=response.json()
    return data["choices"][0]["message"]["content"]

def stage_context(project, stage_key):
    base=[f"EPISODE ID: {project.get('episode_id')}",f"TITLE: {project.get('name')}",f"GENRE: {project.get('genre')}",f"TARGET RUNTIME: {project.get('runtime')}",f"LANGUAGE: {project.get('language')}",f"VISUAL STYLE: {project.get('style')}",f"CREATOR NOTES: {project.get('notes','')}"]
    approved=[]
    for key,title,_ in STAGES:
        if key==stage_key: break
        val=project.get("approved",{}).get(key)
        if val: approved.append(f"\n--- APPROVED {title} ---\n{val}")
    if approved: base.append("APPROVED PREVIOUS STAGES:\n"+"\n".join(approved))
    if stage_key=="analytics" and project.get("metrics"): base.append("METRICS / COMMENTS:\n"+project["metrics"])
    return "\n\n".join(base)


st.markdown("<style> .block-container{padding-top:1rem;padding-bottom:2rem;max-width:1100px} div[data-testid='stMetric']{padding:.6rem;border-radius:12px;background:rgba(120,120,120,.08)} </style>",unsafe_allow_html=True)
st.title("🎬 Bengali Story Studio")
st.caption("Cloud-ready AI storytelling workspace · mobile-friendly · approval-based production")

if "project" not in st.session_state: st.session_state.project=blank_project()
if "stage_editor" not in st.session_state: st.session_state.stage_editor={}
project=st.session_state.project

with st.sidebar:
    st.subheader("☁️ AI connection")
    # Secrets are optional; key can be entered in this session or configured in Streamlit secrets.
    secret_key=""
    try: secret_key=st.secrets.get("AI_API_KEY","")
    except Exception: pass
    api_key=st.text_input("API key",value=secret_key,type="password",help="Recommended: add AI_API_KEY in Streamlit Cloud → App settings → Secrets.")
    endpoint=st.text_input("OpenAI-compatible API URL",value="https://api.groq.com/openai/v1",help="Compatible hosted API base URL")
    model=st.text_input("Model",value="llama-3.3-70b-versatile",help="Model availability depends on your provider.")
    st.caption("The API key is used for generation and is not saved in the episode project file.")
    st.divider()
    st.subheader("📁 Episode")
    if st.button("＋ New episode",use_container_width=True):
        st.session_state.project=blank_project(f"Episode {datetime.now().strftime('%Y%m%d-%H%M')}")
        st.session_state.stage_editor={}
        st.rerun()
    uploaded=st.file_uploader("Restore episode JSON",type=["json"],key="restore_project")
    if uploaded:
        try:
            restored=json.loads(uploaded.getvalue().decode("utf-8"))
            if st.button("Load uploaded project",use_container_width=True):
                st.session_state.project=restored; st.session_state.stage_editor={}; st.rerun()
        except Exception as e: st.error(f"Invalid project JSON: {e}")

project=st.session_state.project
with st.expander("Episode setup",expanded=False):
    a,b=st.columns(2)
    project["episode_id"]=a.text_input("Episode ID",project.get("episode_id","EP01"))
    project["name"]=b.text_input("Episode title",project.get("name","Untitled Episode"))
    a,b=st.columns(2)
    project["genre"]=a.text_input("Genre",project.get("genre",""))
    project["runtime"]=b.text_input("Target runtime",project.get("runtime","8–12 minutes"))
    a,b=st.columns(2)
    project["language"]=a.text_input("Language",project.get("language","Natural West Bengal Bengali"))
    project["style"]=b.text_input("Visual style",project.get("style","Cinematic realism, 16:9"))
    project["notes"]=st.text_area("Creator notes / continuity rules",project.get("notes",""),height=100)

n_approved=sum(bool(project.get("approved",{}).get(k)) for k,_,_ in STAGES)
st.progress(n_approved/len(STAGES),text=f"{n_approved} of {len(STAGES)} stages approved")
with st.expander("Workflow status",expanded=False):
    for k,title,desc in STAGES:
        status="Approved" if project.get("approved",{}).get(k) else project.get("status",{}).get(k,"Not Started")
        st.write(f"**{title}** · {status}")

stage_labels=[f"{name} — {desc}" for _,name,desc in STAGES]
selected=st.selectbox("Choose agent stage",stage_labels)
idx=stage_labels.index(selected); key,name,desc=STAGES[idx]
st.markdown(f"### {name}")
st.caption(desc)
if key=="analytics": project["metrics"]=st.text_area("Paste analytics, audience comments, CTR, retention etc.",project.get("metrics",""),height=140)
current=project.get("approved",{}).get(key) or project.get("drafts",{}).get(key,"")
col1,col2=st.columns([1,1])
with col1:
    if st.button("✨ Generate draft",type="primary",use_container_width=True):
        if not api_key.strip(): st.error("Enter an API key or add AI_API_KEY in Streamlit Cloud Secrets.")
        else:
            try:
                with st.spinner("AI agent is working…"):
                    output=generate_cloud(PROMPTS[key],stage_context(project,key),endpoint,model,api_key.strip())
                project.setdefault("drafts",{})[key]=output
                project.setdefault("status",{})[key]="In Progress"
                st.session_state.stage_editor[key]=output
                st.rerun()
            except Exception as ex: st.error(f"Generation failed: {ex}")
with col2:
    if st.button("Clear this stage draft",use_container_width=True):
        project.setdefault("drafts",{}).pop(key,None); project.setdefault("approved",{}).pop(key,None)
        project.setdefault("status",{})[key]="Not Started"; st.session_state.stage_editor.pop(key,None); st.rerun()
editor_val=st.session_state.stage_editor.get(key,current)
edited=st.text_area("Edit and review the output before approval",value=editor_val,height=420,key=f"edit_{key}")
project.setdefault("drafts",{})[key]=edited
c1,c2,c3=st.columns(3)
with c1:
    if st.button("✅ Approve stage",type="primary",use_container_width=True,disabled=not edited.strip()):
        project.setdefault("approved",{})[key]=edited; project.setdefault("drafts",{})[key]=edited
        project.setdefault("status",{})[key]="Approved"; st.session_state.stage_editor[key]=edited
        st.success("Stage approved. Later agents can use this output."); st.rerun()
with c2:
    if st.button("🟡 Mark review",use_container_width=True): project.setdefault("status",{})[key]="Review"; st.rerun()
with c3:
    if st.button("⛔ Block stage",use_container_width=True): project.setdefault("status",{})[key]="Blocked"; st.rerun()

st.divider()
st.subheader("📦 Export episode")
pack=make_pack(project)
json_blob=project_json(project)
zip_buffer=io.BytesIO()
with zipfile.ZipFile(zip_buffer,"w",zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"{project.get('episode_id','EP')}_production_pack.md",pack)
    zf.writestr(f"{project.get('episode_id','EP')}_project.json",json_blob)
col1,col2,col3=st.columns(3)
with col1: st.download_button("Download production Markdown",pack,file_name=f"{project.get('episode_id','EP')}_production_pack.md",mime="text/markdown",use_container_width=True)
with col2: st.download_button("Backup project JSON",json_blob,file_name=f"{project.get('episode_id','EP')}_project.json",mime="application/json",use_container_width=True)
with col3: st.download_button("Download episode ZIP",zip_buffer.getvalue(),file_name=f"{project.get('episode_id','EP')}_production_pack.zip",mime="application/zip",use_container_width=True)
st.info("Cloud hosting note: Streamlit Cloud's local filesystem may reset/recycle. Download your JSON backup regularly or restore it through the sidebar. Persistent database/cloud storage can be added in a later version.")
