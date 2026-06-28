import os
import datetime
import matplotlib
# Configura o matplotlib para modo não interativo (evita problemas em ambientes headless como GitHub Actions)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import List, Any, Dict

def generate_technical_chart(ticker: str, klines: List[List[Any]], save_path: str) -> str:
    """
    Gera um gráfico técnico sofisticado (Tema Escuro) contendo:
    - Linha de Fechamento de Preço
    - Médias Móveis (SMA 10 e SMA 20)
    - Bandas de Bollinger (Shaded region)
    - Níveis de Retração de Fibonacci (Dotted lines)
    
    Salva a imagem no caminho especificado e retorna o caminho.
    """
    # Garante que o diretório de destino existe
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # 1. Pré-processamento e Ordenação
    sorted_klines = sorted(klines, key=lambda x: int(x[0]))
    
    # Precisamos de pelo menos 20 dias históricos para calcular as bandas e médias.
    # Como a Foxbit traz 100 velas por padrão, temos dados suficientes.
    timestamps = [datetime.datetime.fromtimestamp(int(k[0])/1000) for k in sorted_klines]
    closes = [float(k[4]) for k in sorted_klines]
    
    # 2. Calcula as séries históricas de SMA 10, SMA 20 e Bollinger Bands
    sma_10_series = []
    sma_20_series = []
    bb_upper_series = []
    bb_lower_series = []
    
    for i in range(len(closes)):
        # SMA 10
        if i >= 9:
            sma_10_series.append(sum(closes[i-9:i+1]) / 10)
        else:
            sma_10_series.append(closes[i])
            
        # SMA 20 e Bollinger
        if i >= 19:
            subset = closes[i-19:i+1]
            sma_20 = sum(subset) / 20
            sma_20_series.append(sma_20)
            
            variance = sum((p - sma_20) ** 2 for p in subset) / 20
            std_dev = variance ** 0.5
            bb_upper_series.append(sma_20 + (2.0 * std_dev))
            bb_lower_series.append(sma_20 - (2.0 * std_dev))
        else:
            sma_20_series.append(closes[i])
            bb_upper_series.append(closes[i])
            bb_lower_series.append(closes[i])

    # Foca nos últimos 30 dias para a visualização do gráfico
    view_period = 30
    plot_timestamps = timestamps[-view_period:]
    plot_closes = closes[-view_period:]
    plot_sma_10 = sma_10_series[-view_period:]
    plot_sma_20 = sma_20_series[-view_period:]
    plot_bb_upper = bb_upper_series[-view_period:]
    plot_bb_lower = bb_lower_series[-view_period:]
    
    # 3. Calcula Fibonacci sobre a janela visualizada de 30 dias
    high_30 = max(plot_closes)
    low_30 = min(plot_closes)
    diff = high_30 - low_30
    fib_levels = {
        "0.0 (Min)": low_30,
        "0.236": low_30 + 0.236 * diff,
        "0.382": low_30 + 0.382 * diff,
        "0.500": low_30 + 0.5 * diff,
        "0.618": low_30 + 0.618 * diff,
        "1.0 (Max)": high_30
    }

    # 4. Configuração do Estilo e Tema Escuro (Visual Premium)
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor('#121212')
    ax.set_facecolor('#1e1e1e')
    
    # Plota a faixa das Bandas de Bollinger
    ax.fill_between(plot_timestamps, plot_bb_lower, plot_bb_upper, color='#00E5FF', alpha=0.06, label='Banda de Bollinger (2.0 std)')
    ax.plot(plot_timestamps, plot_bb_upper, color='#455A64', linestyle=':', linewidth=1.0)
    ax.plot(plot_timestamps, plot_bb_lower, color='#455A64', linestyle=':', linewidth=1.0)
    
    # Plota a linha de fechamento e as médias móveis
    ax.plot(plot_timestamps, plot_closes, color='#00E5FF', linewidth=2.0, label='Preço Fechamento')
    ax.plot(plot_timestamps, plot_sma_10, color='#FFD54F', linestyle='--', linewidth=1.2, label='Média SMA 10')
    ax.plot(plot_timestamps, plot_sma_20, color='#FF7043', linestyle='--', linewidth=1.2, label='Média SMA 20')
    
    # Plota as linhas horizontais de Fibonacci
    colors_fib = ["#78909C", "#AB47BC", "#26A69A", "#EC407A", "#26C6DA", "#78909C"]
    for idx, (label, val) in enumerate(fib_levels.items()):
        ax.axhline(val, color=colors_fib[idx % len(colors_fib)], linestyle=':', alpha=0.6, linewidth=1.0)
        # Adiciona a legenda de Fibonacci no final da linha (à direita)
        ax.text(plot_timestamps[-1], val, f" Fib {label}: R$ {val:,.2f}", 
                color=colors_fib[idx % len(colors_fib)], fontsize=7, va='center', ha='left')

    # Configuração de eixos, títulos e labels
    ax.set_title(f"Análise Técnica - {ticker.upper()} (Últimos 30 Dias)", fontsize=13, color='#FFFFFF', pad=15, fontweight='bold')
    ax.set_ylabel("Preço em Reais (BRL)", fontsize=9, color='#B0BEC5')
    
    # Formatação das Datas no eixo X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax.tick_params(colors='#B0BEC5', labelsize=8)
    
    # Adiciona grid fino e legenda
    ax.grid(True, color='#263238', linestyle='-', alpha=0.5)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.8, facecolor='#1e1e1e', edgecolor='#37474F')
    
    # Ajusta as margens para que o texto do Fibonacci à direita caiba na imagem
    plt.subplots_adjust(right=0.82)
    
    # Salva o arquivo em disco
    plt.savefig(save_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close()
    
    return save_path
