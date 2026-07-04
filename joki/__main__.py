#!/usr/bin/env python3
"""
Joki — AI agentic CLI.
Bisa akses file, shell, database (MySQL/PostgreSQL/MongoDB), service systemd, konfigurasi aplikasi.
Jalankan: python joki.py "task"
   atau: python joki.py (mode interaktif)
   atau: python joki.py /path/ke/folder "task" (langsung masuk folder)
"""

import json, httpx, sys, subprocess, os, re, shutil, shlex, time, threading, socket, ssl, select, getpass
try:
    import termios, tty
    _HAS_TTY = True
except ImportError:
    _HAS_TTY = False
from pathlib import Path
from difflib import unified_diff
from datetime import datetime
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich import box
from duckduckgo_search import DDGS
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

from .cli import *
from .config import *
from .llm import *
from .executor import *
from .session import *
from .display import *
from .constants import *
# ============================================================
# MAIN
# ============================================================
_SYSTEM_PROMPT_BASE = (
    "Kamu adalah Joki — AI agent yang dibuat oleh Rahmad Budiman. Jika ditanya siapa yang membuat atau menciptakan kamu, jawab: 'Saya dibuat oleh Rahmad Budiman.'\n"
    "Aturan utama: JANGAN PERNAH BERHENTI DI TENGAH JALAN. Kerjakan task sampai tuntas "
    "dalam satu sesi — jangan minta konfirmasi, jangan ngasih laporan parsial, "
    "jangan nanya 'mau dilanjutkan?' LANJUTKAN TERUS sampai dapat hasil akhir atau error fatal.\n\n"
    "SEBELUM MENGERJAKAN APAPUN, buat TODO list dulu menggunakan todo_create — "
    "rinci langkah-langkah yang akan dilakukan. Setelah satu langkah selesai, "
    "tandai dengan todo_done. Gunakan todo_show untuk cek progress.\n\n"
    "PENTING: Setelah MENYELESAIKAN semua TODO, jangan diam saja. "
    "Buat ringkasan naratif dari hasil kerja — jelaskan apa yang dilakukan "
    "dan hasilnya dalam bahasa yang mudah dipahami pengguna. Jangan hanya "
    "menampilkan output tool mentah atau isi TODO list.\n\n"
    "FILE SEMENTARA: Jika membuat script sebagai alat bantu (misal script Python "
    "untuk ngecek API key, parsing data, dll.), simpan di /tmp/ JANGAN di "
    "direktori kerja. Setelah tugas selesai, hapus file tersebut pakai "
    "run_command(\"rm /tmp/namafile\").\n\n"
    "Keluarkan [RENCANA] sebagai teks (2-3 baris), lalu KIRIMKAN tool_calls SEBENARNYA (fungsi) — jangan tulis deskripsi tool sebagai teks.\n"
    "PENTING: tool_calls harus dikirim sebagai struktur data fungsi, BUKAN ditulis manual sebagai teks.\n"
    "Contoh: content=\"[RENCANA] Cek MySQL\" + tool_calls=run_command(...)\n\n"
    "KALO CODING:\n"
    "  - Tampilkan [RENCANA] struktur file dulu sebagai text\n"
    "  - Lalu write_file/file_edit sebagai tool_calls API (bukan teks)\n"
    "Contoh alur yang benar:\n"
    "  User: 'cek apakah mysql berjalan'\n"
    "  Salah: 'saya akan cek...' (berhenti)\n"
    "  Benar: run_command(\"mysqladmin ping\") → error → service_control(\"status\", \"mysql\") → "
    "run_command(\"mysqld_safe &\") → run_command(\"mysql -e 'SHOW DATABASES'\") → "
    "'Done! MySQL sudah aktif, berikut database-nya: ...'\n\n"
    "Tool yang tersedia:\n"
    "  - read_file / write_file / edit_file / search_code / list_dir\n"
    "  - run_command (untuk APAPUN: psql, mongosh, apachectl, nginx, docker, git, apt, dsb. Tambahkan 'sudo ' (Linux/macOS) atau 'runas ' (Windows) di depan jika perintah butuh admin — contoh: 'sudo apt install', 'sudo systemctl restart nginx', 'runas net start mysql')\n"
    "  - db_query (mysql:// / postgres:// / mongodb:// / sqlite:/// / mssql:// / oracle:// / redis://)\n"
    "  - service_control (start/stop/restart/status)\n"
    "  - config_edit (edit + backup otomatis)\n"
    "  - package_check / web_fetch / web_search\n"
    "  - test_and_fix — jalanin script, kalo error balikin error biar bisa difix\n"
    "  - memory_store / memory_recall / memory_forget — memori jangka panjang lintas sesi\n"
     "  - screenshot — ambil screenshot layar untuk validasi visual\n"
     "  - port_scan — scan port terbuka pada target (reconnaissance)\n"
     "  - dns_enum — DNS record lookup + subdomain brute-force\n"
     "  - web_vuln_scan — cek security headers, SQLi, XSS, info server\n"
     "  - whois_lookup — cari informasi kepemilikan domain/IP\n"
     "  - ssl_check — periksa SSL/TLS certificate validity & cipher\n"
     "  - dir_bruteforce — temukan hidden paths pada web server\n"
      "  - cve_search — cari CVE berdasarkan software/service\n"
     "  - tech_detect — deteksi teknologi/stack website (framework, CMS, dsb)\n"
     "  - js_analyze — analisa JavaScript: ekstrak endpoint & hardcoded secrets\n"
     "  - api_discover — discover REST/GraphQL API endpoints dari HTML+JS\n"
     "  - source_map_check — cek eksposur source map (.map) untuk reverse engineering\n"
     "  - form_analyze — ekstrak form HTML (hidden fields, CSRF, input types)\n"
     "  - apk_analyze — analisa file APK Android (permissions, activities, manifest)\n"
     "  - binary_analyze — analisa file biner (type, strings, header, metadata)\n"
     "  - todo_create / todo_done / todo_show — buat dan kelola TODO list\n\n"
    "MEMORI: Gunakan memory_store untuk menyimpan informasi penting (password, path, port, dsb.) "
    "dan memory_recall untuk mengambilnya kembali di sesi mendatang. "
    "Memori bersifat lintas sesi — apa yang disimpan hari ini bisa dipanggil besok.\n\n"
    "VALIDASI VISUAL: Setelah melakukan perubahan (misal deploy web, ganti konfigurasi), "
    "gunakan screenshot untuk mengambil bukti visual bahwa hasilnya sudah benar.\n\n"
    "AUTO-TEST & AUTO-FIX:\n"
    "  SETIAP kali Joki selesai write_file modul (Python/JS/TS/Shell/Ruby/Go/PHP), sistem akan OTOMATIS "
    "menjalankan test (python3 script.py, node script.js, dll).\n"
    "  Kalo test GAGAL, sistem akan kirim [AUTO-TEST] error ke chat dan minta diperbaiki. "
    "JANGAN BERHENTI — baca error, edit file yang bermasalah, dan sistem akan test ulang otomatis.\n"
    "  Ulangi sampai SUCCESS atau mentok 5 kali percobaan.\n\n"
    "AUTO-FIX LOOP (manual):\n"
    "  Kalo test_and_fix atau run_command return error, JANGAN BERHENTI. "
    "Baca error-nya, analisa, edit file yang bermasalah, test lagi. "
    "Ulangi sampai SUCCESS atau mentok 5 kali percobaan.\n"
    "  Contoh: test_and_fix(\"python3 script.py\") → FAILED → read_file(\"script.py\") "
    "→ edit_file(...) → test_and_fix(\"python3 script.py\") → SUCCESS"
)

