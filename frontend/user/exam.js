let _db=null,_fb=null;
async function initFb(){
  const c=JSON.parse(localStorage.getItem('fb_cfg')||'{}');
  if(!c.projectId)return;
  try{
    const {initializeApp,getApps}=await import('https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js');
    const fs=await import('https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js');
    const app=getApps().length?getApps()[0]:initializeApp(c);
    _db=fs.getFirestore(app);_fb=fs;
  }catch(e){console.warn('Firebase:',e);}
}
const S={studentId:'',studentName:'',examId:'',examName:'',duration:1800,timeLeft:1800,questions:[],answers:{},startTime:null,timerInt:null,warns:0,maxWarns:3,gazeAway:false,gazeAwayTime:0,totalAway:0,gazeTimer:null,gazeThreshold:3,voiceAlerts:0,paused:false,terminated:false,chatTurn:0,chatHistory:[],apiKey:'',recognition:null};
const kwds=['답','정답','answer','solution','알려줘','뭐야','어떻게','맞아','맞지','번이야','번인가'];

function loadExams(){
  const exams=JSON.parse(localStorage.getItem('proctor_exams')||'[]');
  const sel=document.getElementById('l-exam');
  const show=exams.filter(e=>e.status==='active');
  if(!show.length&&exams.length){sel.innerHTML='<option value="">-- 시험 선택 --</option>'+exams.map(e=>`<option value="${e.id}">${e.name}</option>`).join('');}
  else if(show.length){sel.innerHTML='<option value="">-- 시험 선택 --</option>'+show.map(e=>`<option value="${e.id}">${e.name}</option>`).join('');}
  else{sel.innerHTML='<option value="">활성 시험 없음 (관리자에게 문의)</option>';}
  if(_db&&_fb){_fb.onSnapshot(_fb.collection(_db,'exams'),snap=>{const fb=snap.docs.map(d=>({...d.data(),id:d.id})).filter(e=>e.status==='active');if(fb.length){sel.innerHTML='<option value="">-- 시험 선택 --</option>'+fb.map(e=>`<option value="${e.id}">${e.name}</option>`).join('');fb.forEach(e=>{const lo=JSON.parse(localStorage.getItem('proctor_exams')||'[]');const i=lo.findIndex(x=>x.id===e.id);if(i>=0)lo[i]=e;else lo.push(e);localStorage.setItem('proctor_exams',JSON.stringify(lo));});}});}
}

window.startExam=async function(){
  const id=document.getElementById('l-id').value.trim();
  const name=document.getElementById('l-name').value.trim();
  const examId=document.getElementById('l-exam').value;
  if(!id||!name){alert('학번과 이름을 입력하세요');return;}
  if(!examId){alert('시험을 선택하세요');return;}
  const exams=JSON.parse(localStorage.getItem('proctor_exams')||'[]');
  const exam=exams.find(e=>e.id===examId);
  if(!exam){alert('시험 정보를 찾을 수 없습니다');return;}
  Object.assign(S,{studentId:id,studentName:name,examId,examName:exam.name,duration:exam.duration,timeLeft:exam.duration,questions:exam.questions,startTime:Date.now()});
  const cfg=JSON.parse(localStorage.getItem('proctor_cfg')||'{}');
  S.gazeThreshold=parseInt(cfg.gaze)||3;S.maxWarns=parseInt(cfg.maxw)||3;
  S.apiKey=localStorage.getItem('groq_key')||'';
  document.getElementById('login-screen').style.display='none';
  document.getElementById('exam-screen').style.display='flex';
  document.getElementById('tb-name').textContent=exam.name;
  document.getElementById('p-title').textContent=exam.name;
  document.getElementById('p-qcnt').textContent=exam.questions.length;
  document.getElementById('p-dur').textContent=Math.round(exam.duration/60);
  document.getElementById('p-name').textContent=name;
  document.getElementById('p-id').textContent=id;
  renderQs();updateTimer();
  S.timerInt=setInterval(tick,1000);
  addLog('info','시험 시작',exam.name);sendLog('info','시험 시작',exam.name);
  initCam();initVoice();
};

