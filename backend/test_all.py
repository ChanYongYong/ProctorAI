"""ProctorAI 백엔드 전체 API 테스트 스크립트"""
import httpx, json, sys

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=10)
ah = lambda t: {"Authorization": f"Bearer {t}"}
PASS = 0
FAIL = 0

def check(label, r, expected_code):
    global PASS, FAIL
    ok = r.status_code == expected_code
    icon = "✅" if ok else "❌"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    body = ""
    try:
        body = r.json()
    except:
        body = r.text[:100]
    print(f"  {icon} {label}: {r.status_code} (expected {expected_code}) → {body}")
    return r


# ══════════════════════════════════════
print("=" * 60)
print("Phase 0: Health Check")
print("=" * 60)
check("Health", c.get("/api/health"), 200)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 1: Auth")
print("=" * 60)

r = check("Register admin", c.post("/api/auth/register", json={"name":"prof","password":"1234","role":"admin"}), 201)
admin_id = r.json().get("id")

r = check("Register student1", c.post("/api/auth/register", json={"name":"stu1","password":"1234","role":"student"}), 201)
stu1_id = r.json().get("id")

check("Duplicate name", c.post("/api/auth/register", json={"name":"prof","password":"x","role":"admin"}), 400)
check("Invalid role", c.post("/api/auth/register", json={"name":"x","password":"x","role":"teacher"}), 400)

r = check("Login admin", c.post("/api/auth/login", json={"name":"prof","password":"1234"}), 200)
admin_token = r.json()["token"]

r = check("Login student1", c.post("/api/auth/login", json={"name":"stu1","password":"1234"}), 200)
stu1_token = r.json()["token"]

check("Wrong password", c.post("/api/auth/login", json={"name":"prof","password":"wrong"}), 401)
check("Me (admin)", c.get("/api/auth/me", headers=ah(admin_token)), 200)
check("Me (no token)", c.get("/api/auth/me"), 401)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 2: Exam CRUD")
print("=" * 60)

r = check("Create exam", c.post("/api/exams", json={"title":"중간고사","duration":1800}, headers=ah(admin_token)), 201)
exam_id = r.json().get("id")
print(f"    → exam_id = {exam_id}")

check("List exams", c.get("/api/exams", headers=ah(admin_token)), 200)
check("Exam detail", c.get(f"/api/exams/{exam_id}", headers=ah(admin_token)), 200)
check("Student cannot create", c.post("/api/exams", json={"title":"x","duration":60}, headers=ah(stu1_token)), 403)

r = check("Create exam for delete", c.post("/api/exams", json={"title":"삭제대상","duration":60}, headers=ah(admin_token)), 201)
del_id = r.json().get("id")
check("Delete exam", c.delete(f"/api/exams/{del_id}", headers=ah(admin_token)), 204)
check("Delete non-existent", c.delete("/api/exams/99999", headers=ah(admin_token)), 404)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 3: Questions (manual create)")
print("=" * 60)

r = check("Create Q1", c.post("/api/questions", json={
    "exam_id": exam_id, "type": "choice",
    "text": "2+2는?", "options": ["1","2","3","4"], "answer": "3", "explanation": "4번째가 4"
}, headers=ah(admin_token)), 201)
q1_id = r.json().get("id")
print(f"    → q1_id = {q1_id}")

r = check("Create Q2", c.post("/api/questions", json={
    "exam_id": exam_id, "type": "choice",
    "text": "한국 수도?", "options": ["도쿄","베이징","서울","오사카"], "answer": "2", "explanation": "서울"
}, headers=ah(admin_token)), 201)
q2_id = r.json().get("id")

r = check("Create Q3", c.post("/api/questions", json={
    "exam_id": exam_id, "type": "choice",
    "text": "하늘 색?", "options": ["빨강","파랑","초록","노랑"], "answer": "1", "explanation": "파랑"
}, headers=ah(admin_token)), 201)
q3_id = r.json().get("id")

check("Update Q1", c.put(f"/api/questions/{q1_id}", json={"text":"2+3은?","answer":"4"}, headers=ah(admin_token)), 200)
check("Empty update", c.put(f"/api/questions/{q1_id}", json={}, headers=ah(admin_token)), 400)

r = check("Exam detail w/ questions", c.get(f"/api/exams/{exam_id}", headers=ah(admin_token)), 200)
q_count = len(r.json().get("questions", []))
print(f"    → question count = {q_count}")


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 4: Settings")
print("=" * 60)

check("Get settings (first)", c.get("/api/admin/settings", headers=ah(admin_token)), 200)
check("Save settings", c.put("/api/admin/settings", json={"gaze_threshold":5,"max_warnings":5}, headers=ah(admin_token)), 200)
check("Student access settings", c.get("/api/admin/settings", headers=ah(stu1_token)), 403)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 5: Student Exam Flow")
print("=" * 60)

# 시험 활성화
check("Activate exam", c.patch(f"/api/exams/{exam_id}/status", json={"status":"active"}, headers=ah(admin_token)), 200)

check("List active exams", c.get("/api/student/exams", headers=ah(stu1_token)), 200)

r = check("Start exam", c.post(f"/api/student/exams/{exam_id}/start", headers=ah(stu1_token)), 201)
attempt_id = r.json().get("attempt_id")
questions = r.json().get("questions", [])
print(f"    → attempt_id = {attempt_id}")
# 정답/해설 없는지 확인
has_answer = any("answer" in q for q in questions)
print(f"    → answer exposed to student? {has_answer} {'❌ BUG!' if has_answer else '✅'}")

