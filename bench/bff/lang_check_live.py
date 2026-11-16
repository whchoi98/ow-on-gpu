"""배포된 사이트에서 화면이 x-lang을 보내고 BFF가 그 언어로 답하는지 확인한다.

토큰 없는 요청과 가짜 토큰만 쓰므로 BFF는 401을 돌려준다. 모델까지 가는 요청은 없고 로그인 비밀번호가 필요 없다.
결과에는 사이트 주소를 남기지 않는다.

    python bench/bff/lang_check_live.py https://<사이트 주소> > live.json
"""
import json
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

url = sys.argv[1].rstrip("/")
FAKE_SESSION = "sessionStorage.setItem('ow-on-gpu.session', JSON.stringify({email: 'check@example.com', token: 'x'}))"


def without_token(lang):
    """토큰 없이 보낸 요청의 상태 코드와 오류 문구."""
    headers = {"content-type": "application/json", **({"x-lang": lang} if lang else {})}
    request = urllib.request.Request(url + "/v1/chat/completions", method="POST", headers=headers,
                                     data=json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode())
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return {"x-lang": lang, "status": response.status}
    except urllib.error.HTTPError as error:
        return {"x-lang": lang, "status": error.code, "message": json.loads(error.read())["error"]["message"]}


def from_page(browser, english):
    """가짜 세션으로 화면을 열어 요청을 보낸다. 화면이 실은 x-lang, BFF의 응답, 401 뒤의 화면을 돌려준다."""
    calls, errors = [], []
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.add_init_script(FAKE_SESSION)
    page.on("pageerror", lambda error: errors.append(str(error)))

    def on_response(response):
        if "/v1/" in response.url:
            try:
                message = response.json().get("error", {}).get("message")
            except Exception:
                message = None
            calls.append({"path": response.url.split("/v1/")[1], "x-lang": response.request.headers.get("x-lang"),
                          "status": response.status, "message": message})

    page.on("response", on_response)
    page.goto(url + "/")
    page.wait_for_load_state("networkidle")
    if english:
        page.get_by_role("button", name="English", exact=True).click()
        page.wait_for_timeout(300)
    page.get_by_role("button", name="Send" if english else "보내기", exact=True).click()
    page.wait_for_timeout(2500)
    notice = [text.strip() for text in page.locator("[role=alert], [role=status]").all_inner_texts() if text.strip()]
    result = {"page": "en" if english else "ko", "calls": calls, "after_401_heading": page.locator("h1, h2").first.inner_text(),
              "after_401_notice": notice[:2], "page_errors": errors,
              "script": page.locator("script[src*='assets/index-']").first.get_attribute("src")}
    page.close()
    return result


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    pages = [from_page(browser, english) for english in (False, True)]
    browser.close()
print(json.dumps({"without_token": [without_token(lang) for lang in (None, "ko", "en", "fr")], "pages": pages},
                 ensure_ascii=False, indent=1))
