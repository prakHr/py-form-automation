import threading

import h2o
import simple_websocket
from flask import Flask, request, send_from_directory
from h2o_nitro import View, box, option
from h2o_nitro_web import web_directory
from werkzeug.serving import make_server


shutdown_requested = threading.Event()
server = None


def create_viewbox(view, name, value):
    return view(box(name, value=value))


def create_choicebox(view, label, options_list):
    choices = [option(item, item) for item in options_list]
    return view(
        box(
            f"{label} ({' or '.join(options_list)}):",
            options=choices,
        )
    )


def request_shutdown():
    """Shut down H2O, then stop Flask from another thread."""
    if shutdown_requested.is_set():
        return

    shutdown_requested.set()
    print("Exiting H2O-Nitro interaction...")

    def shutdown_servers():
        global server

        # Shut down the connected H2O cluster, if available.
        try:
            cluster = h2o.cluster()
            if cluster is not None:
                cluster.shutdown(prompt=False)
                print("H2O cluster shut down.")
        except Exception as exc:
            print(f"H2O shutdown skipped or failed: {exc}")

        # Stop the Werkzeug/Flask server.
        if server is not None:
            server.shutdown()
            print("Flask server stopped.")

    threading.Thread(target=shutdown_servers, daemon=True).start()


def main(view: View):
    while not shutdown_requested.is_set():
        name = create_viewbox(view, "What is your name?", "")

        feel = create_viewbox(
            view,
            f"How do you feel today, {name}?",
            "",
        )

        create_viewbox(
            view,
            "What a coincidence!",
            f"{name}, I feel {feel}, too!",
        )

        choice = create_choicebox(
            view,
            "Do you have any other questions to ask?",
            ["yes", "no"],
        )

        # Exit when the user selects no.
        if str(choice).strip().lower() in ("no", "n"):
            request_shutdown()
            return


nitro = View(main, title="Hello Nitro!", caption="v1.0")

app = Flask(
    __name__,
    static_folder=web_directory,
    static_url_path="",
)


@app.route("/")
def home_page():
    return send_from_directory(web_directory, "index.html")


@app.route("/nitro", websocket=True)
def socket():
    ws = simple_websocket.Server(request.environ)

    try:
        nitro.serve(ws.send, ws.receive)
    except simple_websocket.ConnectionClosed:
        pass

    return ""


if __name__ == "__main__":
    # Disable the reloader so only one server instance is running.
    server = make_server(
        "127.0.0.1",
        5000,
        app,
        threaded=True,
    )

    try:
        print("Starting H2O-Nitro at http://127.0.0.1:5000")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
        request_shutdown()
    finally:
        if not shutdown_requested.is_set():
            request_shutdown()

