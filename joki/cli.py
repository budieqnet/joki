# ============================================================
# AGENT LOOP (single turn)
# ============================================================
def agent_loop(messages):
    for i in range(25):
        _console.rule("[bold cyan]JOKI[/bold cyan]")
        msg = call_llm(messages)
        messages.append(msg)

        content = (msg.get("content") or "")
        if content.startswith("[CANCELLED]"):
            _console.print("[bold yellow]Dibatalkan oleh pengguna.[/bold yellow]")
            return

        if msg.get("tool_calls"):
            if content and not content.strip().startswith("[RENCANA]"):
                stream_print(content)

            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                raw = tc["function"]["arguments"]
                args = json.loads(raw) if isinstance(raw, str) else raw

                label = _TOOL_LABEL.get(name, name)
                if name == "run_command":
                    detail = args.get("cmd", "")
                elif name in ("read_file", "write_file", "edit_file", "list_dir", "config_edit"):
                    detail = args.get("path", "")
                elif name == "db_query":
                    detail = args.get("query", "")[:60]
                elif name == "web_search":
                    detail = args.get("query", "")
                elif name == "search_code":
                    detail = args.get("pattern", "")
                elif name == "service_control":
                    detail = f"{args.get('action')} {args.get('service')}"
                elif name == "package_check":
                    detail = args.get("app", "")
                elif name == "web_fetch":
                    detail = args.get("url", "")
                elif name == "test_and_fix":
                    detail = args.get("cmd", "")
                elif name in ("memory_store", "memory_recall", "memory_forget"):
                    detail = args.get("key", "")
                elif name == "screenshot":
                    detail = args.get("path", "(auto)")
                elif name == "port_scan":
                    detail = f"{args.get('target')} ports:{args.get('ports','common')}"
                elif name == "dns_enum":
                    detail = f"{args.get('domain')} {args.get('action','records')}"
                elif name == "web_vuln_scan":
                    detail = f"{args.get('url')} {args.get('checks','headers,info')}"
                elif name == "whois_lookup":
                    detail = args.get("target", "")
                elif name == "ssl_check":
                    detail = f"{args.get('host')}:{args.get('port',443)}"
                elif name == "dir_bruteforce":
                    detail = f"{args.get('url')} wordlist:{args.get('wordlist','small')}"
                elif name == "cve_search":
                    detail = args.get("query", "")
                elif name == "tech_detect":
                    detail = f"{args.get('url')} {args.get('deep','simple')}"
                elif name == "js_analyze":
                    detail = f"{args.get('url')} {args.get('extract','all')}"
                elif name == "api_discover":
                    detail = f"{args.get('url')} depth:{args.get('depth',2)}"
                elif name == "source_map_check":
                    detail = args.get("url", "")
                elif name == "form_analyze":
                    detail = args.get("url", "")
                elif name == "apk_analyze":
                    detail = args.get("path", "")
                elif name == "binary_analyze":
                    detail = args.get("path", "")
                elif name == "todo_create":
                    detail = f"{len(args.get('items', []))} items"
                elif name == "todo_done":
                    detail = f"item {args.get('indices', [])}"
                elif name == "todo_show":
                    detail = ""
                elif name in ("ui_screenshot", "ui_click", "ui_type", "ui_keypress", "ui_focus"):
                    detail = json.dumps(args)
                elif name == "usb_list":
                    detail = "USB devices"
                elif name == "serial_send":
                    detail = f"{args.get('port')}: {args.get('data','')[:60]}"
                elif name == "camera_capture":
                    detail = args.get("device", "/dev/video0")
                elif name == "sandbox_run":
                    detail = f"{args.get('interpreter','auto')} — {args.get('code','')[:80]}"
                elif name == "predict_command":
                    detail = args.get("cmd", "")[:80]
                elif name in ("audio_info", "audio_transcribe", "video_info", "video_extract"):
                    detail = args.get("path", "")
                else:
                    detail = json.dumps(args)
                _console.print(f"  [dim]\u2192 {label} {detail}[/dim]")

                if name == "write_file" and "content" in args:
                    lines = args["content"].splitlines(keepends=True)
                    digits = len(str(len(lines)))
                    for i, l in enumerate(lines):
                        print(f"      {i+1:>{digits}}: {l}", end="", flush=True)
                    if lines:
                        print()
                elif name == "edit_file":
                    ot = args.get("old_text", "")
                    nt = args.get("new_text", "")
                    if ot or nt:
                        _console.print(f"      [red]-: {ot[:80]}[/red]")
                        _console.print(f"      [green]+: {nt[:80]}[/green]")

                try:
                    result = execute(name, args)
                except Exception as ex:
                    result = f"[ERROR] Exception saat mengeksekusi {name}: {ex}"
                if result:
                    stream_print(f"       ```\n{result}\n       ```", delay=0.001)
                messages.append({
                    "role": "tool",
                    "content": (result or "")[:10000],
                    "tool_call_id": tc["id"]
                })

                # === AUTO-TEST MODULE ===
                if name == "write_file" and not _joki_cancel.is_set():
                    path = args.get("path", "")
                    content = args.get("content", "")
                    ext = os.path.splitext(path)[1].lower()
                    base = os.path.basename(path)
                    _auto_test_needed = False

                    test_cfg = None
                    if ext == ".py" and ("if __name__" in content or content.strip().startswith("#!")):
                        test_cfg = ("python3", "python3")
                    elif ext == ".js":
                        test_cfg = ("node", "node")
                    elif ext == ".ts":
                        test_cfg = ("npx ts-node", "ts-node")
                    elif ext == ".sh" and content.strip().startswith("#!"):
                        test_cfg = ("bash", "bash")
                    elif ext == ".rb":
                        test_cfg = ("ruby", "ruby")
                    elif ext == ".go":
                        test_cfg = ("go run", "go")
                    elif ext == ".php":
                        test_cfg = ("php", "php")

                    if test_cfg:
                        test_cmd, _ = test_cfg
                        full_cmd = f"{test_cmd} {shlex.quote(path)}"

                        # Deteksi program interaktif/game/server — tidak cocok untuk auto-test kilat
                        _interactive_kw = ["pygame", "tkinter", "turtle", "curses",
                            "PyQt5", "PyQt6", "PySide", "gi.repository",
                            "flask", "fastapi", "bottle", "django", "aiohttp",
                            "sanic", "tornado", "uvicorn", "http.server",
                            "socketserver", "twisted", "matplotlib"]
                        _is_interactive = any(kw in content.lower() for kw in _interactive_kw)

                        if _is_interactive:
                            stream_print(f"       \u2728 Auto-test {base} dilewati \u2014 ini program interaktif/game/server yang berjalan terus-menerus")
                        else:
                            for attempt in range(5):
                                if _joki_cancel.is_set():
                                    break
                                with _Spinner(f"Auto-test {base} (percobaan {attempt+1}/5)"):
                                    rc, output, timed_out = _run_auto_test(full_cmd)
                                if rc == 0:
                                    stream_print(f"       \u2713 Auto-test {base} BERHASIL (percobaan {attempt+1})")
                                    break
                                elif timed_out:
                                    stream_print(f"       \u23F1 Auto-test {base} butuh waktu lebih lama \u2014 tapi program masih jalan, auto-test dilewati")
                                    stream_print(f"       \u2728 Program berjalan normal, hanya saja auto-test memang tidak cocok untuk program yang berjalan terus-menerus")
                                    break
                                else:
                                    stream_print(f"       \u2717 Auto-test {base} GAGAL (percobaan {attempt+1}/5)")
                                    stream_print(f"       ```\n{output[:3000]}\n       ```", delay=0.001)
                                    if attempt < 4:
                                        messages.append({
                                            "role": "user",
                                            "content": f"[AUTO-TEST] Modul {path} gagal test (percobaan {attempt+1}/5).\nPerintah: {full_cmd}\nError:\n{output[:4000]}\n\nPERBAIKI file ini sekarang dan jangan berhenti sampai test berhasil."
                                        })
                                        _auto_test_needed = True
                                        break
                                    else:
                                        stream_print(f"       Auto-test {base} GAGAL setelah 5 percobaan.")
                    if _auto_test_needed:
                        break
        else:
            content = (msg.get("content") or "")
            if content and not content.strip().startswith("[RENCANA]"):
                stream_print(content)
            if content and ("run_command(" in content or "write_file(" in content or "edit_file(" in content or "service_control(" in content):
                messages.append({
                    "role": "user",
                    "content": "Jangan tulis tool sebagai teks. EKSEKUSI tool di atas menggunakan function calling API sekarang."
                })
                continue
            if not content.strip():
                messages.append({
                    "role": "user",
                    "content": "Respons kamu kosong. Berikan respons atau panggil tool yang sesuai. Jangan diam saja — kerjakan task-nya."
                })
                continue
            return
    stream_print(f"\n[INFO] Max iterations reached (25).")
    _console.rule(style="cyan")


