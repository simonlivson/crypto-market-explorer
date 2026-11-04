# Crypto Market Explorer: Cycles, Altseasons and Coins That Break Away From Bitcoin

## Short Description
Crypto moves in cycles, and most coins follow Bitcoin. But in some phases altcoins
outperform ("altseason"), and some coins break away from Bitcoin for months (like
Hyperliquid and Zcash in 2025). I combine long-term Bitcoin/Ethereum history with live
CoinGecko API data on 12 coins to study the market cycle, detect altseasons, and find
when and why coins break away. Results are shown in a report-style notebook and an
interactive Streamlit dashboard.

## Problem Statement
For an investor, owning many coins only spreads the risk if those coins don't all move
with Bitcoin. I want to find out with real data in which market phases diversification
in crypto is real, and which coins are just "Bitcoin in disguise".

### Hypotheses
**Part A: The big picture (long-term history)**
1. Bitcoin follows a roughly 4-year cycle: about 3 bull years and 1 bear year.
2. Bull and bear phases have significantly different returns and volatility.
3. Altseasons (ETH/BTC rising, most altcoins beating Bitcoin) happen late in bull phases.

**Part B: Inside the current phase (last 365 days, 12 coins)**
4. Over the long run, most coins are highly correlated with Bitcoin.
5. This correlation is not stable: a rolling 30/90-day correlation reveals periods when
   some coins break away from Bitcoin.
6. Coins that break away show unusual trading volume or returns during those periods.
7. Breakaways cluster by theme (e.g. privacy coins, DEX/perps, AI coins).

## Data Sources
- **CoinGecko API** (external source): daily price, market cap and volume for 12 coins:
  BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK, HYPE, ZEC, XMR, TAO (last 365 days).
- **BTC and ETH full daily history (CSV)**: long-term prices for the cycle and
  altseason analysis.
- **coin_categories.csv**: my own file with each coin's theme (Layer 1, Payments, Meme,
  Oracle, DEX/Perps, Privacy, AI), merged with the price data.
- Raw API responses are saved as JSON, cleaned data as CSV in the `data/` folder.

## Tech Stack
Python, pandas, NumPy, requests, Matplotlib, Seaborn, Plotly, SciPy, Streamlit,
Jupyter Notebook / Google Colab, Git & GitHub.

## Project Structure
```
crypto-market-explorer/
├── data/            # raw JSON and cleaned CSV files
├── notebooks/       # crypto_analysis.ipynb (the main report)
├── app/             # app.py (Streamlit dashboard)
├── requirements.txt
└── README.md
```

## How to Run the Project
### Option 1: Google Colab (easiest)
1. Open `notebooks/crypto_analysis.ipynb` on GitHub and click "Open in Colab".
2. Run all cells from top to bottom (Runtime → Run all).

### Option 2: On my own computer
1. Clone the repo:
   ```bash
   git clone https://github.com/simonlivson/crypto-market-explorer.git
   cd crypto-market-explorer
   ```
2. Install the libraries:
   ```bash
   pip install -r requirements.txt
   ```
3. Open the notebook in VS Code or Jupyter and run all cells.
4. Start the dashboard:
   ```bash
   streamlit run app/app.py
   ```

No API key or environment variables are needed (CoinGecko's free tier).

## Run the App
From the repo root I install the libraries and start the dashboard:
```bash
pip install -r requirements.txt
streamlit run app/app.py
```
It runs offline from the files in `data/`, so no API key or internet connection is needed.

The sidebar has six pages:
- **Overview**: key numbers for BTC and an interactive risk vs return bubble chart
- **Price & drawdowns**: any coin's price with bull/bear phases shaded, plus its drawdown
- **Monthly returns**: year-by-month heatmap for BTC or ETH
- **Altseason**: ETH/BTC ratio with altseasons highlighted and my 12-coin altseason score
- **Correlation & beta**: correlation heatmap, beta table and 30/90-day rolling correlation with breakaway days
- **Hypothesis scorecard**: the verdict for each hypothesis, computed from the data

## Main Features
- Bitcoin market cycles: bull and bear phases marked from peak to bottom, with their length, returns and volatility
- Altseason detection: ETH/BTC ratio and an "altseason score" (share of coins beating Bitcoin over 90 days)
- Fetch daily market data for 12 coins from the CoinGecko API
- Clean the data: missing values, duplicates, data types and outliers
- Beta to Bitcoin: how much each coin moves when Bitcoin moves 1%
- Rolling correlation with Bitcoin to detect breakaway periods
- Volume and return behavior during breakaways, compared by theme
- Statistical tests with SciPy to check each hypothesis
- Interactive dashboard: pick coins and a date range, see correlations and charts update

## Main Findings
_Coming soon. I will add them once the analysis is finished._

## Team Members
- Simon Livson, solo project (data collection, analysis, dashboard)