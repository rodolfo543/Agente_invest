import requests
from typing import List, Dict, Any

class MarketDataCollector:
    def __init__(self, tickers: List[str], base_url: str = "https://api.foxbit.com.br"):
        self.tickers = tickers
        self.base_url = base_url.rstrip('/')

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        Calcula o RSI (Relative Strength Index) clássico em Python puro.
        """
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        
        gains = [d if d > 0 else 0 for d in deltas[:period]]
        losses = [-d if d < 0 else 0 for d in deltas[:period]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        for i in range(period, len(deltas)):
            delta = deltas[i]
            gain = delta if delta > 0 else 0
            loss = -delta if delta < 0 else 0
            
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def calculate_ema(self, prices: List[float], span: int) -> List[float]:
        """
        Calcula a Média Móvel Exponencial (EMA).
        """
        if len(prices) < span:
            return prices
        
        alpha = 2 / (span + 1)
        ema = [sum(prices[:span]) / span]  # Inicializa com a média simples
        
        for price in prices[span:]:
            ema.append(price * alpha + ema[-1] * (1 - alpha))
            
        return ema

    def calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """
        Calcula o MACD (Linha MACD, Sinal e Histograma).
        """
        if len(prices) < 26 + 9:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
            
        ema12 = self.calculate_ema(prices, 12)
        ema26 = self.calculate_ema(prices, 26)
        
        # Alinha os comprimentos a partir do final
        macd_line = []
        min_len = min(len(ema12), len(ema26))
        for i in range(-min_len, 0):
            macd_line.append(ema12[i] - ema26[i])
            
        signal_line = self.calculate_ema(macd_line, 9)
        
        if macd_line and signal_line:
            macd_val = macd_line[-1]
            signal_val = signal_line[-1]
            hist_val = macd_val - signal_val
            return {
                "macd": round(macd_val, 4),
                "signal": round(signal_val, 4),
                "histogram": round(hist_val, 4)
            }
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, num_std: float = 2.0) -> Dict[str, float]:
        """
        Calcula as Bandas de Bollinger (Média, Superior e Inferior).
        """
        if len(prices) < period:
            latest = prices[-1] if prices else 0.0
            return {"upper": latest, "middle": latest, "lower": latest}
            
        subset = prices[-period:]
        sma = sum(subset) / period
        
        variance = sum((p - sma) ** 2 for p in subset) / period
        std_dev = variance ** 0.5
        
        upper = sma + (num_std * std_dev)
        lower = sma - (num_std * std_dev)
        
        return {
            "upper": round(upper, 2),
            "middle": round(sma, 2),
            "lower": round(lower, 2)
        }

    def calculate_volatility_pct(self, prices: List[float], period: int = 20) -> float:
        """
        Calcula a volatilidade histórica em base percentual.
        """
        if len(prices) < period:
            return 0.0
        subset = prices[-period:]
        sma = sum(subset) / period
        variance = sum((p - sma) ** 2 for p in subset) / period
        std_dev = variance ** 0.5
        
        return round((std_dev / sma) * 100, 2)

    def calculate_fibonacci_retracement(self, prices: List[float], period: int = 30) -> Dict[str, float]:
        """
        Calcula os níveis de retração de Fibonacci baseados nas razões de 0, 23.6%, 38.2%, 50% e 61.8%.
        """
        if len(prices) < period:
            latest = prices[-1] if prices else 0.0
            return {"0.0": latest, "0.236": latest, "0.382": latest, "0.5": latest, "0.618": latest, "1.0": latest}
            
        subset = prices[-period:]
        high = max(subset)
        low = min(subset)
        diff = high - low
        
        return {
            "0.0": round(low, 2),
            "0.236": round(low + 0.236 * diff, 2),
            "0.382": round(low + 0.382 * diff, 2),
            "0.5": round(low + 0.5 * diff, 2),
            "0.618": round(low + 0.618 * diff, 2),
            "1.0": round(high, 2)
        }

    def fetch_data_for_ticker(self, ticker_name: str) -> Dict[str, Any]:
        """
        Coleta estatísticas das últimas 24h e histórico de velas da Foxbit 
        para cálculo de indicadores de Swing Trade.
        """
        print(f"[MarketData] Buscando dados da Foxbit para o par: {ticker_name}")
        try:
            # 1. Busca estatísticas de 24 horas (Ticker público)
            ticker_url = f"{self.base_url}/rest/v3/markets/{ticker_name.lower()}/ticker/24hr"
            res_ticker = requests.get(ticker_url, timeout=10)
            res_ticker.raise_for_status()
            stats = res_ticker.json()
            
            if not stats or "data" not in stats or not stats["data"]:
                print(f"[MarketData] Formato de ticker inválido para {ticker_name}")
                return {}
            ticker_data = stats["data"][0]
            
            latest_price = float(ticker_data["last_trade"]["price"])
            change_percent = float(ticker_data["rolling_24h"]["price_change_percent"])
            high_24h = float(ticker_data["rolling_24h"]["high"])
            low_24h = float(ticker_data["rolling_24h"]["low"])
            volume_24h = float(ticker_data["rolling_24h"]["volume"])

            # 2. Busca histórico de velas de 1 dia (candlesticks)
            klines_url = f"{self.base_url}/rest/v3/markets/{ticker_name.lower()}/candlesticks"
            params = {
                "interval": "1d"
            }
            res_klines = requests.get(klines_url, params=params, timeout=10)
            res_klines.raise_for_status()
            klines = res_klines.json()

            if not klines or len(klines) < 10:
                print(f"[MarketData] Dados insuficientes de candlesticks para {ticker_name}")
                return {}

            # Garante que as velas estão ordenadas de forma cronológica crescente (antigo para novo)
            sorted_klines = sorted(klines, key=lambda x: int(x[0]))
            
            # Fechamento é o index 4 na lista do Candlestick da Foxbit
            close_prices = [float(k[4]) for k in sorted_klines]
            
            # Cálculo de Médias Móveis Simples (SMA)
            sma_10 = round(sum(close_prices[-10:]) / len(close_prices[-10:]), 2) if len(close_prices) >= 10 else latest_price
            sma_20 = round(sum(close_prices[-20:]) / len(close_prices[-20:]), 2) if len(close_prices) >= 20 else latest_price
            
            # Cálculo de RSI 14
            rsi_14 = self.calculate_rsi(close_prices, 14)
            
            # Cálculo de Bandas de Bollinger, MACD, Volatilidade e Fibonacci
            bollinger = self.calculate_bollinger_bands(close_prices, 20)
            macd_vals = self.calculate_macd(close_prices)
            volatility = self.calculate_volatility_pct(close_prices, 20)
            fibonacci = self.calculate_fibonacci_retracement(close_prices, 30)

            return {
                "ticker": ticker_name,
                "latest_price": latest_price,
                "change_percent_24h": change_percent,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "volume_24h": volume_24h,
                "sma_10": sma_10,
                "sma_20": sma_20,
                "rsi_14": rsi_14,
                "bollinger_bands": bollinger,
                "macd": macd_vals,
                "volatility_pct": volatility,
                "fibonacci_retracement_30d": fibonacci,
                "prices_last_10_days": [round(p, 4) for p in close_prices[-10:]],
                "raw_klines": klines
            }


        except Exception as e:
            print(f"[MarketData] Erro ao coletar dados do par {ticker_name}: {e}")
            return {}


    def fetch_all_market_data(self) -> Dict[str, Any]:
        """
        Busca e consolida os indicadores de todos os pares monitorados.
        """
        results = {}
        for ticker in self.tickers:
            data = self.fetch_data_for_ticker(ticker)
            if data:
                results[ticker] = data
        return results

