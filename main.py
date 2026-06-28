import os
import sys
import datetime
import time
from config import Config
from state_manager import StateManager
from clients.foxbit_client import FoxbitClient
from clients.nvidia_deepseek_client import NvidiaDeepSeekClient
from clients.telegram_client import TelegramClient
from data.market_data import MarketDataCollector
from utils.chart_plotter import generate_technical_chart

def get_base_asset(symbol: str) -> str:
    """Retorna o ativo base a partir de um par BRL da Foxbit (ex: 'btcbrl' -> 'btc')."""
    symbol_lower = symbol.lower()
    if symbol_lower.endswith("brl"):
        return symbol_lower[:-3]
    return symbol_lower

def calculate_virtual_mvrv(asset: str, current_price: float, state: dict) -> str:
    """Calcula o MVRV virtual com base no custo médio de aquisição registrado no histórico do estado."""
    trades = state.get("historico_trades", [])
    compras = [t for t in trades if t["ticker"].startswith(asset.lower()) and t["acao"] == "COMPRAR"]
    if not compras:
        return "N/A"
    total_spent = 0.0
    total_qty = 0.0
    for c in compras:
        total_spent += c["quantidade"]
        total_qty += c["quantidade"] / c["preco_estimado"]
    if total_qty <= 0:
        return "N/A"
    avg_cost = total_spent / total_qty
    mvrv = current_price / avg_cost
    return f"{mvrv:.2f}"

def calculate_real_mvrv(asset: str, current_price: float, state: dict) -> str:
    """Calcula o MVRV real com base no custo médio configurado pelo usuário no estado."""
    precos_medios = state.get("precos_medios_reais", {})
    avg_cost = precos_medios.get(asset.lower())
    if not avg_cost:
        return "N/A"
    mvrv = current_price / avg_cost
    return f"{mvrv:.2f}"

