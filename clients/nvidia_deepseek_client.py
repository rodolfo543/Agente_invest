import re
import json
import time
from typing import Dict, List, Any
from openai import OpenAI

class NvidiaDeepSeekClient:
    def __init__(self, api_key: str, model_name: str = "deepseek-ai/deepseek-v4-pro", base_url: str = "https://integrate.api.nvidia.com/v1"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extrai o JSON da resposta da LLM de forma resiliente, lidando com markdown code blocks.
        """
        cleaned_text = text.strip()
        
        # Procura por blocos de código markdown do tipo ```json ... ``` ou ``` ... ```
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned_text, re.DOTALL | re.IGNORECASE)
        if match:
            cleaned_text = match.group(1).strip()
            
        return json.loads(cleaned_text)

    def analyze_market_and_decide(self, 
                                  balances: List[Dict[str, Any]], 
                                  market_data: Dict[str, Any], 
                                  state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envia os saldos em BRL/criptos, dados de mercado e estado para o DeepSeek,
        retornando as decisões estruturadas e classificações de recomendação.
        """
        
        system_prompt = (
            "Você é um Trading Bot autônomo sênior de criptomoedas especializado em Swing Trade no mercado brasileiro (Foxbit).\n"
            "Sua estratégia prioriza a preservação do capital e análise técnica profunda baseada em RSI (14d), Médias Móveis (SMA 10 e 20),\n"
            "Bandas de Bollinger, MACD, Volatilidade histórica e níveis de Retração de Fibonacci de 30 dias (0.236, 0.382, 0.500, 0.618).\n\n"
            "Regras operacionais:\n"
            "1. Preservação de Capital: Mantenha sempre um caixa reserva em BRL para emergências ou correções.\n"
            "2. Classificação de Recomendação: Para CADA ativo analisado, determine um nível de classificação de 1 a 5:\n"
            "   - Nível 1: Comprar (Desconto extremo, reversão altista forte ou suporte Fibonacci chave)\n"
            "   - Nível 2: Acumular (Tendência saudável de alta, compras fracionadas)\n"
            "   - Nível 3: Manter (Hold - Tendência indefinida ou estável)\n"
            "   - Nível 4: Reduzir (Sinais de cansaço, sobrecompra ou resistência Fibonacci)\n"
            "   - Nível 5: Vender (Tendência forte de baixa, sobrecompra extrema)\n"
            "3. Decisões de Compra (COMPRAR):\n"
            "   - Recomende COMPRAR se a classificação for Nível 1 ou 2.\n"
            "   - Especifique a quantidade em Reais (BRL) que deseja gastar (ex: quantidade = 250.0 significa gastar R$ 250,00).\n"
            "4. Decisões de Venda (VENDER):\n"
            "   - Recomende VENDER se a classificação for Nível 4 ou 5.\n"
            "   - Especifique a quantidade da criptomoeda que deseja vender (ex: quantidade = 0.002 BTC).\n\n"
            "Regra estrita de saída: Responda APENAS com um objeto JSON válido, sem explicações externas, prefácios ou tags markdown extras."
        )

        prompt = f"""
CONTEÚDO DO ESTADO ANTERIOR E SALDOS VIRTUAIS (estado.json):
{json.dumps(state, indent=2, ensure_ascii=False)}

SALDOS DISPONÍVEIS ATUALMENTE:
{json.dumps(balances, indent=2)}

DADOS TÉCNICOS AVANÇADOS DE MERCADO (Foxbit API):
{json.dumps(market_data, indent=2, ensure_ascii=False)}

INSTRUÇÃO DE DECISÃO:
Analise as tendências dos pares informados considerando os dados técnicos (RSI, SMAs, Bollinger Bands, MACD, Volatilidade e níveis de Fibonacci).
Forneça a classificação de recomendação (Nível 1 a 5) para todos os ativos e tome as decisões operacionais (COMPRAR, VENDER ou MANTER) adequadas ao saldo disponível.

FORMATO DE RESPOSTA OBRIGATÓRIO (JSON):
{{
  "decisoes": [
    {{
      "ticker": "btcbrl" | "ethbrl" | "solbrl",
      "classificacao_nivel": 1 | 2 | 3 | 4 | 5,
      "classificacao_texto": "Comprar" | "Acumular" | "Manter (Hold)" | "Reduzir" | "Vender",
      "acao": "COMPRAR" | "VENDER" | "MANTER",
      "quantidade": <float>,
      "justificativa": "Breve justificativa técnica (médias móveis, rsi, bollinger, macd, etc.)"
    }}
  ],
  "licoes_aprendidas": "Texto consolidando os aprendizados técnicos e observações desta rodada de swing trade."
}}
"""



        max_retries = 3
        delay = 2.0
        
        for attempt in range(max_retries):
            try:
                # Chamada da API compatível com a NVIDIA
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=1.0,
                    top_p=0.95,
                    max_tokens=4096,
                    extra_body={"chat_template_kwargs": {"thinking": False}},
                    stream=False
                )
                
                raw_content = completion.choices[0].message.content
                decision_data = self._extract_json(raw_content)
                
                # Garante estrutura mínima
                if "decisoes" not in decision_data:
                    decision_data["decisoes"] = []
                if "licoes_aprendidas" not in decision_data:
                    decision_data["licoes_aprendidas"] = state.get("licoes_aprendidas", "")
                    
                return decision_data

            except json.JSONDecodeError as e:
                print(f"[Nvidia DeepSeek] JSON inválido retornado pela LLM (Tentativa {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                print(f"[Nvidia DeepSeek] Erro na chamada do modelo (Tentativa {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(delay)
                delay *= 2
                
        return {"decisoes": [], "licoes_aprendidas": state.get("licoes_aprendidas", "")}
