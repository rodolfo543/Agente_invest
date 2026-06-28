import requests
import html
import time

class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str) -> bool:
        """
        Envia uma mensagem formatada em HTML para o canal do Telegram configurado.
        Se a mensagem for muito longa, divide-a automaticamente em partes seguras.
        """
        if not self.bot_token or not self.chat_id:
            print("[Telegram] Configurações de Telegram ausentes. Mensagem não enviada.")
            return False
            
        MAX_LEN = 4000
        if len(text) <= MAX_LEN:
            return self._send_chunk(text)
            
        print(f"[Telegram] Mensagem muito longa ({len(text)} caracteres). Dividindo em partes...")
        chunks = []
        current_chunk = ""
        for line in text.split("\n"):
            if len(current_chunk) + len(line) + 1 > MAX_LEN:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
        if current_chunk:
            chunks.append(current_chunk)
            
        success = True
        for i, chunk in enumerate(chunks):
            print(f"[Telegram] Enviando parte {i+1}/{len(chunks)} ({len(chunk)} caracteres)...")
            res = self._send_chunk(chunk)
            if not res:
                success = False
            time.sleep(0.5)
        return success

    def _send_chunk(self, text: str) -> bool:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"[Telegram] Erro ao enviar mensagem (HTTP {response.status_code}): {response.text}")
                return False
            return True
        except Exception as e:
            print(f"[Telegram] Exceção ao enviar notificação para o Telegram: {e}")
            return False

    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """
        Envia uma imagem (gráfico) com legenda formatada em HTML para o Telegram.
        """
        if not self.bot_token or not self.chat_id:
            print("[Telegram] Configurações de Telegram ausentes. Foto não enviada.")
            return False
            
        url = f"{self.base_url}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo:
                files = {"photo": photo}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, data=data, files=files, timeout=20)
                if response.status_code != 200:
                    print(f"[Telegram] Erro ao enviar foto (HTTP {response.status_code}): {response.text}")
                    return False
                return True
        except Exception as e:
            print(f"[Telegram] Exceção ao enviar foto para o Telegram: {e}")
            return False

    @staticmethod
    def escape(text: str) -> str:
        """
        Escapa caracteres HTML especiais para evitar erros de renderização no Telegram.
        """
        if not text:
            return ""
        return html.escape(text)

