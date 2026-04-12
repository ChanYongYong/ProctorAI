let _db=null,_fb=null,_unsub=null;
const G={
  logs:JSON.parse(localStorage.getItem('proctor_logs')||'[]'),
  exams:JSON.parse(localStorage.getItem('proctor_exams')||'[]'),
  pdfText:'',genQs:[]
};

// Firebase
async function initFb(){
  const c=getFbCfg();
  if(!c.projectId)return false;
  try{
    const {initializeApp,getApps}=await import('https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js');
    const fs=await import('https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js');
    const app=getApps().length?getApps()[0]:initializeApp(c);
    _db=fs.getFirestore(app);_fb=fs;
    window.__db=_db;window.__fb=fs;
    listenFb();
    setFbStatus('✅ 연결됨','var(--ok)');
    return true;
  }catch(e){setFbStatus('❌ '+e.message,'var(--danger)');return false;}
}
function getFbCfg(){try{return JSON.parse(localStorage.getItem('fb_cfg')||'{}')}catch{return{}}}
function setFbStatus(t,c){const el=document.getElementById('fb-status');el.textContent=t;el.style.color=c;}
function listenFb(){
  if(!_db||!_fb)return;
  const {collection,query,orderBy,limit,onSnapshot,doc,setDoc}=_fb;
  const q=query(collection(_db,'proctor_logs'),orderBy('ts','desc'),limit(300));
  if(_unsub)_unsub();
  _unsub=onSnapshot(q,snap=>{G.logs=snap.docs.map(d=>({id:d.id,...d.data()}));localStorage.setItem('proctor_logs',JSON.stringify(G.logs));refresh();});
  onSnapshot(collection(_db,'exams'),snap=>{
    snap.docs.forEach(d=>{const fd={...d.data(),id:d.id};const i=G.exams.findIndex(e=>e.id===fd.id);if(i>=0)G.exams[i]={...G.exams[i],...fd};else G.exams.push(fd);});
    localStorage.setItem('proctor_exams',JSON.stringify(G.exams));refresh();
  });
}

// Nav
window.nav=(name,btn)=>{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.sb-btn').forEach(b=>b.classList.remove('on'));
  document.getElementById('page-'+name).classList.add('on');btn.classList.add('on');
  const L={dashboard:'대시보드',create:'시험 생성',exams:'시험 목록',monitor:'실시간 감독',logs:'전체 로그',settings:'설정'};
  document.getElementById('crumb').textContent=L[name];
  if(name==='monitor')renderMonitor();
  if(name==='logs')renderLogs();
  if(name==='exams')renderExams();
  if(name==='dashboard')renderDash();
};

// PDF
window.handleDrop=e=>{e.preventDefault();document.getElementById('upload-zone').classList.remove('drag');const f=e.dataTransfer.files[0];if(f&&f.type==='application/pdf')processPdf(f);};
window.handleFile=e=>{const f=e.target.files[0];if(f)processPdf(f);};
window.clearPdf=()=>{G.pdfText='';document.getElementById('pdf-chip').style.display='none';document.getElementById('pdf-preview').style.display='none';document.getElementById('gen-btn').disabled=true;document.getElementById('gen-status').textContent='PDF를 먼저 업로드하세요';document.getElementById('pdf-inp').value='';};

async function processPdf(file){
  document.getElementById('pdf-name').textContent=file.name;
  document.getElementById('pdf-size').textContent=(file.size/1024).toFixed(1)+' KB';
  document.getElementById('pdf-chip').style.display='flex';
  document.getElementById('gen-status').textContent='📖 텍스트 추출 중...';
  try{
    pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    const buf=await file.arrayBuffer();
    const pdf=await pdfjsLib.getDocument({data:buf}).promise;
    let txt='';
    for(let i=1;i<=Math.min(pdf.numPages,20);i++){const pg=await pdf.getPage(i);const tc=await pg.getTextContent();txt+=tc.items.map(t=>t.str).join(' ')+'\n';}
    G.pdfText=txt.trim();
    document.getElementById('pdf-prev-text').textContent=G.pdfText.substring(0,300)+(G.pdfText.length>300?'...':'');
    document.getElementById('pdf-preview').style.display='block';
    document.getElementById('gen-btn').disabled=false;
    document.getElementById('gen-status').textContent=`✅ ${pdf.numPages}페이지 추출 완료`;
  }catch(e){document.getElementById('gen-status').textContent='❌ 추출 실패: '+e.message;}
}

