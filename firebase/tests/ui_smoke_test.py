"""瀏覽器單輪煙霧測試（Firebase 模擬器）：python tests/ui_smoke_test.py http://127.0.0.1:5055 /path/to/file.txt"""
import asyncio, sys
from playwright.async_api import async_playwright
BASE, FILE = sys.argv[1], sys.argv[2]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(); pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(BASE + "/"); await pg.wait_for_function("!document.getElementById('create-btn').disabled", timeout=20000)
        await pg.click('[data-c="crimson-seal"]')
        await pg.set_input_files("#c-file", FILE)
        emails = pg.locator(".signer-email"); await emails.nth(0).fill("a@example.com"); await emails.nth(1).fill("b@example.com")
        await pg.click("#create-btn"); await pg.wait_for_selector("#preview-card:not([hidden]) .cover.crimson-seal", timeout=30000)
        print("cover:", await pg.locator("#owner-preview .cover").get_attribute("class"), "| doc:", await pg.locator("#owner-preview .doc-box").count())
        await pg.click('#owner-lang button[data-l="zh-CN"]'); await pg.wait_for_function("document.querySelector('#owner-preview .c-title') && document.querySelector('#owner-preview .c-title').textContent.includes('合同')||document.querySelector('#owner-preview .c-sum')?.textContent.includes('协议')", timeout=20000)
        print("zh-CN summary:", await pg.inner_text("#owner-preview .c-sum"))
        await pg.click("#send-btn"); await pg.wait_for_selector("#parties .link-box", timeout=30000)
        link = await pg.locator("#parties .link-box").first.inner_text(); print("link:", link[:60])
        q = await ctx.new_page(); q.on("pageerror", lambda e: errs.append(str(e))); q.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await q.goto(link); await q.wait_for_selector("#sign-view:not([hidden])", timeout=20000)
        await q.click('#sign-lang button[data-l="en"]'); await q.wait_for_function("document.getElementById('sign-action').textContent==='Sign'", timeout=20000)
        print("EN button:", await q.inner_text("#sign-action"), "| cover:", await q.locator(".cover").get_attribute("class"))
        await q.fill("#sign-name", "Tester"); await q.check("#sign-consent")
        bx = await q.locator("#sig").bounding_box(); await q.mouse.move(bx["x"]+30, bx["y"]+50); await q.mouse.down()
        for k in range(10): await q.mouse.move(bx["x"]+40+k*20, bx["y"]+50+(15 if k%2 else -15))
        await q.mouse.up(); await q.click("#sign-action"); await q.wait_for_selector("#sign-state .done", timeout=20000)
        print("signed:", (await q.inner_text("#sign-state"))[:40].replace("\n"," "))
        await pg.wait_for_timeout(6500); print("owner chips:", await pg.locator("#parties .status").all_inner_texts())
        print("page errors:", errs); await b.close()
asyncio.run(main())
