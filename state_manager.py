import os
import json
import datetime

class StateManager:
    DEFAULT_STATE = {
        "saldo_anterior": 10000.0,  # R$ 10.000,00 virtuais para simulação
        "saldos_virtuais": {
            "brl": 10000.0,
            "btc": 0.0,
            "eth": 0.0,
            "sol": 0.0
        },
        "historico_trades": [],
        "licoes_aprendidas": "Nenhuma lição registrada ainda. O modelo registrará aprendizados técnicos e comportamentais de swing trade aqui.",
        "ultima_execucao": None
    }

    def __init__(self, filepath="estado.json"):
        self.filepath = filepath

    def load_state(self) -> dict:
        """
        Carrega o estado a partir do arquivo JSON.
        Se o arquivo não existir, estiver vazio ou for inválido, retorna e cria o estado inicial padrão.
        """
        if not os.path.exists(self.filepath):
            print(f"Arquivo {self.filepath} não encontrado. Inicializando novo estado padrão.")
            self.save_state(self.DEFAULT_STATE)
            return self.DEFAULT_STATE.copy()

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print(f"Arquivo {self.filepath} está vazio. Inicializando com estado padrão.")
                    self.save_state(self.DEFAULT_STATE)
                    return self.DEFAULT_STATE.copy()
                
                data = json.loads(content)
                # Garante que as chaves padrão existem no dicionário carregado
                for key, val in self.DEFAULT_STATE.items():
                    if key not in data:
                        data[key] = val
                
                # Garante que os saldos virtuais padrões existam se a chave saldos_virtuais existir mas estiver incompleta
                if "saldos_virtuais" in data:
                    for asset, qty in self.DEFAULT_STATE["saldos_virtuais"].items():
                        if asset not in data["saldos_virtuais"]:
                            data["saldos_virtuais"][asset] = qty
                            
                return data
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON do arquivo {self.filepath}: {e}. Resetando para estado padrão.")
            self.save_state(self.DEFAULT_STATE)
            return self.DEFAULT_STATE.copy()
        except Exception as e:
            print(f"Erro desconhecido ao carregar o estado: {e}. Retornando estado padrão.")
            return self.DEFAULT_STATE.copy()

    def save_state(self, state: dict) -> bool:
        """
        Salva o estado no arquivo de forma atômica (escreve em arquivo temporário e renomeia)
        para evitar corrupção.
        """
        state["ultima_execucao"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        temp_filepath = f"{self.filepath}.tmp"
        try:
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4, ensure_ascii=False)
            
            # Renomeia o arquivo temporário para o destino final (operação atômica no OS)
            if os.path.exists(self.filepath):
                os.remove(self.filepath)
            os.rename(temp_filepath, self.filepath)
            return True
        except Exception as e:
            print(f"Erro ao salvar estado no arquivo {self.filepath}: {e}")
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass
            return False
