import sys, asyncio, pathlib
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "snapshots"
OUT.mkdir(exist_ok=True)
from playwright.async_api import async_playwright
BASE = (HERE / "prototype" / "index.html").as_uri()
SHOTS = [
  # name, query, w, h, full_page
  ("01-food-desktop-light", "view=food&theme=light", 1440, 1100, True),
  ("02-food-desktop-dark", "view=food&theme=dark", 1440, 1100, True),
  ("03-event-drawer-desktop", "view=food&theme=light&open=f1", 1440, 960, False),
  ("04-source-filter-desktop", "view=food&theme=light&popover=sources", 1440, 760, False),
  ("05-events-desktop", "view=events&theme=light", 1440, 1000, True),
  ("06-deadlines-desktop", "view=deadlines&theme=light", 1440, 1000, True),
  ("07-deadlines-desktop-dark", "view=deadlines&theme=dark&open=d2", 1440, 960, False),
  ("08-mobile-food", "view=food&theme=light", 390, 844, False),
  ("09-mobile-food-scrolled", "view=food&theme=light", 390, 1900, True),
  ("10-mobile-detail-sheet", "view=food&theme=light&open=f1", 390, 844, False),
  ("11-mobile-deadlines-dark", "view=deadlines&theme=dark", 390, 844, False),
  ("12-loading-desktop", "view=food&theme=light&state=loading", 1440, 900, False),
  ("13-error-desktop", "view=food&theme=light&state=error", 1440, 900, False),
  ("14-empty-saved-mobile", "view=saved&theme=light&state=empty", 390, 844, False),
  ("15-offline-mobile-dark", "view=food&theme=dark&state=offline", 390, 844, False),
]
only = sys.argv[1:]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, q, w, h, full in SHOTS:
            if only and not any(o in name for o in only): continue
            mobile = w < 500
            ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile)
            pg = await ctx.new_page()
            await pg.emulate_media(reduced_motion="reduce")
            await pg.goto(f"{BASE}?{q}")
            await pg.wait_for_timeout(300)
            if "scrolled" in name: await pg.add_style_tag(content=".bottom-nav{position:static}")
            await pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
            await ctx.close()
        await b.close()
asyncio.run(main())