def _build_system_prompt():
    base = _SYSTEM_PROMPT_BASE
    memories = _load_memory()
    if memories:
        items = "\n".join(f"  - {k}: {v[:120]}" for k, v in memories.items())
        base += f"\n\nMemori tersimpan ({len(memories)}):\n{items}\n\nGunakan memory_recall untuk detail, memory_store untuk menyimpan info baru."
    return base

def main():
    os.system("clear" if os.name == "posix" else "cls")
    global _CURRENT_SESSION, _current_model_config, _MODELS, _exhausted_keys
    _exhausted_keys.clear()
    args = sys.argv[1:]
    target_dir = None
    user_input = ""

    if args:
        first = os.path.expanduser(args[0])
        if os.path.isdir(first):
            target_dir = first
            os.chdir(first)
            rest = args[1:]
            user_input = " ".join(rest)
        else:
            user_input = " ".join(args)

    if target_dir:
        cwd = os.path.abspath(target_dir)
        _console.print(f"\n[cyan]\u2192 Working directory: {cwd}[/cyan]\n")

    if user_input:
        ts_name = subprocess.run(["date", "+%Y%m%d_%H%M%S"], capture_output=True, text=True).stdout.strip()
        _CURRENT_SESSION = f"session_{ts_name}"
        messages = [{"role": "system", "content": _build_system_prompt()}]
        _console.rule("[bold yellow]USER[/bold yellow]")
        _console.print(Markdown(user_input))
        messages.append({"role": "user", "content": user_input})
        agent_loop(messages)
        save_session(messages)
        _console.print(f"[dim]Percakapan tersimpan: logs/{_CURRENT_SESSION}.log[/dim]")
        _close_shell()
        return

    ts = subprocess.run(["date", "+%Y%m%d_%H%M%S"], capture_output=True, text=True).stdout.strip()
    _CURRENT_SESSION = f"session_{ts}"

    _console.print()
    _console.rule("[bold]JOKI[/bold]", style="cyan")
    _console.print(f"  Session: [cyan]{_CURRENT_SESSION}[/cyan]", style="dim")
    _console.print(f"  Model: [cyan]{_current_model_config['name']}[/cyan] [dim]({_current_model_config['model']})[/dim]", style="dim")
    _console.print("  [bold]/model[/bold] — ganti model  |  [bold]/sessions[/bold] [bold]/view[/bold] [bold]/new[/bold] [bold]/exit[/bold]", style="dim")
    _console.rule(style="dim")

    messages = [{"role": "system", "content": _build_system_prompt()}]

    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    session = PromptSession(key_bindings=bindings)

    while True:
        try:
            user_input = session.prompt("joki> ")
        except (EOFError, KeyboardInterrupt):
            print()
            save_session(messages)
            _console.print(f"[dim]Percakapan tersimpan: logs/{_CURRENT_SESSION}.log[/dim]")
            _close_shell()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.strip().split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            now = __import__("datetime").datetime.now()

            if cmd == "/sessions":
                out, files = list_sessions()
                print(out)

            elif cmd == "/view":
                if not arg:
                    print("  Usage: /view <session_name_or_number>")
                    print("  Gunakan /sessions untuk lihat daftar.")
                    continue
                if arg.isdigit():
                    out, files = list_sessions()
                    idx = int(arg) - 1
                    if 0 <= idx < len(files):
                        arg = files[idx].replace(".json", "")
                    else:
                        print(f"  Nomor tidak valid (1-{len(files)}).")
                        continue
                print(view_session_history(arg))

            elif cmd in ("/exit", "/quit"):
                save_session(messages)
                _console.print(f"[dim]Percakapan tersimpan: logs/{_CURRENT_SESSION}.log[/dim]")
                _close_shell()
                break

            elif cmd == "/new":
                if len(messages) > 1:
                    save_session(messages)
                    _console.print(f"[dim]Previous session saved: logs/{_CURRENT_SESSION}.log[/dim]")
                _exhausted_keys.clear()
                ts = subprocess.run(["date", "+%Y%m%d_%H%M%S"], capture_output=True, text=True).stdout.strip()
                _CURRENT_SESSION = f"session_{ts}"
                messages = [{"role": "system", "content": _build_system_prompt()}]
                _console.print(f"[cyan]New session started: {_CURRENT_SESSION}[/cyan]")

            elif cmd == "/model":
                sub = arg.strip().lower()
                if not sub:
                    mc = _current_model_config
                    keys = mc.get("api_keys") or [mc.get("api_key", "")]
                    total = len(keys)
                    exhausted = sum(1 for k in keys if k in _exhausted_keys)
                    active = total - exhausted
                    _console.print(f"[bold]Model aktif:[/bold] {mc['name']} ({mc['model']})")
                    _console.print(f"  Provider: {mc['provider']} | {mc['base_url']}")
                    _console.print(f"  API Keys: {active}/{total} available [red]({exhausted} exhausted)[/red]" if exhausted else f"  API Keys: {total}")
                    if mc.get("fallback"):
                        _console.print(f"  Fallback: {mc['fallback']} — {_MODELS[mc['fallback']]['name']}")
                    _console.print(f"[dim]Model tersedia (edit config.json untuk menambah):[/dim]")
                    for key, m in _MODELS.items():
                        marker = " [green]<-- aktif[/green]" if m["model"] == mc["model"] else ""
                        kcount = len(m.get("api_keys") or [m.get("api_key", "")])
                        key_info = f" ({kcount} keys)" if kcount > 1 else ""
                        _console.print(f"    /model {key}  — {m['name']} ({m['model']}){key_info}{marker}")
                    _console.print(f"  Config file: [underline]{_CONFIG_PATH}[/underline]")
                    continue
                if sub in _MODELS:
                    cfg = dict(_MODELS[sub])
                    keys = cfg.get("api_keys") or [cfg.get("api_key", "")]
                    if cfg.get("provider") == "openai" and not any(keys):
                        _console.print(f"[yellow]Peringatan: API key untuk {sub} kosong. Isi 'api_keys' di config.json[/yellow]")
                    _current_model_config = cfg
                    _console.print(f"[green]Model diganti: {cfg['name']} ({cfg['model']})[/green]")
                else:
                    matches = [k for k, v in _MODELS.items() if sub in k or sub in v["model"]]
                    if matches:
                        print(f"  Maksud Anda: {', '.join(f'/model {m}' for m in matches)}")
                    else:
                        print(f"  Model '{sub}' tidak dikenal. Lihat daftar: /model")

            elif cmd == "/reset_quota":
                _exhausted_keys.clear()
                _console.print(f"[green]Quota exhausted state direset. Semua API key dianggap available kembali.[/green]")

            elif cmd == "/reload":
                _MODELS = _load_models()
                default_model = next((v for v in _MODELS.values() if v.get("default")), next(iter(_MODELS.values())))
                _current_model_config = dict(default_model)
                _console.print(f"[green]Config reloaded dari {_CONFIG_PATH} ({len(_MODELS)} model)[/green]")

            else:
                print(f"  Unknown command: {cmd}")
            continue

        _console.rule("[bold yellow]USER[/bold yellow]")
        _console.print(Markdown(user_input))
        messages.append({"role": "user", "content": user_input})
        agent_loop(messages)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDibatalkan.")
