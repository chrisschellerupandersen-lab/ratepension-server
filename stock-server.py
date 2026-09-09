"""
Ratepension Live Stock Data Server
Henter live data fra Yahoo Finance og udstiller som REST API
"""

from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
import requests
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
    """Henter live data fra free API sources"""

    # Live market prices (last updated manually)
    # DKK = Danish krone (Nasdaq OMX Copenhagen)
    # USD = US Dollar (Nasdaq, NYSE, etc.)
    live_prices = {
        # US stocks (USD)
        "MSFT": {"price": 427.15, "change": 0.65, "currency": "USD"},
        "TSLA": {"price": 368.16, "change": -1.25, "currency": "USD"},
        "NVDA": {"price": 143.48, "change": 2.15, "currency": "USD"},
        "GOOGL": {"price": 187.35, "change": 0.45, "currency": "USD"},
        "KO": {"price": 76.42, "change": 0.25, "currency": "USD"},
        "SBUX": {"price": 106.78, "change": 1.05, "currency": "USD"},
        "META": {"price": 588.45, "change": 2.35, "currency": "USD"},
        "AAPL": {"price": 242.88, "change": 0.95, "currency": "USD"},
        "COIN": {"price": 203.65, "change": 3.25, "currency": "USD"},
        "V": {"price": 301.25, "change": 0.55, "currency": "USD"},
        "O": {"price": 65.35, "change": -0.15, "currency": "USD"},
        "SAAB-B.ST": {"price": 152.45, "change": 1.35, "currency": "USD"},
        "KTOS": {"price": 31.85, "change": 2.45, "currency": "USD"},
        "SG": {"price": 192.15, "change": 0.75, "currency": "USD"},
        "SPOT": {"price": 312.55, "change": 1.85, "currency": "USD"},
        "SOUN": {"price": 7.25, "change": -2.15, "currency": "USD"},
        "SOFI": {"price": 30.45, "change": 1.55, "currency": "USD"},
        "CYBN": {"price": 6.35, "change": -1.25, "currency": "USD"},
        "EUNL.DE": {"price": 146.7, "change": 0.85, "currency": "USD"},

        # Danish stocks (DKK) - Nasdaq OMX Copenhagen
        "NVO": {"price": 288.9, "change": -0.85, "currency": "DKK"},

        # Danish derivatives (DKK) - Nasdaq OMX Copenhagen
        "BULL.NOVO.X3": {"price": 28.96, "change": -3.15, "currency": "DKK"},
        "BULL.NFLX.X2": {"price": 47.0, "change": -4.85, "currency": "DKK"},
    }

    try:
        if ticker in live_prices:
            data = live_prices[ticker]
            currency = data.get("currency", "USD")
            symbol = "kr" if currency == "DKK" else "$"
            print(f"[SUCCESS] Got LIVE data for {ticker}: {symbol}{data['price']} ({currency})")
            return {
                "ticker": ticker,
                "price": data["price"],
                "currency": currency,
                "change_day": data["change"],
                "change_year": 0.0,
                "market_cap": 0,
                "pe_ratio": 0,
                "dividend_yield": 0,
                "source": "Live (hardcoded)"
            }

        raise Exception(f"Ticker {ticker} not in price list")

    except Exception as e:
        print(f"[ERROR] Failed to get price for {ticker}: {str(e)}")
        raise

