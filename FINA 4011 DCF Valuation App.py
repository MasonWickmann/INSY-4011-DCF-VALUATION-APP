"""
FINA 4011/5011 - Project 2
DCF Equity Valuation App
Run with: streamlit run "path/to/dcf_valuation_app.py"
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="DCF Stock Valuation", page_icon="📈", layout="centered")

st.title("📈 DCF Equity Valuation App")
st.markdown(
    "Estimate the **intrinsic value** of a stock using a Discounted Cash Flow (DCF) model. "
    "Fill in each section below, then click **Run Valuation** at the bottom."
)
st.markdown("---")

# ─────────────────────────────────────────────
#  HELPER
# ─────────────────────────────────────────────
def safe_get(info, *keys, default=None):
    for k in keys:
        v = info.get(k)
        if v is not None:
            return v
    return default

# ─────────────────────────────────────────────
#  SECTION 1 — COMPANY INFO
# ─────────────────────────────────────────────
st.header("🏢 Section 1 — Company Information")
st.markdown(
    "Enter the stock ticker. We'll pull a company overview from Yahoo Finance "
    "for context only — you will manually enter all model inputs below."
)

ticker_input = st.text_input(
    "Stock Ticker Symbol",
    value="AAPL",
    help="E.g. AAPL, MSFT, TSLA, AMZN"
).upper().strip()

current_price = None
beta_fetched  = None

if ticker_input:
    with st.spinner("Loading company overview..."):
        try:
            tk   = yf.Ticker(ticker_input)
            info = tk.info
            company_name  = safe_get(info, "longName", "shortName", default=ticker_input)
            sector        = safe_get(info, "sector",   default="N/A")
            industry      = safe_get(info, "industry", default="N/A")
            current_price = safe_get(info, "currentPrice", "regularMarketPrice", default=None)
            market_cap    = safe_get(info, "marketCap", default=None)
            pe_ratio      = safe_get(info, "trailingPE", default=None)
            beta_fetched  = safe_get(info, "beta", default=None)
            summary       = safe_get(info, "longBusinessSummary", default="No description available.")

            st.subheader(f"{company_name} ({ticker_input})")
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Market Price", f"${current_price:,.2f}" if current_price else "N/A")
            col2.metric("Market Cap",           f"${market_cap/1e9:,.2f}B" if market_cap else "N/A")
            col3.metric("Trailing P/E",         f"{pe_ratio:.1f}x" if pe_ratio else "N/A")
            st.caption(f"**Sector:** {sector}  |  **Industry:** {industry}")
            with st.expander("📋 Business Summary"):
                st.write(summary)
        except Exception:
            st.warning("Could not load company data. Check the ticker and your internet connection.")

st.markdown("---")

# ─────────────────────────────────────────────
#  SECTION 2 — REVENUE & FCF INPUTS
# ─────────────────────────────────────────────
st.header("💰 Section 2 — Revenue & Free Cash Flow Inputs")
st.markdown(
    "These inputs define the **starting point** of the model. "
    "Use the company's most recent annual report (10-K) or a site like "
    "[Macrotrends](https://www.macrotrends.net) to find these figures."
)

col_r1, col_r2 = st.columns(2)
with col_r1:
    base_revenue = st.number_input(
        "Most Recent Annual Revenue ($M)",
        min_value=0.0, value=383000.0, step=100.0,
        help="Find on the Income Statement (10-K). Enter in millions of dollars."
    )
with col_r2:
    fcf_margin = st.number_input(
        "Free Cash Flow Margin (%)",
        min_value=0.1, max_value=80.0, value=25.0, step=0.5,
        help=(
            "FCF Margin = Free Cash Flow ÷ Revenue. "
            "Free Cash Flow = Operating Cash Flow − Capital Expenditures. "
            "Find both on the Cash Flow Statement. "
            "A higher margin means the company converts more revenue to cash."
        )
    ) / 100

st.info(
    f"📌 **Implied Base-Year FCF:** ${base_revenue * fcf_margin:,.1f}M  "
    "— This is the starting FCF before any growth is applied."
)

col_r3, col_r4 = st.columns(2)
with col_r3:
    revenue_growth = st.number_input(
        "Revenue Growth Rate — High-Growth Stage (%)",
        min_value=-30.0, max_value=100.0, value=8.0, step=0.5,
        help=(
            "Expected annual revenue growth for years 1–N. "
            "Look at historical revenue growth (last 3–5 years) and analyst forecasts as a reference. "
            "Be conservative — aggressive assumptions lead to inflated valuations."
        )
    ) / 100
with col_r4:
    projection_years = st.slider(
        "Projection Period (Years)",
        min_value=3, max_value=15, value=5, step=1,
        help="Number of years to explicitly project FCF. Typically 5–10 years."
    )

st.markdown("---")

# ─────────────────────────────────────────────
#  SECTION 3 — WACC COMPONENTS
# ─────────────────────────────────────────────
st.header("📐 Section 3 — WACC (Discount Rate) Components")
st.markdown(
    "The **Weighted Average Cost of Capital (WACC)** is the rate we use to discount future cash flows "
    "back to today. It reflects the riskiness of the company's cash flows from the perspective of all "
    "capital providers (equity + debt). We build it up from its individual components below."
)

# ── 3a: Cost of Equity ────────────────────────
st.subheader("3a — Cost of Equity (Kₑ) via CAPM")
st.markdown(
    r"""
