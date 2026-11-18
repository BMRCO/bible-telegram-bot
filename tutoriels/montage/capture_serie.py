"""Captures reelles de LaBible.app pour la serie « Decouvrir LaBible.app ».
Chromium 390x844 x3, polices Android (Roboto, Noto Serif via fontconfig).
Chaque capture : cap/<nom>.jpg + positions (px CSS) dans cap/serie.json."""
import asyncio, base64, json, sys
from playwright.async_api import async_playwright

U = "http://localhost:8767/"
POS = {}

async def shot(pg, nom, **sels):
    await pg.wait_for_timeout(900)
    await pg.screenshot(path=f"cap/{nom}.jpg", type="jpeg", quality=92)
    bx = {"scrollY": await pg.evaluate("scrollY")}
    for k, sel in sels.items():
        bx[k] = await pg.evaluate(
            "(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]}", sel)
    POS[nom] = bx
    print("ok", nom, {k: v for k, v in bx.items() if v is None})

async def vers(pg, sel, bloc="center"):
    await pg.evaluate("([s,b])=>document.querySelector(s).scrollIntoView({block:b,behavior:'instant'})", [sel, bloc])

async def propre(pg):
    await pg.evaluate("document.querySelectorAll('#verseHint,.verseHint,.hint').forEach(e=>e.remove())")