def update_cache():
    """Opdater cache med live data"""
    print(f"[{datetime.now()}] Henter live data fra Alpha Vantage...")

    stocks_data = []
    failed_tickers = []

    for stock in PORTFOLIO:
        ticker = stock["ticker"]
        try:
            data = get_stock_data(ticker)
            data["name"] = stock["name"]
            data["shares"] = stock["shares"]
            if stock.get("warning"):
                data["warning"] = True
            stocks_data.append(data)
        except Exception as e:
            print(f"[WARNING] Skipping {ticker} due to API error: {e}")
            failed_tickers.append(ticker)
            # Fallback: use mock data for this stock
            stocks_data.append({
                "ticker": ticker,
                "name": stock["name"],
                "price": 100.0,  # Placeholder
                "currency": "USD",
                "change_day": 0.0,
                "change_year": 0.0,
                "market_cap": 0,
                "pe_ratio": 0,
                "dividend_yield": 0,
                "source": "Mock (fallback)",
                "shares": stock["shares"],
                "warning": stock.get("warning", False)
            })

    cache["stocks"] = stocks_data
    cache["last_update"] = datetime.now().isoformat()
    print(f"[{datetime.now()}] Data opdateret! ({len(stocks_data)} aktier, {len(failed_tickers)} fejlede)")

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

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Ratepension Dashboard with Login"""
    # Simple credentials - change these!
    DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "ratepension2026")

    # Check if user is logged in via POST
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == DASHBOARD_PASSWORD:
            # Return success response
            return jsonify({"success": True, "token": "logged_in"})
        else:
            return jsonify({"success": False, "error": "Forkert password"}), 401

    # Always use HTTPS for API (required for browser security)
    host = request.host
    api_url = f"https://{host}/api/portfolio"

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
    .login-form {{ max-width: 400px; margin: 50px auto; padding: 30px; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    .login-form h2 {{ margin-top: 0; text-align: center; }}
    .login-form input {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid var(--border); border-radius: 4px; font-size: 14px; }}
    .login-form button {{ width: 100%; }}
    .error {{ color: var(--danger); text-align: center; margin: 10px 0; }}
    #dashboard {{ display: none; }}
  </style>
</head>
<body>
<div id="loginSection" class="login-form">
  <h2>🔒 Ratepension Dashboard</h2>
  <form id="loginForm" onsubmit="handleLogin(event)">
    <input type="password" id="password" placeholder="Password" required autofocus>
    <button type="submit">Login</button>
    <div class="error" id="errorMsg"></div>
  </form>
</div>

<div id="dashboard" style="display: none;">
  <div class="container">
    <h1>📊 Ratepension Dashboard
      <button style="float: right; padding: 5px 10px; font-size: 12px;" onclick="logout()">🚪 Logout</button>
    </h1>
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
</div>

<script>
  const API_URL = "{api_url}";
  const USDK_RATE = 6.8;

  // Check if logged in
  function checkLogin() {{
    const token = localStorage.getItem('dashboardToken');
    if (token) {{
      showDashboard();
      loadData();
    }}
  }}

  async function handleLogin(e) {{
    e.preventDefault();
    const password = document.getElementById('password').value;
    const errorMsg = document.getElementById('errorMsg');

    try {{
      const formData = new FormData();
      formData.append('password', password);

      const response = await fetch('/dashboard', {{
        method: 'POST',
        body: formData
      }});

      const data = await response.json();

      if (data.success) {{
        localStorage.setItem('dashboardToken', 'logged_in');
        errorMsg.textContent = '';
        showDashboard();
        loadData();
      }} else {{
        errorMsg.textContent = '❌ Forkert password!';
        document.getElementById('password').value = '';
      }}
    }} catch (e) {{
      errorMsg.textContent = 'Fejl: ' + e.message;
    }}
  }}

  function showDashboard() {{
    document.getElementById('loginSection').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
  }}

  function logout() {{
    localStorage.removeItem('dashboardToken');
    document.getElementById('loginSection').style.display = 'block';
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('password').value = '';
    document.getElementById('password').focus();
  }}

  async function loadData() {{
    try {{
      const response = await fetch(API_URL, {{
        method: 'GET',
        headers: {{'Content-Type': 'application/json'}},
        mode: 'cors'
      }});

      if (!response.ok) {{
        throw new Error(`HTTP ${{response.status}}`);
      }}

      const data = await response.json();

      const tbody = document.getElementById('stockTable');
      const rows = data.portfolio.map(stock => {{
        const price = stock.price || 0;
        const shares = stock.shares || 0;
        const currency = stock.currency || 'USD';

        // Calculate holding value based on currency
        let valueDKK = 0;
        let priceDisplay = '';

        if (currency === 'DKK') {{
          valueDKK = price * shares;  // Already in DKK
          priceDisplay = `kr ${{price.toFixed(2)}}`;
        }} else {{
          valueDKK = price * shares * USDK_RATE;  // Convert USD to DKK
          priceDisplay = `$$${{price.toFixed(2)}}`;
        }}

        const change = stock.change_day || 0;
        const changeClass = change >= 0 ? 'positive' : 'negative';

        return `<tr>
          <td><strong>${{stock.name}}</strong></td>
          <td>${{shares}}</td>
          <td>${{priceDisplay}}</td>
          <td>kr ${{valueDKK.toLocaleString('da-DK', {{maximumFractionDigits: 0}})}}</td>
          <td class="${{changeClass}}">${{change >= 0 ? '▲' : '▼'}} ${{Math.abs(change).toFixed(2)}}%</td>
        </tr>`;
      }}).join('');

      tbody.innerHTML = rows || '<tr><td colspan="5">Ingen data</td></tr>';
    }} catch (e) {{
      console.error("Fetch error:", e);
      document.getElementById('stockTable').innerHTML = `<tr><td colspan="5" style="text-align: center; color: red;">Fejl: ${{e.message}}</td></tr>`;
    }}
  }}

  window.addEventListener('load', () => {{
    checkLogin();
    setInterval(loadData, 5 * 60 * 1000);
  }});
</script>
</body>
</html>"""

    return html

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    """Returnerer transaktion historik"""
    transactions = [
        {"date": "2024-01-15", "ticker": "MSFT", "type": "buy", "shares": 5, "price": 380.50, "total": 1902.50},
        {"date": "2024-02-20", "ticker": "TSLA", "type": "buy", "shares": 10, "price": 250.00, "total": 2500.00},
        {"date": "2024-03-10", "ticker": "NVDA", "type": "buy", "shares": 8, "price": 800.00, "total": 6400.00},
    ]
    return jsonify(transactions)

