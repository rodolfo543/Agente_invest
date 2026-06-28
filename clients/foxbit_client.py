import time
import hmac
import hashlib
import json
import requests
from typing import Dict, List, Optional, Any

class FoxbitClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://api.foxbit.com.br"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip('/')

    def _generate_headers(self, method: str, path: str, query_params: dict = None, body_data: dict = None) -> dict:
        """
        Gera a assinatura de requisição para a API Foxbit v3 e constrói os cabeçalhos.
        A assinatura consiste de: timestamp + httpMethod + requestPath + queryString + rawBody
        criptografados com HMAC-SHA256 usando o Secret Key.
        """
        timestamp = str(int(time.time() * 1000))
        
        # 1. Monta a Query String ordenada (se houver)
        query_str = ""
        if query_params:
            # Ordena parâmetros para consistência na assinatura
            sorted_items = sorted(query_params.items())
            query_str = "?" + "&".join([f"{k}={v}" for k, v in sorted_items])
            
        # 2. Monta o Raw Body (se houver)
        body_str = ""
        if body_data:
            # JSON compacto sem espaços extras
            body_str = json.dumps(body_data, separators=(',', ':'))

        # 3. Concatena a string de prehash
        pre_hash = timestamp + method.upper() + path + query_str + body_str
        
        # 4. Gera a assinatura HMAC-SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            pre_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            "X-FB-ACCESS-KEY": self.api_key,
            "X-FB-ACCESS-TIMESTAMP": timestamp,
            "X-FB-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None, signed: bool = False, max_retries: int = 3) -> Optional[dict]:
        """
        Executa requisições na API REST v3 da Foxbit, com retentativas automáticas e 
        gerenciamento de cabeçalhos de assinatura.
        """
        url = f"{self.base_url}{endpoint}"
        
        headers = {"Content-Type": "application/json"}
        if signed:
            headers = self._generate_headers(method, endpoint, query_params=params, body_data=json_data)

        delay = 1.0
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=15
                )

                # Trata Rate Limits (429) ou erros temporários de infraestrutura
                if response.status_code in [429, 502, 503, 504]:
                    print(f"[Foxbit] Recebido HTTP {response.status_code}. Tentativa {attempt + 1}/{max_retries}. Aguardando {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                print(f"[Foxbit] Erro na requisição {method} {endpoint} (Tentativa {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(delay)
                delay *= 2
        return None

    def get_account_balances(self) -> List[Dict]:
        """
        Retorna os saldos disponíveis da conta do membro.
        Caminho da assinatura: '/rest/v3/accounts'
        """
        endpoint = "/rest/v3/accounts"
        res = self._request("GET", endpoint, signed=True)
        if not res or "data" not in res:
            raise Exception("Não foi possível carregar os saldos da conta Foxbit.")
        return res["data"]

    def get_ticker_price(self, symbol: str) -> Dict[str, Any]:
        """
        Busca estatísticas do mercado nas últimas 24h e o preço atual (Público).
        """
        endpoint = f"/rest/v3/markets/{symbol.lower()}/ticker/24hr"
        res = self._request("GET", endpoint, signed=False)
        if not res:
            raise Exception(f"Não foi possível buscar o ticker para {symbol}.")
        return res

    def submit_instant_order(self, symbol: str, side: str, amount_brl: float) -> Dict:
        """
        Submete uma ordem instantânea (usada para comprar com uma quantia em BRL).
        Preenche automaticamente os campos requeridos para a Ordem Instantânea da Foxbit.
        """
        endpoint = "/rest/v3/orders"
        order_data = {
            "side": side.upper(),
            "type": "INSTANT",
            "market_symbol": symbol.lower(),
            "amount": f"{amount_brl:.2f}"
        }
        print(f"[Foxbit API] Enviando Ordem Instantânea: {side.upper()} R$ {amount_brl:.2f} em {symbol.lower()}")
        res = self._request("POST", endpoint, json_data=order_data, signed=True)
        if not res:
            raise Exception(f"Falha ao enviar ordem instantânea para {symbol}.")
        return res

    def submit_market_order(self, symbol: str, side: str, qty: float) -> Dict:
        """
        Submete uma ordem de mercado (usada para vender frações de cripto).
        Preenche os campos requeridos para a Ordem Market da Foxbit.
        """
        endpoint = "/rest/v3/orders"
        # Formata quantidade de cripto com precisão adequada (ex: 8 casas decimais)
        qty_str = f"{qty:.8f}".rstrip('0').rstrip('.')
        order_data = {
            "side": side.upper(),
            "type": "MARKET",
            "market_symbol": symbol.lower(),
            "quantity": qty_str
        }
        print(f"[Foxbit API] Enviando Ordem de Mercado: {side.upper()} {qty_str} {symbol.lower()}")
        res = self._request("POST", endpoint, json_data=order_data, signed=True)
        if not res:
            raise Exception(f"Falha ao enviar ordem de mercado para {symbol}.")
        return res
