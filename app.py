import streamlit as st, os, json, re, base64, subprocess, shutil, tempfile, textwrap
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title='Bengali Story Studio V3', page_icon='🎬', layout='wide')
ROOT=Path(tempfile.gettempdir())/'bengali_story_studio_v3'; ROOT.mkdir(exist_ok=True)

# ---------- utilities ----------
def get_secret(k, default=''):
    try: return st.secrets.get(k, os.getenv(k, default))
    except Exception: return os.getenv(k, default)
def safe_name(s): return re.sub(r'[^A-Za-z0-9_-]+','_',s).strip('_')[:60] or 'episode'
def api_chat(prompt, key, base, model):
    import requests
    url=base.rstrip('/')+'/chat/completions'
    resp=requests.post(url,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json={'model':model,'messages':[{'role':'system','content':'You are an expert Bengali-language cinematic horror writer and production planner. Return valid JSON when asked.'},{'role':'user','content':prompt}], 'temperature':0.8},timeout=180)
    if not resp.ok: raise RuntimeError(f'Text API {resp.status_code}: {resp.text[:700]}')
    return resp.json()['choices'][0]['message']['content']
def parse_json_text(t):
    t=re.sub(r'^```(?:json)?\s*|\s*```$', '', t.strip(), flags=re.I)
    return json.loads(t)
def image_valid(path):
    try:
        from PIL import Image
        with Image.open(path) as im: im.verify()
        return True
    except Exception: return False
def audio_duration(path):
    if not Path(path).is_file(): raise RuntimeError(f'Audio file missing: {path}')
    if not shutil.which('ffprobe'): raise RuntimeError('ffprobe is missing from cloud container.')
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)],capture_output=True,text=True)
    if p.returncode or not p.stdout.strip(): raise RuntimeError(f'Cannot read audio duration for {Path(path).name}: {p.stderr[-500:]}')
    return float(p.stdout.strip())
def split_caption(text, duration):
    # Divide Bengali narration into readable caption chunks, distributing time by character count.
    chunks=[x.strip() for x in re.split(r'(?<=[।!?])\s*', text.strip()) if x.strip()]
    if not chunks: chunks=[text.strip()]
    # merge very short chunks and cap chunk count
    merged=[]
    for c in chunks:
        if merged and len(merged[-1])<35: merged[-1]+=' '+c
        else: merged.append(c)
    merged=merged[:12]
    if not merged: return []
    weights=[max(1,len(c)) for c in merged]; total=sum(weights)
    times=[]; cur=0
    for c,w in zip(merged,weights):
        span=duration*w/total; times.append((cur,cur+span,c)); cur+=span
    return times
def srt_stamp(t):
    ms=int(round((t%1)*1000)); sec=int(t); return f'{sec//3600:02}:{(sec%3600)//60:02}:{sec%60:02},{ms:03}'
def write_srt(text,dur,path):
    lines=[]
    for i,(a,b,c) in enumerate(split_caption(text,dur),1):
        lines.extend([str(i),f'{srt_stamp(a)} --> {srt_stamp(b)}',c,''])
    Path(path).write_text('\n'.join(lines),encoding='utf-8')
def ffmpeg_sub_path(path):
    # FFmpeg filter path escaping for absolute paths
    return str(path).replace('\\','/').replace(':','\\:').replace("'","\\'")
