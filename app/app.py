# My Crypto Market Explorer dashboard
# run from the repo root: streamlit run app/app.py
import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

# my data folder sits next to the app folder
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data") + os.sep

st.set_page_config(page_title="Crypto Market Explorer", layout="wide")


# ---------- loading ----------
@st.cache_data
def load_data():
    coins_df = pd.read_csv(DATA + "coins_clean.csv", parse_dates=["date"])
    history = pd.read_csv(DATA + "btc_eth_clean.csv", parse_dates=["date"])
    return coins_df, history


# ---------- Part A: cycles ----------
def find_phases(df, col):
    # the same drawdown rule as my notebook: at least -50% and at least 180 days
    part_df = df[["date", col]].dropna().reset_index(drop=True)
    part_df["running_peak"] = part_df[col].cummax()
    part_df["drawdown"] = part_df[col] / part_df["running_peak"] - 1
    part_df["episode"] = (part_df[col] >= part_df["running_peak"]).cumsum()

    bears = []
    for ep, part in part_df.groupby("episode"):
        bottom = part.loc[part["drawdown"].idxmin()]
        days = (bottom["date"] - part["date"].iloc[0]).days
        if bottom["drawdown"] <= -0.5 and days >= 180:
            bears.append((part["date"].iloc[0], bottom["date"], bottom["drawdown"]))

    phases = []
    start = part_df["date"].iloc[0]
    for peak, bottom, dd in bears:
        phases.append(("Bull", start, peak))
        phases.append(("Bear", peak, bottom))
        start = bottom
    phases.append(("After last low (ongoing)", start, part_df["date"].iloc[-1]))
    return part_df, bears, phases


def phase_table(part_df, col, phases):
    rows = []
    for name, start, end in phases:
        part = part_df[(part_df["date"] > start) & (part_df["date"] <= end)]
        first_price = part_df.loc[part_df["date"] == start, col].iloc[0]
        last_price = part_df.loc[part_df["date"] == end, col].iloc[0]
        rows.append({
            "phase": name,
            "start": start.date(),
            "end": end.date(),
            "days": (end - start).days,
            "years": round((end - start).days / 365.25, 2),
            "total_return_%": round((last_price / first_price - 1) * 100, 1),
        })
    table = pd.DataFrame(rows)
    table.loc[0, "phase"] = "Bull (partial, data starts)"
    if len(table) >= 2 and table.loc[len(table) - 2, "phase"] == "Bear":
        table.loc[len(table) - 2, "phase"] = "Bear (ongoing, low so far)"
    return table


@st.cache_data
def part_a(history):
    btc, bears, phases = find_phases(history, "BTC")
    table = phase_table(btc, "BTC", phases)
    complete = table[table["phase"].isin(["Bull", "Bear"])]

    # every day gets the name of its phase, then my Welch t-test and Levene test
    btc_ret = history[["date", "BTC_return"]].copy()
    btc_ret["phase"] = None
    for name, start, end in phases:
        btc_ret.loc[(btc_ret["date"] > start) & (btc_ret["date"] <= end), "phase"] = name
    bull_days = btc_ret.loc[btc_ret["phase"] == "Bull", "BTC_return"].dropna()
    bear_days = btc_ret.loc[btc_ret["phase"] == "Bear", "BTC_return"].dropna()
    t_p = stats.ttest_ind(bull_days, bear_days, equal_var=False).pvalue
    lev_p = stats.levene(bull_days, bear_days).pvalue

    # ETH/BTC altseasons: +50% in 90 days, gaps up to 30 days joined
    eth = history[["date", "BTC", "ETH"]].dropna().copy()
    eth["eth_btc"] = eth["ETH"] / eth["BTC"]
    eth["change_90d"] = eth["eth_btc"].pct_change(90)
    eth["alt_signal"] = eth["change_90d"] >= 0.5
    signal_days = eth.loc[eth["alt_signal"], "date"]
    period_id = (signal_days.diff().dt.days > 30).cumsum()
    alt_periods = signal_days.groupby(period_id).agg(["min", "max"])
    alt_periods.columns = ["start", "end"]
    alt_periods["days"] = (alt_periods["end"] - alt_periods["start"]).dt.days + 1

    # where in the BTC cycle each altseason sits
    def where_in_cycle(day):
        for name, start, end in phases:
            if start < day <= end:
                return name, round((day - start).days / (end - start).days * 100)
        return None, None

    middles = alt_periods["start"] + (alt_periods["end"] - alt_periods["start"]) / 2
    alt_periods["btc_phase"] = [where_in_cycle(d)[0] for d in middles]
    alt_periods["position_in_phase_%"] = [where_in_cycle(d)[1] for d in middles]

    return {"btc": btc, "phases": phases, "table": table, "complete": complete,
            "bull_days": bull_days, "bear_days": bear_days, "t_p": t_p, "lev_p": lev_p,
            "eth": eth, "alt_periods": alt_periods}


