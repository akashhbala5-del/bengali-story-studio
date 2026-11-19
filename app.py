import streamlit as st
import os, json, tempfile, zipfile, shutil, subprocess, re, math
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title='Bengali Story Studio', page_icon='🎬', layout='wide')
ROOT=Path('/tmp/bengali_story_studio'); ROOT.mkdir(exist_ok=True)

def secrets_get(k, default=''):
    try: return st.secrets.get(k, default)
    except Exception: return os.getenv(k, default)

def ai_chat(prompt, system='You are a Bengali cinematic story writer.', model=None):
    import requests
    key=st.session_state.get('groq_key') or secrets_get('AI_API_KEY')
    base=st.session_state.get('api_url') or secrets_get('AI_API_URL','https://api.groq.com/openai/v1')
    model=model or st.session_state.get('model') or secrets_get('AI_MODEL','openai/gpt-oss-120b')
    if not key: raise RuntimeError('Add your Groq API key in the sidebar or Streamlit Secrets.')
    url=base.rstrip('/')+'/chat/completions'
    r=requests.post(url,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}], 'temperature':0.8},timeout=120)
    if not r.ok: raise RuntimeError(f'AI API error {r.status_code}: {r.text[:500]}')
    return r.json()['choices'][0]['message']['content']

def parse_scenes(raw):
    try:
        obj=json.loads(raw)
        scenes=obj.get('scenes',obj) if isinstance(obj,dict) else obj
        if isinstance(scenes,list): return scenes
    except: pass
    # fallback split on numbered scene headings
    parts=re.split(r'(?im)(?=^(?:scene|দৃশ্য)\s*\d+)',raw)
    return [{'title':f'Scene {i+1}','narration':p.strip(),'visual_prompt':''} for i,p in enumerate(parts) if p.strip()]

def safe_filename(s): return re.sub(r'[^a-zA-Z0-9_-]+','_',s)[:45] or 'episode'

st.title('🎬 Bengali Story Studio — Video Edition')
st.caption('Create a Bengali story, scene visuals, narration, subtitles and render an MP4 from your phone.')
with st.sidebar:
    st.header('AI connection')
    st.text_input('Groq API key',type='password',key='groq_key',help='Or set AI_API_KEY in Streamlit Secrets')
    st.text_input('API base URL',value=secrets_get('AI_API_URL','https://api.groq.com/openai/v1'),key='api_url')
    st.text_input('Model',value=secrets_get('AI_MODEL','openai/gpt-oss-120b'),key='model')
    st.divider(); st.header('Video settings')
    width=st.selectbox('Video format', ['1920 × 1080 (YouTube)','1080 × 1920 (Shorts)','1280 × 720'],index=0)
    fps=st.selectbox('FPS',[24,25,30],index=0)
    motion=st.checkbox('Ken Burns zoom motion',value=True)
    burn_subs=st.checkbox('Burn Bengali subtitles into video',value=True)
    st.caption('API key is used only by this session unless you add it to Streamlit Secrets.')

if 'episode' not in st.session_state:
    st.session_state.episode={'title':'','story':'','scenes':[],'created':datetime.now().isoformat(),'approved':False}
if 'audio_paths' not in st.session_state: st.session_state.audio_paths={}
ep=st.session_state.episode

with st.expander('1. Episode setup',expanded=True):
    ep_title=st.text_input('Episode title',value=ep.get('title',''))
    premise=st.text_area('Story premise / instructions',value=ep.get('story',''),height=120,placeholder='A mysterious house in rural Bengal...')
    col1,col2=st.columns(2)
    with col1:
        if st.button('✨ Generate Bengali story and scene breakdown',use_container_width=True):
            try:
                prompt=f'''Write an original cinematic Bengali supernatural mystery for a YouTube video. Title: {ep_title}. Premise: {premise}. Return ONLY valid JSON with keys story and scenes. scenes should be 6-10 objects, each with title, narration (Bengali spoken narration, 2-5 sentences), visual_prompt (detailed image prompt in English, cinematic 16:9, recurring character consistency), and duration_hint. Make continuity consistent. JSON only.'''
                out=ai_chat(prompt,system='You are a Bengali horror screenwriter and film director. Output valid JSON only.')
                # strip fenced json
                out=re.sub(r'^```(?:json)?\s*|\s*```$','',out.strip(),flags=re.I)
                data=json.loads(out)
                ep.update(title=ep_title,story=data.get('story',premise),scenes=data.get('scenes',[]),approved=False)
                st.session_state.episode=ep; st.success('Story and scenes created. Review below.'); st.rerun()
            except Exception as e: st.error(str(e))
    with col2:
        if st.button('Clear episode',use_container_width=True): st.session_state.episode={'title':'','story':'','scenes':[],'created':datetime.now().isoformat(),'approved':False}; st.session_state.audio_paths={}; st.rerun()

