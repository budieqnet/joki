import os, sys, json, subprocess, sqlite3, re, time, random, base64, socket, urllib, csv, platform
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
import httpx
from duckduckgo_search import DDGS
from joki.shared import _console, _current_model_config, _get_data_dir, _print_markdown, _numbered, _HAS_TTY, TOOLS, _joki_cancel, JokiError, ToolError, LLMError, ConfigError, _shell_execute

def handle_port_scan(args):
        target = args["target"]
        port_str = args.get("ports", "common")
        scan_type = args.get("scan_type", "quick")
        results = []

        common_ports = [21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
                       993, 995, 1433, 1521, 2049, 2082, 2083, 3306, 3389, 5432,
                       5900, 5984, 6379, 8080, 8443, 9000, 9090, 27017]

        if port_str == "common":
            ports = common_ports
        elif port_str == "1-1000":
            ports = list(range(1, 1001))
        elif port_str == "1-1024":
            ports = list(range(1, 1025))
        else:
            ports = []
            for part in port_str.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    ports.extend(range(int(a), int(b) + 1))
                else:
                    ports.append(int(part))

        if scan_type == "quick":
            ports = [p for p in ports if p in common_ports] or ports[:50]

        with _Spinner(f"Scanning {target} ({len(ports)} ports)"):
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                r = sock.connect_ex((target, port))
                if r == 0:
                    try:
                        service = socket.getservbyport(port)
                    except Exception:
                        service = "unknown"
                    results.append(f"  PORT {port:>5}/tcp  OPEN  {service}")
                sock.close()

        if not results:
            return f"[PORTS] No open ports found on {target} (scanned {len(ports)} ports)"
        return f"[PORTS] Open ports on {target} ({len(results)} open of {len(ports)} scanned):\n" + "\n".join(results)


def handle_dns_enum(args):
        domain = args["domain"]
        action = args.get("action", "records")
        output = []

        if action in ("records", "all"):
            record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
            for rtype in record_types:
                r = subprocess.run(
                    ["dig", "+short", domain, rtype],
                    capture_output=True, text=True, timeout=15
                )
                if r.stdout.strip():
                    output.append(f"  {rtype} Records:")
                    for line in r.stdout.strip().splitlines():
                        output.append(f"    {line}")
            if not output:
                output.append("  (no DNS records found via dig)")

        if action in ("subdomains", "all"):
            common_subdomains = [
                "www", "mail", "ftp", "admin", "blog", "webmail", "pop3",
                "smtp", "api", "dev", "test", "staging", "vpn", "remote",
                "portal", "cpanel", "whm", "mysql", "backup", "proxy",
                "cdn", "static", "img", "docs", "wiki", "git", "jenkins",
                "jira", "confluence", "grafana", "prometheus", "monitor",
                "ns1", "ns2", "ns3", "mx", "chat", "help", "support",
                "status", "app", "beta", "demo", "shop", "store", "ssl",
                "cloud", "web", "server", "db", "redis", "mongo"
            ]
            output.append(f"\n  Subdomain brute-force ({len(common_subdomains)}):")
            found = 0
            for sd in common_subdomains:
                sd_target = f"{sd}.{domain}"
                try:
                    r = subprocess.run(
                        ["dig", "+short", sd_target, "A"],
                        capture_output=True, text=True, timeout=3
                    )
                    if r.stdout.strip():
                        output.append(f"    {sd_target} -> {r.stdout.strip()}")
                        found += 1
                except Exception:
                    pass
            output.append(f"  Found {found} subdomains")

        return f"[DNS] Enumeration for {domain}:\n" + "\n".join(output)


