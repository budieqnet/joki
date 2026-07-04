import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_list_dir(args):
        items = os.listdir(args["path"])
        lines = []
        for item in sorted(items):
            full = os.path.join(args["path"], item)
            label = "DIR" if os.path.isdir(full) else "   "
            lines.append(f"{label} {item}")
        return "\n".join(lines)


def handle_service_control(args):
        svc = args["service"]
        act = args["action"]
        is_macos = sys.platform == 'darwin'
        if act == "status":
            with _Spinner(f"{act} {svc}"):
                if os.name == 'nt':
                    r = subprocess.run(
                        f"sc query {svc}", shell=True,
                        capture_output=True, text=True, timeout=30
                    )
                elif is_macos:
                    r = subprocess.run(
                        f"launchctl list | grep -i {svc} || launchctl print system/{svc} 2>/dev/null || echo 'Service {svc} tidak ditemukan'",
                        shell=True, capture_output=True, text=True, timeout=30
                    )
                else:
                    r = subprocess.run(
                        f"systemctl status {svc} --no-pager -l", shell=True,
                        capture_output=True, text=True, timeout=30
                    )
        else:
            sudo_password = _prompt_sudo()
            if os.name == 'nt':
                actual_cmd = f"net {act} {svc}"
            elif is_macos:
                if act == "enable":
                    actual_cmd = f"launchctl load -w /System/Library/LaunchDaemons/{svc}.plist 2>/dev/null || launchctl enable system/{svc}"
                elif act == "disable":
                    actual_cmd = f"launchctl unload -w /System/Library/LaunchDaemons/{svc}.plist 2>/dev/null || launchctl disable system/{svc}"
                elif act == "restart":
                    actual_cmd = f"launchctl kickstart -k system/{svc} 2>/dev/null || (launchctl stop {svc} 2>/dev/null; sleep 1; launchctl start {svc} 2>/dev/null)"
                else:
                    actual_cmd = f"launchctl {act} {svc}"
            else:
                actual_cmd = f"systemctl {act} {svc}"
            if sudo_password:
                with _Spinner(f"{act} {svc}"):
                    r = _run_elevated(actual_cmd, sudo_password)
            else:
                cmd = f"sudo {actual_cmd}" if sudo_password != "__ROOT__" else actual_cmd
                with _Spinner(f"{act} {svc}"):
                    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip() or f"OK: {act} {svc}"


def handle_config_edit(args):
        path = args["path"]
        if not os.path.exists(path):
            return f"Error: file not found: {path}"

        with open(path) as f:
            content = f.read()

        directive = args.get("directive")
        set_value = args.get("set_value")

        if not directive:
            return _numbered(content)

        # Show current value
        pattern = re.compile(rf'^\s*{re.escape(directive)}\s+(.+)$', re.MULTILINE)
        matches = pattern.findall(content)
        if not set_value:
            if not matches:
                return f"Directive '{directive}' not found in {path}"
            return f"Current value(s) for '{directive}': {matches}"

        # Backup then edit
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(BACKUP_DIR, os.path.basename(path) + ".bak")
        shutil.copy2(path, backup_path)

        if matches:
            # Replace first occurrence
            new_content = pattern.sub(f"{directive} {set_value}", content, count=1)
        else:
            # Append at end
            new_content = content.rstrip() + f"\n{directive} {set_value}\n"

        with open(path, "w") as f:
            f.write(new_content)

        return f"Backup saved: {backup_path}\nEdited: {directive} → {set_value}"


def handle_package_check(args):
        app = args["app"]
        # Check via which, dpkg, rpm, etc.
        checks = [
            f"which {app} 2>/dev/null",
            f"command -v {app} 2>/dev/null",
            f"dpkg -l {app} 2>/dev/null | grep '^ii'",
            f"rpm -q {app} 2>/dev/null"
        ]
        for c in checks:
            r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                return f"INSTALLED: {r.stdout.strip()}"
        return f"NOT INSTALLED: {app} tidak ditemukan di system"


def handle_web_fetch(args):
        with _Spinner("Mengambil konten web"):
            r = httpx.get(args["url"], timeout=30, follow_redirects=True)
            r.raise_for_status()
        return r.text


def handle_web_search(args):
        with _Spinner("Mencari di web"):
            results = DDGS().text(args["query"], max_results=args.get("max_results", 5))
        if not results:
            return "(no results)"
        lines = []
        for r in results:
            lines.append(f"- {r['title']}\n  {r['href']}\n  {r['body']}")
        return "\n\n".join(lines)


def handle_test_and_fix(args):
        try:
            with _Spinner("Mengetes"):
                r = subprocess.run(args["cmd"], shell=True, capture_output=True, text=True, timeout=60)
            output = r.stdout + r.stderr
            if r.returncode != 0:
                return f"FAILED (exit code {r.returncode})\n{output}"
            return f"SUCCESS\n{output}"
        except subprocess.TimeoutExpired:
            return "FAILED (timeout)"