def format_telegram_message(brl_balance: float,
                             portfolio_value_brl: float,
                             balances: list,
                             executed_trades: list,
                             decisions: list,
                             lessons: str,
                             market_data: dict,
                             is_simulation: bool,
                             real_balances: list = None,
                             state: dict = None) -> str:
    """
    Formata o relatório de execução do bot em HTML para o Telegram.
    Compacto, legível, com separadores e emojis clássicos de alta/queda (🟢/🔴).
    """
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
    env_name = "SIMULAÇÃO (Papel)" if is_simulation else "PRODUÇÃO REAL"
    env_emoji = "🧪" if is_simulation else "⚠️"
    
    msg = f"{env_emoji} <b>DEEPSEEK TRADING BOT - FOXBIT ({env_name})</b>\n"
    msg += f"📅 <i>Executado em: {now_str}</i>\n"
    msg += "────────────────────────\n\n"
    
    # 1. Caixa/Carteira Operada
    carteira_titulo = "Virtual Operada" if is_simulation else "Real Operada"
    msg += f"💼 <b>Carteira {carteira_titulo}:</b>\n"
    msg += f"• <b>Patrimônio Total:</b> R$ {portfolio_value_brl:,.2f}\n"
    msg += f"• <b>Caixa (BRL):</b> R$ {brl_balance:,.2f}\n"
    
    # Lista apenas ativos operados com saldo positivo para evitar poluição
    has_positions = False
    for bal in balances:
        asset = bal["asset"].lower()
        if asset == "brl":
            continue
        total_qty = bal["free"] + bal.get("locked", 0.0)
        if total_qty <= 0.000001:
            continue
            
        pair = f"{asset}brl"
        if pair in market_data:
            price = market_data[pair]["latest_price"]
            value = total_qty * price
            mvrv_val = calculate_virtual_mvrv(asset, price, state) if is_simulation else calculate_real_mvrv(asset, price, state)
            mvrv_str = f" | MVRV: {mvrv_val}" if mvrv_val != "N/A" else ""
            
            has_positions = True
            msg += f"• <b>{asset.upper()}</b>: {total_qty:.6f} (R$ {value:,.2f}{mvrv_str})\n"
            
    if not has_positions:
        msg += "• Nenhuma criptomoeda em carteira operada no momento.\n"
    msg += "\n"

    # 2. Consulta de Saldos Reais da Conta Foxbit (Limpa, organizada e sem zeros)
    if real_balances:
        msg += "🔍 <b>Saldos Reais na Foxbit (Consulta):</b>\n"
        has_real_positions = False
        
        # Exibe o BRL se existir
        brl_real = next((r for r in real_balances if r["asset"].lower() == "brl"), None)
        if brl_real and brl_real["total"] > 0:
            msg += f"• <b>BRL (Caixa)</b>: R$ {brl_real['total']:,.2f}\n"
            has_real_positions = True
            
        # Filtra e ordena as criptos por valor estimado descrescente
        crypto_real_valued = []
        for rbal in real_balances:
            asset = rbal["asset"].lower()
            if asset == "brl":
                continue
            total_qty = rbal["total"]
            pair = f"{asset}brl"
            price = market_data.get(pair, {}).get("latest_price", 0.0)
            value = total_qty * price
            change_pct = market_data.get(pair, {}).get("change_percent_24h", 0.0)
            
            crypto_real_valued.append({
                "asset": asset.upper(),
                "total": total_qty,
                "price": price,
                "value": value,
                "change_pct": change_pct
            })
            
        # Ordena do maior valor estimado para o menor
        crypto_real_valued = sorted(crypto_real_valued, key=lambda x: x["value"], reverse=True)
        
        for c in crypto_real_valued:
            # Emojis clássicos de bola verde ou vermelha para subindo/caindo
            if c["change_pct"] > 0.0:
                var_emoji = "🟢"
            elif c["change_pct"] < 0.0:
                var_emoji = "🔴"
            else:
                var_emoji = "⚪"
                
            sign = "+" if c["change_pct"] > 0 else ""
            mvrv_val = calculate_real_mvrv(c["asset"], c["price"], state)
            mvrv_str = f" | MVRV: {mvrv_val}" if mvrv_val != "N/A" else ""
            
            msg += f"• <b>{c['asset']}</b>: {c['total']:.6f} (R$ {c['value']:,.2f}{mvrv_str} | {var_emoji} {sign}{c['change_pct']:.2f}%)\n"
            has_real_positions = True
            
        if not has_real_positions:
            msg += "• Nenhum saldo real com valor positivo na conta.\n"
        msg += "\n"
        
    msg += "────────────────────────\n\n"

    # 3. Recomendações e Classificações (Organizadas com Hold resumido para economizar espaço e reduzir ruído)
    msg += "📊 <b>Recomendações e Classificações:</b>\n"
    if not decisions:
        msg += "• Nenhuma análise de recomendação disponível.\n\n"
    else:
        # Separa decisões ativas das decisões de Manter (Nível 3)
        active_decisions = [d for d in decisions if d.get("classificacao_nivel", 3) != 3]
        hold_decisions = [d for d in decisions if d.get("classificacao_nivel", 3) == 3]
        
        if active_decisions:
            # Ordena decisões ativas por nível (1, 5, 2, 4)
            sorted_active = sorted(active_decisions, key=lambda x: x.get("classificacao_nivel", 3))
            
            emojis = {1: "🟢", 2: "🔵", 4: "🟡", 5: "🔴"}
            for d in sorted_active:
                ticker_upper = d.get("ticker", "").upper()
                level = d.get("classificacao_nivel", 3)
                level_text = d.get("classificacao_texto", "Hold")
                emoji = emojis.get(level, "⚪")
                
                msg += f"{emoji} <b>Nível {level} - {level_text}</b> | <b>{ticker_upper}</b>\n"
                msg += f"   <i>{d.get('justificativa', '')}</i>\n\n"
                
        if hold_decisions:
            hold_tickers = [d.get("ticker", "").upper() for d in hold_decisions]
            msg += f"⚪ <b>Nível 3 - Manter (Hold):</b> {', '.join(hold_tickers)}\n\n"
            
    msg += "────────────────────────\n\n"
        
    # 4. Ordens executadas nesta rodada
    msg += "🛒 <b>Operações Realizadas nesta Execução:</b>\n"
    if not executed_trades:
        msg += "• Nenhuma ordem simulada ou enviada nesta rodada.\n\n"
    else:
        for trade in executed_trades:
            status_emoji = "✅" if trade.get("status") == "success" else "⚠️"
            symbol_label = trade['ticker'].upper()
            
            if trade['acao'] == "COMPRAR":
                msg += f"{status_emoji} <b>{trade['acao']}</b> R$ {trade['quantidade']:.2f} em <b>{symbol_label}</b>\n"
            else:
                msg += f"{status_emoji} <b>{trade['acao']}</b> {trade['quantidade']:.6f} <b>{trade['ticker'].upper()}</b>\n"
                
            if trade.get("erro"):
                msg += f"  <i>Erro: {trade['erro']}</i>\n"
            else:
                msg += f"  <i>Preço de Ref: R$ {trade['preco']:,.2f}</i>\n"
        msg += "\n"

    # 5. Lições Aprendidas
    msg += "💡 <b>Lições Aprendidas pelo Agente:</b>\n"
    msg += f"<i>{TelegramClient.escape(lessons)}</i>"
    
    return msg

