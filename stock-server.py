"""
Ratepension Live Stock Data Server
Henter live data fra Yahoo Finance og udstiller som REST API
"""

from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
import yfinance as yf
import json
from datetime import datetime, timedelta
import threading
import time
import os

app = Flask(__name__)
CORS(app)

# Din portefølje
PORTFOLIO = [
    # Top aktier
    {"ticker": "MSFT", "name": "Microsoft", "shares": 30},
    {"ticker": "TSLA", "name": "Tesla", "shares": 31},
    {"ticker": "NVDA", "name": "NVIDIA", "shares": 51},
    {"ticker": "GOOGL", "name": "Alphabet", "shares": 26},
    {"ticker": "NVO", "name": "Novo Nordisk B", "shares": 189},
    {"ticker": "KO", "name": "Coca-Cola", "shares": 84},
    {"ticker": "SBUX", "name": "Starbucks", "shares": 62},
    {"ticker": "META", "name": "Meta", "shares": 8},
    {"ticker": "AAPL", "name": "Apple", "shares": 16},
    {"ticker": "COIN", "name": "Coinbase", "shares": 20},

    # Øvrige aktier
    {"ticker": "V", "name": "Visa Inc.", "shares": 9},
    {"ticker": "O", "name": "Realty Income", "shares": 48},
    {"ticker": "SAAB-B.ST", "name": "SAAB B", "shares": 44},
    {"ticker": "KTOS", "name": "Kratos Defense", "shares": 42},
    {"ticker": "SG", "name": "Strategy A", "shares": 14},
    {"ticker": "SPOT", "name": "Spotify", "shares": 3},
    {"ticker": "SOUN", "name": "SoundHound AI", "shares": 218},
    {"ticker": "SOFI", "name": "SoFi Technologies", "shares": 47},
    {"ticker": "CYBN", "name": "Cybin", "shares": 27},

    # ETF
    {"ticker": "EUNL.DE", "name": "iShares MSCI World ETF", "shares": 125},

    # Derivater (SKAL LUKKES!)
    {"ticker": "BULL.NOVO.X3", "name": "BULL NOVO X3 ND1", "shares": 198, "warning": True},
    {"ticker": "BULL.NFLX.X2", "name": "BULL NFLX X2 ND", "shares": 62, "warning": True},
]

# Cache for data
cache = {
    "stocks": {},
    "last_update": None,
    "update_interval": 300  # 5 minutter
}

