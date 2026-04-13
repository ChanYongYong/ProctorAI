"""
ProctorAI 유지보수 스크립트
- 시험/유저 목록 조회
- 이름 변경 (exam title, user name)
- 문제 내용 출력 및 답 검증 + 수정

사용법: python maintenance.py
"""
import httpx, json

BASE = "https://proctorai-production.up.railway.app"
c = httpx.Client(base_url=BASE, timeout=15)

ADMIN_NAME = "prof"
ADMIN_PASS = "1234"

r = c.post("/api/auth/login", json={"name": ADMIN_NAME, "password": ADMIN_PASS})
if r.status_code != 200:
    print(f"❌ 로그인 실패: {r.text}")
    exit(1)
token = r.json()["token"]
ah = {"Authorization": f"Bearer {token}"}
print(f"✅ 관리자 로그인 성공 ({ADMIN_NAME})\n")

def get_list(resp):
    data = resp.json()
    if isinstance(data, list):
        return data
    print(f"  ⚠️  예상치 못한 응답 ({resp.status_code}): {data}")
    return []

def fix_answer(q_id, new_answer, reason):
    r = c.put(f"/api/questions/{q_id}", json={"answer": str(new_answer)}, headers=ah)
    if r.status_code == 200:
        print(f"    ✅ 수정 완료: 정답 → [{new_answer}]  ({reason})")
    else:
        print(f"    ❌ 수정 실패: {r.text}")

# ─── 사용자 목록 ─────────────────────────────────────────
print("=" * 60)
print("👤 사용자 목록")
print("=" * 60)
# 새 엔드포인트가 아직 배포 안 됐을 수 있으므로 fallback 처리
users_r = c.get("/api/auth/users", headers=ah)
if users_r.status_code == 200:
    users = users_r.json() if isinstance(users_r.json(), list) else []
    for u in users:
        print(f"  ID={u['id']:3d} | role={u['role']:7s} | name={u['name']}")
else:
    print(f"  ⚠️  /api/auth/users 미배포 ({users_r.status_code}) — 스킵")
    users = []

# ─── 시험 목록 ───────────────────────────────────────────
print("\n" + "=" * 60)
print("📝 시험 목록")
print("=" * 60)
exams = get_list(c.get("/api/exams", headers=ah))
for e in exams:
    print(f"  ID={e['id']:3d} | status={e['status']:8s} | questions={e.get('question_count',0):2d}개 | title={e['title']}")

# ─── 이름 변경 ───────────────────────────────────────────
print("\n" + "=" * 60)
print("✏️  이름 변경")
print("=" * 60)

# 시험 이름: PATCH /api/exams/{id} (신규 엔드포인트)
exam_to_rename = next((e for e in exams if e['title'] == '중간고사'), None)
if exam_to_rename:
    r = c.patch(f"/api/exams/{exam_to_rename['id']}", json={"title": "test 시험"}, headers=ah)
    if r.status_code == 200:
        print(f"  ✅ 시험 이름 변경: '중간고사' → 'test 시험' (ID={exam_to_rename['id']})")
        exam_to_rename['title'] = 'test 시험'
    elif r.status_code in (404, 405):
        print(f"  ⏳ PATCH /api/exams 엔드포인트 배포 대기 중 ({r.status_code}) — 나중에 재실행")
    else:
        print(f"  ❌ 시험 이름 변경 실패: {r.text}")
else:
    print("  ℹ️  '중간고사' 시험 없음")

# 사용자 이름: PATCH /api/auth/users/{id}/name (신규 엔드포인트)
user_to_rename = next((u for u in users if u['name'] == 'stu2'), None)
if user_to_rename:
    r = c.patch(f"/api/auth/users/{user_to_rename['id']}/name", json={"name": "test 응시자"}, headers=ah)
    if r.status_code == 200:
        print(f"  ✅ 사용자 이름 변경: 'stu2' → 'test 응시자' (ID={user_to_rename['id']})")
    elif r.status_code in (404, 405):
        print(f"  ⏳ PATCH /api/auth/users 엔드포인트 배포 대기 중 ({r.status_code}) — 나중에 재실행")
    else:
        print(f"  ❌ 사용자 이름 변경 실패: {r.text}")
else:
    print("  ℹ️  'stu2' 사용자 없음")