def render_scene(image,audio,out,w,h,fps,motion,subs_path=None):
    duration=audio_duration(audio)
    filters=[f'scale={w}:{h}:force_original_aspect_ratio=increase','crop='+str(w)+':'+str(h),f'fps={fps}']
    if motion:
        filters.append(f'zoompan=z=1+0.0005*on:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s={w}x{h}:fps={fps}')
    if subs_path:
        filters.append(f"subtitles='{ffmpeg_sub_path(subs_path)}':force_style='FontName=Noto Sans Bengali\\,FontSize=28\\,Outline=2\\,Shadow=1\\,Alignment=2\\,MarginV=70'")
    vf=','.join(filters)
    cmd=['ffmpeg','-hide_banner','-y','-loop','1','-framerate',str(fps),'-i',str(image),'-i',str(audio),'-t',f'{duration:.3f}','-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(out)]
    proc=subprocess.run(cmd,capture_output=True,text=True)
    if proc.returncode: raise RuntimeError('FFmpeg scene render failed:\n'+proc.stderr[-2500:])
    return duration

# ---------- settings ----------
st.title('🎬 Bengali Story Studio — V3 Production')
st.caption('A stricter production pipeline: real scene images and valid narration are required before MP4 rendering.')
with st.sidebar:
    st.subheader('AI text connection')
    ai_key=st.text_input('Groq API key',type='password',value=get_secret('AI_API_KEY',''),help='Use Groq key or set AI_API_KEY in Streamlit Secrets')
    api_base=st.text_input('API base URL',value=get_secret('AI_API_URL','https://api.groq.com/openai/v1'))
    model=st.text_input('Model',value=get_secret('AI_MODEL','openai/gpt-oss-120b'))
    st.divider(); st.subheader('Video settings')
    fmt=st.selectbox('Format',['YouTube 16:9','Shorts 9:16'],index=0)
    fps=st.selectbox('FPS',[24,25,30],index=0)
    motion=st.checkbox('Ken Burns motion',True)
    subtitles=st.checkbox('Burn Bengali subtitles',True)
    st.caption('For real images, upload scene images or use OpenAI image generation. Render blocks if required assets are missing.')

if 'ep' not in st.session_state:
    st.session_state.ep={'title':'','premise':'','story':'','scenes':[]}
if 'audio_paths' not in st.session_state: st.session_state.audio_paths={}
if 'image_paths' not in st.session_state: st.session_state.image_paths={}
ep=st.session_state.ep

with st.expander('1. Episode setup',expanded=True):
    title=st.text_input('Episode title',value=ep.get('title',''))
    premise=st.text_area('Story premise / instructions',value=ep.get('premise',''),height=130)
    if st.button('✍️ Generate story and scene plan',type='primary'):
        if not ai_key: st.error('Enter your Groq API key in the sidebar first.')
        else:
            try:
                prompt=f'''Create an original cinematic Bengali supernatural mystery horror episode. Title: {title}. Premise: {premise}. Write in natural spoken Bengali, 8 scenes, total intended duration 8-10 minutes. Return valid JSON with keys story and scenes. Each scene object must contain title, narration (70-130 Bengali words, spoken and atmospheric), visual_prompt (detailed English prompt for a realistic cinematic image; include recurring character appearance and 16:9 framing), duration_hint. Avoid scene text cards. Keep character continuity.'''
                raw=api_chat(prompt,ai_key,api_base,model); data=parse_json_text(raw)
                ep.update(title=title,premise=premise,story=data.get('story',''),scenes=data.get('scenes',[])); st.session_state.ep=ep; st.success('Story and scene plan created.'); st.rerun()
            except Exception as e: st.error(f'Story generation failed: {e}')

if ep.get('scenes'):
    st.subheader('2. Review and edit story / scenes')
    ep['title']=title or ep.get('title','')
    ep['story']=st.text_area('Full story',value=ep.get('story',''),height=180,key='story_v3_edit')
    for i,sc in enumerate(ep['scenes']):
        with st.expander(f'Scene {i+1}: {sc.get("title","Untitled")}',expanded=(i==0)):
            sc['title']=st.text_input('Scene title',sc.get('title',''),key=f'v3title{i}')
            sc['narration']=st.text_area('Bengali narration',sc.get('narration',''),height=160,key=f'v3narr{i}')
            sc['visual_prompt']=st.text_area('Visual prompt',sc.get('visual_prompt',''),height=120,key=f'v3prompt{i}')
            upl=st.file_uploader('Upload REAL image for this scene',type=['png','jpg','jpeg','webp'],key=f'v3img{i}')
            if upl:
                folder=ROOT/f'episode_{safe_name(ep.get("title"))}'; folder.mkdir(parents=True,exist_ok=True); p=folder/f'scene_{i+1}{Path(upl.name).suffix.lower()}'; p.write_bytes(upl.getvalue()); st.session_state.image_paths[str(i)]=str(p)
            pth=st.session_state.image_paths.get(str(i),sc.get('image_path',''))
            if pth and image_valid(pth): st.image(pth,width=300); sc['image_path']=pth
    st.session_state.ep=ep

    st.subheader('3. Scene visuals — generated images or uploads')
    image_key=st.text_input('OpenAI API key for image generation (optional)',type='password',key='v3_openai_img_key')
    if st.button('🖼️ Generate missing scene images with OpenAI',disabled=not bool(image_key)):
        try:
            import requests
            for i,sc in enumerate(ep['scenes']):
                if st.session_state.image_paths.get(str(i)) and image_valid(st.session_state.image_paths[str(i)]): continue
                with st.spinner(f'Generating scene image {i+1}/{len(ep["scenes"])}...'):
                    prompt=sc.get('visual_prompt','Cinematic rural Bengal mystery scene')+' Maintain visual continuity with previous scenes. No text, no watermark, 16:9 composition.'
                    rr=requests.post('https://api.openai.com/v1/images/generations',headers={'Authorization':'Bearer '+image_key},json={'model':'gpt-image-1','prompt':prompt,'size':'1536x1024','quality':'low','n':1},timeout=240)
                    if not rr.ok: raise RuntimeError(f'Image API {rr.status_code}: {rr.text[:500]}')
                    b64=rr.json()['data'][0].get('b64_json')
                    if not b64: raise RuntimeError('Image API returned no image bytes.')
                    folder=ROOT/f'episode_{safe_name(ep.get("title"))}'; folder.mkdir(parents=True,exist_ok=True)
                    p=folder/f'scene_{i+1}.png'; p.write_bytes(base64.b64decode(b64)); st.session_state.image_paths[str(i)]=str(p); sc['image_path']=str(p)
            st.session_state.ep=ep; st.success('Scene images generated.'); st.rerun()
        except Exception as e: st.error(f'Image generation failed: {e}')

    st.subheader('4. Bengali narration')
    tts_provider=st.radio('Narration provider', ['Edge TTS (free, synthetic)','OpenAI TTS (API usage billed)'],horizontal=True,key='v3tts_provider')
    voice=st.selectbox('Edge Bengali voice',['bn-IN-BashkarNeural (male)','bn-IN-TanishaaNeural (female)'],index=0,key='v3voice')
    rate=st.select_slider('Voice rate',options=['-15%','-10%','-5%','+0%'],value='-10%',key='v3rate')
    openai_tts_key=st.text_input('OpenAI API key for narration (optional)',type='password',key='v3tts_key')
    if st.button('🎙️ Generate narration for every scene'):
        try:
            folder=ROOT/f'episode_{safe_name(ep.get("title"))}'; folder.mkdir(parents=True,exist_ok=True)
            if tts_provider.startswith('OpenAI'):
                if not openai_tts_key: raise RuntimeError('Enter an OpenAI API key for OpenAI TTS. API usage is billed separately.')
                import requests
                for i,sc in enumerate(ep['scenes']):
                    txt=sc.get('narration','').strip()
                    if not txt: raise RuntimeError(f'Scene {i+1} has no narration.')
                    p=folder/f'narration_{i+1}.mp3'
                    rr=requests.post('https://api.openai.com/v1/audio/speech',headers={'Authorization':'Bearer '+openai_tts_key,'Content-Type':'application/json'},json={'model':'tts-1','voice':'onyx','input':txt,'response_format':'mp3'},timeout=180)
                    if not rr.ok: raise RuntimeError(f'OpenAI TTS {rr.status_code}: {rr.text[:500]}')
                    p.write_bytes(rr.content); st.session_state.audio_paths[str(i)]=str(p)
            else:
                import edge_tts, asyncio
                vid='bn-IN-BashkarNeural' if 'Bashkar' in voice else 'bn-IN-TanishaaNeural'
                async def run_all():
                    for i,sc in enumerate(ep['scenes']):
                        txt=sc.get('narration','').strip()
                        if not txt: raise RuntimeError(f'Scene {i+1} has no narration.')
                        p=folder/f'narration_{i+1}.mp3'
                        await edge_tts.Communicate(txt,vid,rate=rate).save(str(p)); st.session_state.audio_paths[str(i)]=str(p)
                asyncio.run(run_all())
            st.success('Narration files generated. Preview below.'); st.rerun()
        except Exception as e: st.error(f'Narration generation failed: {e}')
    for k,p in st.session_state.audio_paths.items():
        if Path(p).is_file(): st.audio(p)

    st.subheader('5. Render MP4')
    st.info('Render requires every scene to have a real image file and narration audio file. Missing assets are never replaced with title cards.')
    if st.button('🎬 Render cinematic MP4',type='primary'):
        try:
            if not shutil.which('ffmpeg') or not shutil.which('ffprobe'): raise RuntimeError('FFmpeg/FFprobe not installed. Check packages.txt and wait for cloud rebuild.')
            missing=[]
            for i,sc in enumerate(ep['scenes']):
                img=st.session_state.image_paths.get(str(i),sc.get('image_path',''))
                aud=st.session_state.audio_paths.get(str(i),'')
                if not img or not image_valid(img): missing.append(f'Scene {i+1}: missing/invalid image')
                if not aud or not Path(aud).is_file(): missing.append(f'Scene {i+1}: missing narration audio')
            if missing: raise RuntimeError('Rendering blocked until assets are complete:\n- '+'\n- '.join(missing))
            w,h=(1920,1080) if fmt.startswith('YouTube') else (1080,1920)
            folder=ROOT/f'episode_{safe_name(ep.get("title"))}'/'render'; folder.mkdir(parents=True,exist_ok=True)
            clips=[]; durations=[]
            progress=st.progress(0)
            for i,sc in enumerate(ep['scenes']):
                img=st.session_state.image_paths.get(str(i),sc.get('image_path','')); audio=st.session_state.audio_paths[str(i)]
                dur=audio_duration(audio); durations.append(dur)
                sub=None
                if subtitles and sc.get('narration','').strip(): sub=folder/f'scene_{i+1}.srt'; write_srt(sc['narration'],dur,sub)
                clip=folder/f'clip_{i+1:02d}.mp4'; render_scene(img,audio,clip,w,h,fps,motion,sub); clips.append(clip); progress.progress((i+1)/len(ep['scenes']))
            concat=folder/'concat.txt'; concat.write_text('\n'.join("file '"+str(c).replace("'","'\\''")+"'" for c in clips),encoding='utf-8')
            out=folder/f'{safe_name(ep.get("title"))}.mp4'
            # Re-encode concat to guarantee consistent timestamps/audio instead of stream-copying.
            finalcmd=['ffmpeg','-hide_banner','-y','-f','concat','-safe','0','-i',str(concat),'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)]
            p=subprocess.run(finalcmd,capture_output=True,text=True)
            if p.returncode: raise RuntimeError('Final assembly failed:\n'+p.stderr[-2500:])
            st.session_state.video_path=str(out); st.success(f'Render complete. Duration: {sum(durations)/60:.1f} minutes.'); st.rerun()
        except Exception as e: st.error(str(e))
    if st.session_state.get('video_path') and Path(st.session_state.video_path).is_file():
        vp=Path(st.session_state.video_path); st.video(str(vp)); st.download_button('⬇️ Download MP4',vp.read_bytes(),file_name=vp.name,mime='video/mp4')

    st.subheader('6. Save / restore project')
    backup={'title':ep.get('title',''),'premise':ep.get('premise',''),'story':ep.get('story',''),'scenes':ep.get('scenes',[])}
    st.download_button('Download episode JSON backup',json.dumps(backup,ensure_ascii=False,indent=2),file_name=f'{safe_name(ep.get("title"))}_project.json',mime='application/json')
    restore=st.file_uploader('Import episode JSON backup',type=['json'],key='v3restore')
    if restore and st.button('Restore project JSON'):
        st.session_state.ep=json.loads(restore.getvalue()); st.rerun()