# ---------- Part B: correlation and breakaways ----------
@st.cache_data
def part_b(coins_df):
    returns = coins_df.pivot_table(index="date", columns="coin", values="daily_return").dropna()
    volumes = coins_df.pivot_table(index="date", columns="coin", values="volume")
    prices = coins_df.pivot_table(index="date", columns="coin", values="price")
    themes = coins_df.groupby("coin")["theme"].first()
    alts = [c for c in returns.columns if c != "BTC"]

    corr = returns.corr()
    corr_btc = corr["BTC"].drop("BTC").sort_values(ascending=False)

    # beta = cov / var, R² = correlation squared
    btc_var = returns["BTC"].var()
    beta = {coin: returns[coin].cov(returns["BTC"]) / btc_var for coin in alts}
    beta_table = pd.DataFrame({"beta": pd.Series(beta), "correlation": corr["BTC"][alts]})
    beta_table["r_squared_%"] = beta_table["correlation"] ** 2 * 100
    beta_table["theme"] = themes[alts]
    beta_table = beta_table.sort_values("beta", ascending=False).round(2)

    roll_30 = returns[alts].rolling(30).corr(returns["BTC"])
    roll_90 = returns[alts].rolling(90).corr(returns["BTC"])

    # my breakaway rule: 30-day corr below 0.4 and beating BTC by more than 20% over 30 days
    change_30 = prices.pct_change(30)
    excess_30 = change_30[alts].sub(change_30["BTC"], axis=0)
    breakaway = (roll_30 < 0.4) & (excess_30.loc[roll_30.index] > 0.2)

    periods = []
    for coin in alts:
        days = breakaway.index[breakaway[coin]]
        if len(days) == 0:
            continue
        period_id = (pd.Series(days).diff().dt.days > 7).cumsum()
        for _, group in pd.Series(days).groupby(period_id.values):
            periods.append({"coin": coin, "theme": themes[coin],
                            "start": group.min().date(), "end": group.max().date(),
                            "days": len(group)})
    breakaway_periods = pd.DataFrame(periods)

    # volume on breakaway days vs normal days (Mann-Whitney)
    rel_volume = (volumes[alts] / volumes[alts].rolling(30).median()).loc[breakaway.index]
    vol_long = pd.DataFrame({"rel_volume": rel_volume.stack(),
                             "breakaway": breakaway.stack()}).dropna()
    on_break = vol_long.loc[vol_long["breakaway"].astype(bool), "rel_volume"]
    normal = vol_long.loc[~vol_long["breakaway"].astype(bool), "rel_volume"]
    vol_p = stats.mannwhitneyu(on_break, normal, alternative="greater").pvalue

    # themes (chi-square)
    counts = vol_long.copy()
    counts["theme"] = themes[counts.index.get_level_values("coin")].values
    table = pd.crosstab(counts["theme"], counts["breakaway"])
    chi_p = stats.chi2_contingency(table)[1]

    theme_table = beta_table.copy()
    theme_table["breakaway_days"] = breakaway.sum()
    by_theme = theme_table.groupby("theme").agg(coins=("beta", "size"),
                                                breakaway_days=("breakaway_days", "sum"))
    by_theme["breakaway_days_per_coin"] = by_theme["breakaway_days"] / by_theme["coins"]
    by_theme = by_theme.sort_values("breakaway_days_per_coin", ascending=False).round(2)

    # my 12-coin altseason score: share of altcoins beating BTC over 90 days
    change_90d = prices.pct_change(90).dropna()
    beat_btc = change_90d[alts].gt(change_90d["BTC"], axis=0)
    alt_score = beat_btc.mean(axis=1) * 100

    # risk vs return: return x 365, volatility x sqrt(365)
    summary = pd.DataFrame({
        "ann_return_%": returns.mean() * 365 * 100,
        "ann_volatility_%": returns.std() * np.sqrt(365) * 100,
        "corr_btc": corr["BTC"],
        "beta": pd.Series(beta),
        "breakaway_days": breakaway.sum(),
        "theme": themes,
    })
    summary.loc["BTC", ["beta", "breakaway_days"]] = [1, 0]
    summary = summary.round(2).sort_values("ann_return_%", ascending=False)

    return {"returns": returns, "prices": prices, "alts": alts, "corr": corr,
            "corr_btc": corr_btc, "beta_table": beta_table, "roll_30": roll_30,
            "roll_90": roll_90, "breakaway": breakaway, "breakaway_periods": breakaway_periods,
            "on_break": on_break, "normal": normal, "vol_p": vol_p, "chi_p": chi_p,
            "by_theme": by_theme, "alt_score": alt_score, "beat_btc": beat_btc,
            "summary": summary}