async def app(ctx, hash_=""):
    pg = await ctx.new_page()
    await pg.goto(U + hash_, wait_until="load")
    await pg.wait_for_selector("#verses .verse", timeout=60000)
    await pg.wait_for_timeout(2500)
    await propre(pg)
    return pg

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                                  has_touch=True, color_scheme="dark", locale="fr-FR")
        # ---------- 1. Lire la Bible
        pg = await app(ctx, "#Psaumes-23")
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "l1_haut", livre="#bookSelect", chap="#chapterSelect", vers_="#verseSelect",
                   suiv="#btnNext", prec="#btnPrev", aplus="#btnFontPlus", theme="#btnTheme", wake="#btnWake")
        await pg.locator("#btnNext").tap(); await pg.wait_for_timeout(1500); await propre(pg)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "l2_suivant", suiv="#btnNext")
        await pg.evaluate("scrollTo(0,330)")
        await shot(pg, "l3_texte", lecture="#verses")
        for _ in range(2):
            await pg.locator("#btnFontPlus").tap(); await pg.wait_for_timeout(400)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "l4_grand", aplus="#btnFontPlus")
        for _ in range(2):
            await pg.locator("#btnFontMinus").tap(); await pg.wait_for_timeout(300)
        await pg.locator("#btnTheme").tap(); await pg.wait_for_timeout(1200)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "l5_clair", theme="#btnTheme", wake="#btnWake")
        await pg.locator("#btnTheme").tap(); await pg.wait_for_timeout(800)
        await pg.close()

        # ---------- 2. Toucher un verset
        pg = await app(ctx, "#Jean-3:16")
        v16 = '#verses .verse[data-v="16"]'
        await vers(pg, v16)
        await shot(pg, "t1_lecture", v16=v16)
        await pg.locator(v16).tap(); await pg.wait_for_timeout(1200)
        await vers(pg, "#verseActionBar")
        await shot(pg, "t2_barre", bar="#verseActionBar", v16=v16)
        POS["t2_barre"]["btns"] = await pg.evaluate(
            "[...document.querySelectorAll('#verseActionBar>button')].map(b=>{const r=b.getBoundingClientRect();return [b.getAttribute('aria-label'),r.x,r.y,r.width,r.height]})")
        await pg.locator('#verseActionBar button[aria-label="Ajouter le verset suivant"]').tap(); await pg.wait_for_timeout(1200)
        await vers(pg, "#verseActionBar")
        await shot(pg, "t3_plus", bar="#verseActionBar")
        await pg.locator("#verseActionBar .btnRefs").tap(); await pg.wait_for_timeout(1200)
        await pg.evaluate("(()=>{const r=document.getElementById('verseActionBar').getBoundingClientRect();scrollBy({top:r.top-150,behavior:'instant'})})()")
        await shot(pg, "t4_refs", bar="#verseActionBar")
        img = await pg.evaluate("""async()=>{const b=state.bible.books.find(x=>/^Jean$/.test(x.name));const t=document.querySelector('#verses .verse[data-v="16"]').innerText.replace(/^\\s*16\\s*/,'');const cv=await renderVerseImage(b.name,3,16,t,16);return cv.toDataURL('image/jpeg',0.92)}""")
        open("cap/t5_image.jpg", "wb").write(base64.b64decode(img.split(",")[1]))
        # favori pour la bibliotheque
        await pg.locator("#verseActionBar button[aria-label='Fermer']").tap(); await pg.wait_for_timeout(500)
        await pg.locator(v16).tap(); await pg.wait_for_timeout(800)
        await pg.locator("#verseActionBar button[aria-label='Ajouter aux favoris']").tap(); await pg.wait_for_timeout(800)
        await pg.close()

        # ---------- 3. Rechercher
        pg = await app(ctx, "#Genèse-1")
        await pg.evaluate("scrollTo(0,0)")
        await pg.locator("#globalSearchInput").tap()
        await pg.locator("#globalSearchInput").type("Jean 3:16", delay=40)
        await shot(pg, "r1_ref", champ="#globalSearchInput", bouton="#globalSearchBtn")
        await pg.locator("#globalSearchBtn").tap(); await pg.wait_for_timeout(2000); await propre(pg)
        res = pg.locator("#gResultsList .gResultItem").first
        bb = await res.bounding_box()
        await shot(pg, "r1b_resultat")
        POS["r1b_resultat"]["res"] = [bb["x"], bb["y"], bb["width"], bb["height"]]
        await res.tap(); await pg.wait_for_timeout(1200)
        await shot(pg, "r1c_deplie", texte="#gResultsList .gResultItem .gResultText")
        await pg.locator("#gResultsList .gResultItem .gResultText").first.tap(); await pg.wait_for_timeout(2000); await propre(pg)
        await vers(pg, '#verses .verse[data-v="16"]')
        await shot(pg, "r2_ouvert", v16='#verses .verse[data-v="16"]')
        await pg.evaluate("scrollTo(0,0)")
        await pg.locator("#globalSearchInput").fill("")
        await pg.locator("#globalSearchInput").type("berger", delay=60)
        await shot(pg, "r3_mot", champ="#globalSearchInput", bouton="#globalSearchBtn")
        await pg.locator("#globalSearchBtn").tap(); await pg.wait_for_timeout(2500); await propre(pg)
        await shot(pg, "r4_resultats")
        await pg.evaluate("scrollBy(0,250)")
        await shot(pg, "r5_resultats_bas")
        await pg.close()

        # ---------- 4. Verset du jour + 6. Bibliotheque
        pg = await app(ctx, "#Romains-8")
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "j1_bouton", vdd="#btnVDD")
        await pg.locator("#btnVDD").tap(); await pg.wait_for_timeout(2000); await propre(pg)
        await shot(pg, "j2_ouvert")
        await pg.locator('.tab[data-view="library"]').first.tap(); await pg.wait_for_timeout(1500)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "b1_biblio", vddbox="#vddBox", ouvrir="#btnOpenVDD", copier="#btnCopyVDD", image="#btnImgVDD",
                   favs="#btnClearFav", hist="#btnClearHistory")
        await pg.evaluate("scrollBy(0,330)")
        await shot(pg, "b2_biblio_bas")
        img = await pg.evaluate("""async()=>{const r=state.vddRef;const b=state.bible.books[r.bi];const t=(document.getElementById('vddBox').textContent.split(' — ')[1]||'').trim();const cv=await renderVerseImage(b.name,r.c,r.v,t,r.v);return cv.toDataURL('image/jpeg',0.92)}""")
        open("cap/j3_image.jpg", "wb").write(base64.b64decode(img.split(",")[1]))

        # ---------- 5. Plan
        await pg.locator('.tab[data-view="plan"]').first.tap(); await pg.wait_for_timeout(1500)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "p1_plan", lu="#btnMarkDone", ouvrir="#btnOpenToday", jour="#btnJumpDay")
        await pg.locator("#btnMarkDone").tap(); await pg.wait_for_timeout(1500)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "p2_lu", lu="#btnMarkDone")

        # ---------- 7. Versets par theme
        await pg.locator('.tab[data-view="versets"]').first.tap(); await pg.wait_for_timeout(2000)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "v1_themes")
        prot = pg.get_by_text("Protection", exact=True).first
        box = await prot.bounding_box()
        POS["v1_themes"]["protection"] = [box["x"], box["y"], box["width"], box["height"]] if box else None
        await prot.tap(); await pg.wait_for_timeout(2000)
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "v2_theme")
        await pg.evaluate("scrollBy(0,420)")
        await shot(pg, "v3_theme_bas")
        await pg.close()

        # ---------- 8. Bible audio
        pg = await ctx.new_page()
        await pg.goto(U + "bible-audio.html", wait_until="load"); await pg.wait_for_timeout(3000)
        await shot(pg, "a1_audio")
        gen = pg.get_by_text("Genèse", exact=True).first
        await gen.scroll_into_view_if_needed()
        await pg.evaluate("scrollBy(0,-200)")
        box = await gen.bounding_box()
        await shot(pg, "a2_livres")
        POS["a2_livres"]["genese"] = [box["x"], box["y"], box["width"], box["height"]] if box else None
        await gen.tap(); await pg.wait_for_timeout(2000)
        await shot(pg, "a3_chapitres")
        await pg.close()

        # ---------- 9. Quiz (on recommence jusqu'a tomber sur la bonne reponse)
        pg = await ctx.new_page()
        for essai in range(10):
            await pg.goto(U + "quiz.html", wait_until="load"); await pg.wait_for_timeout(2000)
            if essai == 0:
                await shot(pg, "q1_themes")
            ps = pg.get_by_text("Psaumes", exact=True).first
            box = await ps.bounding_box()
            POS.setdefault("q1_themes", {})["psaumes"] = [box["x"], box["y"], box["width"], box["height"]]
            await ps.tap(); await pg.wait_for_timeout(1200)
            k = essai % 3
            opt = pg.locator(".optBtn").nth(k)
            await shot(pg, "q2_question")
            bb = await opt.bounding_box()
            POS["q2_question"]["choix"] = [bb["x"], bb["y"], bb["width"], bb["height"]]
            await opt.tap(); await pg.wait_for_timeout(1200)
            if "good" in (await opt.get_attribute("class") or ""):
                await shot(pg, "q3_reponse"); break
        await pg.close()

        # ---------- 10. Installer
        pg = await app(ctx, "#Psaumes-121")
        await pg.evaluate("scrollTo(0,0)")
        await shot(pg, "i1_bouton", inst="#btnInstall")
        await pg.goto(U + "installer.html", wait_until="load"); await pg.wait_for_timeout(2000)
        await shot(pg, "i2_page")
        await pg.evaluate("scrollBy(0,700)")
        await shot(pg, "i3_page_bas")
        await pg.close()

        json.dump(POS, open("cap/serie.json", "w"), ensure_ascii=False, indent=1)
        await b.close()

asyncio.run(main())