def handle_screenshot(args):
        path = args.get("path", f"/tmp/joki_screenshot_{int(time.time())}.png")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        cmds = [
            f"scrot '{path}'",
            f"import -window root '{path}'",
            f"gnome-screenshot -f '{path}'"
        ]
        for cmd in cmds:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                size = os.path.getsize(path)
                return f"Screenshot saved: {path} ({size} bytes)"
        return "Error: gagal mengambil screenshot. Install scrot: sudo apt install scrot"


def handle_whois_lookup(args):
        target = args["target"]
        with _Spinner(f"WHOIS lookup {target}"):
            r = subprocess.run(
                ["whois", target],
                capture_output=True, text=True, timeout=30
            )
        output = r.stdout or r.stderr
        if not output:
            return f"  No WHOIS data for {target} (install whois: sudo apt install whois)"
        lines = output.splitlines()
        important = []
        keywords = ["domain", "registrar", "registrant", "admin", "creation date",
                    "expir", "name server", "status", "org", "organization", "email",
                    "phone", "address", "country", "referral", "whois", "inetnum",
                    "netname", "descr", "role", "nic-hdl", "mnt-by", "source"]
        for line in lines:
            if any(k.lower() in line.lower() for k in keywords):
                important.append(f"  {line.strip()}")
        if important:
            return f"[WHOIS] {target}:\n" + "\n".join(important[:40])
        return f"[WHOIS] {target}:\n" + "\n".join(f"  {l}" for l in lines[:30])


def handle_ssl_check(args):
        host = args["host"]
        port = int(args.get("port", 443))
        output = []

        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    output.append(f"  Host: {host}:{port}")
                    output.append(f"  Protocol: {ssock.version()}")

                    if cert:
                        output.append(f"  Subject: {dict(cert['subject'][0]).get('commonName', 'N/A')}")
                        output.append(f"  Issuer: {dict(cert['issuer'][0]).get('organizationName', 'N/A')}")
                        output.append(f"  Serial: {cert.get('serialNumber', 'N/A')}")
                        output.append(f"  Valid From: {cert.get('notBefore', 'N/A')}")
                        output.append(f"  Valid Until: {cert.get('notAfter', 'N/A')}")

                        import datetime
                        not_after = cert.get('notAfter', '')
                        if not_after:
                            try:
                                exp = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                                remaining = (exp - datetime.datetime.now()).days
                                if remaining < 0:
                                    output.append(f"  \033[31mEXPIRED ({abs(remaining)} days ago)\033[0m")
                                elif remaining < 30:
                                    output.append(f"  \033[33mExpiring soon: {remaining} days\033[0m")
                                else:
                                    output.append(f"  \033[32mValid: {remaining} days remaining\033[0m")
                            except Exception:
                                pass

                        san = cert.get('subjectAltName', [])
                        if san:
                            domains = [v for k, v in san if k == 'DNS']
                            output.append(f"  SAN: {', '.join(domains[:5])}{'...' if len(domains) > 5 else ''}")
                    else:
                        output.append("  No certificate returned")
        except ssl.SSLError as e:
            output.append(f"  SSL Error: {e}")
        except Exception as e:
            output.append(f"  Connection Error: {e}")

        if not output:
            return f"[SSL] No response from {host}:{port}"
        return f"[SSL] Certificate check for {host}:{port}\n" + "\n".join(output)