def make_scorecard(a, b):
    # the same logic as Section 5 of my notebook
    avg_years = a["complete"].groupby("phase")["years"].mean()
    alt_periods = a["alt_periods"]
    alt_in_bull = (alt_periods["btc_phase"] == "Bull").sum()
    late_in_bull = ((alt_periods["btc_phase"] == "Bull") & (alt_periods["position_in_phase_%"] >= 66)).sum()
    p_value, lev_p = a["t_p"], a["lev_p"]
    corr_btc, beta_table = b["corr_btc"], b["beta_table"]
    breakaway, on_break, normal = b["breakaway"], b["on_break"], b["normal"]
    vol_p, chi_p = b["vol_p"], b["chi_p"]
    coins_breaking = (breakaway.sum() >= 5).sum()

    return pd.DataFrame([
        ["H1: ~3 bull years, ~1 bear year", "drawdown rule (-50%, 180 days)",
         f"bull {avg_years['Bull']:.1f} y, bear {avg_years['Bear']:.1f} y",
         "supported" if abs(avg_years["Bull"] - 3) < 0.5 and abs(avg_years["Bear"] - 1) < 0.5 else "partly"],
        ["H2: bull and bear days differ", "Welch t-test + Levene",
         f"mean p = {p_value:.1e}, volatility p = {lev_p:.3f}",
         "partly" if p_value < 0.05 and lev_p > 0.01 else ("supported" if p_value < 0.05 else "not")],
        ["H3: altseasons come late in the bull", "ETH/BTC +50% in 90 days",
         f"{alt_in_bull} of {len(alt_periods)} in bulls, {late_in_bull} late",
         "supported" if late_in_bull > len(alt_periods) / 2 else ("partly" if alt_in_bull > 0 else "not")],
        ["H4: altcoins highly correlated with BTC", "Pearson r",
         f"average r = {corr_btc.mean():.2f}, lowest {corr_btc.idxmin()} {corr_btc.min():.2f}",
         "supported" if corr_btc.min() >= 0.6 else ("partly" if corr_btc.mean() >= 0.6 else "not")],
        ["H5: altcoins amplify BTC (beta > 1)", "beta = cov / var",
         f"{(beta_table['beta'] > 1).sum()} of {len(beta_table)} above 1",
         "supported" if (beta_table["beta"] > 1).mean() >= 0.8 else ("partly" if (beta_table["beta"] > 1).mean() >= 0.5 else "not")],
        ["H6: some coins break away", "rolling corr < 0.4 and +20% vs BTC",
         f"{len(b['breakaway_periods'])} periods, {int(breakaway.sum().sum())} days, {coins_breaking} coins",
         "supported" if len(b["breakaway_periods"]) > 0 else "not"],
        ["H7: breakaways come with unusual volume", "Mann-Whitney U",
         f"median {on_break.median():.2f}x vs {normal.median():.2f}x, p = {vol_p:.1e}",
         "partly" if vol_p < 0.05 and on_break.median() / normal.median() < 1.5 else ("supported" if vol_p < 0.05 else "not")],
        ["H8: breakaways cluster by theme", "chi-square",
         f"p = {chi_p:.1e}, top theme {b['by_theme'].index[0]}",
         "supported" if chi_p < 0.05 else "not"],
    ], columns=["hypothesis", "test used", "key number", "verdict"])


