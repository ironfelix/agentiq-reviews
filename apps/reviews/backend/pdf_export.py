"""PDF export via Playwright — render HTML string to PDF."""
from playwright.async_api import async_playwright


async def html_to_pdf(html_content: str) -> bytes:
    """Convert HTML string to PDF bytes using Playwright Chromium.

    Opens all <details> elements before printing so expandable
    sections ("Как стоило ответить") appear in the PDF.
    Dark background is preserved via print_background=True.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.set_content(html_content, wait_until="networkidle")

        # Open all <details> so recommendations are visible in PDF
        await page.evaluate("""
            () => {
                document.querySelectorAll('details').forEach(d => d.open = true);
                // Hide nav/back links in print
                const nav = document.querySelector('.nav');
                if (nav) nav.style.display = 'none';
            }
        """)

        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "16px", "bottom": "16px", "left": "16px", "right": "16px"},
        )

        await browser.close()

    return pdf_bytes
