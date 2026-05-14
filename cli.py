"""
CLI para controlar el pipeline desde la terminal.

Uso:
    python cli.py start [--host HOST] [--port PORT]
    python cli.py stop
    python cli.py status
    python cli.py logs [--lines N]
    python cli.py trigger-pipeline
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: Se requiere 'requests'. Instala con: pip install requests")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Inicia el servidor en segundo plano."""
    print(f"🚀 Iniciando servidor en {host}:{port}...")

    subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "server.py"), "--host", host, "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=PROJECT_ROOT,
    )

    # Esperar a que esté listo
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = requests.get(f"http://{host}:{port}/health", timeout=2)
            if resp.status_code == 200:
                print(f"✅ Servidor listo en http://{host}:{port}")
                print(f"📊 Dashboard: http://{host}:{port}/docs")
                return
        except requests.RequestException:
            pass

        print(f"⏳ Esperando servidor... ({i+1}/{max_retries})")
        time.sleep(1)

    print("❌ Timeout: El servidor no respondió")
    sys.exit(1)


def stop_server() -> None:
    """Detiene el servidor."""
    pid_file = PROJECT_ROOT / ".server.pid"
    if not pid_file.exists():
        print("⚠️  No hay servidor corriendo")
        return

    try:
        pid = int(pid_file.read_text().strip())
        subprocess.run(["kill", str(pid)], check=False)
        pid_file.unlink(missing_ok=True)
        print("✅ Servidor detenido")
    except Exception as e:
        print(f"❌ Error: {e}")


def get_status() -> None:
    """Obtiene el estado del pipeline."""
    try:
        resp = requests.get("http://127.0.0.1:8000/status", timeout=5)
        resp.raise_for_status()
        status = resp.json()

        print("\n📊 Estado del Pipeline")
        print("=" * 50)
        print(f"Etapa actual: {status['stage']}")
        print(f"Inicio: {status.get('start_time', 'N/A')}")
        print(f"Fin: {status.get('end_time', 'N/A')}")

        if status.get("error"):
            print(f"❌ Error: {status['error']}")

        if status.get("progress"):
            print("\nProgreso:")
            for key, value in status["progress"].items():
                print(f"  {key}: {value}")

    except requests.RequestException as e:
        print(f"❌ Error conectando al servidor: {e}")
        print("   ¿Está el servidor corriendo? Usa: python cli.py start")


def show_logs(lines: int = 50) -> None:
    """Muestra los logs del servidor."""
    log_file = PROJECT_ROOT / "server.log"

    if not log_file.exists():
        print("⚠️  No hay logs aún")
        return

    content = log_file.read_text(encoding="utf-8")
    log_lines = content.splitlines()

    print(f"\n📋 Últimas {min(lines, len(log_lines))} líneas del log")
    print("=" * 50)
    for line in log_lines[-lines:]:
        print(line)


def trigger_pipeline(force_restart: bool = False) -> None:
    """Inicia la ejecución del pipeline."""
    try:
        payload = {"force_restart": force_restart}
        resp = requests.post(
            "http://127.0.0.1:8000/start",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()

        print(f"✅ {result['message']}")
        print("\n💡 Monitorea el progreso con: python cli.py status")

    except requests.RequestException as e:
        print(f"❌ Error: {e}")
        print("   ¿Está el servidor corriendo? Usa: python cli.py start")


def show_results() -> None:
    """Muestra los archivos de resultados disponibles."""
    try:
        resp = requests.get("http://127.0.0.1:8000/results", timeout=5)
        resp.raise_for_status()
        results = resp.json()

        print("\n📁 Resultados Disponibles")
        print("=" * 50)

        for category, files in results.items():
            if files:
                print(f"\n{category}:")
                if isinstance(files, list):
                    for f in files:
                        print(f"  - {f}")
                else:
                    print(f"  ✓ {files}")

    except requests.RequestException as e:
        print(f"❌ Error: {e}")


def main():
    """Punto de entrada."""
    parser = argparse.ArgumentParser(
        description="CLI para controlar el pipeline de procesamiento de especies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python cli.py start
  python cli.py start --host 0.0.0.0 --port 8000
  python cli.py status
  python cli.py trigger-pipeline
  python cli.py logs --lines 100
  python cli.py stop
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Comando: start
    start_parser = subparsers.add_parser("start", help="Iniciar servidor")
    start_parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    start_parser.add_argument("--port", type=int, default=8000, help="Puerto (default: 8000)")

    # Comando: stop
    subparsers.add_parser("stop", help="Detener servidor")

    # Comando: status
    subparsers.add_parser("status", help="Ver estado del pipeline")

    # Comando: logs
    logs_parser = subparsers.add_parser("logs", help="Ver logs del servidor")
    logs_parser.add_argument("--lines", type=int, default=50, help="Cantidad de líneas (default: 50)")

    # Comando: trigger
    trigger_parser = subparsers.add_parser("trigger-pipeline", help="Iniciar pipeline")
    trigger_parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar reinicio si ya está en ejecución",
    )

    # Comando: results
    subparsers.add_parser("results", help="Ver archivos disponibles")

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port)
    elif args.command == "stop":
        stop_server()
    elif args.command == "status":
        get_status()
    elif args.command == "logs":
        show_logs(args.lines)
    elif args.command == "trigger-pipeline":
        trigger_pipeline(args.force)
    elif args.command == "results":
        show_results()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