def shade_phases(fig, phases):
    # green for bulls, red for bears, grey for the ongoing part
    colors = {"Bull": "green", "Bear": "red"}
    for name, start, end in phases:
        fig.add_vrect(x0=start, x1=end, fillcolor=colors.get(name, "grey"), opacity=0.12, line_width=0)


# ---------- the app ----------
coins_df, history = load_data()
a = part_a(history)
b = part_b(coins_df)

st.sidebar.title("Crypto Market Explorer")
page = st.sidebar.radio("Page", ["Overview", "Price & drawdowns", "Monthly returns",
                                 "Altseason", "Correlation & beta", "Hypothesis scorecard"])
st.sidebar.caption(f"Data: CoinGecko 12 coins up to {coins_df['date'].max().date()}, "
                   f"Coin Metrics BTC/ETH since {history['date'].min().year}")

if page == "Overview":
    st.title("Crypto Market Explorer")
    st.write("My look at crypto cycles and which altcoins break away from Bitcoin.")
    summary = b["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BTC yearly return", f"{summary.loc['BTC', 'ann_return_%']:.1f}%")
    c2.metric("BTC yearly volatility", f"{summary.loc['BTC', 'ann_volatility_%']:.1f}%")
    c3.metric("Best coin", summary.index[0], f"{summary['ann_return_%'].iloc[0]:.0f}%")
    c4.metric("Average corr with BTC", f"{b['corr_btc'].mean():.2f}")

    # bubble size can't be 0, so I add 1
    plot_df = summary.reset_index().rename(columns={"index": "coin"})
    plot_df["size"] = plot_df["breakaway_days"] + 1
    fig = px.scatter(plot_df, x="ann_volatility_%", y="ann_return_%", color="theme", size="size",
                     text="coin", hover_data=["corr_btc", "beta", "breakaway_days"],
                     title="Risk vs return over the last year (bubble size = breakaway days)")
    fig.add_hline(y=0, line_color="grey")
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, width="stretch")
    st.caption("Yearly return = average daily return x 365. Yearly volatility = daily std x sqrt(365).")
    st.dataframe(summary)

elif page == "Price & drawdowns":
    st.title("Price & drawdowns")
    source = st.radio("Data", ["BTC/ETH since 2013", "12 coins, last year"], horizontal=True)
    if source == "BTC/ETH since 2013":
        coin = st.selectbox("Coin", ["BTC", "ETH"])
        df = history[["date", coin]].dropna()
    else:
        coin = st.selectbox("Coin", sorted(coins_df["coin"].unique()))
        df = coins_df.loc[coins_df["coin"] == coin, ["date", "price"]].rename(columns={"price": coin})

    part_df, bears, phases = find_phases(df, coin)
    log_scale = st.checkbox("Log scale", value=source.startswith("BTC"))

    fig = px.line(part_df, x="date", y=coin, title=f"{coin} price (green = bull, red = bear)",
                  log_y=log_scale)
    if bears:
        shade_phases(fig, phases)
    st.plotly_chart(fig, width="stretch")

    fig = px.area(part_df, x="date", y="drawdown", title=f"{coin} drawdown from its running peak")
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

    if bears:
        st.subheader("Bull and bear phases (bear = -50% or more, lasting 180+ days)")
        st.dataframe(phase_table(part_df, coin, phases), hide_index=True)
    else:
        st.info("No fall of 50% lasting 180 days in this data, so no bear phase by my rule.")
    if coin == "BTC" and source.startswith("BTC"):
        st.write(f"Welch t-test bull vs bear days: p = {a['t_p']:.1e}; Levene (volatility): p = {a['lev_p']:.3f}")