// AI Generate
window.generateQs=async function(){
  const key=localStorage.getItem('groq_key');
  if(!key){alert('설정에서 Groq API 키를 먼저 입력하세요!');nav('settings',document.querySelectorAll('.sb-btn')[5]);return;}
  if(!G.pdfText){alert('PDF를 먼저 업로드하세요');return;}
  const qcnt=document.getElementById('n-qcnt').value;
  const diff=document.getElementById('n-diff').value;
  prog(true,'Groq llama3 요청 중...',15);
  document.getElementById('gen-btn').disabled=true;
  document.getElementById('q-preview').innerHTML='';
  document.getElementById('save-sec').style.display='none';
  G.genQs=[];
  const prompt=`다음 교육 자료를 분석하여 ${diff} 난이도의 4지선다 객관식 문제 ${qcnt}개를 생성하세요.\n\n교육 자료:\n${G.pdfText.substring(0,5500)}\n\n반드시 아래 JSON 형식으로만 응답 (다른 텍스트 없이):\n{"questions":[{"question":"문제 내용","options":["① 보기1","② 보기2","③ 보기3","④ 보기4"],"answer":0,"explanation":"해설"}]}\nanswer는 정답 index(0~3). 반드시 한국어.`;
  try{
    prog(true,'AI가 문제 생성 중...',45);
    const res=await fetch('https://api.groq.com/openai/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${key}`},body:JSON.stringify({model:'llama3-8b-8192',max_tokens:4000,temperature:.7,messages:[{role:'user',content:prompt}]})});
    prog(true,'응답 파싱 중...',80);
    const data=await res.json();
    if(!res.ok)throw new Error(data.error?.message||'API 오류 '+res.status);
    const raw=data.choices[0].message.content.trim().replace(/```json|```/g,'').trim();
    const parsed=JSON.parse(raw);
    G.genQs=parsed.questions;
    prog(true,'완료!',100);setTimeout(()=>prog(false),500);
    renderQPreview(G.genQs);
    document.getElementById('save-sec').style.display='block';
    document.getElementById('gen-status').textContent=`✅ ${G.genQs.length}문항 생성 완료`;
  }catch(e){prog(false);document.getElementById('gen-status').textContent='❌ 실패: '+e.message;}
  document.getElementById('gen-btn').disabled=false;
};

function prog(show,step='',pct=0){
  document.getElementById('gen-prog').style.display=show?'block':'none';
  if(show){document.getElementById('gen-step').textContent=step;document.getElementById('gen-pct').textContent=pct+'%';document.getElementById('gen-bar').style.width=pct+'%';}
}
function renderQPreview(qs){
  const c=document.getElementById('q-preview');c.innerHTML='';
  qs.forEach((q,i)=>{const d=document.createElement('div');d.className='q-item fi';d.innerHTML=`<div class="q-head"><div class="q-badge">Q${String(i+1).padStart(2,'0')}</div><div class="q-txt">${q.question}</div></div><div class="q-opts">${q.options.map((o,oi)=>`<div class="q-opt${oi===q.answer?' ans':''}"><div class="opt-l">${['A','B','C','D'][oi]}</div>${o}</div>`).join('')}</div>${q.explanation?`<div class="q-exp">💡 ${q.explanation}</div>`:''}`; c.appendChild(d);});
}

// Save Exam
window.saveExam=async function(){
  const name=document.getElementById('n-name').value.trim();
  if(!name){alert('시험 이름을 입력하세요');return;}
  if(!G.genQs.length){alert('문제를 먼저 생성하세요');return;}
  const exam={id:'exam_'+Date.now(),name,duration:parseInt(document.getElementById('n-dur').value),questions:G.genQs,createdAt:new Date().toISOString(),status:'ready'};
  G.exams.push(exam);persist();
  if(_db&&_fb)await _fb.setDoc(_fb.doc(_db,'exams',exam.id),exam).catch(console.warn);
  alert(`✅ "${name}" 시험 등록!\n응시자 페이지에서 선택 가능합니다.`);
  nav('exams',document.querySelectorAll('.sb-btn')[2]);renderExams();
};

// Exams table
function renderExams(){
  const tb=document.getElementById('exam-tbody');
  if(!G.exams.length){tb.innerHTML='<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:28px">등록 없음</td></tr>';return;}
  const sc={ready:'bb',active:'bg',closed:'bm'};const st={ready:'대기',active:'진행중',closed:'종료'};
  tb.innerHTML=G.exams.map(e=>{
    const uniq=[...new Set(G.logs.filter(l=>l.examId===e.id).map(l=>l.studentId))].length;
    return `<tr><td><strong>${e.name}</strong><br><span style="font-size:10px;color:var(--muted)">${new Date(e.createdAt).toLocaleDateString('ko')}</span></td><td>${e.questions.length}문항</td><td>${Math.floor(e.duration/60)}분</td><td>${uniq}명</td><td><span class="badge ${sc[e.status]||'bb'}">${st[e.status]||'대기'}</span></td><td style="display:flex;gap:6px;"><button class="btn btn-ghost btn-sm" onclick="toggleExam('${e.id}')">${e.status==='active'?'⏹ 종료':'▶ 활성화'}</button><button class="btn btn-ghost btn-sm" onclick="deleteExam('${e.id}')">🗑</button></td></tr>`;
  }).join('');
}
window.toggleExam=id=>{const e=G.exams.find(x=>x.id===id);if(!e)return;e.status=e.status==='active'?'closed':'active';persist();if(_db&&_fb)_fb.setDoc(_fb.doc(_db,'exams',e.id),e).catch(console.warn);renderExams();};
window.deleteExam=id=>{if(!confirm('삭제?'))return;G.exams=G.exams.filter(e=>e.id!==id);persist();renderExams();};

// Monitor
function renderMonitor(){
  const now=Date.now();
  const recent=G.logs.filter(l=>(now-new Date(l.ts||l.timestamp).getTime())<7200000);
  const students={};
  recent.forEach(l=>{if(!students[l.studentId])students[l.studentId]={name:l.studentName,id:l.studentId,exam:l.examName,warns:0,last:l.ts||l.timestamp};if(l.severity==='warn')students[l.studentId].warns++;if(l.severity==='danger')students[l.studentId].warns+=2;students[l.studentId].last=l.ts||l.timestamp;});
  const list=Object.values(students);
  const grid=document.getElementById('stu-grid');
  if(!list.length){grid.innerHTML='<div style="font-size:12px;color:var(--muted)">응시 중인 학생 없음</div>';document.getElementById('mon-live').classList.remove('show');document.getElementById('live-chip').classList.remove('show');document.getElementById('alert-badge').classList.remove('show');return;}
  document.getElementById('mon-live').classList.add('show');document.getElementById('live-chip').classList.add('show');
  document.getElementById('mon-exam').textContent=list[0].exam||'진행 중';
  document.getElementById('alert-badge').classList.toggle('show',list.some(s=>s.warns>=2));
  grid.innerHTML=list.map(s=>{const pct=Math.max(0,100-s.warns*18);const col=pct>70?'var(--ok)':pct>40?'var(--warn)':'var(--danger)';return `<div class="stu-card ${s.warns>=3?'dc':s.warns>=1?'wc':''}"><div class="stu-top"><div><div class="stu-name">${s.name}</div><div class="stu-id">${s.id}</div></div><div>${s.warns>0?`<span class="badge bw">⚠ ${s.warns}회</span>`:'<span class="badge bg">정상</span>'}</div></div><div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px;"><span style="color:var(--muted)">집중도</span><span style="color:${col}">${pct}%</span></div><div class="mini-bar"><div class="mini-fill" style="width:${pct}%;background:${col}"></div></div><div style="font-size:10px;color:var(--muted);margin-top:7px">${new Date(s.last).toLocaleTimeString('ko')}</div></div>`;}).join('');
}

// Logs
window.renderLogs=function(){
  const ef=document.getElementById('lf-exam').value;const sf=document.getElementById('lf-sev').value;
  let logs=[...G.logs];if(ef)logs=logs.filter(l=>l.examId===ef);if(sf)logs=logs.filter(l=>l.severity===sf);
  document.getElementById('log-cnt').textContent=logs.length+'건';
  const tb=document.getElementById('log-tbody');
  if(!logs.length){tb.innerHTML='<div style="padding:22px;text-align:center;font-size:12px;color:var(--muted)">로그 없음</div>';return;}
  const sm={ok:'정상',info:'정보',warn:'경고',danger:'위험'};
  tb.innerHTML=logs.slice(0,150).map(l=>`<div class="log-row ${l.severity==='danger'?'rd':l.severity==='warn'?'rw':''}"><div class="log-time">${new Date(l.ts||l.timestamp).toLocaleTimeString('ko')}</div><div class="log-stu">${l.studentName}<br><span style="color:var(--muted);font-size:10px">${l.studentId}</span></div><div>${l.event} — ${l.detail}</div><div><span class="sev sv-${l.severity}">${sm[l.severity]||l.severity}</span></div></div>`).join('');
};
window.exportCsv=()=>{const rows=['시각,학번,이름,시험,이벤트,내용,등급',...G.logs.map(l=>`${new Date(l.ts||l.timestamp).toLocaleString('ko')},${l.studentId},${l.studentName},${l.examName||''},${l.event},"${l.detail}",${l.severity}`)];const a=document.createElement('a');a.href='data:text/csv;charset=utf-8,\uFEFF'+encodeURIComponent(rows.join('\n'));a.download=`proctor_logs_${new Date().toISOString().slice(0,10)}.csv`;a.click();};

// Dashboard
function renderDash(){
  document.getElementById('d-exams').textContent=G.exams.length;
  document.getElementById('d-active').textContent=G.exams.filter(e=>e.status==='active').length;
  document.getElementById('d-warns').textContent=G.logs.filter(l=>l.severity==='warn'||l.severity==='danger').length;
  document.getElementById('d-term').textContent=G.logs.filter(l=>l.event&&l.event.includes('강제 종료')).length;
  const ic={ok:'✅',info:'ℹ️',warn:'⚠️',danger:'🚨'};
  document.getElementById('d-loglist').innerHTML=G.logs.slice(0,5).map(l=>`<div style="display:flex;align-items:center;gap:8px;font-size:12px;padding:6px 0;border-bottom:1px solid rgba(30,42,61,.4)"><span>${ic[l.severity]||'•'}</span><span style="color:var(--muted);font-size:10px">${new Date(l.ts||l.timestamp).toLocaleTimeString('ko')}</span><span><strong>${l.studentName}</strong> — ${l.event}</span></div>`).join('')||'<div style="font-size:12px;color:var(--muted)">이벤트 없음</div>';
  document.getElementById('d-examlist').innerHTML=G.exams.map(e=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid rgba(30,42,61,.4)"><span style="font-size:13px;font-weight:600">${e.name}</span><span class="badge ${e.status==='active'?'bg':'bb'}">${e.status==='active'?'진행중':'대기'}</span></div>`).join('')||'<div style="font-size:12px;color:var(--muted)">시험을 먼저 생성하세요</div>';
  const sel=document.getElementById('lf-exam');const cur=sel.value;
  sel.innerHTML='<option value="">전체 시험</option>'+G.exams.map(e=>`<option value="${e.id}">${e.name}</option>`).join('');sel.value=cur;
}

function persist(){localStorage.setItem('proctor_exams',JSON.stringify(G.exams));localStorage.setItem('proctor_logs',JSON.stringify(G.logs));}
function refresh(){renderDash();renderMonitor();renderLogs();renderExams();}

// Settings
window.saveAdmin=()=>{const v=document.getElementById('set-admin').value.trim()||'관리자';localStorage.setItem('admin_name',v);document.getElementById('admin-name-disp').textContent=v;alert('저장됨');};
window.saveGroq=()=>{localStorage.setItem('groq_key',document.getElementById('set-groq').value.trim());alert('✅ Groq API 키 저장 완료');};
window.saveFb=async()=>{const cfg={apiKey:document.getElementById('fb-k').value.trim(),authDomain:document.getElementById('fb-d').value.trim(),projectId:document.getElementById('fb-p').value.trim(),storageBucket:document.getElementById('fb-b').value.trim(),messagingSenderId:document.getElementById('fb-s').value.trim(),appId:document.getElementById('fb-a').value.trim()};localStorage.setItem('fb_cfg',JSON.stringify(cfg));await initFb();};
window.saveProctor=()=>{localStorage.setItem('proctor_cfg',JSON.stringify({gaze:document.getElementById('set-gaze').value,maxw:document.getElementById('set-maxw').value}));alert('저장됨');};

// Poll localStorage fallback
setInterval(()=>{
  const lg=JSON.parse(localStorage.getItem('proctor_logs')||'[]');if(lg.length!==G.logs.length){G.logs=lg;refresh();}
  const ex=JSON.parse(localStorage.getItem('proctor_exams')||'[]');if(ex.length!==G.exams.length){G.exams=ex;refresh();}
},1500);

// Init
(async()=>{
  const an=localStorage.getItem('admin_name')||'관리자';
  document.getElementById('admin-name-disp').textContent=an;document.getElementById('set-admin').value=an;
  document.getElementById('set-groq').value=localStorage.getItem('groq_key')||'';
  const fc=getFbCfg();
  if(fc.projectId){document.getElementById('fb-k').value=fc.apiKey||'';document.getElementById('fb-d').value=fc.authDomain||'';document.getElementById('fb-p').value=fc.projectId||'';document.getElementById('fb-b').value=fc.storageBucket||'';document.getElementById('fb-s').value=fc.messagingSenderId||'';document.getElementById('fb-a').value=fc.appId||'';await initFb();}
  const pc=JSON.parse(localStorage.getItem('proctor_cfg')||'{}');
  if(pc.gaze)document.getElementById('set-gaze').value=pc.gaze;if(pc.maxw)document.getElementById('set-maxw').value=pc.maxw;
  renderDash();
})();
