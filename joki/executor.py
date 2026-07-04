from joki.shared import *
import joki.tools.files
import joki.tools.shell
import joki.tools.other
import joki.tools.database
import joki.tools.memory
import joki.tools.security
import joki.tools.reverse_eng
import joki.tools.ui
import joki.tools.media

TOOL_HANDLERS = {
    "read_file": joki.tools.files.handle_read_file,
    "write_file": joki.tools.files.handle_write_file,
    "edit_file": joki.tools.files.handle_edit_file,
    "run_command": joki.tools.shell.handle_run_command,
    "search_code": joki.tools.files.handle_search_code,
    "list_dir": joki.tools.other.handle_list_dir,
    "db_query": joki.tools.database.handle_db_query,
    "service_control": joki.tools.other.handle_service_control,
    "config_edit": joki.tools.other.handle_config_edit,
    "package_check": joki.tools.other.handle_package_check,
    "web_fetch": joki.tools.other.handle_web_fetch,
    "web_search": joki.tools.other.handle_web_search,
    "test_and_fix": joki.tools.other.handle_test_and_fix,
    "memory_store": joki.tools.memory.handle_memory_store,
    "memory_recall": joki.tools.memory.handle_memory_recall,
    "memory_forget": joki.tools.memory.handle_memory_forget,
    "screenshot": joki.tools.other.handle_screenshot,
    "port_scan": joki.tools.security.handle_port_scan,
    "dns_enum": joki.tools.security.handle_dns_enum,
    "web_vuln_scan": joki.tools.security.handle_web_vuln_scan,
    "whois_lookup": joki.tools.other.handle_whois_lookup,
    "ssl_check": joki.tools.other.handle_ssl_check,
    "dir_bruteforce": joki.tools.other.handle_dir_bruteforce,
    "cve_search": joki.tools.other.handle_cve_search,
    "tech_detect": joki.tools.other.handle_tech_detect,
    "js_analyze": joki.tools.reverse_eng.handle_js_analyze,
    "api_discover": joki.tools.other.handle_api_discover,
    "source_map_check": joki.tools.other.handle_source_map_check,
    "form_analyze": joki.tools.other.handle_form_analyze,
    "apk_analyze": joki.tools.reverse_eng.handle_apk_analyze,
    "binary_analyze": joki.tools.reverse_eng.handle_binary_analyze,
    "todo_create": joki.tools.other.handle_todo_create,
    "todo_done": joki.tools.other.handle_todo_done,
    "todo_show": joki.tools.other.handle_todo_show,
    "ui_screenshot": joki.tools.ui.handle_ui_screenshot,
    "ui_click": joki.tools.ui.handle_ui_click,
    "ui_type": joki.tools.ui.handle_ui_type,
    "ui_keypress": joki.tools.other.handle_ui_keypress,
    "ui_focus": joki.tools.other.handle_ui_focus,
    "usb_list": joki.tools.other.handle_usb_list,
    "serial_send": joki.tools.other.handle_serial_send,
    "camera_capture": joki.tools.media.handle_camera_capture,
    "sandbox_run": joki.tools.other.handle_sandbox_run,
    "predict_command": joki.tools.other.handle_predict_command,
    "audio_info": joki.tools.other.handle_audio_info,
    "audio_transcribe": joki.tools.other.handle_audio_transcribe,
    "video_info": joki.tools.other.handle_video_info,
    "video_extract": joki.tools.other.handle_video_extract,
}

def execute(name, args):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    try:
        return handler(args)
    except Exception as e:
        return f"Error: {e}"
