"""
Módulo de verificação de atualizações do Accessible Timeline via GitHub Releases.
"""

import json
import logging
import urllib.request
from typing import Optional, Dict, Any
from src.core.version import __version__, GITHUB_OWNER, GITHUB_REPO

logger = logging.getLogger("AccessibleTimeline.Updater")


def parse_version_tuple(v_str: str) -> tuple:
    """Converte strings como 'v0.2.0' ou '0.2.0' em tupla de inteiros (0, 2, 0)."""
    cleaned = v_str.lstrip("v").strip().split("-")[0]
    parts = []
    for p in cleaned.split("."):
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
