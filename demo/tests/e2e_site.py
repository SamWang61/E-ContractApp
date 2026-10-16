import asyncio, re
from playwright.async_api import async_playwright

URL = "http://localhost:3000/"


async def draw(pg):
    box = await pg.locator("#sig").bounding_box()
    await pg.mouse.move(box["x"]+30, box["y"]+80); await pg.mouse.down()
    for i in range(20): await pg.mouse.move(box["x"]+30+i*15, box["y"]+80+(25 if i%2 else -25))
    await pg.mouse.up()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 1000})
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await page.goto(URL)
        await page.click("#gen")
        await page.wait_for_selector("#parties .party")
        print("parties:", await page.locator("#parties .party").count())
        print("status:", await page.inner_text("#contract-status"))
        links = await page.eval_on_selector_all("#parties .link-box", "els=>els.map(e=>e.textContent)")
        print("links:", len(links), links[0][:90])
        await page.screenshot(path="/tmp/w1_dashboard.png", full_page=True)

        # 甲方：簽署（含手寫簽名）
        a = await ctx.new_page(); a.on("pageerror", lambda e: errs.append(str(e)))
        await a.goto(links[0]); await a.wait_for_selector("#sign-title")
        print("A title:", await a.inner_text("#sign-title"))
        await a.click("#sign-action"); print("A no-input msg:", await a.inner_text("#sign-result"))
        box = await a.locator("#sig").bounding_box()
        await a.mouse.move(box["x"]+30, box["y"]+80); await a.mouse.down()
        for i in range(30): await a.mouse.move(box["x"]+30+i*15, box["y"]+80+(30 if i%2 else -30))
        await a.mouse.up()
        await a.fill("#sign-name", "王大明"); await a.check("#sign-consent"); await a.click("#sign-action")
        print("A result:", await a.inner_text("#sign-result"))
        await a.screenshot(path="/tmp/w2_signed.png", full_page=True)
        # 重複開同一連結
        a2 = await ctx.new_page(); await a2.goto(links[0]); await a2.reload()
        await a2.wait_for_selector("#sign-title")
        print("A reopen:", await a2.inner_text("#sign-title"), "|", await a2.inner_text("#sign-result"))

        # 乙方：退回修改（先不填原因）
        bpg = await ctx.new_page(); await bpg.goto(links[1]); await bpg.wait_for_selector("#sign-title")
        await bpg.click("#change-action"); print("B no-reason:", await bpg.inner_text("#sign-result"))
        await bpg.fill("#sign-reason", "第 3 條付款條件請改為 30 天"); await bpg.click("#change-action")
        print("B result:", await bpg.inner_text("#sign-result"))

        await page.wait_for_timeout(300)
        print("dashboard status after A,B:", await page.inner_text("#contract-status"))
        print("party chips:", await page.eval_on_selector_all("#parties .party .status", "els=>els.map(e=>e.textContent)"))

        # 逾期：丙方
        await page.click("#expire"); print("expire msg:", await page.inner_text("#remind-msg"))
        c = await ctx.new_page(); await c.goto(links[2]); await c.wait_for_selector("#sign-title")
        print("C after expire:", await c.inner_text("#sign-title"), "|", await c.inner_text("#sign-result"))
        await page.screenshot(path="/tmp/w3_after.png", full_page=True)

        # 重設 + 全簽
        await page.click("#reset"); await page.click("#gen"); await page.wait_for_selector("#parties .party")
        links = await page.eval_on_selector_all("#parties .link-box", "els=>els.map(e=>e.textContent)")
        for i, l in enumerate(links):
            q = await ctx.new_page(); await q.goto(l); await q.wait_for_selector("#sign-title")
            await q.fill("#sign-name", f"簽署人{i+1}"); await q.check("#sign-consent"); await q.click("#sign-action"); print("no-sig msg:", await q.inner_text("#sign-result")) if i==0 else None; await draw(q); await q.click("#sign-action")
        await page.wait_for_timeout(300)
        print("ALL SIGNED status:", await page.inner_text("#contract-status"), "|", await page.inner_text("#contract-state"))
        # 催簽
        await page.click("#reset"); await page.click("#gen"); await page.wait_for_selector("#parties .party")
        await page.click("#remind"); print("remind:", await page.inner_text("#remind-msg"))
        # 手機寬度檢視
        m = await b.new_context(viewport={"width": 390, "height": 800}, is_mobile=True)
        mp = await m.new_page(); await mp.goto(links[0] if False else URL)
        await mp.click("#gen"); await mp.wait_for_selector("#parties .party")
        ml = await mp.eval_on_selector_all("#parties .link-box", "els=>els.map(e=>e.textContent)")
        await mp.goto(ml[2]); await mp.wait_for_selector("#sign-title")
        await mp.screenshot(path="/tmp/w4_mobile_sign.png", full_page=True)
        print("JS errors:", errs)
        await b.close()
asyncio.run(main())