def get_stock_data(ticker):
    """Henter data for en enkelt aktie"""
    try:
        stock = yf.Ticker(ticker)
        # Brug fast_info som fallback (mere robust)
        try:
            info = stock.fast_info
            current_price = info.get("currentPrice", 0) or info.get("lastPrice", 0)
        except:
            info = stock.info
            current_price = info.get("currentPrice", 0) or info.get("regularMarketPrice", 0)

        # Hent historisk data for år-performance
        hist = stock.history(period="1y")

        if len(hist) > 0:
            year_ago_price = hist.iloc[0]["Close"]
            year_change = ((current_price - year_ago_price) / year_ago_price * 100) if year_ago_price > 0 else 0
        else:
            year_change = 0

        return {
            "ticker": ticker,
            "price": round(current_price, 2) if current_price else 0,
            "currency": "USD",
            "change_day": round(info.get("regularMarketChangePercent", 0), 2) if info else 0,
            "change_year": round(year_change, 2),
            "market_cap": info.get("marketCap", 0) if info else 0,
            "pe_ratio": info.get("trailingPE", 0) if info else 0,
            "dividend_yield": 0,
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {str(e)}")
        # Fallback: mock data så dashboardet ikke er helt tomt
        mock_prices = {
            "MSFT": 418.65, "TSLA": 252.45, "NVDA": 128.95, "GOOGL": 178.50,
            "NVO": 83.45, "KO": 74.30, "SBUX": 102.15, "META": 561.75,
            "AAPL": 231.40, "COIN": 195.50, "V": 290.00, "O": 62.40,
            "SAAB-B.ST": 145.00, "KTOS": 28.50, "SG": 185.30, "SPOT": 300.50,
            "SOUN": 6.54, "SOFI": 28.30, "CYBN": 5.80, "EUNL.DE": 947.00
        }

        price = mock_prices.get(ticker, 100.0)

        return {
            "ticker": ticker,
            "price": price,
            "currency": "USD",
            "change_day": 0.0,
            "change_year": 0.0,
            "market_cap": 0,
            "pe_ratio": 0,
            "dividend_yield": 0,
            "note": "Mock data - yfinance fejl"
        }

def update_cache():
    """Opdater cache med live data"""
    print(f"[{datetime.now()}] Henter live data fra Yahoo Finance...")

    stocks_data = []
    for stock in PORTFOLIO:
        ticker = stock["ticker"]
        data = get_stock_data(ticker)
        data["name"] = stock["name"]
        data["shares"] = stock["shares"]
        if stock.get("warning"):
            data["warning"] = True
        stocks_data.append(data)

    cache["stocks"] = stocks_data
    cache["last_update"] = datetime.now().isoformat()
    print(f"[{datetime.now()}] Data opdateret succesfuldt! ({len(stocks_data)} aktier)")

def background_updater():
    """Opdater data i baggrund hver 5 minutter"""
    while True:
        update_cache()
        time.sleep(cache["update_interval"])

# Start background thread
updater_thread = threading.Thread(target=background_updater, daemon=True)
updater_thread.start()

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    """Returnerer hele porteføljen med live data"""

    if not cache["stocks"]:
        update_cache()  # First load

    # Beregn totaler
    total_value = 0
    total_shares_value = 0

    for stock in cache["stocks"]:
        if "price" in stock and stock["price"] > 0:
            value = stock["price"] * stock["shares"]
            total_shares_value += value

    return jsonify({
        "portfolio": cache["stocks"],
        "last_update": cache["last_update"],
        "total_shares": len(cache["stocks"]),
        "update_interval": cache["update_interval"],
        "summary": {
            "total_value_usd": round(total_shares_value, 2),
            "total_value_dkk": round(total_shares_value * 6.8, 2),
            "number_of_stocks": len(cache["stocks"]),
            "warning_count": len([s for s in cache["stocks"] if s.get("warning")])
        }
    })

@app.route("/api/stock/<ticker>", methods=["GET"])
def get_stock(ticker):
    """Returnerer data for en specifik aktie"""
    data = get_stock_data(ticker)
    return jsonify(data)

@app.route("/api/portfolio/<category>", methods=["GET"])
def get_portfolio_category(category):
    """Returnerer kategori af portefølje"""

    if not cache["stocks"]:
        update_cache()

    if category == "top":
        # Top 10 efter værdi
        sorted_stocks = sorted(
            cache["stocks"],
            key=lambda x: (x.get("price", 0) * x.get("shares", 0)),
            reverse=True
        )
        return jsonify(sorted_stocks[:10])

    elif category == "warnings":
        # Aktier med advarsler (derivater)
        warnings = [s for s in cache["stocks"] if s.get("warning")]
        return jsonify(warnings)

    elif category == "gainers":
        # Bedste performers i dag
        sorted_stocks = sorted(
            cache["stocks"],
            key=lambda x: x.get("change_day", 0),
            reverse=True
        )
        return jsonify(sorted_stocks[:5])

    elif category == "losers":
        # Værste performers i dag
        sorted_stocks = sorted(
            cache["stocks"],
            key=lambda x: x.get("change_day", 0)
        )
        return jsonify(sorted_stocks[:5])

    else:
        return jsonify({"error": "Unknown category"}), 400

@app.route("/api/refresh", methods=["POST"])
def manual_refresh():
    """Manuelt opdater data nu (i stedet for at vente 5 min)"""
    update_cache()
    return jsonify({
        "status": "success",
        "last_update": cache["last_update"],
        "stocks_count": len(cache["stocks"])
    })

@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "last_update": cache["last_update"],
        "stocks_cached": len(cache["stocks"])
    })

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Ratepension Dashboard"""
    api_url = os.environ.get("DASHBOARD_API_URL", "http://localhost:5000/api/portfolio")

    html = f"""<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ratepension Dashboard</title>
  <style>
    :root {{ --primary: #2563eb; --success: #10b981; --danger: #ef4444; --warning: #f59e0b; --dark: #1f2937; --light: #f3f4f6; --border: #e5e7eb; }}
    * {{ box-sizing: border-box; }} body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--light); color: var(--dark); padding: 20px; margin: 0; }}
    .container {{ max-width: 1600px; margin: 0 auto; }} h1 {{ margin: 0 0 10px 0; font-size: 28px; }} .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }}
    .table {{ width: 100%; border-collapse: collapse; font-size: 13px; }} .table th {{ text-align: left; padding: 10px; background: var(--light); font-weight: 600; border-bottom: 2px solid var(--border); }}
    .table td {{ padding: 10px; border-bottom: 1px solid var(--border); }} .positive {{ color: var(--success); }} .negative {{ color: var(--danger); }}
    button {{ padding: 8px 16px; border: none; border-radius: 4px; font-size: 13px; cursor: pointer; background: var(--primary); color: white; font-weight: 500; }}
  </style>
