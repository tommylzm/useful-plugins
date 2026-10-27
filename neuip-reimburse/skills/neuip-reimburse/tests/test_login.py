from scripts import login

CFG = {
    "base_url": "https://cloud.nueip.com",
    "endpoints": {"submit": {"method": "POST", "path": "/payment_request"}},
    "headers": {"X-Requested-With": "XMLHttpRequest"},
    "csrf": {"cookie": "csrf_token", "header": "X-Csrf-Token"},
}


def test_should_probe_only_after_leaving_login_page():
    assert login._should_probe("https://portal.nueip.com/login") is False
    assert login._should_probe("https://portal.nueip.com/login?redirect=x") is False
    assert login._should_probe("about:blank") is False
    assert login._should_probe("https://accounts.google.com/o/oauth2") is False  # SSO hop
    assert login._should_probe("https://portal.nueip.com/home") is True
    assert login._should_probe("https://cloud.nueip.com/portal") is True


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeRequest:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, form=None, headers=None):
        self.calls.append({"url": url, "form": form, "headers": headers})
        return self.response


class FakeContext:
    def __init__(self, response, pages=()):
        self.request = FakeRequest(response)
        self.pages = list(pages)

    def cookies(self, urls=None):
        return [{"name": "csrf_token", "value": "TOK"}, {"name": "PHPSESSID", "value": "S"}]


def test_probe_true_when_api_returns_payroll_options():
    ctx = FakeContext(FakeResponse(200, [{"s_sn": "1", "name": "通勤補助"}]))
    assert login.probe(ctx, CFG) is True
    call = ctx.request.calls[0]
    assert call["url"] == "https://cloud.nueip.com/payment_request"
    assert call["form"]["action"] == "get_payroll_options"
    assert call["headers"]["X-Csrf-Token"] == "TOK"
    assert call["headers"]["X-Requested-With"] == "XMLHttpRequest"


def test_probe_false_when_unauthorized():
    assert login.probe(FakeContext(FakeResponse(401, {"error": "x"})), CFG) is False


def test_probe_false_when_redirected_to_html():
    assert login.probe(FakeContext(FakeResponse(200, ValueError("not json"))), CFG) is False


class FakePage:
    def __init__(self, url):
        self.url = url

    def wait_for_timeout(self, ms):
        pass


class Clock:
    def __init__(self, step):
        self.t = 0.0
        self.step = step

    def __call__(self):
        self.t += self.step
        return self.t


def test_wait_returns_true_once_logged_in(monkeypatch):
    page = FakePage("https://portal.nueip.com/login")
    ctx = FakeContext(None, pages=[page])
    probes = []

    def fake_probe(context, cfg):
        probes.append(page.url)
        return True

    monkeypatch.setattr(login, "probe", fake_probe)

    def tick():                                  # user finishes logging in on the 3rd poll
        tick.n += 1
        if tick.n == 3:
            page.url = "https://portal.nueip.com/home"
        return float(tick.n)
    tick.n = 0

    assert login._wait_for_login(ctx, CFG, timeout_s=60, alive=lambda: True, clock=tick) is True
    assert probes == ["https://portal.nueip.com/home"]   # never probed while on /login


def test_wait_returns_false_when_window_closed(monkeypatch):
    monkeypatch.setattr(login, "probe", lambda c, cfg: False)
    ctx = FakeContext(None, pages=[])
    assert login._wait_for_login(ctx, CFG, timeout_s=60, alive=lambda: True, clock=Clock(1)) is False


def test_wait_returns_false_when_browser_gone(monkeypatch):
    monkeypatch.setattr(login, "probe", lambda c, cfg: False)
    ctx = FakeContext(None, pages=[FakePage("https://portal.nueip.com/login")])
    assert login._wait_for_login(ctx, CFG, timeout_s=60, alive=lambda: False, clock=Clock(1)) is False


def test_wait_times_out(monkeypatch):
    monkeypatch.setattr(login, "probe", lambda c, cfg: False)
    ctx = FakeContext(None, pages=[FakePage("https://portal.nueip.com/login")])
    assert login._wait_for_login(ctx, CFG, timeout_s=5, alive=lambda: True, clock=Clock(1)) is False