if ep.get('scenes'):
    st.subheader('2. Review story & scenes')
    ep['title']=ep_title
    ep['story']=st.text_area('Story summary / full story',value=ep.get('story',''),height=180,key='story_edit')
    scenes=ep['scenes']
    for i,scene in enumerate(scenes):
        with st.expander(f"Scene {i+1}: {scene.get('title','Untitled')}",expanded=(i==0)):
            scene['title']=st.text_input('Scene title',scene.get('title',''),key=f'title_{i}')
            scene['narration']=st.text_area('Bengali narration',scene.get('narration',''),height=140,key=f'narr_{i}')
            scene['visual_prompt']=st.text_area('Image prompt',scene.get('visual_prompt',''),height=100,key=f'prompt_{i}')
            upload=st.file_uploader('Upload image for this scene (PNG/JPG)',type=['png','jpg','jpeg'],key=f'image_{i}')
            if upload:
                imgpath=ROOT/f'img_{i}{Path(upload.name).suffix.lower()}'; imgpath.write_bytes(upload.getvalue()); scene['image_path']=str(imgpath)
                st.image(upload,width=300)
    ep['scenes']=scenes; st.session_state.episode=ep
    if st.button('Approve script and scene plan',type='primary'):
        ep['approved']=True; st.session_state.episode=ep; st.success('Approved. Continue to visuals and audio.')

if ep.get('scenes'):
    st.subheader('3. Generate visuals (optional API) or upload scene images')
    st.info('Image generation needs an OpenAI API key. Otherwise upload images above. Missing scenes will use a cinematic gradient/title card in the render.')
    openai_key=st.text_input('OpenAI API key for image generation (optional)',type='password',key='image_api_key')
    if st.button('Generate scene images using OpenAI',disabled=not bool(openai_key)):
        try:
            import requests
            for i,s in enumerate(ep['scenes']):
                with st.spinner(f'Generating scene {i+1}/{len(ep["scenes"])}...'):
                    r=requests.post('https://api.openai.com/v1/images/generations',headers={'Authorization':f'Bearer {openai_key}'},json={'model':'gpt-image-1','prompt':s.get('visual_prompt','cinematic Bengali horror scene'),'size':'1536x1024','quality':'low','n':1},timeout=180)
                    if not r.ok: raise RuntimeError(r.text[:500])
                    import base64
                    b64=r.json()['data'][0].get('b64_json')
                    if b64: p=ROOT/f'generated_scene_{i}.png'; p.write_bytes(base64.b64decode(b64)); s['image_path']=str(p)
            st.session_state.episode=ep; st.success('Images generated.'); st.rerun()
        except Exception as e: st.error(f'Image generation error: {e}')

if ep.get('scenes'):
    st.subheader('4. Bengali narration audio')
    st.caption('Uses Edge TTS Bengali voices. Requires internet access during generation.')
    voice=st.selectbox('Bengali voice',['bn-IN-TanishaaNeural (female)','bn-IN-BashkarNeural (male)'],index=1)
    rate=st.select_slider('Narration speed',options=['-10%','-5%','+0%','+5%'],value='-5%')
    if st.button('🎙️ Generate narration for all scenes'):
        try:
            import edge_tts, asyncio
            voice_id='bn-IN-BashkarNeural' if 'Bashkar' in voice else 'bn-IN-TanishaaNeural'
            async def gen_all():
                for i,s in enumerate(ep['scenes']):
                    txt=s.get('narration','').strip()
                    if not txt: continue
                    audio=ROOT/f'voice_{i}.mp3'
                    communicate=edge_tts.Communicate(txt,voice_id,rate=rate)
                    await communicate.save(str(audio)); st.session_state.audio_paths[str(i)]=str(audio)
            asyncio.run(gen_all()); st.success('Narration generated for scenes.');
        except Exception as e: st.error(f'TTS failed: {e}')
    for i,path in st.session_state.audio_paths.items():
        if Path(path).exists(): st.audio(path)