def handle_dir_bruteforce(args):
        url = args["url"].rstrip("/")
        wordlist_size = args.get("wordlist", "small")
        extensions = args.get("extensions", "")
        ext_list = [f".{e.strip()}" for e in extensions.split(",") if e.strip()] if extensions else []

        wordlists = {
            "small": ["admin", "login", "wp-admin", "backup", "config", "db", "sql",
                      "admin.php", "login.php", "config.php", ".env", "wp-config.php",
                      "robots.txt", "sitemap.xml", "index.php", "index.html", "test",
                      "api", "v1", "v2", "static", "assets", "uploads", "images",
                      "css", "js", "private", "secret", "hidden", "tmp", "temp",
                      "logs", "error_log", "phpinfo.php", "info.php", "shell.php",
                      "cmd.php", "upload.php", "download.php", "cgi-bin", "cron",
                      "setup", "install", "readme.html", "license.txt"],
            "medium": [],  # Will use small + more
            "large": []
        }

        if wordlist_size == "medium":
            wordlists["medium"] = wordlists["small"] + [
                "app", "src", "lib", "include", "inc", "modules", "plugins",
                "themes", "templates", "cache", "data", "dump", "export",
                "import", "manager", "panel", "dashboard", "user", "users",
                "member", "members", "account", "register", "signup", "forgot",
                "reset", "password", "profile", "edit", "settings", "preferences",
                "ajax", "rest", "graphql", "ws", "websocket", "soap", "xmlrpc",
                "rss", "feed", "atom", "json", "csv", "txt", "xml", "pdf",
                "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "pdf",
            ]

        if wordlist_size == "large":
            wordlists["large"] = wordlists["medium"] + [
                "0", "1", "2", "3", "a", "b", "c", "d", "e", "f", "g", "h",
                "old", "new", "bak", "copy", "original", "latest", "final",
                "working", "dev", "development", "staging", "prod", "production",
                "local", "live", "master", "main", "release", "patch", "hotfix",
                "docker", "docker-compose.yml", "Dockerfile", "Makefile",
                "package.json", "composer.json", "pom.xml", "build.gradle",
                "Procfile", "requirements.txt", "Gemfile", "Podfile",
                ".gitignore", ".htaccess", ".htpasswd", ".svn", ".DS_Store",
                "Thumbs.db", "crossdomain.xml", "clientaccesspolicy.xml",
                "web.config", "application.properties", "log4j.properties",
                "struts.xml", "web.xml", "index.jsp", "default.aspx",
            ]

        paths = wordlists.get(wordlist_size, wordlists["small"])

        found = []
        with _Spinner(f"Bruteforcing {url} ({len(paths)} paths)"):
            for path in paths:
                test_url = f"{url}/{path}"
                try:
                    rr = httpx.get(test_url, timeout=5, verify=False)
                    if rr.status_code in (200, 201, 204, 301, 302, 307, 308, 401, 403):
                        size = len(rr.content)
                        found.append(f"  {rr.status_code:>3}  {size:>8}b  {test_url}")
                except Exception:
                    pass

                if ext_list:
                    for ext in ext_list:
                        test_url_ext = f"{url}/{path}{ext}"
                        try:
                            rr = httpx.get(test_url_ext, timeout=5, verify=False)
                            if rr.status_code in (200, 201, 204, 301, 302, 307, 308, 401, 403):
                                size = len(rr.content)
                                found.append(f"  {rr.status_code:>3}  {size:>8}b  {test_url_ext}")
                        except Exception:
                            pass

        if not found:
            return f"[DIRBRUTE] No paths found on {url} ({len(paths)} tested)"
        return f"[DIRBRUTE] Found {len(found)} paths on {url}:\n" + "\n".join(found)


def handle_cve_search(args):
        query = args["query"]
        with _Spinner(f"Searching CVEs for {query}"):
            try:
                search_url = f"https://cve.circl.lu/api/search/{query.replace(' ', '/')}"
                r = httpx.get(search_url, timeout=20, follow_redirects=True, verify=False)
                if r.status_code == 200:
                    data = r.json()
                else:
                    data = None
            except Exception:
                data = None

        output = []
        if data and isinstance(data, list):
            cves = data[:15]
            for cve in cves:
                cve_id = cve.get("id", "N/A")
                summary = cve.get("summary", "")[:200]
                cvss = cve.get("cvss_score", "N/A")
                severity = cve.get("severity", "")
                output.append(f"  {cve_id} (CVSS: {cvss} {severity})")
                output.append(f"    {summary}")
                output.append("")
            if not output:
                output.append(f"  No CVEs found for '{query}'")
        else:
            output.append(f"  CIRCL API unavailable, searching via web...")
            try:
                results = DDGS().text(f"CVE {query}", max_results=5)
                if results:
                    for r in results:
                        output.append(f"  {r['title']}")
                        output.append(f"    {r['href']}")
                        output.append(f"    {r['body'][:200]}")
                        output.append("")
                else:
                    output.append(f"  No results found for '{query}'")
            except Exception:
                output.append(f"  Error searching for '{query}'")

        return f"[CVE] Results for '{query}':\n" + "\n".join(output)


