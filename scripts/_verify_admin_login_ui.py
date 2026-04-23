"""One-off Playwright check: admin can focus inputs and sign in on Streamlit auth page."""

from __future__ import annotations

from playwright.sync_api import sync_playwright


def main() -> int:
    base = "http://127.0.0.1:8501"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(90_000)
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(3000)
        user = page.get_by_placeholder("your.name")
        user.wait_for(state="visible")
        user.click()
        user.fill("admin")
        page.get_by_label("Password", exact=True).fill("admin")
        # Streamlit uses data-testid=stForm, not a native <form>.
        page.locator('[data-testid="stForm"]').locator(
            '[data-testid="stBaseButton-primaryFormSubmit"]'
        ).click(force=True)
        page.get_by_text("Administrator", exact=False).wait_for(
            state="visible", timeout=90_000
        )
        page.get_by_role("button", name="Log out").wait_for(state="visible")
        browser.close()
    print("OK: admin login UI flow succeeded (inputs focusable, sign-in works).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