The **Capital Asset Pricing Model (CAPM)** tells us the return equity investors require:

> **Kₑ = Rₓ + β × (Rₘ − Rₓ)**

- **Rₓ** = Risk-Free Rate (yield on 10-year US Treasury)
- **β (Beta)** = How volatile the stock is vs. the market (Beta > 1 means riskier than market)
- **(Rₘ − Rₓ)** = Equity Risk Premium — extra return demanded for owning stocks over bonds
"""
)

col_e1, col_e2, col_e3 = st.columns(3)
with col_e1:
    risk_free_rate = st.number_input(
        "Risk-Free Rate — Rₓ (%)",
        min_value=0.0, max_value=15.0, value=4.3, step=0.1,
        help=(
            "Use the current 10-year US Treasury yield. "
            "Check finance.yahoo.com → search '^TNX' for the live rate."
        )
    ) / 100
with col_e2:
    beta_default = float(round(beta_fetched, 2)) if beta_fetched else 1.20
    beta = st.number_input(
        "Beta (β)",
        min_value=0.0, max_value=5.0, value=beta_default, step=0.05,
        help=(
            "Beta measures market sensitivity. Beta = 1 moves with the market. "
            ">1 is more volatile (e.g. tech). <1 is more stable (e.g. utilities). "
            "Pre-filled from Yahoo Finance if available — you can override."
        )
    )
with col_e3:
    equity_risk_premium = st.number_input(
        "Equity Risk Premium — (Rₘ − Rₓ) (%)",
        min_value=0.0, max_value=15.0, value=5.5, step=0.1,
        help=(
            "The historical average excess return of stocks over bonds. "
            "Damodaran (NYU) estimates the US ERP at ~5.5% as of 2025. "
            "This is the most widely used standard assumption."
        )
    ) / 100

cost_of_equity = risk_free_rate + beta * equity_risk_premium
st.success(
    f"**Cost of Equity (Kₑ) = {risk_free_rate*100:.2f}% + {beta:.2f} × {equity_risk_premium*100:.2f}% "
    f"= {cost_of_equity*100:.2f}%**"
)

st.markdown("---")

# ── 3b: Cost of Debt ──────────────────────────
st.subheader("3b — Cost of Debt (K_d)")
st.markdown(
    r"""
The **Cost of Debt** is the effective interest rate the company pays on borrowings, tax-adjusted because interest is deductible:

> **After-Tax Cost of Debt = K_d × (1 − Tax Rate)**