def handle_web_vuln_scan(args):
        url = args["url"].rstrip("/")
        checks = args.get("checks", "headers,info")
        output = []

        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, verify=False)
        except Exception as e:
            return f"[WEB_VULN] Error accessing {url}: {e}"

        output.append(f"  URL: {url}")
        output.append(f"  Status: {r.status_code}")
        output.append(f"  Server: {r.headers.get('Server', 'N/A')}")
        output.append(f"  Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        output.append(f"  Content-Length: {len(r.content)} bytes")

        if "headers" in checks or "all" in checks:
            output.append("\n  [Security Headers]")
            sec_headers = {
                "Strict-Transport-Security": "HSTS (HttpOnly)",
                "Content-Security-Policy": "CSP",
                "X-Frame-Options": "Clickjacking protection",
                "X-Content-Type-Options": "MIME-sniffing protection",
                "X-XSS-Protection": "XSS protection",
                "Referrer-Policy": "Referrer policy",
                "Permissions-Policy": "Permissions policy",
                "Set-Cookie": "Cookie flags (HttpOnly/Secure)",
            }
            for hdr, desc in sec_headers.items():
                val = r.headers.get(hdr, "MISSING")
                marker = "\033[31mMISSING\033[0m" if val == "MISSING" else "\033[32mPRESENT\033[0m"
                output.append(f"    {marker} {desc} ({hdr})")
                if val != "MISSING":
                    output.append(f"      Value: {val[:100]}")

        if "info" in checks or "all" in checks:
            output.append("\n  [Server Information]")
            via = r.headers.get("Via", "")
            cf_ray = r.headers.get("CF-RAY", "")
            powered = r.headers.get("X-Powered-By", "")
            asp = r.headers.get("X-AspNet-Version", "")
            runtime = r.headers.get("X-Runtime", "")
            for hdr, label in [(via, "Via"), (cf_ray, "CF-RAY"),
                               (powered, "X-Powered-By"), (asp, "X-AspNet-Version"),
                               (runtime, "X-Runtime")]:
                if hdr:
                    output.append(f"    {label}: {hdr}")

        if "sqli" in checks or "all" in checks:
            output.append("\n  [SQL Injection Test]")
            sqli_payloads = [
                ("'", "single quote"),
                ("' OR '1'='1", "OR true"),
                ("' UNION SELECT 1--", "UNION"),
                ("1' AND 1=1--", "AND true"),
                ("1' AND 1=2--", "AND false"),
            ]
            import urllib.parse
            for payload, desc in sqli_payloads:
                try:
                    encoded = urllib.parse.quote(payload)
                    test_url = f"{url}?id={encoded}"
                    rr = httpx.get(test_url, timeout=10, verify=False)
                    if rr.status_code == 200:
                        import html
                        body_lower = rr.text.lower()
                        sqli_indicators = ["sql", "mysql", "syntax", "uncaught",
                                           "odbc", "exception", "warning", "db_",
                                           "column", "rowCount", "oracle", "postgre"]
                        if any(ind in body_lower for ind in sqli_indicators):
                            output.append(f"    \033[31mSUSPECT SQLi\033[0m (payload: {desc})")
                        else:
                            output.append(f"    OK (payload: {desc})")
                    else:
                        output.append(f"    {rr.status_code} (payload: {desc})")
                except Exception:
                    output.append(f"    Error (payload: {desc})")

        if "xss" in checks or "all" in checks:
            output.append("\n  [XSS Reflection Test]")
            xss_payloads = [
                "<script>alert(1)</script>",
                "<img src=x onerror=alert(1)>",
                "\"><script>alert(1)</script>",
            ]
            import urllib.parse, html
            for payload in xss_payloads:
                try:
                    encoded = urllib.parse.quote(payload)
                    test_url = f"{url}?q={encoded}"
                    rr = httpx.get(test_url, timeout=10, verify=False)
                    if html.unescape(payload) in rr.text or payload in rr.text:
                        output.append(f"    \033[31mSUSPECT XSS\033[0m (payload reflected)")
                    else:
                        output.append(f"    No reflection (payload: {payload[:30]})")
                except Exception:
                    output.append(f"    Error (payload: {payload[:30]})")

        return f"[WEB_VULN] Scan result for {url}:\n" + "\n".join(output)


