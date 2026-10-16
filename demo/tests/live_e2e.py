import asyncio, sys, json
from playwright.async_api import async_playwright
BASE = sys.argv[1] if len(sys.argv)>1 else "http://localhost:3000"
N = int(sys.argv[2]) if len(sys.argv)>2 else 2
FULL = len(sys.argv)>3 and sys.argv[3]=="full"
ACTS = sys.argv[4].split(",") if len(sys.argv)>4 else []
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(); pg=await ctx.new_page(); errs=[]
        pg.on("pageerror",lambda e:errs.append(str(e)))
        pg.on("console",lambda m: errs.append("console:"+m.text) if m.type=="error" else None)
        await pg.goto(BASE+"/live.html")
        await pg.wait_for_function("document.getElementById('conn-badge').textContent!=='連線中…'", timeout=30000)
        print("badge:", await pg.inner_text("#conn-badge"), "|", (await pg.inner_text("#conn"))[:80])
        if N==3: await pg.check("input[name=parties][value='3']")
        emails=[f"sam.test.party{i+1}@example.com" for i in range(N)]
        for i,e in enumerate(emails): await pg.locator(".signer-email").nth(i).fill(e)
        await pg.click("#send")
        await pg.wait_for_function("(t=>!/中…$/.test(t))(document.getElementById('send-msg').textContent)", timeout=45000)
        print("send-msg:", await pg.inner_text("#send-msg"))
        if FULL and not await pg.locator("#track-card").is_hidden():
            await pg.wait_for_function(f"document.querySelectorAll('#parties .party').length==={N}", timeout=30000)
            print("cards:", await pg.locator("#parties .party").count(), "|", await pg.inner_text("#contract-state"))
            links=await pg.locator("#parties .link-box").all_inner_texts()
            print("link sample:", links[0][:70] if links else None)
            await pg.screenshot(path="/tmp/live_after_send.png", full_page=True)
            # signer 1 sign, signer 2 request_changes or sign
            for i,l in enumerate(links):
                q=await ctx.new_page(); q.on("dialog", lambda d: asyncio.ensure_future(d.accept())); await q.goto(l); await q.wait_for_selector("#form:not([hidden])", timeout=20000)
                title=await q.inner_text("#sign-title")
                act = ACTS[i] if i < len(ACTS) else "sign"
                await q.fill("#sign-name",f"測試簽署人{i+1}")
                if act=="sign":
                    await q.check("#sign-consent")
                    bx=await q.locator("#sig").bounding_box(); await q.mouse.move(bx["x"]+30,bx["y"]+60); await q.mouse.down()
                    for k in range(12): await q.mouse.move(bx["x"]+30+k*18,bx["y"]+60+(20 if k%2 else -20))
                    await q.mouse.up(); await q.click("#sign-action")
                else:
                    await q.fill("#sign-reason","條款第 3 條需調整（測試）")
                    await q.click("#change-action" if act=="change" else "#decline-action")
                await q.wait_for_function("document.getElementById('state').textContent.length>0 || (document.getElementById('sign-result').textContent.length>0 && document.getElementById('sign-result').textContent!=='送出中…')", timeout=30000)
                print(f"signer{i+1} [{act}]:", title, "->", (await q.inner_text("#state")) or await q.inner_text("#sign-result"))
                await q.reload(); await q.wait_for_timeout(2500); print(f"signer{i+1} reopen:", await q.inner_text("#sign-title"), "|", (await q.inner_text("#state"))[:60]); await q.close()
            await pg.wait_for_timeout(9000)
            print("final:", await pg.inner_text("#contract-status"), "|", await pg.inner_text("#contract-state"))
            print("chips:", await pg.locator("#parties .party .status").all_inner_texts())
            await pg.screenshot(path="/tmp/live_final.png", full_page=True)
        print("errors:", errs[:5])
        await b.close()
asyncio.run(main())