function renderQs(){
  const a=document.getElementById('q-area');a.innerHTML='';
  S.questions.forEach((q,i)=>{
    const d=document.createElement('div');d.className='q-block fi';
    d.innerHTML=`<div class="q-num">문제 ${String(i+1).padStart(2,'0')}</div><div class="q-text">${q.question}</div><div class="q-options">${q.options.map((o,oi)=>`<div class="q-option" id="opt-${i}-${oi}" onclick="selOpt(${i},${oi})"><div class="opt-l">${['A','B','C','D'][oi]}</div>${o}</div>`).join('')}</div>`;
    a.appendChild(d);
  });
}
window.selOpt=(qi,oi)=>{document.querySelectorAll(`[id^="opt-${qi}-"]`).forEach(e=>e.classList.remove('sel'));document.getElementById(`opt-${qi}-${oi}`).classList.add('sel');S.answers[qi]=oi;};

function tick(){if(S.paused||S.terminated)return;S.timeLeft--;updateTimer();if(S.timeLeft<=0)submitExam();}
function updateTimer(){const m=Math.floor(S.timeLeft/60),s=S.timeLeft%60;const el=document.getElementById('timer');el.textContent=`${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;el.className='timer'+(S.timeLeft<120?' td':S.timeLeft<300?' tw':'');}

async function initCam(){
  try{
    const vid=document.getElementById('cam-vid'),cvs=document.getElementById('cam-cvs'),ctx=cvs.getContext('2d');
    const stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480,facingMode:'user'}});
    vid.srcObject=stream;vid.addEventListener('loadedmetadata',()=>{cvs.width=vid.videoWidth;cvs.height=vid.videoHeight;});
    if(typeof FaceMesh!=='undefined'){
      const fm=new FaceMesh({locateFile:f=>`https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${f}`});
      fm.setOptions({maxNumFaces:1,refineLandmarks:true,minDetectionConfidence:.5,minTrackingConfidence:.5});
      fm.onResults(r=>processLM(r,ctx,cvs));
      const cam=new Camera(vid,{onFrame:async()=>await fm.send({image:vid}),width:640,height:480});
      cam.start();addLog('ok','MediaPipe','얼굴 추적 시작');
    }else simEye();
  }catch(e){addLog('warn','카메라','접근 실패');simEye();}
}
function processLM(r,ctx,cvs){
  ctx.clearRect(0,0,cvs.width,cvs.height);
  if(!r.multiFaceLandmarks||!r.multiFaceLandmarks.length){updateGaze(true,.5);return;}
  const lm=r.multiFaceLandmarks[0];
  const li=lm[468],ri=lm[473];
  const lIn=lm[362],lOut=lm[263],rIn=lm[133],rOut=lm[33];
  const lg=(li.x-lIn.x)/(lOut.x-lIn.x),rg=(ri.x-rIn.x)/(rOut.x-rIn.x);
  const avg=(lg+rg)/2;const et=lm[386],eb=lm[374];const lv=(li.y-et.y)/(eb.y-et.y);
  const away=avg<.22||avg>.78||lv<.18||lv>.82;updateGaze(away,avg);
  const w=cvs.width,h=cvs.height;ctx.save();
  ctx.fillStyle=away?'rgba(239,68,68,.85)':'rgba(34,197,94,.85)';
  [[li.x,li.y],[ri.x,ri.y]].forEach(([x,y])=>{ctx.beginPath();ctx.arc(x*w,y*h,4,0,Math.PI*2);ctx.fill();});
  [[362,385,387,263,373,380],[33,160,158,133,153,144]].forEach(pts=>{ctx.beginPath();pts.forEach((i,idx)=>{const p=lm[i];idx===0?ctx.moveTo(p.x*w,p.y*h):ctx.lineTo(p.x*w,p.y*h);});ctx.closePath();ctx.strokeStyle=away?'rgba(239,68,68,.5)':'rgba(34,197,94,.5)';ctx.lineWidth=1.5;ctx.stroke();});
  ctx.restore();
}
function simEye(){setInterval(()=>{if(S.terminated||S.paused)return;updateGaze(Math.random()<.08,Math.random());},700);addLog('info','시뮬레이션','데모 모드');}
function updateGaze(away,val){
  if(S.paused||S.terminated)return;
  const pct=Math.max(0,Math.min(100,away?18:68+val*32));
  const fill=document.getElementById('gaze-fill');fill.style.width=pct+'%';fill.style.background=away?'var(--danger)':pct>70?'var(--ok)':'var(--warn)';
  document.getElementById('gaze-lbl').textContent=away?'⚠ 시선 이탈':'시선 정상';
  const fe=document.getElementById('st-focus');fe.textContent=Math.round(pct)+'%';fe.className='sbox-v '+(pct>70?'g':pct>40?'w':'d');
  if(away&&!S.gazeAway){S.gazeAway=true;S.gazeAwayTime=0;S.gazeTimer=setInterval(()=>{if(!S.gazeAway||S.paused||S.terminated){clearInterval(S.gazeTimer);return;}S.gazeAwayTime++;S.totalAway++;document.getElementById('st-away').textContent=S.totalAway+'s';if(S.gazeAwayTime>=S.gazeThreshold){gazeWarn();clearInterval(S.gazeTimer);}},1000);}
  else if(!away&&S.gazeAway){S.gazeAway=false;S.gazeAwayTime=0;clearInterval(S.gazeTimer);}
}
function gazeWarn(){S.warns++;updateWB();addLog('warn','시선 이탈',`${S.gazeThreshold}초+ (${S.warns}/${S.maxWarns})`);sendLog('warn','시선 이탈',`${S.gazeThreshold}초+ 이탈`);const we=document.getElementById('st-warns');we.textContent=S.warns+'회';we.className='sbox-v '+(S.warns>=S.maxWarns-1?'d':'w');if(S.warns>=S.maxWarns)startChat('gaze');else{showWarn('시선 이탈 감지',`화면을 ${S.gazeThreshold}초+ 이탈했습니다. 경고 ${S.warns}/${S.maxWarns}회`);flash('w');}}

function initVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){addLog('warn','음성','미지원');return;}
  const rec=new SR();rec.lang='ko-KR';rec.continuous=true;rec.interimResults=true;
  rec.onstart=()=>{document.getElementById('v-status').textContent='감지 중';document.querySelectorAll('.wave-bar').forEach(b=>b.classList.add('act'));addLog('ok','음성','마이크 활성화');};
  rec.onresult=e=>{if(S.paused||S.terminated)return;let t='';for(let i=e.resultIndex;i<e.results.length;i++)t+=e.results[i][0].transcript;if(!t.trim())return;document.getElementById('v-txt').textContent=`"${t}"`;if(kwds.some(k=>t.toLowerCase().includes(k))){S.voiceAlerts++;const ve=document.getElementById('st-voice');ve.textContent=S.voiceAlerts+'회';ve.className='sbox-v '+(S.voiceAlerts>=3?'d':'w');addLog('danger','음성 경고',`의심 발언: "${t.substring(0,28)}"`);sendLog('danger','음성 경고',`의심 발언: "${t.substring(0,28)}"`);S.warns++;updateWB();if(S.warns>=S.maxWarns)startChat('voice');else{showWarn('의심 발언 감지',`"${t.substring(0,28)}" 감지`);flash('d');}}};
  rec.onerror=e=>{if(e.error!=='no-speech')addLog('warn','음성 오류',e.error);};
  rec.onend=()=>{if(!S.paused&&!S.terminated)setTimeout(()=>{try{rec.start();}catch(_){}},500);};
  S.recognition=rec;try{rec.start();}catch(_){}
}

function showWarn(title,msg){if(S.paused||S.terminated)return;document.getElementById('ov-warn-title').textContent=title;document.getElementById('ov-warn-msg').textContent=msg;document.getElementById('ov-warn').classList.add('act');S.paused=true;document.getElementById('exam-content').classList.add('blurred');setStatus('w','경고 '+S.warns+'/'+S.maxWarns);setTimeout(()=>{if(document.getElementById('ov-warn').classList.contains('act'))dismissWarn();},8000);}
window.dismissWarn=()=>{document.getElementById('ov-warn').classList.remove('act');S.paused=false;document.getElementById('exam-content').classList.remove('blurred');setStatus('ok','정상 감독 중');addLog('info','경고 확인','재개');};
function flash(t){const el=document.getElementById('b-flash');el.className='b-flash bf-'+t;setTimeout(()=>el.className='b-flash',2000);}
function updateWB(){for(let i=1;i<=3;i++){const b=document.getElementById('wb'+i);if(i<=S.warns)b.classList.add(i===S.maxWarns?'crit':'used');}}

async function startChat(reason){
  if(S.paused||S.terminated)return;S.paused=true;document.getElementById('exam-content').classList.add('blurred');document.getElementById('ov-warn').classList.remove('act');if(S.recognition){try{S.recognition.stop();}catch(_){}}
  S.chatHistory=[];S.chatTurn=0;document.getElementById('chat-msgs').innerHTML='';document.getElementById('resume-btn').style.display='none';document.getElementById('ov-chat').classList.add('act');setStatus('d','AI 면담 중');
  const rm={gaze:'시선이 반복 이탈',voice:'의심 발언이 반복 감지'};
  const msg=`안녕하세요, ${S.studentName}님. 저는 ProctorAI 감독 시스템입니다.\n\n${rm[reason]}되었습니다. 시험 공정성을 위해 간단한 확인이 필요합니다.\n\n현재 시험 외 다른 자료나 도움을 받고 있습니까?`;
  await typeMsg('ai',msg);S.chatHistory.push({role:'assistant',content:msg});S.chatTurn=1;addLog('danger','AI 면담 시작',rm[reason]);sendLog('danger','AI 면담 시작',rm[reason]);
}
window.sendChat=async function(){
  const inp=document.getElementById('chat-inp');const txt=inp.value.trim();if(!txt)return;inp.value='';
  await typeMsg('user',txt);S.chatHistory.push({role:'user',content:txt});
  const reply=await getAIReply();await typeMsg('ai',reply);S.chatHistory.push({role:'assistant',content:reply});S.chatTurn++;
  if(S.chatTurn>=3){document.getElementById('resume-btn').style.display='inline-flex';addLog('info','AI 면담','완료');}
};
async function getAIReply(){
  if(S.apiKey){try{const sys=`당신은 온라인 시험 감독 AI. 응시자 ${S.studentName}(${S.studentId}), 시험: ${S.examName}. 2~3문장 한국어만.`;const res=await fetch('https://api.groq.com/openai/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${S.apiKey}`},body:JSON.stringify({model:'llama3-8b-8192',max_tokens:250,temperature:.7,messages:[{role:'system',content:sys},...S.chatHistory]})});if(res.ok){const d=await res.json();return d.choices[0].message.content.trim();}}catch(e){console.warn(e);}}
  const sims=[`이해합니다, ${S.studentName}님. 혹시 주변 소리나 다른 화면으로 인해 시선이 이탈된 이유를 설명해 주시겠습니까?`,'말씀 감사합니다. 추가 위반 시 시험이 자동 종료됩니다. 이해하셨나요?','확인되었습니다. 면담을 종료하겠습니다. 최선을 다해 응시해 주세요.'];
  return sims[Math.min(S.chatTurn-1,2)];
}
function typeMsg(role,text){return new Promise(res=>{const c=document.getElementById('chat-msgs');const d=document.createElement('div');d.className='chat-msg cm-'+role;c.appendChild(d);c.scrollTop=c.scrollHeight;if(role==='ai'){const t=document.createElement('div');t.className='typing';t.innerHTML='<div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>';d.appendChild(t);c.scrollTop=c.scrollHeight;setTimeout(()=>{d.innerHTML=text.replace(/\n/g,'<br>');c.scrollTop=c.scrollHeight;res();},900+Math.random()*700);}else{d.textContent=text;c.scrollTop=c.scrollHeight;res();}});}
window.resumeChat=()=>{document.getElementById('ov-chat').classList.remove('act');S.paused=false;S.warns=0;for(let i=1;i<=3;i++){const b=document.getElementById('wb'+i);b.classList.remove('used','crit');}document.getElementById('exam-content').classList.remove('blurred');setStatus('ok','정상 감독 중');addLog('ok','시험 재개','면담 완료');sendLog('ok','시험 재개','면담 후 재개');if(S.recognition){try{S.recognition.start();}catch(_){}}};

