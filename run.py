"""
Ponto de entrada do Accessible Timeline.
Para executar:
    python run.py
"""

import logging
import sys
from src.ui.app import AccessibleTimelineApp


def main():
    # Configuração de logging no terminal para acompanhamento do desenvolvedor
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S"
    )

    app = AccessibleTimelineApp(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
