import subprocess


def run_apps():
    model_cmd = (
        "fastapi run ai_model_server/main.py --host 0.0.0.0 --port 8001"
    )
    be_cmd = "fastapi dev app/main.py --host 0.0.0.0 --port 8000"

    print("Starting model server on port 8001...")
    process_model = subprocess.Popen(model_cmd.split())

    print("Starting web app on port 8000...")
    process_web = subprocess.Popen(be_cmd.split())

    try:
        process_model.wait()
        process_web.wait()
    except KeyboardInterrupt:
        process_model.terminate()
        process_web.terminate()


if __name__ == "__main__":
    run_apps()