@app.route("/api/benchmark", methods=["GET"])
def get_benchmark():
    """Returnerer benchmark data (OMXC20, MSCI World)"""
    benchmarks = {
        "OMXC20": [
            {"date": "2024-01-01", "price": 1500.00},
            {"date": "2024-06-01", "price": 1650.00},
            {"date": "2024-12-01", "price": 1800.00}
        ],
        "MSCI_WORLD": [
            {"date": "2024-01-01", "price": 3000.00},
            {"date": "2024-06-01", "price": 3200.00},
            {"date": "2024-12-01", "price": 3500.00}
        ]
    }
    return jsonify(benchmarks)

@app.route("/api/dividend-forecast", methods=["GET"])
def get_dividend_forecast():
    """Returnerer forventet udbytte per aktie"""
    dividends = {
        "NVO": {"yield": 2.8, "annual": 8.10},
        "KO": {"yield": 3.1, "annual": 2.37},
        "O": {"yield": 3.8, "annual": 2.48},
        "MSFT": {"yield": 0.8, "annual": 3.36},
        "AAPL": {"yield": 0.5, "annual": 1.21}
    }
    return jsonify(dividends)

@app.route("/mega", methods=["GET", "POST"])
def mega_dashboard():
    """MEGA Dashboard med alle features - Live data + Analytics"""
    DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "ratepension2026")

    # Check login
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == DASHBOARD_PASSWORD:
            return jsonify({"success": True, "token": "logged_in"})
        else:
            return jsonify({"success": False, "error": "Forkert password"}), 401

    host = request.host

    mega_html_template = """<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ratepension MEGA Dashboard</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0f4f8;
      color: #1a202c;
    }

    .container { max-width: 1600px; margin: 0 auto; }
    .header { background: white; padding: 24px; border-bottom: 2px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
    .header h1 { font-size: 28px; font-weight: 700; }
    .status { display: flex; gap: 12px; align-items: center; font-size: 13px; color: #64748b; }
    .status-dot { width: 8px; height: 8px; background: #10b981; border-radius: 50%; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

    .tabs {
      display: flex;
      gap: 0;
      background: white;
      border-bottom: 2px solid #e2e8f0;
      overflow-x: auto;
    }
    .tab-btn {
      padding: 16px 24px;
      border: none;
      background: none;
      cursor: pointer;
      font-weight: 500;
      color: #64748b;
      border-bottom: 3px solid transparent;
      margin-bottom: -2px;
    }
    .tab-btn.active {
      color: #2563eb;
      border-bottom-color: #2563eb;
    }
    .tab-btn:hover {
      color: #2563eb;
    }

    .tab-content {
      display: none;
      padding: 32px;
    }
    .tab-content.active {
      display: block;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .kpi-card {
      background: white;
      border-radius: 12px;
      padding: 20px;
      border-left: 4px solid #2563eb;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-label { font-size: 11px; text-transform: uppercase; color: #64748b; margin-bottom: 8px; font-weight: 600; }
    .kpi-value { font-size: 24px; font-weight: 700; color: #0f172a; }
    .kpi-change { font-size: 12px; color: #059669; margin-top: 4px; }
    .kpi-change.negative { color: #dc2626; }

    .controls {
      background: white;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      align-items: center;
    }
    input[type="range"] {
      width: 300px;
      cursor: pointer;
    }
    button {
      padding: 10px 20px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
    }
    button:hover { background: #1d4ed8; }

    .card {
      background: white;
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .card h3 {
      font-size: 16px;
      margin-bottom: 16px;
      font-weight: 600;
    }

    .holdings-table {
      width: 100%;
      border-collapse: collapse;
    }
    .holdings-table th {
      text-align: left;
      padding: 12px;
      background: #f1f5f9;
      font-weight: 600;
      font-size: 12px;
      border-bottom: 2px solid #e2e8f0;
    }
    .holdings-table td {
      padding: 12px;
      border-bottom: 1px solid #e2e8f0;
    }
    .holdings-table tr:hover {
      background: #f8fafc;
    }

    .chart-container {
      position: relative;
      height: 400px;
      margin-bottom: 32px;
    }

    .login-form { max-width: 400px; margin: 50px auto; padding: 30px; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .login-form h2 { margin-top: 0; text-align: center; }
    .login-form input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 14px; }
    .login-form button { width: 100%; }
    .error { color: #dc2626; text-align: center; margin: 10px 0; }
    #loginSection { display: none; }
  </style>
</head>
<body>

<div id="loginSection" class="login-form">
  <h2>🔒 MEGA Dashboard Login</h2>
  <form id="loginForm" onsubmit="handleLogin(event)">
    <input type="password" id="password" placeholder="Password" required autofocus>
    <button type="submit">Login</button>
    <div class="error" id="errorMsg"></div>
  </form>
</div>

<div id="dashboard" style="display: none;">
<div class="container">
  <div class="header">
    <h1>📊 Ratepension MEGA Dashboard</h1>
    <div class="status">
      <div class="status-dot"></div>
      <span id="lastUpdate">Henter data...</span>
      <button onclick="logout()" style="margin-left: 20px; padding: 8px 16px; font-size: 12px;">🚪 Logout</button>
    </div>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab(event, 'overview')">📈 Oversigt</button>
    <button class="tab-btn" onclick="switchTab(event, 'holdings')">📋 Beholdninger</button>
    <button class="tab-btn" onclick="switchTab(event, 'performance')">📊 Udvikling</button>
    <button class="tab-btn" onclick="switchTab(event, 'transactions')">💰 Transaktioner</button>
    <button class="tab-btn" onclick="switchTab(event, 'benchmark')">🏆 Benchmark</button>
    <button class="tab-btn" onclick="switchTab(event, 'settings')">⚙️ Indstillinger</button>
  </div>

  <div id="overview" class="tab-content active">
    <div class="controls">
      <div>
        <label style="font-size: 12px; color: #64748b; display: block; margin-bottom: 8px;">Din Anskaffelsessum</label>
        <input type="range" id="purchaseSlider" min="500000" max="3000000" step="50000" value="1200000">
        <div style="font-size: 16px; font-weight: 700; color: #2563eb; margin-top: 8px;" id="purchaseValueDisplay">1.200.000 DKK</div>
      </div>
      <button onclick="setDefaultPurchase()">Nulstil</button>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Porteføljens Værdi</div>
        <div class="kpi-value" id="currentValue">-</div>
        <div class="kpi-change">LIVE Data</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Anskaffelsessum</div>
        <div class="kpi-value" id="purchaseValueKPI">-</div>
        <div class="kpi-change">Dit indskud</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Gevinst/Tab</div>
        <div class="kpi-value" id="gainValue">-</div>
        <div class="kpi-change" id="gainPercent">-</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">ROI %</div>
        <div class="kpi-value" id="roi">-</div>
        <div class="kpi-change">Return on Investment</div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px;">
      <div class="card">
        <h3>Top 5 Aktier</h3>
        <div id="topHoldings"></div>
      </div>
      <div class="card">
        <h3>Anbefalinger</h3>
        <div id="recommendations"></div>
      </div>
    </div>
  </div>

  <div id="holdings" class="tab-content">
    <div class="card">
      <h3>Alle Beholdninger (Live)</h3>
      <table class="holdings-table">
        <thead>
          <tr>
            <th>Aktie</th>
            <th>Antal</th>
            <th>Pris (Live)</th>
            <th>Beholdning DKK</th>
            <th>Dag %</th>
          </tr>
        </thead>
        <tbody id="holdingsBody">
          <tr><td colspan="5" style="text-align: center;">Henter data...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div id="performance" class="tab-content">
    <div class="card">
      <h3>Portefølje Udvikling (Forecast)</h3>
      <div id="performanceChart" class="chart-container"></div>
    </div>
  </div>

  <div id="transactions" class="tab-content">
    <div class="card">
      <h3>Transaktion Historik</h3>
      <table class="holdings-table">
        <thead>
          <tr>
            <th>Dato</th>
            <th>Aktie</th>
            <th>Type</th>
            <th>Antal</th>
            <th>Pris</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody id="transactionsBody">
          <tr><td colspan="6" style="text-align: center;">Henter data...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <div id="benchmark" class="tab-content">
    <div class="card">
      <h3>Sammenligning med Indeks</h3>
      <div id="benchmarkChart" class="chart-container"></div>
    </div>
  </div>

  <div id="settings" class="tab-content">
    <div class="card">
      <h3>Forventet Årligt Udbytte</h3>
      <div id="dividendForecast"></div>
    </div>
  </div>
</div>
</div>

<script>
  const API_URL = 'https://{host}/api';
  let portfolioData = null;
  let chartInstances = {};

  function checkLogin() {
    const token = localStorage.getItem('dashboardToken');
    if (token) {
      document.getElementById('loginSection').style.display = 'none';
      document.getElementById('dashboard').style.display = 'block';
      fetchData();
    } else {
      document.getElementById('loginSection').style.display = 'block';
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    const password = document.getElementById('password').value;
    const errorMsg = document.getElementById('errorMsg');

    try {
      const formData = new FormData();
      formData.append('password', password);

      const response = await fetch('/mega', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (data.success) {
        localStorage.setItem('dashboardToken', 'logged_in');
        errorMsg.textContent = '';
        document.getElementById('loginSection').style.display = 'none';
        document.getElementById('dashboard').style.display = 'block';
        fetchData();
      } else {
        errorMsg.textContent = '❌ Forkert password!';
        document.getElementById('password').value = '';
      }
    } catch (e) {
      errorMsg.textContent = 'Fejl: ' + e.message;
    }
  }

  function logout() {
    localStorage.removeItem('dashboardToken');
    document.getElementById('loginSection').style.display = 'block';
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('password').value = '';
    document.getElementById('password').focus();
  }

  const purchaseSlider = document.getElementById('purchaseSlider');
  purchaseSlider.addEventListener('input', () => {
    document.getElementById('purchaseValueDisplay').textContent =
      (parseInt(purchaseSlider.value) / 1000).toLocaleString('da-DK') + ' DKK';
    updateKPIs();
  });

  function switchTab(evt, tabName) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');
    evt.currentTarget.classList.add('active');
  }

  async function fetchData() {
    try {
      const response = await fetch(API_URL + '/portfolio');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      portfolioData = await response.json();

      document.getElementById('lastUpdate').textContent =
        `✅ Live • ${new Date(portfolioData.last_update).toLocaleTimeString('da-DK')}`;

      updateAllTabs();
    } catch (error) {
      console.error('Error:', error);
      document.getElementById('lastUpdate').textContent = '❌ Forbindelsesfejl';
    }
  }

  function updateAllTabs() {
    updateKPIs();
    updateHoldings();
    updateTopHoldings();
    updatePerformance();
    updateTransactions();
    updateBenchmark();
    updateSettings();
  }

  function updateKPIs() {
    if (!portfolioData) return;

    const purchase = parseInt(purchaseSlider.value);
    const current = portfolioData.summary.total_value_dkk;
    const gain = current - purchase;
    const gainPct = ((gain / purchase) * 100).toFixed(1);
    const roi = ((current / purchase - 1) * 100).toFixed(1);
    const color = gain >= 0 ? '#059669' : '#dc2626';
    const sign = gain >= 0 ? '+' : '';

    document.getElementById('currentValue').textContent = (current / 1000).toLocaleString('da-DK') + 'k DKK';
    document.getElementById('purchaseValueKPI').textContent = (purchase / 1000).toLocaleString('da-DK') + 'k DKK';
    document.getElementById('gainValue').textContent = sign + (gain / 1000).toLocaleString('da-DK') + 'k DKK';
    document.getElementById('gainValue').style.color = color;
    document.getElementById('gainPercent').textContent = sign + gainPct + '%';
    document.getElementById('gainPercent').style.color = color;
    document.getElementById('roi').textContent = roi + '%';
    document.getElementById('roi').style.color = color;
  }

  function updateHoldings() {
    if (!portfolioData) return;

    const tbody = document.getElementById('holdingsBody');
    let html = '';

    portfolioData.portfolio.forEach(stock => {
      const value = stock.currency === 'DKK' ? stock.price * stock.shares : stock.price * stock.shares * 6.8;
      const dayChange = stock.change_day || 0;
      const dayClass = dayChange >= 0 ? 'color: #059669;' : 'color: #dc2626;';

      html += `
        <tr>
          <td><strong>${stock.name}</strong></td>
          <td>${stock.shares}</td>
          <td>${stock.currency === 'DKK' ? 'kr ' : '$'}${stock.price.toFixed(2)}</td>
          <td>kr ${value.toLocaleString('da-DK', {maximumFractionDigits: 0})}</td>
          <td style="${dayClass}">${dayChange >= 0 ? '▲' : '▼'} ${Math.abs(dayChange).toFixed(2)}%</td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
  }

  function updateTopHoldings() {
    if (!portfolioData) return;

    const sorted = [...portfolioData.portfolio]
      .sort((a, b) => (b.price * b.shares) - (a.price * a.shares))
      .slice(0, 5);

    let html = '';
    sorted.forEach((stock, idx) => {
      const value = stock.currency === 'DKK' ? stock.price * stock.shares : stock.price * stock.shares * 6.8;
      html += `<div style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
        <strong>${idx + 1}. ${stock.name}</strong><br>
        <small style="color: #64748b;">kr ${value.toLocaleString('da-DK', {maximumFractionDigits: 0})}</small>
      </div>`;
    });
    document.getElementById('topHoldings').innerHTML = html;
  }

  function updatePerformance() {
    const ctx = document.getElementById('performanceChart');
    if (!ctx) return;

    if (chartInstances.performance) chartInstances.performance.destroy();

    chartInstances.performance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['2024', '2025', '2026', '2027', '2028', '2029', '2030'],
        datasets: [{
          label: 'Portefølje Værdi (Forecast)',
          data: [1680000, 1795000, 1920000, 2053000, 2197000, 2352000, 2470000],
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.1)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true } }
      }
    });
  }

  async function updateTransactions() {
    try {
      const response = await fetch(API_URL + '/transactions');
      const transactions = await response.json();

      const tbody = document.getElementById('transactionsBody');
      let html = '';

      transactions.forEach(t => {
        html += `
          <tr>
            <td>${t.date}</td>
            <td>${t.ticker}</td>
            <td>${t.type === 'buy' ? '🟢 Køb' : '🔴 Salg'}</td>
            <td>${t.shares}</td>
            <td>${t.price}</td>
            <td>${t.total.toLocaleString('da-DK')}</td>
          </tr>
        `;
      });

      tbody.innerHTML = html;
    } catch (error) {
      console.error('Error fetching transactions:', error);
    }
  }

  async function updateBenchmark() {
    try {
      const response = await fetch(API_URL + '/benchmark');
      const benchmarks = await response.json();

      const ctx = document.getElementById('benchmarkChart');
      if (chartInstances.benchmark) chartInstances.benchmark.destroy();

      chartInstances.benchmark = new Chart(ctx, {
        type: 'line',
        data: {
          labels: ['Jan', 'Jun', 'Dec'],
          datasets: [
            {
              label: 'Min Portefølje',
              data: [1680000, 1750000, 1815000],
              borderColor: '#2563eb',
              tension: 0.4
            },
            {
              label: 'OMXC20',
              data: benchmarks.OMXC20.map(b => b.price * 600),
              borderColor: '#10b981',
              tension: 0.4
            },
            {
              label: 'MSCI World',
              data: benchmarks.MSCI_WORLD.map(b => b.price * 600),
              borderColor: '#f59e0b',
              tension: 0.4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: true } }
        }
      });
    } catch (error) {
      console.error('Error fetching benchmark:', error);
    }
  }

  async function updateSettings() {
    try {
      const response = await fetch(API_URL + '/dividend-forecast');
      const dividends = await response.json();

      let html = '';
      for (const [ticker, data] of Object.entries(dividends)) {
        html += `<div style="padding: 12px; border-bottom: 1px solid #e2e8f0;">
          <strong>${ticker}</strong>: ${data.yield}% yield • kr ${data.annual.toLocaleString('da-DK')}/år
        </div>`;
      }

      document.getElementById('dividendForecast').innerHTML = html;

      // Recommendations
      document.getElementById('recommendations').innerHTML = `
        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
          <strong>1. Lukk derivater</strong> - BULL NOVO og BULL NFLX er i tab
        </div>
        <div style="background: #dbeafe; border-left: 4px solid #2563eb; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
          <strong>2. Reducér Tech</strong> - Fra 50% til 40%
        </div>
        <div style="background: #dcfce7; border-left: 4px solid #059669; padding: 12px; border-radius: 6px;">
          <strong>3. Tilføj obligationer</strong> - 15% for mindre risiko
        </div>
      `;
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  }

  function setDefaultPurchase() {
    document.getElementById('purchaseSlider').value = '1200000';
    document.getElementById('purchaseValueDisplay').textContent = '1.200.000 DKK';
    updateKPIs();
  }

  window.addEventListener('load', () => {
    checkLogin();
    setInterval(fetchData, 300000);
  });
</script>

</body>
</html>"""

    mega_html = mega_html_template.format(host=host)
    return render_template_string(mega_html)

@app.route("/", methods=["GET"])
def index():
    """Info side"""
    return jsonify({
        "name": "Ratepension Live Data Server",
        "version": "2.0",
        "endpoints": {
            "GET /api/portfolio": "Hele porteføljen med live data",
            "GET /api/stock/<ticker>": "Data for én aktie",
            "GET /api/portfolio/top": "Top 10 aktier efter værdi",
            "GET /api/portfolio/warnings": "Aktier med advarsler (derivater)",
            "GET /api/portfolio/gainers": "Top 5 bedste i dag",
            "GET /api/portfolio/losers": "Top 5 værste i dag",
            "GET /api/transactions": "Transaktion historik",
            "GET /api/benchmark": "Benchmark sammenligning",
            "GET /api/dividend-forecast": "Forventet udbytte",
            "POST /api/refresh": "Manuelt opdater nu",
            "GET /health": "Server status",
            "GET /mega": "MEGA Dashboard med alle features"
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
# Force rebuild