elif page == "Monthly returns":
    st.title("Monthly returns heatmap")
    coin = st.selectbox("Coin", ["BTC", "ETH"])
    # last price of every month, then the change from month to month
    monthly = history.set_index("date")[coin].dropna().resample("ME").last().pct_change().to_frame("return")
    monthly["year"] = monthly.index.year
    monthly["month"] = monthly.index.month
    month_table = monthly.pivot_table(index="year", columns="month", values="return") * 100

    fig = px.imshow(month_table.round(0), text_auto=True, color_continuous_scale="RdYlGn",
                    color_continuous_midpoint=0, aspect="auto",
                    labels={"x": "Month", "y": "Year", "color": "Return %"},
                    title=f"{coin} monthly returns (%) by year")
    st.plotly_chart(fig, width="stretch")

    month_avg = month_table.agg(["mean", "median"]).T.round(1)
    month_avg["positive_years"] = (month_table > 0).sum()
    st.dataframe(month_avg)

elif page == "Altseason":
    st.title("Altseason")
    eth = a["eth"]
    fig = px.line(eth, x="date", y="eth_btc", title="ETH/BTC ratio, altseasons in yellow")
    shade_phases(fig, a["phases"])
    for _, row in a["alt_periods"].iterrows():
        fig.add_vrect(x0=row["start"], x1=row["end"], fillcolor="gold", opacity=0.6, line_width=0)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(a["alt_periods"], hide_index=True)

    alt_score = b["alt_score"]
    fig = px.line(x=alt_score.index, y=alt_score.values,
                  labels={"x": "date", "y": "altcoins beating BTC (%)"},
                  title="My altseason score: share of 11 altcoins beating BTC over 90 days")
    fig.add_hline(y=75, line_dash="dash", line_color="red")
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, width="stretch")
    st.write(f"Days at or above 75%: {(alt_score >= 75).sum()} of {len(alt_score)} "
             f"(average {alt_score.mean():.0f}%)")

elif page == "Correlation & beta":
    st.title("Correlation & beta")
    fig = px.imshow(b["corr"].round(2), text_auto=True, color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1, title="Correlation of daily returns (last year)")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Beta and R² vs BTC")
    st.dataframe(b["beta_table"])

    st.subheader("Rolling correlation with BTC")
    coin = st.selectbox("Coin", b["alts"])
    window = st.radio("Window", [30, 90], horizontal=True)
    roll = b["roll_30"] if window == 30 else b["roll_90"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=roll.index, y=roll[coin], name=f"{window}-day correlation"))
    fig.add_hline(y=0.4, line_dash="dash", line_color="red")
    # green marks on my breakaway days
    days = b["breakaway"].index[b["breakaway"][coin]]
    fig.add_trace(go.Scatter(x=days, y=b["roll_30"].loc[days, coin], mode="markers",
                             marker=dict(color="green", size=8), name="breakaway day"))
    fig.update_layout(title=f"{coin}: correlation with BTC")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Breakaway days by theme")
    st.dataframe(b["by_theme"])
    if len(b["breakaway_periods"]):
        st.dataframe(b["breakaway_periods"], hide_index=True)

elif page == "Hypothesis scorecard":
    st.title("Hypothesis scorecard")
    st.write("Every verdict is computed from the data, with the same rules as my notebook.")
    scorecard = make_scorecard(a, b)
    st.dataframe(scorecard, hide_index=True, width="stretch")
    st.write(scorecard["verdict"].value_counts())