if ep.get('scenes'):
    st.subheader('5. Render MP4')
    st.warning('Rendering requires FFmpeg installed in the cloud container. This package includes its installation configuration.')
    if st.button('🎬 Render episode video',type='primary'):
        try:
            import subprocess
            if not shutil.which('ffmpeg'): raise RuntimeError('FFmpeg is missing. Streamlit Cloud may need to rebuild after packages.txt is committed.')
            scenes=ep['scenes']; wh='1920x1080' if width.startswith('1920') else ('1080x1920' if width.startswith('1080') else '1280x720')
            W,H=map(int,wh.split('x')); temp=ROOT/'render'; temp.mkdir(exist_ok=True)
            # Create per-scene clips with image or generated fallback, scene voice audio
            clips=[]; concatfile=temp/'concat.txt'
            for i,s in enumerate(scenes):
                audio=Path(st.session_state.audio_paths.get(str(i),''))
                if not audio.exists(): raise RuntimeError(f'Generate narration first. Missing scene {i+1} audio.')
                # Probe duration robustly: try format duration, then audio-stream duration.
                dur=None
                probe_errors=[]
                for probe_args in (
                    ['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(audio)],
                    ['ffprobe','-v','error','-show_entries','stream=duration','-of','default=noprint_wrappers=1:nokey=1',str(audio)],
                ):
                    try:
                        raw=subprocess.check_output(probe_args,stderr=subprocess.STDOUT).decode().strip().splitlines()
                        vals=[float(x) for x in raw if x.strip() and x.strip()!='N/A']
                        if vals:
                            dur=max(vals); break
                    except Exception as probe_exc:
                        probe_errors.append(str(probe_exc))
                if dur is None:
                    # Rendering can still proceed without duration probing; audio determines clip length.
                    dur=30.0
                    st.warning(f'Could not read duration for scene {i+1}; rendering with audio-driven duration and approximate subtitle timing.')
                img=Path(s.get('image_path',''))
                # Path('') resolves to the current directory ('.'), which exists but is not an image.
                # Only accept an actual image file; otherwise create a fallback title card.
                if not img.is_file():
                    # generate fallback visual from title card using Pillow
                    from PIL import Image,ImageDraw,ImageFont
                    card=Image.new('RGB',(W,H),(12,18,28)); draw=ImageDraw.Draw(card)
                    try: font=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf',64)
                    except: font=ImageFont.load_default()
                    draw.text((W//2,H//2),s.get('title','Scene'),fill=(230,230,240),font=font,anchor='mm')
                    img=temp/f'card_{i}.png'; card.save(img)
                clip=temp/f'clip_{i}.mp4'; clips.append(clip)
                vf=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}'
                if motion: vf+=f',zoompan=z=1.0+0.0006*on:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s={wh}:fps={fps}'
                if burn_subs and s.get('narration','').strip():
                    # One timed Bengali caption per scene; subtitle timestamps span that scene audio.
                    sub=temp/f'sub_{i}.srt'
                    end=dur
                    stamp=lambda t: f'{int(t//3600):02d}:{int((t%3600)//60):02d}:{int(t%60):02d},{int((t%1)*1000):03d}'
                    caption=s.get('narration','').strip().replace('\n',' ')
                    sub.write_text(f'1\n{stamp(0)} --> {stamp(end)}\n{caption}\n',encoding='utf-8')
                    vf+=f",subtitles={sub.as_posix()}:force_style='FontName=Noto Sans Bengali,FontSize=26,Outline=2,Shadow=1,Alignment=2,MarginV=60"
                # -shortest lets the narration determine scene duration; avoids relying on ffprobe.
                render_cmd=['ffmpeg','-y','-loop','1','-i',str(img),'-i',str(audio),'-vf',vf,'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(clip)]
                try:
                    subprocess.run(render_cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as render_exc:
                    detail=(render_exc.stderr or b'').decode(errors='replace')[-1800:]
                    raise RuntimeError(f'FFmpeg failed on scene {i+1}. Details: {detail}') from render_exc
            concatfile.write_text('\n'.join(f"file '{c.as_posix()}'" for c in clips))
            output=temp/f'{safe_filename(ep_title)}.mp4'
            try:
                subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concatfile),'-c','copy',str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as concat_exc:
                detail=(concat_exc.stderr or b'').decode(errors='replace')[-1800:]
                raise RuntimeError(f'Final video assembly failed. Details: {detail}') from concat_exc
            st.session_state.video_path=str(output); st.success('Video rendered!'); st.rerun()
        except Exception as e: st.error(f'Render failed: {e}')
    if st.session_state.get('video_path') and Path(st.session_state.video_path).exists():
        vp=Path(st.session_state.video_path); st.video(str(vp)); st.download_button('⬇️ Download MP4',vp.read_bytes(),file_name=vp.name,mime='video/mp4')

with st.expander('6. Save / restore episode project'):
    st.download_button('Download project JSON backup',json.dumps(ep,ensure_ascii=False,indent=2).encode('utf-8'),file_name=f'{safe_filename(ep_title)}_project.json',mime='application/json')
    restore=st.file_uploader('Import project JSON',type=['json'],key='restore')
    if restore and st.button('Load project backup'):
        st.session_state.episode=json.loads(restore.getvalue()); st.rerun()

st.divider(); st.caption('Video rendering uses FFmpeg. AI text uses Groq-compatible API. Image generation is optional and requires an OpenAI API key. Narration uses Edge TTS online voices.')