Find Interest Expense and Total Debt on the 10-K to estimate K_d = Interest Expense ÷ Total Debt.
"""
)

col_d1, col_d2 = st.columns(2)
with col_d1:
    cost_of_debt_pretax = st.number_input(
        "Pre-Tax Cost of Debt — K_d (%)",
        min_value=0.0, max_value=20.0, value=4.0, step=0.1,
        help=(
            "Estimate as: Annual Interest Expense ÷ Total Debt. "
            "Both are on the 10-K. Investment-grade large-caps are typically 3–5%."
        )
    ) / 100
with col_d2:
    tax_rate = st.number_input(
        "Effective Tax Rate (%)",
        min_value=0.0, max_value=50.0, value=21.0, step=0.5,
        help=(
            "Effective Tax Rate = Income Tax Expense ÷ Pre-Tax Income (Income Statement). "
            "The US statutory corporate rate is 21%, but effective rates vary by company."
        )
    ) / 100

cost_of_debt_aftertax = cost_of_debt_pretax * (1 - tax_rate)
st.success(
    f"**After-Tax Cost of Debt = {cost_of_debt_pretax*100:.2f}% × (1 − {tax_rate*100:.1f}%) "
    f"= {cost_of_debt_aftertax*100:.2f}%**"
)

st.markdown("---")

# ── 3c: Capital Structure Weights ─────────────
st.subheader("3c — Capital Structure Weights")
st.markdown(
    r"""
WACC weights each component by its share of total financing:

> **WACC = (E/V) × Kₑ + (D/V) × K_d × (1 − T)**

Where **E** = market value of equity (market cap), **D** = market value of debt, **V** = E + D.