</head>
<body>
<div class="container">
  <h1>📊 Ratepension Dashboard</h1>
  <div class="card">
    <h3>Live Aktier fra Yahoo Finance</h3>
    <button onclick="location.reload()">🔄 Opdater</button>
    <table class="table">
      <thead><tr><th>Aktie</th><th>Antal</th><th>Pris (USD)</th><th>Beholdning (DKK)</th><th>Dag %</th></tr></thead>
      <tbody id="stockTable">
        <tr><td colspan="5" style="text-align: center; padding: 20px; color: #999;">📊 Henter data...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
  const API_URL = "{api_url}";
  const USDK_RATE = 6.8;

  async function loadData() {{
    try {{
      const response = await fetch(API_URL);
      const data = await response.json();

      const tbody = document.getElementById('stockTable');
      const rows = data.portfolio.map(stock => {{
        const price = stock.price || 0;
        const shares = stock.shares || 0;
        const valueDKK = price * shares * USDK_RATE;
        const change = stock.change_day || 0;
        const changeClass = change >= 0 ? 'positive' : 'negative';

        return `<tr>
          <td><strong>${{stock.name}}</strong></td>
          <td>${{shares}}</td>
          <td>$${{price.toFixed(2)}}</td>
          <td>kr ${{valueDKK.toLocaleString('da-DK', {{maximumFractionDigits: 0}})}}</td>
          <td class="${{changeClass}}">${{change >= 0 ? '▲' : '▼'}} ${{Math.abs(change).toFixed(2)}}%</td>
        </tr>`;
      }}).join('');

      tbody.innerHTML = rows;
    }} catch (e) {{
      document.getElementById('stockTable').innerHTML = `<tr><td colspan="5" style="text-align: center; color: red;">Fejl: ${{e.message}}</td></tr>`;
    }}
  }}

  window.addEventListener('load', loadData);
  setInterval(loadData, 5 * 60 * 1000);
</script>
</body>
</html>"""

    return html

@app.route("/", methods=["GET"])
def index():
    """Info side"""
    return jsonify({
        "name": "Ratepension Live Data Server",
        "version": "1.0",
        "endpoints": {
            "GET /api/portfolio": "Hele porteføljen med live data",
            "GET /api/stock/<ticker>": "Data for én aktie",
            "GET /api/portfolio/top": "Top 10 aktier efter værdi",
            "GET /api/portfolio/warnings": "Aktier med advarsler (derivater)",
            "GET /api/portfolio/gainers": "Top 5 bedste i dag",
            "GET /api/portfolio/losers": "Top 5 værste i dag",
            "POST /api/refresh": "Manuelt opdater nu",
            "GET /health": "Server status"
        },
        "last_update": cache["last_update"],
        "update_interval_seconds": cache["update_interval"]
    })

if __name__ == "__main__":
    print("🚀 Ratepension Live Data Server starter...")
    print("📊 Henter live data fra Yahoo Finance...")

    # Initial load
    update_cache()

    # Railway bruger PORT miljøvariabel, localhost bruger 5000
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0"  # Railway kræver 0.0.0.0, ikke 127.0.0.1

    print(f"\n✅ Server klar på port {port}!")
    print(f"📡 API dokumentation: http://localhost:{port}/")
    print("🔄 Data opdateres automatisk hver 5 minutter")
    print(f"📱 Dashboard kalder: http://localhost:{port}/api/portfolio\n")

    app.run(debug=False, port=port, host=host)