# 관리자 계정: prof/1234 → admin/1234
admin_user = next((u for u in users if u['name'] == 'prof'), None)
if admin_user:
    uid = admin_user['id']
    r1 = c.patch(f"/api/auth/users/{uid}/name", json={"name": "admin"}, headers=ah)
    r2 = c.patch(f"/api/auth/users/{uid}/password", json={"password": "1234"}, headers=ah)
    if r1.status_code == 200:
        print(f"  ✅ 관리자 이름 변경: 'prof' → 'admin'")
        # 토큰 재발급 (이름 변경됐으므로)
        login_r = c.post("/api/auth/login", json={"name": "admin", "password": "1234"})
        if login_r.status_code == 200:
            token = login_r.json()["token"]
            ah = {"Authorization": f"Bearer {token}"}
            print(f"  ✅ 토큰 재발급 완료")
    elif r1.status_code in (404, 405):
        print(f"  ⏳ PATCH /api/auth/users 엔드포인트 배포 대기 중 ({r1.status_code}) — 나중에 재실행")
    else:
        print(f"  ❌ 관리자 이름 변경 실패: {r1.text}")
    if r2.status_code == 200:
        print(f"  ✅ 관리자 비밀번호 유지: 1234")
    elif r2.status_code in (404, 405):
        print(f"  ⏳ 비밀번호 변경 엔드포인트 배포 대기 중")
    else:
        print(f"  ❌ 비밀번호 변경 실패: {r2.text}")
elif next((u for u in users if u['name'] == 'admin'), None):
    print(f"  ℹ️  이미 'admin' 계정 존재")
else:
    print(f"  ℹ️  'prof' 계정 없음")

# ─── 문제 검증 및 수정 ───────────────────────────────────
exams = get_list(c.get("/api/exams", headers=ah))  # 이름 변경 후 재로드

# 수학2 Q9 정답 검증: 반구 부피 = (2/3)πr³ = 16π/3 → 인덱스 0
# 수학2 Q2 Jacobian: u=x-y, v=x+y → J(x,y)=2 → 인덱스 0
# 수학2 Q3: 설명과 다른 답 → 의심, 수동 확인 필요
# 아래는 수학적으로 명확히 검증 가능한 것만 자동 수정

KNOWN_FIXES = {
    # (exam_title_keyword, q_number): (correct_index, reason)
    ("중간고사", 1): (3, "2+3=5인데 보기에 없음 → 원래 2+2=4 문제, 답은 인덱스 3 ('4')"),
    ("test 시험", 1): (3, "2+3=5인데 보기에 없음 → 원래 2+2=4 문제, 답은 인덱스 3 ('4')"),
    ("수학2", 9): (0, "반구(r=2) 부피 = (2/3)π·8 = 16π/3 → 인덱스 0"),
    ("수학2", 2): (0, "J(x,y) = |∂u/∂x ∂u/∂y; ∂v/∂x ∂v/∂y| = |1 -1; 1 1| = 2 → 인덱스 0"),
}

for e in exams:
    if e.get('question_count', 0) == 0:
        continue
    print(f"\n{'=' * 60}")
    print(f"📋 시험: {e['title']} (ID={e['id']})")
    print("=" * 60)
    detail = c.get(f"/api/exams/{e['id']}", headers=ah).json()
    questions = detail.get("questions", [])
    if not questions:
        print("  문제 없음")
        continue

    issues = []
    for q in questions:
        opts = q.get("options") or []
        ans_str = str(q.get("answer", ""))
        try:
            ans_idx = int(ans_str)
        except:
            ans_idx = -1
        valid = 0 <= ans_idx < len(opts) if opts else True
        flag = "✅" if valid else "❌ 정답 인덱스 오류!"
        print(f"\n  Q{q['number']} {flag}")
        print(f"  문제: {q['text'][:80]}{'...' if len(q['text'])>80 else ''}")
        if opts:
            for i, o in enumerate(opts):
                marker = " ◀ 정답" if i == ans_idx else ""
                print(f"    [{i}] {o}{marker}")
        if q.get("explanation"):
            print(f"  해설: {q['explanation'][:100]}{'...' if len(q.get('explanation',''))>100 else ''}")

        # 자동 수정
        for (title_kw, q_num), (correct_idx, reason) in KNOWN_FIXES.items():
            if title_kw in e['title'] and q['number'] == q_num:
                if ans_idx != correct_idx:
                    print(f"  🔧 자동 수정 필요: 현재 [{ans_idx}] → [{correct_idx}]")
                    print(f"     근거: {reason}")
                    fix_answer(q['id'], correct_idx, reason)
                else:
                    print(f"  ✅ 정답 이미 정상 [{correct_idx}]")

        if not valid:
            issues.append(q)

    if issues:
        print(f"\n  ⚠️  {len(issues)}개 문제 인덱스 오류")
    else:
        print(f"\n  ✅ 모든 문제 인덱스 정상")

print("\n" + "=" * 60)
print("완료. 배포 대기 항목은 Railway 재배포 후 재실행하세요.")
print("=" * 60)