window.submitExam=function(){if(S.terminated)return;S.terminated=true;S.paused=true;clearInterval(S.timerInt);if(S.recognition){try{S.recognition.stop();}catch(_){}}addLog('ok','제출','답안 제출');sendLog('ok','시험 제출','답안 제출');showDone(false);};
function terminate(reason){S.terminated=true;S.paused=true;clearInterval(S.timerInt);if(S.recognition){try{S.recognition.stop();}catch(_){}}document.getElementById('ov-chat').classList.remove('act');addLog('danger','강제 종료',reason);sendLog('danger','시험 강제 종료',reason);showDone(true);}
function showDone(forced){const el=Math.round((Date.now()-S.startTime)/1000);const em=Math.floor(el/60),es=el%60;document.getElementById('done-icon').textContent=forced?'🚫':'✅';document.getElementById('done-title').textContent=forced?'시험 강제 종료':'시험 제출 완료';document.getElementById('done-title').className='ov-title '+(forced?'d':'g');document.getElementById('done-sub').textContent=forced?'부정행위 의심으로 강제 종료되었습니다.':'수고하셨습니다!';document.getElementById('dn-warns').textContent=S.warns;document.getElementById('dn-away').textContent=S.totalAway+'s';document.getElementById('dn-voice').textContent=S.voiceAlerts;document.getElementById('dn-time').textContent=`${String(em).padStart(2,'0')}:${String(es).padStart(2,'0')}`;document.getElementById('ov-done').classList.add('act');}

function setStatus(t,txt){const el=document.getElementById('sp');const m={ok:'sp-ok',w:'sp-w',d:'sp-d'};el.className='status-pill '+m[t];document.getElementById('sp-txt').textContent=txt;}
function addLog(type,event,detail){const now=new Date();const t=`${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;const list=document.getElementById('log-list');const item=document.createElement('div');item.className='log-item li-'+type;item.innerHTML=`<span class="lt">${t}</span><span><strong>${event}</strong> — ${detail}</span>`;list.insertBefore(item,list.firstChild);if(list.children.length>30)list.removeChild(list.lastChild);}
async function sendLog(severity,event,detail){const entry={studentId:S.studentId,studentName:S.studentName,examId:S.examId,examName:S.examName,severity,event,detail,ts:new Date().toISOString(),timestamp:new Date().toISOString()};if(_db&&_fb){try{await _fb.addDoc(_fb.collection(_db,'proctor_logs'),entry);}catch(e){console.warn(e);}}const stored=JSON.parse(localStorage.getItem('proctor_logs')||'[]');stored.unshift(entry);localStorage.setItem('proctor_logs',JSON.stringify(stored.slice(0,500)));}

(async()=>{await initFb();loadExams();})();