def main():
    print("=== INICIANDO EXECUÇÃO DO DEEPSEEK FOXBIT BOT ===")
    
    # 1. Carrega e valida configurações
    try:
        Config.validate()
    except ValueError as e:
        print(f"[Erro de Configuração] {e}")
        sys.exit(1)
        
    # Inicializa os clientes
    state_manager = StateManager()
    foxbit = FoxbitClient(Config.FOXBIT_API_KEY, Config.FOXBIT_SECRET_KEY, Config.FOXBIT_BASE_URL)
    deepseek = NvidiaDeepSeekClient(Config.NVIDIA_API_KEY, Config.NVIDIA_MODEL)
    telegram = TelegramClient(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
    
    # 2. Carrega o estado atual (inicializa precos_medios_reais caso não existam)
    state = state_manager.load_state()
    if "precos_medios_reais" not in state:
        state["precos_medios_reais"] = {
            "btc": 312000.0,
            "eth": 8200.0,
            "sol": 370.0
        }
        state_manager.save_state(state)
    
    # 3. Busca saldos reais para Consulta (Carrega no início para sabermos quais moedas existem)
    print("[Passo 1/6] Buscando saldos reais da conta Foxbit para consulta...")
    real_balances_consultation = []
    try:
        raw_real_balances = foxbit.get_account_balances()
        for bal in raw_real_balances:
            total = float(bal["balance"])
            if total > 0.000001:  # Ignora poeiras insignificantes
                real_balances_consultation.append({
                    "asset": bal["currency_symbol"].upper(),
                    "free": float(bal["balance_available"]),
                    "locked": float(bal["balance_locked"]),
                    "total": total
                })
    except Exception as e:
        print(f"[Foxbit] Aviso: Falha ao carregar saldos reais da conta para consulta: {e}")

    # Define os saldos que serão operados pelo robô (Real ou Simulado)
    balances = []
    if Config.SIMULATION_MODE:
        print("[Passo 2/6] Lendo saldos virtuais de swing trade do estado.json...")
        saldos_v = state.get("saldos_virtuais", {})
        for asset, qty in saldos_v.items():
            balances.append({
                "asset": asset.upper(),
                "free": float(qty),
                "locked": 0.0
            })
    else:
        print("[Passo 2/6] Copiando saldos reais da conta para negociação...")
        for rbal in real_balances_consultation:
            balances.append({
                "asset": rbal["asset"],
                "free": rbal["free"],
                "locked": rbal["locked"]
            })

    # Mapeamento do saldo livre disponível por ativo operado
    balance_map = {bal["asset"].lower(): bal["free"] for bal in balances}
    brl_free = balance_map.get("brl", 0.0)

    # 4. Constrói a lista de tickers a serem analisados dinamicamente (inclui TARGET_TICKERS + moedas em carteira)
    print("[Passo 3/6] Mapeando pares de moedas para análise técnica...")
    analysis_tickers = list(Config.TARGET_TICKERS)
    
    all_held_assets = set()
    for bal in balances:
        all_held_assets.add(bal["asset"].lower())
    for rbal in real_balances_consultation:
        all_held_assets.add(rbal["asset"].lower())
        
    for asset in all_held_assets:
        if asset == "brl":
            continue
        pair = f"{asset}brl"
        if pair not in analysis_tickers:
            analysis_tickers.append(pair)
            
    print(f"[MarketData] Tickers ativos para análise: {', '.join(analysis_tickers)}")

    # 5. Coleta dados de mercado e indicadores técnicos avançados (RSI, Bollinger, MACD, Volatilidade e Fibonacci)
    print("[Passo 4/6] Coletando dados históricos e calculando indicadores técnicos na Foxbit...")
    collector = MarketDataCollector(analysis_tickers, Config.FOXBIT_BASE_URL)
    market_data = collector.fetch_all_market_data()
    
    if not market_data:
        err_msg = "Não foi possível coletar dados de mercado para nenhum par. Abortando execução."
        print(err_msg)
        telegram.send_message(f"🚨 <b>Falha Crítica no Foxbit Trading Bot:</b>\n{err_msg}")
        sys.exit(1)

    # 6. Prepara os dados de mercado para enviar à LLM (remove raw_klines para economizar tokens)
    llm_market_data = {}
    for pair, data in market_data.items():
        llm_market_data[pair] = {k: v for k, v in data.items() if k != "raw_klines"}

    # 7. Análise da LLM (Nvidia DeepSeek) com dados avançados
    print("[Passo 5/6] Enviando contexto técnico detalhado para o DeepSeek...")
    try:
        analysis_result = deepseek.analyze_market_and_decide(
            balances=balances,
            market_data=llm_market_data,
            state=state
        )
    except Exception as e:
        err_msg = f"Falha na tomada de decisão do DeepSeek: {e}"
        print(err_msg)
        telegram.send_message(f"🚨 <b>Falha no DeepSeek Trading Bot:</b>\n{err_msg}")
        sys.exit(1)
        
    decisions = analysis_result.get("decisoes", [])
    new_lessons = analysis_result.get("licoes_aprendidas", state.get("licoes_aprendidas", ""))
    
    # 8. Execução de Ordens (Simulação Local ou API Foxbit Real)
    print("[Passo 6/6] Processando decisões de investimento...")
    executed_trades = []
    
    for decision in decisions:
        ticker = decision.get("ticker", "").lower()
        acao = decision.get("acao", "").upper()
        quantidade = float(decision.get("quantidade", 0.0))
        
        if not ticker or quantidade <= 0 or acao == "MANTER":
            continue
            
        ticker_data = market_data.get(ticker)
        if not ticker_data:
            print(f"[Execução] Pulando decisão de {ticker} pois dados de mercado não estão disponíveis.")
            continue
            
        price = ticker_data["latest_price"]
        base_asset = get_base_asset(ticker)
        
        if acao == "COMPRAR":
            amount_brl = quantidade
            if amount_brl > brl_free:
                amount_brl_safe = brl_free * 0.99
                if amount_brl_safe >= 10.0:
                    print(f"[Execução] Saldo BRL insuficiente. Ajustando compra de R$ {amount_brl:.2f} para R$ {amount_brl_safe:.2f}.")
                    amount_brl = amount_brl_safe
                else:
                    err_txt = f"Saldo em BRL insuficiente para comprar {ticker}. Requerido: R$ {amount_brl:.2f} | Disponível: R$ {brl_free:.2f}"
                    print(f"[Execução] {err_txt}")
                    executed_trades.append({
                        "ticker": ticker,
                        "acao": acao,
                        "quantidade": quantidade,
                        "status": "error",
                        "erro": "Saldo BRL insuficiente"
                    })
                    continue
            
            crypto_qty_est = amount_brl / price
            
            if Config.SIMULATION_MODE:
                print(f"[Simulação] COMPRA virtual: {crypto_qty_est:.6f} {base_asset.upper()} por R$ {amount_brl:.2f}")
                balance_map["brl"] = balance_map.get("brl", 0.0) - amount_brl
                balance_map[base_asset] = balance_map.get(base_asset, 0.0) + crypto_qty_est
                brl_free = balance_map["brl"]
                
                executed_trades.append({
                    "ticker": ticker,
                    "acao": acao,
                    "quantidade": amount_brl,
                    "status": "success",
                    "preco": price,
                    "order_id": f"sim-buy-{int(time.time())}"
                })
            else:
                try:
                    order = foxbit.submit_instant_order(symbol=ticker, side="BUY", amount_brl=amount_brl)
                    executed_trades.append({
                        "ticker": ticker,
                        "acao": acao,
                        "quantidade": amount_brl,
                        "status": "success",
                        "preco": price,
                        "order_id": order.get("id")
                    })
                    brl_free -= amount_brl
                except Exception as e:
                    print(f"[Execução] Erro real ao comprar {ticker}: {e}")
                    executed_trades.append({
                        "ticker": ticker,
                        "acao": acao,
                        "quantidade": amount_brl,
                        "status": "error",
                        "erro": str(e)
                    })
                    
        elif acao == "VENDER":
            qty_to_sell = quantidade
            qty_owned = balance_map.get(base_asset, 0.0)
            
            if qty_owned <= 0.0:
                print(f"[Execução] Tentativa de vender {ticker}, mas não possui saldo de {base_asset.upper()}.")
                executed_trades.append({
                    "ticker": ticker,
                    "acao": acao,
                    "quantidade": qty_to_sell,
                    "status": "error",
                    "erro": f"Sem saldo de {base_asset.upper()} para vender"
                })
                continue
                
            if qty_to_sell > qty_owned:
                print(f"[Execução] Solicitada venda de {qty_to_sell:.6f} {base_asset.upper()}, mas possui apenas {qty_owned:.6f}. Limitando para {qty_owned:.6f}.")
                qty_to_sell = qty_owned
                
            revenue_brl_est = qty_to_sell * price
            
            if Config.SIMULATION_MODE:
                print(f"[Simulação] VENDA virtual: {qty_to_sell:.6f} {base_asset.upper()} gerando R$ {revenue_brl_est:.2f}")
                balance_map[base_asset] = balance_map.get(base_asset, 0.0) - qty_to_sell
                balance_map["brl"] = balance_map.get("brl", 0.0) + revenue_brl_est
                brl_free = balance_map["brl"]
                
                executed_trades.append({
                    "ticker": ticker,
                    "acao": acao,
                    "quantidade": qty_to_sell,
                    "status": "success",
                    "preco": price,
                    "order_id": f"sim-sell-{int(time.time())}"
                })
            else:
                try:
                    order = foxbit.submit_market_order(symbol=ticker, side="SELL", qty=qty_to_sell)
                    executed_trades.append({
                        "ticker": ticker,
                        "acao": acao,
                        "quantidade": qty_to_sell,
                        "status": "success",
                        "preco": price,
                        "order_id": order.get("id")
                    })
                except Exception as e:
                    print(f"[Execução] Erro real ao vender {ticker}: {e}")
                    executed_trades.append({
                        "ticker": ticker,
                        "acao": acao,
                        "quantidade": qty_to_sell,
                        "status": "error",
                        "erro": str(e)
                    })
                    
    # 9. Salva novo estado do bot
    print("[Passo 6/6] Salvando estado e enviando resumo de operações para o Telegram...")
    
    final_balances = []
    if Config.SIMULATION_MODE:
        state["saldos_virtuais"] = {
            k: float(v) for k, v in balance_map.items()
        }
        for asset, qty in state["saldos_virtuais"].items():
            final_balances.append({
                "asset": asset.upper(),
                "free": qty,
                "locked": 0.0
            })
    else:
        try:
            raw_balances = foxbit.get_account_balances()
            for bal in raw_balances:
                final_balances.append({
                    "asset": bal["currency_symbol"].upper(),
                    "free": float(bal["balance_available"]),
                    "locked": float(bal["balance_locked"])
                })
        except Exception:
            final_balances = balances

    final_balance_map = {bal["asset"].lower(): (bal["free"] + bal.get("locked", 0.0)) for bal in final_balances}
    total_portfolio_brl = final_balance_map.get("brl", 0.0)
    for asset, qty in final_balance_map.items():
        if asset == "brl":
            continue
        pair = f"{asset}brl"
        if pair in market_data:
            total_portfolio_brl += qty * market_data[pair]["latest_price"]

    state["saldo_anterior"] = round(total_portfolio_brl, 2)
    state["licoes_aprendidas"] = new_lessons
    
    for trade in executed_trades:
        if trade["status"] == "success":
            state["historico_trades"].append({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "ticker": trade["ticker"],
                "acao": trade["acao"],
                "quantidade": trade["quantidade"],
                "preco_estimado": trade["preco"]
            })
            
    if len(state["historico_trades"]) > 50:
        state["historico_trades"] = state["historico_trades"][-50:]
        
    state_manager.save_state(state)
    
    brl_final_cash = final_balance_map.get("brl", 0.0)
    
    telegram_msg = format_telegram_message(
        brl_balance=brl_final_cash,
        portfolio_value_brl=total_portfolio_brl,
        balances=final_balances,
        executed_trades=executed_trades,
        decisions=decisions,
        lessons=new_lessons,
        market_data=market_data,
        is_simulation=Config.SIMULATION_MODE,
        real_balances=real_balances_consultation,
        state=state
    )
    
    # Envia o relatório de texto principal
    telegram.send_message(telegram_msg)
    
    # 10. GERAÇÃO E ENVIO DE GRÁFICOS TÉCNICOS
    # Identifica os ativos que receberam recomendação ativa (Níveis 1, 2, 4, 5) para plotar
    active_tickers = [d.get("ticker", "").lower() for d in decisions if d.get("classificacao_nivel", 3) in [1, 2, 4, 5]]
    # Se não houver nenhum ativo ativo, envia o gráfico do BTCBRL por padrão
    if not active_tickers:
        active_tickers = ["btcbrl"]
        
    # Limita ao envio de no máximo 3 gráficos para evitar flood/spam de imagens no chat
    for ticker_to_plot in active_tickers[:3]:
        ticker_data = market_data.get(ticker_to_plot)
        if ticker_data and "raw_klines" in ticker_data:
            chart_path = f"charts/{ticker_to_plot}.png"
            try:
                print(f"[Chart] Gerando gráfico de análise técnica para {ticker_to_plot}...")
                generate_technical_chart(ticker_to_plot, ticker_data["raw_klines"], chart_path)
                
                # Envia a imagem do gráfico com uma breve legenda explicativa
                caption = f"📊 <b>Gráfico Técnico de Swing Trade - {ticker_to_plot.upper()}</b>"
                telegram.send_photo(chart_path, caption)
                
                # Exclui o arquivo de imagem local após o envio com sucesso
                if os.path.exists(chart_path):
                    os.remove(chart_path)
            except Exception as e:
                print(f"[Chart] Erro ao gerar ou enviar gráfico para {ticker_to_plot}: {e}")
                
    print("=== EXECUÇÃO FINALIZADA COM SUCESSO ===")

if __name__ == "__main__":
    main()