check("Duplicate start", c.post(f"/api/student/exams/{exam_id}/start", headers=ah(stu1_token)), 400)
check("Current attempt", c.get("/api/student/attempts/current", headers=ah(stu1_token)), 200)

# 답안 제출 (Q1 answer=4 → selected 4? No, answer was updated to "4" meaning index 4, but options only 0-3)
# Q1: answer "4" (updated), Q2: answer "2", Q3: answer "1"
# 전부 정답으로 제출
r = check("Submit answers", c.post(f"/api/student/attempts/{attempt_id}/submit", json={
    "answers": [
        {"question_id": q1_id, "selected": 4},
        {"question_id": q2_id, "selected": 2},
        {"question_id": q3_id, "selected": 1},
    ]
}, headers=ah(stu1_token)), 200)
print(f"    → score = {r.json().get('score')}")

check("Duplicate submit", c.post(f"/api/student/attempts/{attempt_id}/submit", json={"answers":[]}, headers=ah(stu1_token)), 400)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 6: Proctoring")
print("=" * 60)

# 학생2 생성
r = c.post("/api/auth/register", json={"name":"stu2","password":"1234","role":"student"})
r = c.post("/api/auth/login", json={"name":"stu2","password":"1234"})
stu2_token = r.json()["token"]

r = check("Stu2 start exam", c.post(f"/api/student/exams/{exam_id}/start", headers=ah(stu2_token)), 201)
attempt_id_2 = r.json().get("attempt_id")
print(f"    → attempt_id_2 = {attempt_id_2}")

check("Log info", c.post(f"/api/student/attempts/{attempt_id_2}/logs", json={"severity":"info","event":"gaze_return","detail":"돌아봄"}, headers=ah(stu2_token)), 201)
check("Log warn", c.post(f"/api/student/attempts/{attempt_id_2}/logs", json={"severity":"warn","event":"warning","detail":"5초 이탈"}, headers=ah(stu2_token)), 201)
check("Log danger", c.post(f"/api/student/attempts/{attempt_id_2}/logs", json={"severity":"danger","event":"voice_detected","detail":"음성 감지"}, headers=ah(stu2_token)), 201)
check("Invalid severity", c.post(f"/api/student/attempts/{attempt_id_2}/logs", json={"severity":"critical","event":"x"}, headers=ah(stu2_token)), 400)
check("Wrong user's attempt", c.post(f"/api/student/attempts/{attempt_id_2}/logs", json={"severity":"info","event":"x"}, headers=ah(stu1_token)), 403)

check("End exam", c.post(f"/api/student/attempts/{attempt_id_2}/end", json={"warning_count":3,"total_away_time":45,"voice_alerts":1}, headers=ah(stu2_token)), 200)
check("End again (should fail)", c.post(f"/api/student/attempts/{attempt_id_2}/end", json={"warning_count":0,"total_away_time":0,"voice_alerts":0}, headers=ah(stu2_token)), 400)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 7: Monitor (Admin)")
print("=" * 60)

check("All logs", c.get("/api/admin/logs", headers=ah(admin_token)), 200)
check("Logs filter severity", c.get("/api/admin/logs?severity=warn", headers=ah(admin_token)), 200)
check("Logs pagination", c.get("/api/admin/logs?page=1&size=2", headers=ah(admin_token)), 200)
check("Attempt logs", c.get(f"/api/admin/attempts/{attempt_id_2}/logs", headers=ah(admin_token)), 200)
r = check("CSV export", c.get("/api/admin/logs/export", headers=ah(admin_token)), 200)
print(f"    → Content-Type = {r.headers.get('content-type')}")


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 8: Results")
print("=" * 60)

check("Student own result", c.get(f"/api/student/attempts/{attempt_id}/result", headers=ah(stu1_token)), 200)
check("Student other's result", c.get(f"/api/student/attempts/{attempt_id_2}/result", headers=ah(stu1_token)), 403)
check("Admin any result", c.get(f"/api/admin/attempts/{attempt_id}/result", headers=ah(admin_token)), 200)
check("Exam results list", c.get(f"/api/admin/exams/{exam_id}/results", headers=ah(admin_token)), 200)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print("Phase 9: Clarifications")
print("=" * 60)

# attempt를 under_review로 변경
check("Set under_review", c.patch(f"/api/admin/attempts/{attempt_id_2}/status", json={"status":"under_review"}, headers=ah(admin_token)), 200)

r = check("Submit clarification", c.post("/api/clarifications", json={
    "attempt_id": attempt_id_2,
    "reason_type": "gaze_away",
    "reason_detail": "시선 이탈 감지",
    "student_message": "필기 확인 중이었습니다"
}, headers=ah(stu2_token)), 201)
clar_id = r.json().get("id")
print(f"    → clarification_id = {clar_id}")

check("My clarification", c.get(f"/api/clarifications/me/{attempt_id_2}", headers=ah(stu2_token)), 200)
check("Pending list", c.get("/api/admin/clarifications/pending", headers=ah(admin_token)), 200)
check("Clarification detail", c.get(f"/api/admin/clarifications/{clar_id}", headers=ah(admin_token)), 200)

r = check("Approve", c.patch(f"/api/admin/clarifications/{clar_id}/decision", json={
    "status": "approved", "teacher_comment": "허용된 필기입니다"
}, headers=ah(admin_token)), 200)

check("Duplicate decision", c.patch(f"/api/admin/clarifications/{clar_id}/decision", json={"status":"rejected"}, headers=ah(admin_token)), 400)


# ══════════════════════════════════════
print("\n" + "=" * 60)
print(f"결과: ✅ PASS={PASS}  ❌ FAIL={FAIL}")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
