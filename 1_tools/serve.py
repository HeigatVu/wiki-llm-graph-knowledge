import http.server
import socketserver
import json
import subprocess
from utils import _call_gemini, _call_ollama, call_gemini_cli, REPO_ROOT
import sys
sys.path.append(str(REPO_ROOT / "1_tools"))
from query import query as wiki_query
PORT = 8080
GRAPH_DIR = REPO_ROOT / "2_graph"

class GraphChatHandler(http.server.SimpleHTTPRequestHandler):

    def do_POST(self):
        if self.path == "/chat":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            question = data.get("question", "")
            context = data.get("context", "")
            
            # Load instructions from GEMINI.md if it exists
            instructions = ""
            gemini_md_path = REPO_ROOT / "GEMINI.md"
            if gemini_md_path.exists():
                instructions = gemini_md_path.read_text(encoding="utf-8")
                
            prompt = f"System Instructions (Follow these rules for the wiki):\n{instructions}\n\n---\n\nGiven the following context, answer the user's question.\n\nContext:\n{context}\n\nQuestion: {question}"
            try:
                if model == "ollama":
                    print(f"Calling Ollama for question: {question[:50]}...")
                    response = _call_ollama(prompt, max_tokens=2048)
                elif model == "gemini-cli":
                    print(f"Calling Gemini CLI for question: {question[:50]}...")
                    response = call_gemini_cli(prompt)
                else:
                    print(f"Calling Gemini API for question: {question[:50]}...")
                    response = _call_gemini(prompt, max_tokens=2048)
            except Exception as e:
                response = f"Error calling LLM: {e}"
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"response": response}).encode('utf-8'))
            return
            
        if self.path == "/query":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            question = data.get("question", "")
            model = data.get("model", "gemini")
            
            try:
                print(f"Calling Global Wiki Query for: {question[:50]}...")
                response = wiki_query(question, save_path=None, model=model)
            except Exception as e:
                response = f"Error running global query: {e}"
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"response": response}).encode('utf-8'))
            return
            
        if self.path == "/rebuild":
            try:
                print("Rebuilding knowledge graph...")
                result = subprocess.run(
                    ["uv", "run", "main.py", "graph"],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                output = result.stdout + result.stderr
                success = result.returncode == 0
                print(output)
            except subprocess.TimeoutExpired:
                output = "Build timed out after 120 seconds."
                success = False
            except Exception as e:
                output = f"Error running build: {e}"
                success = False

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "output": output}).encode('utf-8'))
            return

        self.send_error(404, "File not found")

if __name__ == "__main__":
    import webbrowser
    print(f"Starting server at http://localhost:{PORT}/graph.html")
    # Uncomment next line to auto-open
    # webbrowser.open(f"http://localhost:{PORT}/graph.html")
    import functools
    Handler = functools.partial(GraphChatHandler, directory=str(GRAPH_DIR))
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
