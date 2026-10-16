"""Firestore 規則測試：前端（含已登入者）直接讀寫合約資料必須全部被拒。
用法：python tests/rules_test.py   （需先啟動模擬器並跑過 api_flow_test 產生資料）"""
import requests, sys
FS = "http://127.0.0.1:8181/v1/projects/mycontractapp-911/databases/(default)/documents"
AUTH = "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key"
me = requests.post(AUTH, json={"returnSecureToken": True}).json(); H = {"Authorization": "Bearer " + me["idToken"]}; uid = me["localId"]
owner = requests.get("http://127.0.0.1:8181/v1/projects/mycontractapp-911/databases/(default)/documents/tenants", headers={"Authorization": "Bearer owner"}).json()
tenant = owner["documents"][0]["name"].split("/")[-1]
contracts = requests.get(f"{FS}/tenants/{tenant}/contracts", headers={"Authorization": "Bearer owner"}).json()["documents"]
cid = contracts[0]["name"].split("/")[-1]
cases = [
  ("讀別人的租戶", requests.get(f"{FS}/tenants/{tenant}", headers=H)),
  ("讀別人的合約", requests.get(f"{FS}/tenants/{tenant}/contracts/{cid}", headers=H)),
  ("列出合約", requests.get(f"{FS}/tenants/{tenant}/contracts", headers=H)),
  ("讀簽署邀請（含加密 Token）", requests.get(f"{FS}/tenants/{tenant}/contracts/{cid}/signatureInvites", headers=H)),
  ("未登入讀合約", requests.get(f"{FS}/tenants/{tenant}/contracts/{cid}")),
  ("自建租戶", requests.post(f"{FS}/tenants?documentId=t-{uid}", headers=H, json={"fields": {"ownerId": {"stringValue": uid}}})),
  ("竄改合約狀態", requests.patch(f"{FS}/tenants/{tenant}/contracts/{cid}?updateMask.fieldPaths=status", headers=H, json={"fields": {"status": {"stringValue": "fully_signed"}}})),
  ("collection group 查詢邀請", requests.post(f"{FS}:runQuery", headers=H, json={"structuredQuery": {"from": [{"collectionId": "signatureInvites", "allDescendants": True}]}})),
]
bad = 0
for name, r in cases:
    ok = r.status_code in (401, 403)
    bad += not ok
    print(("PASS " if ok else "FAIL ") + f"拒絕：{name}  (HTTP {r.status_code})")
r = requests.patch(f"{FS}/users/{uid}", headers=H, json={"fields": {"lang": {"stringValue": "zh-TW"}}})
print(("PASS " if r.status_code == 200 else "FAIL ") + f"允許：寫自己的 users 文件 (HTTP {r.status_code})"); bad += r.status_code != 200
print(f"\n規則測試：{len(cases) + 1 - bad}/{len(cases) + 1} 通過"); sys.exit(1 if bad else 0)