def handle_tech_detect(args):
        url = args["url"].rstrip("/")
        deep = args.get("deep", "simple")
        output = []
        tech = {}

        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            return f"[TECH] Error accessing {url}: {e}"

        output.append(f"  URL: {url}")
        output.append(f"  Status: {r.status_code}")
        output.append(f"  Content-Type: {r.headers.get('Content-Type', 'N/A')}")

        output.append("\n  [HTTP Headers]")
        interesting_headers = [
            "Server", "X-Powered-By", "X-Generator", "X-Drupal-Cache",
            "X-Drupal-Dynamic-Cache", "X-Varnish", "X-Cache", "X-Cache-Hits",
            "CF-RAY", "X-Server-Powered-By", "X-AspNet-Version", "X-Runtime",
            "Via", "X-Proxy-Cache", "X-Served-By", "X-CMS", "X-Version",
            "Access-Control-Allow-Origin", "X-Frame-Options",
            "X-Content-Type-Options", "Strict-Transport-Security"
        ]
        for h in interesting_headers:
            val = r.headers.get(h)
            if val:
                output.append(f"    {h}: {val}")

        output.append("\n  [Cookies]")
        for cookie in r.cookies:
            name = cookie.name
            output.append(f"    {name}")

        if deep == "deep":
            html = r.text.lower()

            detectors = {
                "WordPress": ["wp-content", "wp-includes", "wp-json", "wordpress"],
                "Drupal": ["drupal", "drupal.js", "sites/default"],
                "Joomla": ["joomla", "com_content", "com_users"],
                "Laravel": ["laravel", "csrf-token", "livewire"],
                "Django": ["csrfmiddlewaretoken", "django", "__admin"],
                "Ruby on Rails": ["rails", "csrf-param", "authenticity_token"],
                "React": ["react", "react-dom", "__NEXT_DATA__", "nextjs", "next/js"],
                "Vue.js": ["vue", "vuejs", "v-bind", "v-model", "vue-router"],
                "Angular": ["ng-app", "ng-controller", "angular", "ng-version"],
                "jQuery": ["jquery", "$.fn", "jquery-"],
                "Bootstrap": ["bootstrap", "bootstrap-", "bs-"],
                "Tailwind": ["tailwind", "tailwindcss"],
                "Alpine.js": ["alpinejs", "x-data", "x-init", "x-on"],
                "HTMX": ["htmx", "hx-get", "hx-post", "hx-trigger"],
                "PHP": [".php", "php-session"],
                "ASP.NET": ["__viewstate", "__eventvalidation", "asp.net", "aspnet"],
                "Java": ["javax.faces", "jsf", "spring", "struts"],
                "Nginx": ["nginx", "nginx/"],
                "Apache": ["apache/", "apache", ".htaccess"],
                "Cloudflare": ["cloudflare", "cf-ray", "__cfduid"],
                "Google Analytics": ["gtag", "ga.js", "analytics.js", "google-analytics"],
                "Facebook Pixel": ["fbq(", "facebook pixel", "connect.facebook"],
                "Hotjar": ["hotjar", "hj("],
                "Intercom": ["intercom", "intercom-script"],
                "Stripe": ["stripe", "pk_live", "sk_live"],
                "Google Maps": ["maps.google", "google.maps", "maps.googleapis"],
                "reCAPTCHA": ["recaptcha", "g-recaptcha"],
                "Disqus": ["disqus", "disqus_thread"],
                "Algolia": ["algolia", "algoliasearch"],
                "Sentry": ["sentry", "raven-"],
                "New Relic": ["newrelic", "nr-"],
            }

            output.append(f"\n  [Detected Technologies]")
            for name, sigs in sorted(detectors.items()):
                for sig in sigs:
                    if sig in html or sig in r.text.lower():
                        tech[name] = tech.get(name, 0) + 1
                        break
            if tech:
                for name in sorted(tech, key=lambda k: -tech[k]):
                    output.append(f"    {name}")
            else:
                output.append(f"    (no specific tech detected)")

            output.append(f"\n  [HTML Analysis]")
            title_match = re.search(r'<title[^>]*>(.*?)</title>', r.text, re.IGNORECASE | re.DOTALL)
            if title_match:
                output.append(f"    Title: {title_match.group(1).strip()[:100]}")
            desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', r.text, re.IGNORECASE)
            if desc_match:
                output.append(f"    Meta Desc: {desc_match.group(1)[:120]}")
            script_count = len(re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', r.text, re.IGNORECASE))
            css_count = len(re.findall(r'<link[^>]+href=["\']([^"\']+\.css)["\']', r.text, re.IGNORECASE))
            output.append(f"    External JS: {script_count}")
            output.append(f"    External CSS: {css_count}")

        return f"[TECH] Tech Stack for {url}:\n" + "\n".join(output)


def handle_api_discover(args):
        url = args["url"].rstrip("/")
        depth = int(args.get("depth", 2))
        output = []

        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            return f"[API] Error accessing {url}: {e}"

        text = r.text
        apis = set()

        output.append(f"  Target: {url}")

        output.append(f"\n  [Form Actions]")
        form_actions = re.findall(r'<form[^>]+action=["\']([^"\']+)["\']', text, re.IGNORECASE)
        for fa in form_actions:
            apis.add(fa)
            output.append(f"    {fa}")
        if not form_actions:
            output.append(f"    (no forms found)")

        output.append(f"\n  [Inline API Calls]")
        fetch_patterns = [
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.\w+\(["\']([^"\']+)["\']',
            r'\$\.(?:get|post|ajax)\(["\']([^"\']+)["\']',
            r'\.ajax\(\{.*?url:\s*["\']([^"\']+)["\']',
            r'XMLHttpRequest[^;]*?\.open\(["\'][A-Z]+["\'],\s*["\']([^"\']+)["\']',
            r'url:\s*["\']([^"\']+)["\']',
        ]
        for pat in fetch_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                apis.add(m.group(1))
                output.append(f"    {m.group(1)[:100]}")

        if depth >= 2:
            output.append(f"\n  [Script File URLs]")
            js_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, re.IGNORECASE)
            for js_src in js_srcs[:10]:
                js_url = js_src if js_src.startswith("http") else (url.rstrip("/") + "/" + js_src.lstrip("/"))
                try:
                    rr = httpx.get(js_url, timeout=10, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                    if rr.status_code == 200:
                        inner_patterns = [
                            r'["\'](https?://[^"\']*api[^"\']*)["\']',
                            r'["\'](/api/[^"\']+)["\']',
                            r'["\'](/v[0-9]+/[^"\']+)["\']',
                            r'["\'](/graphql)[^"\']*["\']',
                            r'["\'](/rest/[^"\']+)["\']',
                            r'["\'](/[^"\']*(?:endpoint|webhook|callback)[^"\']*)["\']',
                        ]
                        for ipat in inner_patterns:
                            for m in re.finditer(ipat, rr.text, re.IGNORECASE):
                                apis.add(m.group(1))
                except Exception:
                    pass

            if apis:
                output.append(f"\n  [Unique API Paths Found]")
                for api in sorted(apis)[:40]:
                    output.append(f"    {api}")
            else:
                output.append(f"\n  [Unique API Paths Found]")
                output.append(f"    (none found)")

            output.append(f"\n  [API Patterns]")
            api_patterns_found = set()
            for api in apis:
                parts = api.rstrip("/").split("/")
                for i, p in enumerate(parts):
                    if p in ("api", "v1", "v2", "v3", "rest", "graphql", "webhook", "endpoint"):
                        pattern = "/".join(parts[:i+2])
                        api_patterns_found.add(pattern)
            if api_patterns_found:
                for p in sorted(api_patterns_found)[:15]:
                    output.append(f"    /{p.lstrip('/')}")
            else:
                output.append(f"    (no specific API pattern)")

        return f"[API] API Discovery for {url}:\n" + "\n".join(output)


def handle_source_map_check(args):
        url = args["url"].rstrip("/")
        output = []

        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            return f"[SOURCEMAP] Error accessing {url}: {e}"

        output.append(f"  Target: {url}")

        output.append(f"\n  [Source Map Discovery]")
        js_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', r.text, re.IGNORECASE)
        found_maps = []

        for js_src in js_srcs[:20]:
            js_url = js_src if js_src.startswith("http") else (url.rstrip("/") + "/" + js_src.lstrip("/"))
            if js_url.endswith(".map"):
                found_maps.append(js_url)
                continue
            map_url = js_url + ".map"
            alt_map = re.sub(r'\.js$', '.map', js_url)
            for mu in [map_url, alt_map]:
                try:
                    mr = httpx.head(mu, timeout=5, verify=False)
                    if mr.status_code in (200, 204):
                        found_maps.append(mu)
                except Exception:
                    pass

        comment_maps = re.findall(r'//#\s*sourceMappingURL=(.+\.map)', r.text)
        if comment_maps:
            for cm in comment_maps:
                if not cm.startswith("http"):
                    cm = url.rstrip("/") + "/" + cm.lstrip("/")
                found_maps.append(cm)

        if found_maps:
            output.append(f"  \033[31mEXPOSED SOURCE MAPS DETECTED!\033[0m")
            for fm in sorted(set(found_maps)):
                output.append(f"    {fm}")
        else:
            output.append(f"  No source maps found (good)")

        if found_maps:
            output.append(f"\n  [Content from First Source Map]")
            try:
                sm_url = list(set(found_maps))[0]
                sm_r = httpx.get(sm_url, timeout=10, verify=False)
                if sm_r.status_code == 200:
                    sm_data = sm_r.json()
                    sources = sm_data.get("sources", [])
                    names = sm_data.get("names", [])
                    if sources:
                        output.append(f"    Original sources ({len(sources)}):")
                        for s in sources[:15]:
                            output.append(f"      {s}")
                    if names:
                        output.append(f"    Identifiers ({len(names)}):")
                        for n in names[:20]:
                            output.append(f"      {n}")
            except Exception:
                output.append(f"    (could not parse source map)")

        return f"[SOURCEMAP] Source Map Check for {url}:\n" + "\n".join(output)


def handle_form_analyze(args):
        url = args["url"].rstrip("/")
        output = []

        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            return f"[FORM] Error accessing {url}: {e}"

        output.append(f"  Target: {url}")
        output.append(f"  Status: {r.status_code}")

        forms = re.findall(r'(<form[^>]*>(.*?)</form>)', r.text, re.IGNORECASE | re.DOTALL)

        if not forms:
            output.append(f"\n  No forms found")
            return f"[FORM] Form Analysis for {url}:\n" + "\n".join(output)

        output.append(f"\n  Forms found: {len(forms)}")

        for i, (form_html, form_body) in enumerate(forms):
            output.append(f"\n  {'='*40}")
            output.append(f"  Form #{i+1}")

            action = re.search(r'action=["\']([^"\']*)["\']', form_html, re.IGNORECASE)
            method = re.search(r'method=["\']([^"\']*)["\']', form_html, re.IGNORECASE)
            enctype = re.search(r'enctype=["\']([^"\']*)["\']', form_html, re.IGNORECASE)

            output.append(f"    Action: {action.group(1) if action else '(self)'}")
            output.append(f"    Method: {method.group(1).upper() if method else 'GET'}")
            if enctype:
                output.append(f"    Enctype: {enctype.group(1)}")

            output.append(f"\n    [Fields]")
            inputs = re.findall(r'(<input[^>]*>)', form_body, re.IGNORECASE)
            selects = re.findall(r'(<select[^>]*>.*?</select>)', form_body, re.IGNORECASE | re.DOTALL)
            textareas = re.findall(r'(<textarea[^>]*>.*?</textarea>)', form_body, re.IGNORECASE | re.DOTALL)

            for inp in inputs:
                inp_type = re.search(r'type=["\']([^"\']*)["\']', inp, re.IGNORECASE)
                inp_name = re.search(r'name=["\']([^"\']*)["\']', inp, re.IGNORECASE)
                inp_val = re.search(r'value=["\']([^"\']*)["\']', inp, re.IGNORECASE)
                inp_id = re.search(r'id=["\']([^"\']*)["\']', inp, re.IGNORECASE)
                inp_auto = re.search(r'autocomplete=["\']([^"\']*)["\']', inp, re.IGNORECASE)

                t = inp_type.group(1).lower() if inp_type else "text"
                n = inp_name.group(1) if inp_name else "(unnamed)"
                v = inp_val.group(1) if inp_val else "(empty)"

                tag = ""
                if t == "hidden":
                    tag = " \033[33m[HIDDEN]\033[0m"
                if inp_auto and inp_auto.group(1).lower() == "off":
                    tag += " \033[31m[autocomplete=off]\033[0m"

                output.append(f"      [{t}] {n} = {v[:40]}{tag}")

            for sel in selects:
                sel_name = re.search(r'name=["\']([^"\']*)["\']', sel, re.IGNORECASE)
                n = sel_name.group(1) if sel_name else "(unnamed)"
                options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', sel, re.IGNORECASE)
                output.append(f"      [select] {n} (options: {options[:5]})")

            for ta in textareas:
                ta_name = re.search(r'name=["\']([^"\']*)["\']', ta, re.IGNORECASE)
                n = ta_name.group(1) if ta_name else "(unnamed)"
                output.append(f"      [textarea] {n}")

            csrf_inputs = re.findall(r'<input[^>]*name=["\']([^"\']*(?:csrf|token|authenticity|_token)[^"\']*)["\'][^>]*>', form_html, re.IGNORECASE)
            if csrf_inputs:
                output.append(f"    \033[32m[CSRF Protection Detected]\033[0m")
                for c in csrf_inputs:
                    output.append(f"      CSRF field: {c}")

        return f"[FORM] Form Analysis for {url}:\n" + "\n".join(output)


def handle_todo_create(args):
        items = args["items"]
        _save_todo(items)
        lines = [f"  {i+1}. [ ] {item}" for i, item in enumerate(items)]
        return f"TODO list dibuat ({len(items)} item):\n" + "\n".join(lines)


def handle_todo_done(args):
        indices = args["indices"]
        items = _load_todo()
        marked = []
        for idx in indices:
            if 1 <= idx <= len(items):
                items[idx - 1] = f"✅ {items[idx - 1]}"
                marked.append(str(idx))
        _save_todo(items)
        
        # Trigger visual verification if the last item is completed and mentions "Verifikasi"
        visual_trigger = ""
        if indices and max(indices) == len(items):
            last_item = items[-1]
            if "Verifikasi" in last_item:
                visual_trigger = "\n\n[SISTEM] Deteksi item 'Verifikasi' di akhir TODO. Menyiapkan validasi visual..."
        
        return f"Item TODO {' dan '.join(marked)} selesai! {visual_trigger}\n" + "\n".join(f"  {i+1}. {item}" for i, item in enumerate(items))


def handle_todo_show(args):
        items = _load_todo()
        if not items:
            return "(TODO list kosong)"
        lines = [f"  {i+1}. {item}" for i, item in enumerate(items)]
        done = sum(1 for i in items if i.startswith("✅"))
        return f"TODO list ({done}/{len(items)} selesai):\n" + "\n".join(lines)


def handle_ui_keypress(args):
        keys = args["keys"]
        r = subprocess.run(["xdotool", "key", keys], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return f"Key pressed: {keys}"
        return f"Key error: {r.stderr}"


def handle_ui_focus(args):
        title = args["title"]
        r = subprocess.run(["xdotool", "search", "--name", title, "windowactivate"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return f"Window focused: {title}"
        # fallback: coba windowactivate via classname
        r2 = subprocess.run(["xdotool", "search", "--class", title, "windowactivate"],
                            capture_output=True, text=True, timeout=10)
        if r2.returncode == 0 and r2.stdout.strip():
            return f"Window focused: {title}"
        return f"Window '{title}' not found. Gunakan --name atau --class."


def handle_usb_list(args):
        verbose = args.get("verbose", False)
        cmd = ["lsusb"] if not verbose else ["lsusb", "-v"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            out = r.stdout.strip()
            return out or "(no USB devices)"
        return f"lsusb error: {r.stderr}. Install usbutils: sudo apt install usbutils"


def handle_serial_send(args):
        port = args["port"]
        data = args["data"]
        baud = str(args.get("baud", 9600))
        timeout = args.get("read_timeout", 2)
        try:
            import serial
        except ImportError:
            return "pyserial tidak terinstall. Install: pip install pyserial"
        try:
            ser = serial.Serial(port, int(baud), timeout=timeout)
            ser.write(data.encode())
            response = b""
            import time as _time
            _time.sleep(0.5)
            while ser.in_waiting:
                response += ser.read(ser.in_waiting)
                _time.sleep(0.2)
            ser.close()
            resp_text = response.decode(errors="replace").strip()
            if resp_text:
                return f"Sent: {data}\nResponse: {resp_text}"
            return f"Sent: {data} (no response)"
        except Exception as e:
            return f"Serial error: {e}"


def handle_sandbox_run(args):
        code = args["code"]
        interpreter = args.get("interpreter", "auto")
        timeout = min(args.get("timeout", 15), 60)
        import tempfile, uuid
        sandbox_dir = os.path.join(tempfile.gettempdir(), f"joki_sandbox_{uuid.uuid4().hex[:8]}")
        os.makedirs(sandbox_dir, exist_ok=True)

        files_raw = args.get("files", "")
        if files_raw:
            for entry in files_raw.split("|"):
                if "=" in entry:
                    fpath, fcontent = entry.split("=", 1)
                    fdest = os.path.join(sandbox_dir, fpath.strip())
                    os.makedirs(os.path.dirname(fdest), exist_ok=True)
                    with open(fdest, "w") as f:
                        f.write(fcontent)

        script_path = os.path.join(sandbox_dir, "script")
        ext_map = {"python3": ".py", "node": ".js", "bash": ".sh", "sh": ".sh", "auto": ""}

        if interpreter == "auto":
            if code.startswith("#!"):
                interp_cmd = code.splitlines()[0].lstrip("#!").strip()
                interpreter = "bash" if "bash" in interp_cmd or "sh" in interp_cmd else "python3" if "python" in interp_cmd else "node" if "node" in interp_cmd else "bash"
            elif any(kw in code for kw in ["import ", "def ", "class ", "print("]):
                interpreter = "python3"
            elif any(kw in code for kw in ["require(", "module.exports", "console.log"]):
                interpreter = "node"
            else:
                interpreter = "bash"

        ext = ext_map.get(interpreter, "")
        script_path = os.path.join(sandbox_dir, f"script{ext}")
        with open(script_path, "w") as f:
            f.write(code)
        os.chmod(script_path, 0o755)

        try:
            r = subprocess.run(
                [interpreter, script_path] if interpreter in ("python3", "node") else ["bash", script_path],
                capture_output=True, text=True, timeout=timeout, cwd=sandbox_dir
            )
            output = r.stdout + r.stderr
            if not output.strip():
                output = "(no output)"
            status = "SUCCESS" if r.returncode == 0 else f"FAILED (exit {r.returncode})"
            import shutil
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            return f"[SANDBOX] {status}\n{output.strip()}"
        except subprocess.TimeoutExpired:
            import shutil
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            return f"[SANDBOX] TIMEOUT (>{timeout}s)"
        except Exception as e:
            import shutil
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            return f"[SANDBOX] Error: {e}"


def handle_predict_command(args):
        cmd = args["cmd"]
        risks = []
        dangerous_patterns = [
            (r"\brm\s+-rf\b", "Menghapus file/direktori secara paksa (rm -rf) — data bisa hilang permanen"),
            (r"\bmv\s+", "Memindahkan file — bisa timpa file tujuan"),
            (r"\bdd\b", "Low-level disk operation — bisa merusak partisi jika salah"),
            (r"\bmkfs|mkfs\.|fdisk|parted", "Operasi partisi/format — bisa menghapus seluruh data"),
            (r"\bchmod\s+777", "Memberi izin akses penuh ke semua user — risiko keamanan"),
            (r"\bchown\b", "Mengubah kepemilikan file — bisa menyebabkan akses error"),
            (r":(){ :\|:& };:", "Fork bomb — bisa crash sistem"),
            (r">\s*/dev/", "Menulis langsung ke device — bisa merusak sistem"),
            (r"wget|curl.*\|.*sh", "Download dan pipe ke shell — risiko malware"),
            (r"sudo", "Menjalankan dengan hak akses root"),
            (r"apt install|apt-get install|pip install|npm install", "Menginstall package baru"),
            (r"systemctl (stop|disable|mask)", "Menghentikan/menonaktifkan service sistem"),
            (r"DROP TABLE|DELETE FROM|TRUNCATE", "Operasi database destruktif"),
            (r">\s+\S+\.(json|txt|py|js|yaml|conf|ini)", "Menimpa isi file (write)"),
        ]
        for pattern, desc in dangerous_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                risks.append(f"  ⚠ {desc}")
        if not risks:
            risks.append("  ✓ Tidak terdeteksi pola berbahaya")
        return f"Analisa perintah: `{cmd[:200]}`\n" + "\n".join(risks)


def handle_audio_info(args):
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", args["path"]],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return f"Error: {r.stderr or 'ffprobe not found. Install: sudo apt install ffmpeg'}"
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        lines = [f"  File: {args['path']}"]
        lines.append(f"  Duration: {fmt.get('duration', 'N/A')}s")
        lines.append(f"  Size: {fmt.get('size', 'N/A')} bytes")
        lines.append(f"  Bitrate: {fmt.get('bit_rate', 'N/A')} bps")
        for s in streams:
            if s.get("codec_type") == "audio":
                lines.append(f"  Codec: {s.get('codec_name', 'N/A')}")
                lines.append(f"  Sample Rate: {s.get('sample_rate', 'N/A')} Hz")
                lines.append(f"  Channels: {s.get('channels', 'N/A')}")
                lines.append(f"  Language: {s.get('tags', {}).get('language', 'N/A')}")
        return "\n".join(lines)


def handle_audio_transcribe(args):
        path = args["path"]
        model_size = args.get("model", "base")
        language = args.get("language", "")
        if not os.path.exists(path):
            return f"File not found: {path}"
        try:
            import whisper
        except ImportError:
            return "whisper tidak terinstall. Install: pip install openai-whisper"
        with _Spinner(f"Transkripsi audio (model: {model_size})..."):
            model = whisper.load_model(model_size)
            opts = {"language": language} if language else {}
            result = model.transcribe(path, **opts)
        text = result.get("text", "").strip()
        detected = result.get("language", "")
        segments = result.get("segments", [])
        duration = segments[-1]["end"] if segments else 0
        info = f"  Bahasa: {detected.upper() if detected else 'auto'}"
        info += f"\n  Durasi: {duration:.1f}s" if duration else ""
        info += f"\n  Teks ({len(text)} chars):\n{text}"
        return info


def handle_video_info(args):
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", args["path"]],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return f"Error: {r.stderr or 'ffprobe not found. Install: sudo apt install ffmpeg'}"
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        lines = [f"  File: {args['path']}"]
        lines.append(f"  Duration: {fmt.get('duration', 'N/A')}s")
        lines.append(f"  Size: {fmt.get('size', 'N/A')} bytes")
        lines.append(f"  Bitrate: {fmt.get('bit_rate', 'N/A')} bps")
        for s in streams:
            codec_type = s.get("codec_type", "unknown")
            lines.append(f"  [{codec_type}]")
            lines.append(f"    Codec: {s.get('codec_name', 'N/A')}")
            if codec_type == "video":
                lines.append(f"    Resolution: {s.get('width', 'N/A')}x{s.get('height', 'N/A')}")
                rate = s.get('r_frame_rate', '0/1')
                if '/' in rate:
                    try:
                        num, den = rate.split('/')
                        fps = float(int(num) / int(den)) if int(den) else 0.0
                    except ValueError:
                        fps = 0.0
                else:
                    try:
                        fps = float(rate)
                    except ValueError:
                        fps = 0.0
                lines.append(f"    FPS: {fps:.2f}")
                lines.append(f"    Pixel Format: {s.get('pix_fmt', 'N/A')}")
            elif codec_type == "audio":
                lines.append(f"    Sample Rate: {s.get('sample_rate', 'N/A')} Hz")
                lines.append(f"    Channels: {s.get('channels', 'N/A')}")
        return "\n".join(lines)


def handle_video_extract(args):
        path = args["path"]
        mode = args["mode"]
        output_dir = args.get("output_dir", "/tmp/joki_video_extract")
        os.makedirs(output_dir, exist_ok=True)
        if mode == "thumbnail":
            out = os.path.join(output_dir, "thumbnail.jpg")
            r = subprocess.run(
                ["ffmpeg", "-i", path, "-vframes", "1", "-q:v", "2", "-y", out],
                capture_output=True, text=True, timeout=30
            )
            if os.path.exists(out):
                return f"Thumbnail saved: {out} ({os.path.getsize(out)} bytes)"
            return f"Error: {r.stderr}"
        elif mode == "timestamp":
            ts = args.get("timestamp", 0)
            out = os.path.join(output_dir, f"frame_{ts}s.jpg")
            r = subprocess.run(
                ["ffmpeg", "-ss", str(ts), "-i", path, "-vframes", "1", "-q:v", "2", "-y", out],
                capture_output=True, text=True, timeout=30
            )
            if os.path.exists(out):
                return f"Frame at {ts}s saved: {out} ({os.path.getsize(out)} bytes)"
            return f"Error: {r.stderr}"
        elif mode == "frames":
            fps = args.get("fps", 1)
            out_pattern = os.path.join(output_dir, "frame_%04d.jpg")
            r = subprocess.run(
                ["ffmpeg", "-i", path, "-vf", f"fps={fps}", "-q:v", "2", "-y", out_pattern],
                capture_output=True, text=True, timeout=60
            )
            count = len([f for f in os.listdir(output_dir) if f.startswith("frame_")])
            return f"Extracted {count} frames to {output_dir}/ (fps={fps})"
        return f"Unknown mode: {mode}"

    return "Error: command timed out (60s)"
    return f"Error: {e.output}"