Find Market Cap on Yahoo Finance and Total Debt on the Balance Sheet.
"""
)

col_w1, col_w2 = st.columns(2)
with col_w1:
    equity_weight = st.number_input(
        "Weight of Equity — E/V (%)",
        min_value=0.0, max_value=100.0, value=90.0, step=1.0,
        help=(
            "Equity Weight = Market Cap ÷ (Market Cap + Total Debt). "
            "Most large-cap companies are equity-heavy (80–95%)."
        )
    ) / 100
with col_w2:
    debt_weight = round(1 - equity_weight, 4)
    st.metric("Weight of Debt — D/V (%)", f"{debt_weight*100:.1f}%")
    st.caption("Automatically calculated as 1 − Equity Weight")

wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt_aftertax

st.markdown("### ✅ Calculated WACC")
col_wacc1, col_wacc2, col_wacc3 = st.columns(3)
col_wacc1.metric("Equity Component",  f"{equity_weight * cost_of_equity * 100:.2f}%")
col_wacc2.metric("Debt Component",    f"{debt_weight * cost_of_debt_aftertax * 100:.2f}%")
col_wacc3.metric("🎯 WACC",           f"{wacc*100:.2f}%")
st.info(
    f"**WACC = ({equity_weight*100:.0f}% × {cost_of_equity*100:.2f}%) + "
    f"({debt_weight*100:.0f}% × {cost_of_debt_aftertax*100:.2f}%) = {wacc*100:.2f}%**"
)

st.markdown("---")

# ─────────────────────────────────────────────
#  SECTION 4 — TERMINAL VALUE & BALANCE SHEET
# ─────────────────────────────────────────────
st.header("🔭 Section 4 — Terminal Value & Balance Sheet Inputs")
st.markdown(
    "Enter the terminal growth rate and balance sheet figures from the company's most recent 10-K "
    "or sites like [Macrotrends](https://www.macrotrends.net) or Yahoo Finance."
)

col_t1, col_t2 = st.columns(2)
with col_t1:
    terminal_growth_rate = st.number_input(
        "Terminal Growth Rate (%)",
        min_value=0.0, max_value=5.0, value=2.5, step=0.25,
        help=(
            "The perpetual growth rate applied after the projection period. "
            "Should not exceed long-run nominal GDP growth (~2–3%). "
            "Using a rate higher than this implies the company eventually grows larger than the economy."
        )
    ) / 100
with col_t2:
    margin_of_safety = st.number_input(
        "Margin of Safety (%)",
        min_value=0.0, max_value=50.0, value=20.0, step=5.0,
        help=(
            "A discount applied to intrinsic value as a buffer for model uncertainty. "
            "Benjamin Graham (Warren Buffett's mentor) recommended 20–30%."
        )
    ) / 100

st.markdown("**Balance Sheet Inputs** — enter in millions of dollars:")
col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    total_debt = st.number_input(
        "Total Debt ($M)",
        min_value=0.0, value=97000.0, step=100.0,
        help="Long-term debt + short-term debt. Found on the Balance Sheet of the 10-K."
    )
with col_b2:
    total_cash = st.number_input(
        "Cash & Cash Equivalents ($M)",
        min_value=0.0, value=65000.0, step=100.0,
        help="Cash and short-term investments. Found on the Balance Sheet of the 10-K."
    )
with col_b3:
    shares_outstanding = st.number_input(
        "Shares Outstanding (M)",
        min_value=0.1, value=15200.0, step=10.0,
        help=(
            "Found on Yahoo Finance's summary page or the cover of the 10-K. "
            "Enter in millions (e.g. 15,200 for 15.2 billion shares)."
        )
    )

net_debt = total_debt - total_cash
st.info(f"**Net Debt = Total Debt − Cash = ${net_debt:,.1f}M**")

st.markdown("---")

# ─────────────────────────────────────────────
#  RUN BUTTON
# ─────────────────────────────────────────────
run_button = st.button("🚀 Run Valuation", use_container_width=True, type="primary")

# ─────────────────────────────────────────────
#  VALUATION OUTPUT
# ─────────────────────────────────────────────
if run_button:

    if wacc <= terminal_growth_rate:
        st.error("⚠️ WACC must be greater than the terminal growth rate. Please adjust your inputs.")
        st.stop()
    if base_revenue <= 0:
        st.error("⚠️ Revenue must be greater than zero.")
        st.stop()

    # Convert to absolute dollars
    base_revenue_abs = base_revenue * 1e6
    net_debt_abs     = net_debt * 1e6
    shares_abs       = shares_outstanding * 1e6

    # Project FCFs
    years              = list(range(1, projection_years + 1))
    projected_revenues = [base_revenue_abs * (1 + revenue_growth) ** y for y in years]
    projected_fcfs     = [r * fcf_margin for r in projected_revenues]
    discount_factors   = [(1 + wacc) ** (-y) for y in years]
    pv_fcfs            = [fcf * df for fcf, df in zip(projected_fcfs, discount_factors)]
    sum_pv_fcfs        = sum(pv_fcfs)

    # Terminal value
    terminal_value = projected_fcfs[-1] * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)
    pv_terminal    = terminal_value * discount_factors[-1]

    # Enterprise → Equity → Per share
    enterprise_value = sum_pv_fcfs + pv_terminal
    equity_value     = enterprise_value - net_debt_abs
    intrinsic_value  = equity_value / shares_abs
    mos_price        = intrinsic_value * (1 - margin_of_safety)

    st.markdown("---")
    st.header("📊 Valuation Results")

    # ── STEP 1: Projected FCFs ────────────────
    st.subheader("Step 1 — Projected Free Cash Flows")
    st.markdown(
        f"Starting from **${base_revenue:,.0f}M** in base revenue, we grow revenue at "
        f"**{revenue_growth*100:.1f}% per year** for **{projection_years} years**, "
        f"then apply a **{fcf_margin*100:.1f}% FCF margin** to estimate each year's Free Cash Flow. "
        f"Each FCF is then discounted to today using WACC = **{wacc*100:.2f}%**."
    )

    proj_df = pd.DataFrame({
        "Year":            years,
        "Revenue ($M)":    [r / 1e6 for r in projected_revenues],
        "FCF ($M)":        [f / 1e6 for f in projected_fcfs],
        "Discount Factor": discount_factors,
        "PV of FCF ($M)":  [p / 1e6 for p in pv_fcfs],
    }).set_index("Year")

    st.dataframe(proj_df.style.format({
        "Revenue ($M)":    "${:,.1f}",
        "FCF ($M)":        "${:,.1f}",
        "Discount Factor": "{:.4f}",
        "PV of FCF ($M)":  "${:,.1f}",
    }), use_container_width=True)

    st.success(f"**Sum of PV of FCFs = ${sum_pv_fcfs/1e9:.2f}B**")

    # ── STEP 2: Terminal Value ─────────────────
    st.subheader("Step 2 — Terminal Value (Gordon Growth Model)")
    st.markdown(
        "After the projection period, we assume the company grows at a constant **terminal growth rate** forever. "
        "The Terminal Value captures all value beyond Year N:"
        "\n\n> **Terminal Value = FCF_final × (1 + g) / (WACC − g)**"
        f"\n\n> **= ${projected_fcfs[-1]/1e6:,.1f}M × (1 + {terminal_growth_rate*100:.2f}%) "
        f"/ ({wacc*100:.2f}% − {terminal_growth_rate*100:.2f}%)**"
    )

    tv_pct = pv_terminal / (sum_pv_fcfs + pv_terminal) * 100
    col_tv1, col_tv2, col_tv3 = st.columns(3)
    col_tv1.metric("Terminal Value",        f"${terminal_value/1e9:.2f}B")
    col_tv2.metric("PV of Terminal Value",  f"${pv_terminal/1e9:.2f}B")
    col_tv3.metric("TV as % of Total EV",   f"{tv_pct:.1f}%")
    st.caption(
        "📌 A TV share of 60–80% is typical for stable companies. "
        "If it's very high (>85%), consider lowering the terminal growth rate or raising WACC."
    )

    # ── STEP 3: Enterprise Value ───────────────
    st.subheader("Step 3 — Enterprise Value")
    st.markdown(
        "Enterprise Value (EV) is the total value of the firm to ALL capital providers (equity + debt holders):"
        "\n\n> **EV = Sum of PV of FCFs + PV of Terminal Value**"
    )
    col_ev1, col_ev2, col_ev3 = st.columns(3)
    col_ev1.metric("PV of FCFs",        f"${sum_pv_fcfs/1e9:.2f}B")
    col_ev2.metric("PV Terminal Value", f"${pv_terminal/1e9:.2f}B")
    col_ev3.metric("Enterprise Value",  f"${enterprise_value/1e9:.2f}B")

    # ── STEP 4: Equity Value Per Share ─────────
    st.subheader("Step 4 — Equity Value Per Share")
    st.markdown(
        "We subtract **Net Debt** (debt − cash) from EV to get what belongs to equity holders only, "
        "then divide by shares outstanding:"
        "\n\n> **Equity Value = Enterprise Value − Net Debt**"
        "\n\n> **Intrinsic Value Per Share = Equity Value ÷ Shares Outstanding**"
    )
    col_eq1, col_eq2, col_eq3, col_eq4 = st.columns(4)
    col_eq1.metric("Enterprise Value", f"${enterprise_value/1e9:.2f}B")
    col_eq2.metric("Net Debt",         f"${net_debt_abs/1e9:.2f}B")
    col_eq3.metric("Equity Value",     f"${equity_value/1e9:.2f}B")
    col_eq4.metric("Shares Out.",      f"{shares_outstanding:,.0f}M")

    # ── FINAL VERDICT ─────────────────────────
    st.markdown("---")
    st.header("🏁 Final Verdict")

    col_v1, col_v2, col_v3 = st.columns(3)
    col_v1.metric("Intrinsic Value / Share",                           f"${intrinsic_value:,.2f}")
    col_v2.metric(f"w/ {margin_of_safety*100:.0f}% Margin of Safety", f"${mos_price:,.2f}")
    col_v3.metric("Current Market Price", f"${current_price:,.2f}" if current_price else "N/A")

    if current_price:
        upside     = (intrinsic_value - current_price) / current_price * 100
        mos_upside = (mos_price - current_price) / current_price * 100
        if mos_price > current_price:
            st.success(
                f"✅ **POTENTIALLY UNDERVALUED** — Even after a {margin_of_safety*100:.0f}% margin of safety, "
                f"the stock appears **{abs(mos_upside):.1f}% below intrinsic value**. May be a buying opportunity."
            )
        elif intrinsic_value > current_price:
            st.warning(
                f"⚠️ **MARGINALLY UNDERVALUED** — Intrinsic value exceeds market price by {upside:.1f}%, "
                "but the stock does not pass the margin of safety threshold."
            )
        else:
            st.error(
                f"🔴 **POTENTIALLY OVERVALUED** — The stock trades **{abs(upside):.1f}% above** estimated "
                "intrinsic value. The market may be pricing in more growth than your assumptions reflect."
            )

    # ── WACC BREAKDOWN CHART ──────────────────
    st.markdown("---")
    st.subheader("📊 WACC Breakdown Chart")
    fig_wacc, ax_wacc = plt.subplots(figsize=(8, 3.5))
    comp_labels = [
        "Equity Component\n(E/V × Kₑ)",
        "Debt Component\n(D/V × Kd×(1−T))",
        "WACC (Total)"
    ]
    comp_vals   = [
        equity_weight * cost_of_equity * 100,
        debt_weight * cost_of_debt_aftertax * 100,
        wacc * 100
    ]
    bar_colors  = ["#2196F3", "#FF9800", "#4CAF50"]
    bars        = ax_wacc.bar(comp_labels, comp_vals, color=bar_colors, width=0.45)
    ax_wacc.bar_label(bars, fmt="%.2f%%", padding=4, fontsize=11, fontweight="bold")
    ax_wacc.set_ylabel("Rate (%)")
    ax_wacc.set_title("WACC Component Breakdown", fontsize=13)
    ax_wacc.set_ylim(0, max(comp_vals) * 1.35)
    ax_wacc.spines["top"].set_visible(False)
    ax_wacc.spines["right"].set_visible(False)
    plt.tight_layout()
    st.pyplot(fig_wacc)

    # ── VALUE COMPOSITION CHART ───────────────
    st.subheader("📊 DCF Value Composition")
    bar_labels = [f"Yr {y} PV FCF" for y in years] + ["PV Terminal\nValue", "Less:\nNet Debt"]
    bar_values = [p / 1e9 for p in pv_fcfs] + [pv_terminal / 1e9, -net_debt_abs / 1e9]
    bar_clrs   = ["#4C72B0"] * len(years) + ["#DD8452",
                  "#C44E52" if net_debt_abs > 0 else "#55A868"]

    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.bar(bar_labels, bar_values, color=bar_clrs)
    ax2.axhline(equity_value / 1e9, color="green", linestyle="--", linewidth=1.5,
                label=f"Equity Value ${equity_value/1e9:.1f}B")
    ax2.set_ylabel("Value ($B)")
    ax2.set_title(f"{ticker_input} — DCF Value Composition")
    ax2.tick_params(axis="x", rotation=30)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend()
    plt.tight_layout()
    st.pyplot(fig2)

    # ── SENSITIVITY TABLE ─────────────────────
    st.markdown("---")
    st.subheader("🔬 Sensitivity Analysis — Intrinsic Value Per Share")
    st.markdown(
        "How does intrinsic value change as **WACC** and **terminal growth rate** vary? "
        + ("Green = above current market price, Red = below." if current_price else "")
    )

    wacc_range = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
    tgr_range  = [
        terminal_growth_rate - 0.005,
        terminal_growth_rate,
        terminal_growth_rate + 0.005,
        terminal_growth_rate + 0.010,
    ]

    sens_rows = {}
    for tg in tgr_range:
        row = {}
        for w in wacc_range:
            col_label = f"WACC {w*100:.1f}%"
            if w <= tg or w <= 0:
                row[col_label] = np.nan
                continue
            pv_s  = sum(projected_fcfs[i] / (1 + w) ** (i + 1) for i in range(len(projected_fcfs)))
            tv_s  = projected_fcfs[-1] * (1 + tg) / (w - tg)
            pv_tv = tv_s / (1 + w) ** projection_years
            iv_s  = (pv_s + pv_tv - net_debt_abs) / shares_abs
            row[col_label] = iv_s
        sens_rows[f"TGR {tg*100:.1f}%"] = row

    sens_df = pd.DataFrame(sens_rows).T

    def color_cells(val):
        if pd.isna(val) or current_price is None:
            return ""
        return ("background-color: #d4edda; color: #155724" if val > current_price
                else "background-color: #f8d7da; color: #721c24")

    st.dataframe(
        sens_df.style.applymap(color_cells).format("${:,.2f}", na_rep="N/A"),
        use_container_width=True
    )

    # ── ASSUMPTIONS SUMMARY ───────────────────
    st.markdown("---")
    st.subheader("📋 Full Assumptions Summary (for Excel Replication)")
    st.markdown("Use this table to reproduce the valuation step-by-step in Excel.")

    assumptions = {
        "Ticker":                       ticker_input,
        "Base Revenue ($M)":            f"${base_revenue:,.1f}",
        "FCF Margin":                   f"{fcf_margin*100:.1f}%",
        "Revenue Growth Rate":          f"{revenue_growth*100:.1f}%",
        "Projection Years":             str(projection_years),
        "── WACC Build-Up ──":          "",
        "Risk-Free Rate (Rₓ)":         f"{risk_free_rate*100:.2f}%",
        "Beta (β)":                     f"{beta:.2f}",
        "Equity Risk Premium":          f"{equity_risk_premium*100:.2f}%",
        "Cost of Equity (Kₑ = CAPM)":  f"{cost_of_equity*100:.2f}%",
        "Pre-Tax Cost of Debt":         f"{cost_of_debt_pretax*100:.2f}%",
        "Tax Rate":                     f"{tax_rate*100:.1f}%",
        "After-Tax Cost of Debt":       f"{cost_of_debt_aftertax*100:.2f}%",
        "Equity Weight (E/V)":          f"{equity_weight*100:.1f}%",
        "Debt Weight (D/V)":            f"{debt_weight*100:.1f}%",
        "WACC":                         f"{wacc*100:.2f}%",
        "── Terminal Value ──":         "",
        "Terminal Growth Rate":         f"{terminal_growth_rate*100:.2f}%",
        "Terminal Value ($B)":          f"${terminal_value/1e9:.2f}",
        "PV of Terminal Value ($B)":    f"${pv_terminal/1e9:.2f}",
        "── Balance Sheet ──":          "",
        "Total Debt ($M)":              f"${total_debt:,.1f}",
        "Total Cash ($M)":              f"${total_cash:,.1f}",
        "Net Debt ($M)":                f"${net_debt:,.1f}",
        "Shares Outstanding (M)":       f"{shares_outstanding:,.1f}",
        "── Output ──":                 "",
        "Sum PV of FCFs ($B)":          f"${sum_pv_fcfs/1e9:.2f}",
        "Enterprise Value ($B)":        f"${enterprise_value/1e9:.2f}",
        "Equity Value ($B)":            f"${equity_value/1e9:.2f}",
        "Intrinsic Value / Share":      f"${intrinsic_value:,.2f}",
        "Margin of Safety":             f"{margin_of_safety*100:.0f}%",
        "MOS-Adjusted Value / Share":   f"${mos_price:,.2f}",
        "Current Market Price":         f"${current_price:,.2f}" if current_price else "N/A",
    }

    st.table(pd.DataFrame(list(assumptions.items()), columns=["Parameter", "Value"]))

    st.caption(
        "⚠️ **Disclaimer:** This app is for educational purposes only. "
        "DCF models are highly sensitive to assumptions and should not be used as sole investment advice."
    )

else:
    st.info("👆 Fill in all sections above and click **Run Valuation** to see results.")

    st.markdown("---")
    st.subheader("📚 How the DCF Model Works")
    st.markdown(
        r"""
A **Discounted Cash Flow (DCF)** model values a company by projecting its future Free Cash Flows
and discounting them back to today using the company's cost of capital (WACC).

**Core Formula:**
> **Intrinsic Value = Σ [FCFₜ / (1+WACC)ᵗ] + [Terminal Value / (1+WACC)ⁿ] − Net Debt**
> **Per Share = Equity Value ÷ Shares Outstanding**

**Steps:**
1. Start with base revenue from the most recent 10-K
2. Project revenue forward using an assumed growth rate
3. Apply FCF Margin to get Free Cash Flow each year
4. Build WACC from its components: CAPM cost of equity + after-tax cost of debt, weighted by capital structure
5. Discount each FCF to today using WACC
6. Compute Terminal Value (Gordon Growth Model) for value beyond the projection period
7. Sum → Enterprise Value. Subtract Net Debt → Equity Value. Divide by Shares → Intrinsic Value per Share
8. Apply Margin of Safety and compare to the current market price
"""
    )
