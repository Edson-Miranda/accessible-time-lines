"""
Módulo de verificação de atualizações do Accessible Timeline via GitHub Releases.
"""

import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
from typing import Callable, Optional, Dict, Any
from src.core.version import __version__, GITHUB_OWNER, GITHUB_REPO

logger = logging.getLogger("AccessibleTimeline.Updater")


def parse_version_tuple(v_str: str) -> tuple:
    """Converte strings como 'v0.2.0', '0.2.1A' ou 'v1.0.0-dev.1' em tupla comparável."""
    cleaned = v_str.lstrip("v").strip().split("-")[0]
    parts = []
    for p in cleaned.split("."):
        m = re.match(r"^(\d+)([a-zA-Z]*)", p)
        if m:
            parts.append(int(m.group(1)))
            if m.group(2):
                parts.append(ord(m.group(2).upper()))
        else:
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
    return tuple(parts)


def check_for_updates(
    current_version: str = __version__,
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
    timeout: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Consulta o GitHub Releases para verificar se há uma nova versão disponível.
    Retorna um dicionário com detalhes da nova versão ou None se já estiver na versão mais recente.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"AccessibleTimeline/{current_version}",
            "Accept": "application/vnd.github.v3+json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return None

        current_tuple = parse_version_tuple(current_version)
        latest_tuple = parse_version_tuple(latest_tag)

        if latest_tuple > current_tuple:
            # Encontra link do asset .zip ou .exe se houver
            download_url = data.get("html_url", "")
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".zip") or name.endswith(".exe"):
                    download_url = asset.get("browser_download_url", download_url)
                    break

            return {
                "latest_version": latest_tag.lstrip("v"),
                "release_name": data.get("name", latest_tag),
                "notes": data.get("body", ""),
                "html_url": data.get("html_url", ""),
                "download_url": download_url
            }

    except Exception as e:
        logger.debug(f"Não foi possível verificar atualizações: {e}")

    return None


def get_application_directory() -> str:
    """Retorna o diretório base da instalação do aplicativo."""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).parent.resolve())
    return str(Path(__file__).resolve().parent.parent.parent)


def download_update_archive(
    url: str,
    target_file: str,
    progress_callback: Optional[Callable[[int, int], Optional[bool]]] = None,
    chunk_size: int = 65536
) -> bool:
    """
    Baixa o pacote compactado da atualização a partir da URL do GitHub.
    Chama progress_callback(bytes_baixados, total_bytes).
    Se o callback retornar False, o download é cancelado.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"AccessibleTimeline/{__version__}"}
    )
    temp_target = target_file + ".part"
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(temp_target, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        should_continue = progress_callback(downloaded, total_size)
                        if should_continue is False:
                            logger.info("Download cancelado pelo usuário.")
                            f.close()
                            if os.path.exists(temp_target):
                                os.remove(temp_target)
                            return False

            if os.path.exists(target_file):
                os.remove(target_file)
            os.rename(temp_target, target_file)
            logger.info(f"Download da atualização concluído com sucesso: {target_file}")
            return True
    except Exception as e:
        logger.error(f"Erro ao baixar arquivo de atualização: {e}")
        if os.path.exists(temp_target):
            try:
                os.remove(temp_target)
            except Exception:
                pass
        return False


def apply_update_and_restart(zip_path: str, target_dir: str, current_pid: int) -> bool:
    """
    Cria e executa um script batch desacoplado que aguarda o encerramento do processo atual,
    extrai o pacote ZIP na pasta da aplicação e reinicia o Accessible Timeline.
    """
    script_path = os.path.join(tempfile.gettempdir(), f"update_at_{current_pid}.bat")

    batch_content = f"""@echo off
chcp 65001 >nul
set PID={current_pid}
set ZIP_PATH="{zip_path}"
set TARGET_DIR="{target_dir}"
set EXE_PATH="{os.path.join(target_dir, 'AccessibleTimeline.exe')}"

:: Aguarda o processo principal encerrar
:wait_loop
tasklist /fi "PID eq %PID%" | findstr /i "%PID%" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

:: Aguarda liberar eventuais travas de DLLs e arquivos
timeout /t 2 /nobreak >nul

:: Extrai a atualizacao sobre a pasta de instalacao
tar -xf %ZIP_PATH% -C %TARGET_DIR% 2>nul
if errorlevel 1 (
    powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%TARGET_DIR%' -Force"
)

:: Remove o arquivo ZIP temporario
del /f /q %ZIP_PATH% 2>nul

:: Reinicia a aplicacao atualizada se o executavel existir
if exist %EXE_PATH% (
    start "" %EXE_PATH%
)

:: Deleta este script de atualizacao
(goto) 2>nul & del "%~f0"
"""

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(batch_content)

        # Inicia o script batch em processo totalmente independente (detached)
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            ["cmd.exe", "/c", script_path],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            shell=False
        )
        logger.info(f"Script de atualização disparado com sucesso: {script_path}")
        return True
    except Exception as e:
        logger.error(f"Falha ao disparar script de atualização: {e}")
        return False

