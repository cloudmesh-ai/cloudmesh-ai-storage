import json
import webbrowser
from pathlib import Path
import yaml
import http.server
import socketserver
import threading
import subprocess
import urllib.parse

class StorageViewHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP Handler to serve the storage view and handle terminal actions.
    """
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/":
            # Access html_content from the server object
            html_content = getattr(self.server, "html_content", "<h1>No content found</h1>")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif url.path == "/storage_table_config.js":
            try:
                # Path relative to this file
                file_path = Path(__file__).parent / "storage_table_config.js"
                if file_path.exists():
                    self.send_response(200)
                    self.send_header("Content-type", "application/javascript")
                    self.end_headers()
                    with open(file_path, "rb") as f:
                        self.wfile.write(f.read())
                    return
            except Exception:
                pass
            self.send_error(404)
        elif url.path == "/open-terminal":
            query = urllib.parse.parse_qs(url.query)
            path = query.get("path", [None])[0]
            if path:
                try:
                    parent_dir = Path(path).parent
                    # Use a more robust AppleScript to ensure a new window is opened and activated
                    cmd_args = [
                        "osascript", 
                        "-e", 'tell application "Terminal" to activate', 
                        "-e", f'tell application "Terminal" to do script "cd \\"{parent_dir}\\" && ls"'
                    ]
                    subprocess.run(cmd_args, check=True)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Terminal opened")
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error: {e}".encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing path parameter")
        elif url.path == "/delete-folder":
            query = urllib.parse.parse_qs(url.query)
            path = query.get("path", [None])[0]
            dirname = query.get("dirname", [None])[0]
            if path and dirname:
                # Print the shell command that would be used to delete the directory
                print(f"\n[StorageView] To delete this directory, run: rm -rf \"{path}\"")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Delete request received and logged")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing path or dirname parameter")
        else:
            super().do_GET()

def get_panel_metadata():
    """
    Returns metadata for the AI Panel discovery by reading the metadata.yaml file.
    """
    try:
        # Path to the metadata file relative to this file
        # This file is in src/cloudmesh/ai/command/storage_view.py
        # Metadata is in src/cloudmesh/ai/app/storage.yaml
        metadata_path = Path(__file__).parent.parent / "app" / "storage.yaml"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                data = yaml.safe_load(f)
                app_info = data.get("cloudmesh", {}).get("ai", {}).get("app", [{}])[0]
                return {
                    "name": app_info.get("name", "Storage View"),
                    "icon": app_info.get("image", "mdi-database")
                }
    except Exception as e:
        print(f"Error reading storage metadata: {e}")
    
    return {"name": "Storage View", "icon": "mdi-database"}

class StorageInfoView:
    """
    Handles the generation and display of the HTML view for storage equivalencies using Tabulator.
    """

    def __init__(self, config_file=None):
        self.config_file = Path(config_file) if config_file else Path.home() / ".config" / "cloudmesh" / "storage" / "equivalencies.yaml"

    def load_data(self):
        """Loads the equivalencies data from the YAML file."""
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def generate_html(self):
        """
        Generates a standalone HTML page for viewing storage equivalencies.
        """
        raw_data = self.load_data()
        
        # The YAML structure is {"equivalencies": {...}, "candidates": {...}}
        candidates = raw_data.get("candidates", {}) if isinstance(raw_data, dict) else {}
        
        flattened_data = []
        metrics_map = {}
        group_counter = 1
        
        for dirname, paths_meta in candidates.items():
            if not isinstance(paths_meta, dict):
                continue
                
            for path, meta in paths_meta.items():
                if not isinstance(meta, dict):
                    continue
                
                size = meta.get("size", 0)
                files = meta.get("files", 0)
                dirs = meta.get("dirs", 0)
                
                metrics = (size, files, dirs)
                if metrics not in metrics_map:
                    metrics_map[metrics] = f"Group {group_counter}"
                    group_counter += 1
                
                flattened_data.append({
                    "dirname": dirname,
                    "path": path,
                    "size": size,
                    "files": files,
                    "dirs": dirs,
                    "group": metrics_map[metrics] if size >= 0 else "Unique"
                })

        data_json = json.dumps(flattened_data)

        # Read HTML template from file
        template_path = Path(__file__).parent / "storage_view.html"
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                html = f.read()
            
            # Replace placeholders
            html = html.replace("{{DATA_JSON}}", data_json)
            return html
        except Exception as e:
            return f"<h1 style='font-family: sans-serif;'>Error loading template</h1><p>{e}</p>"

    def open_in_browser(self):
        """
        Starts a local server to serve the HTML and handle terminal actions, then opens it in the browser.
        """
        html_content = self.generate_html()
        
        try:
            # Use port 0 to let the OS pick an available port
            with socketserver.TCPServer(("", 0), StorageViewHandler) as httpd:
                # Attach the HTML content to the server object so the handler can access it
                httpd.html_content = html_content
                port = httpd.server_address[1]
                
                # Run server in a background thread so it doesn't block the CLI
                server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                server_thread.start()
                
                url = f"http://localhost:{port}"
                webbrowser.open(url)
                print(f"\n[StorageView] Server running at {url}")
                
                import click
                click.echo("\nInteractive view is open. Press Enter to close the server and return to CLI...")
                input()
                httpd.shutdown()
        except Exception as e:
            print(f"Error starting storage view server: {e}")
