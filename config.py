import os
from dotenv import load_dotenv

# Carrega o arquivo .env local
load_dotenv()

class Config:
    # Foxbit settings
    FOXBIT_API_KEY = os.getenv("FOXBIT_API_KEY")
    FOXBIT_SECRET_KEY = os.getenv("FOXBIT_SECRET_KEY")
    FOXBIT_CLIENT_ID = os.getenv("FOXBIT_CLIENT_ID")
    FOXBIT_BASE_URL = os.getenv("FOXBIT_BASE_URL", "https://api.foxbit.com.br").rstrip('/')
    
    # Simulation mode settings
    SIMULATION_MODE = os.getenv("SIMULATION_MODE", "True").strip().lower() in ["true", "1", "yes"]

    # NVIDIA DeepSeek settings
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
    NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro")

    # Telegram settings
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # Target symbols (must be lowercase in Foxbit, e.g. btcbrl)
    TARGET_TICKERS = [
        ticker.strip().lower()
        for ticker in os.getenv("TARGET_TICKERS", "btcbrl,ethbrl,solbrl").split(",")
        if ticker.strip()
    ]

    @classmethod
    def validate(cls):
        """Valida se todas as variáveis obrigatórias de ambiente estão configuradas."""
        missing = []
        if not cls.FOXBIT_API_KEY:
            missing.append("FOXBIT_API_KEY")
        if not cls.FOXBIT_SECRET_KEY:
            missing.append("FOXBIT_SECRET_KEY")
        if not cls.NVIDIA_API_KEY:
            missing.append("NVIDIA_API_KEY")

        if not cls.TELEGRAM_BOT_TOKEN or not cls.TELEGRAM_CHAT_ID:
            print("Aviso: Telegram Bot Token ou Chat ID não configurados. Notificações estão desabilitadas.")

        if missing:
            raise ValueError(f"As seguintes variáveis de ambiente obrigatórias estão faltando: {', '.join(missing)}")
