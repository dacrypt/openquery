"""Universal CAPTCHA detection and solving middleware.

Auto-detects CAPTCHAs on browser pages and solves them using the best
available solver. Supports:
- reCAPTCHA v2 (standard + invisible + Enterprise)
- Cloudflare Turnstile
- Image-based CAPTCHAs (BotDetect, custom)
- Imperva/Incapsula bot challenges

Usage:
    from openquery.core.captcha_middleware import solve_page_captchas

    with browser.page(url) as page:
        # ... fill form ...
        solved = solve_page_captchas(page)
        # ... submit form ...
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── CAPTCHA Type Detection ────────────────────────────────────────────────

def detect_captcha_type(page: Any) -> str | None:
    """Detect what type of CAPTCHA is present on the page.

    Returns:
        One of: "recaptcha_v2", "recaptcha_enterprise", "turnstile",
                "image", "imperva", or None if no CAPTCHA detected.
    """
    # reCAPTCHA v2 / Enterprise
    recaptcha_frame = page.query_selector(
        'iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"]'
    )
    recaptcha_div = page.query_selector('.g-recaptcha, [data-sitekey]')
    recaptcha_textarea = page.query_selector('#g-recaptcha-response, textarea[name="g-recaptcha-response"]')

    if recaptcha_frame or recaptcha_div or recaptcha_textarea:
        # Check if Enterprise
        enterprise_script = page.query_selector('script[src*="recaptcha/enterprise"]')
        if enterprise_script:
            logger.info("Detected: reCAPTCHA Enterprise")
            return "recaptcha_enterprise"
        logger.info("Detected: reCAPTCHA v2")
        return "recaptcha_v2"

    # Cloudflare Turnstile
    turnstile_frame = page.query_selector(
        'iframe[src*="challenges.cloudflare.com/turnstile"], '
        '.cf-turnstile, [data-sitekey][data-callback]'
    )
    if turnstile_frame:
        logger.info("Detected: Cloudflare Turnstile")
        return "turnstile"

    # Image CAPTCHA (BotDetect, custom, etc.)
    captcha_img = page.query_selector(
        'img[id*="captcha" i], img[alt*="captcha" i], img[src*="captcha" i], '
        'img[id*="Captcha"], img[class*="captcha" i], '
        '.BDC_CaptchaDiv img'  # BotDetect
    )
    if captcha_img:
        logger.info("Detected: Image CAPTCHA")
        return "image"

    # Imperva/Incapsula bot challenge
    imperva = page.query_selector(
        '#captcha-challenge, .vc-captcha, '
        'input[name="answer"][id="ans"]'  # Imperva bot challenge
    )
    if imperva:
        logger.info("Detected: Imperva bot challenge")
        return "imperva"

    return None


# ── CAPTCHA Solving ───────────────────────────────────────────────────────

def solve_page_captchas(page: Any, max_attempts: int = 3) -> bool:
    """Auto-detect and solve CAPTCHAs on the current page.

    Args:
        page: Playwright/Patchright page object.
        max_attempts: Maximum solving attempts for image CAPTCHAs.

    Returns:
        True if a CAPTCHA was detected and solved, False if no CAPTCHA found.

    Raises:
        CaptchaError: If CAPTCHA detected but all solvers fail.
    """
    captcha_type = detect_captcha_type(page)
    if not captcha_type:
        return False

    if captcha_type in ("recaptcha_v2", "recaptcha_enterprise"):
        return _solve_recaptcha(page)
    elif captcha_type == "turnstile":
        return _solve_turnstile(page)
    elif captcha_type == "image":
        return _solve_image_captcha(page, max_attempts)
    elif captcha_type == "imperva":
        return _solve_imperva(page)

    return False


def _solve_recaptcha(page: Any) -> bool:
    """Solve reCAPTCHA v2 using task-based solver services."""
    from openquery.core.captcha import (
        build_recaptcha_solver,
        extract_recaptcha_sitekey,
        inject_recaptcha_token,
    )

    sitekey = extract_recaptcha_sitekey(page)
    if not sitekey:
        logger.warning("reCAPTCHA detected but could not extract sitekey")
        return False

    solver = build_recaptcha_solver()
    if not solver:
        logger.warning(
            "reCAPTCHA detected but no solver configured. "
            "Set OPENQUERY_CAPSOLVER_API_KEY, OPENQUERY_CAPMONSTER_API_KEY, "
            "OPENQUERY_ANTICAPTCHA_API_KEY, or OPENQUERY_TWO_CAPTCHA_API_KEY"
        )
        return False

    logger.info("Solving reCAPTCHA v2 (sitekey=%s...)", sitekey[:20])
    try:
        token = solver.solve_recaptcha_v2(sitekey, page.url)
        inject_recaptcha_token(page, token)
        logger.info("reCAPTCHA solved and token injected")
        page.wait_for_timeout(1000)
        return True
    except Exception as e:
        logger.error("reCAPTCHA solving failed: %s", e)
        return False


def _solve_turnstile(page: Any) -> bool:
    """Solve Cloudflare Turnstile using CapSolver."""
    from openquery.config import get_settings

    settings = get_settings()
    api_key = settings.capsolver_api_key
    if not api_key:
        logger.warning(
            "Turnstile detected but no CapSolver API key. "
            "Set OPENQUERY_CAPSOLVER_API_KEY"
        )
        return False

    # Extract sitekey from Turnstile widget
    sitekey = page.evaluate("""() => {
        const el = document.querySelector('.cf-turnstile, [data-sitekey]');
        return el ? el.getAttribute('data-sitekey') : null;
    }""")

    if not sitekey:
        # Try from iframe src
        frame = page.query_selector('iframe[src*="challenges.cloudflare.com"]')
        if frame:
            src = frame.get_attribute("src") or ""
            import re
            match = re.search(r"k=([A-Za-z0-9_-]+)", src)
            if match:
                sitekey = match.group(1)

    if not sitekey:
        logger.warning("Turnstile detected but could not extract sitekey")
        return False

    logger.info("Solving Turnstile (sitekey=%s...)", sitekey[:20])

    try:
        import httpx

        # Create CapSolver task for Turnstile
        resp = httpx.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": api_key,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": page.url,
                    "websiteKey": sitekey,
                },
            },
            timeout=30,
        )
        data = resp.json()
        task_id = data.get("taskId")
        if not task_id:
            logger.error("CapSolver createTask failed: %s", data)
            return False

        # Poll for result
        import time
        for _ in range(24):  # 24 * 5s = 120s max
            time.sleep(5)
            resp = httpx.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": api_key, "taskId": task_id},
                timeout=15,
            )
            result = resp.json()
            if result.get("status") == "ready":
                token = result.get("solution", {}).get("token", "")
                if token:
                    # Inject Turnstile token
                    page.evaluate(f"""(token) => {{
                        const resp = document.querySelector('input[name="cf-turnstile-response"], #cf-chl-widget-response');
                        if (resp) resp.value = token;
                        // Also try g-recaptcha-response (compatibility mode)
                        const gResp = document.querySelector('#g-recaptcha-response');
                        if (gResp) gResp.value = token;
                    }}""", token)
                    logger.info("Turnstile solved and token injected")
                    return True
            elif result.get("status") == "failed":
                logger.error("Turnstile solving failed: %s", result)
                return False

    except Exception as e:
        logger.error("Turnstile solving error: %s", e)

    return False


def _solve_image_captcha(page: Any, max_attempts: int = 3) -> bool:
    """Solve image CAPTCHA using LLM vision + OCR chain."""
    # Find CAPTCHA image
    captcha_img = page.query_selector(
        'img[id*="captcha" i], img[alt*="captcha" i], img[src*="captcha" i], '
        'img[id*="Captcha"], img[class*="captcha" i], '
        '.BDC_CaptchaDiv img'
    )
    if not captcha_img:
        return False

    # Find CAPTCHA input
    captcha_input = page.query_selector(
        'input[id*="captcha" i], input[name*="captcha" i], '
        'input[id*="Captcha"], input[name*="Captcha"], '
        '#CaptchaCodeTextBox, #token, #txtCodigo, #captchacode'
    )
    if not captcha_input:
        logger.warning("CAPTCHA image found but no input field to fill")
        return False

    # Build solver chain: LLM vision → PaddleOCR → EasyOCR → Tesseract
    chain = _build_vision_chain()

    for attempt in range(1, max_attempts + 1):
        try:
            image_bytes = captcha_img.screenshot()
            if not image_bytes or len(image_bytes) < 100:
                logger.warning("CAPTCHA image screenshot too small")
                continue

            text = chain.solve(image_bytes)
            if text:
                captcha_input.fill(text)
                logger.info("Image CAPTCHA solved (attempt %d): %s", attempt, text)
                return True
        except Exception as e:
            logger.warning("CAPTCHA solve attempt %d failed: %s", attempt, e)

        # Try refreshing the CAPTCHA
        refresh = page.query_selector(
            'a[href*="refrescar" i], button[id*="reload" i], '
            'img[id*="reload" i], a[onclick*="captcha" i], '
            '#c_index_examplecaptcha_ReloadIcon'
        )
        if refresh:
            refresh.click()
            page.wait_for_timeout(1000)

    return False


def _solve_imperva(page: Any) -> bool:
    """Solve Imperva/Incapsula bot challenge."""
    # Imperva challenges are usually simple image CAPTCHAs
    return _solve_image_captcha(page, max_attempts=2)


def _build_vision_chain():
    """Build a CAPTCHA solver chain prioritizing LLM vision."""
    from openquery.core.captcha import ChainedSolver, LLMCaptchaSolver, OCRSolver

    solvers = []

    # 1. LLM vision (most accurate for novel CAPTCHAs)
    try:
        solver = LLMCaptchaSolver()
        solvers.append(solver)
        logger.debug("Added LLM vision solver to chain")
    except Exception:
        pass

    # 2. PaddleOCR (best local accuracy)
    try:
        from openquery.core.captcha import PaddleOCRSolver
        solvers.append(PaddleOCRSolver())
        logger.debug("Added PaddleOCR solver to chain")
    except ImportError:
        pass

    # 3. Tesseract (always available)
    solvers.append(OCRSolver(max_chars=6))

    return ChainedSolver(solvers)
