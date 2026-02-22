"""Streamlit dashboard for visualising eval results.

Run with:
    streamlit run evals/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

RESULTS_DIR = Path("evals/results")

METRIC_FIELDS = [
    "ir_mode",
    "parking_spot_status",
    "number_plate",
    "number_plate_null_accuracy",
    "events_description",
    "send_notification",
]


@st.cache_data
def load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def get_result_files() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def report_label(report: dict) -> str:
    cfg = report["config"]
    return f"{cfg['name']} ({cfg['provider']}/{cfg['model']})"


def results_to_dataframe(report: dict) -> pd.DataFrame:
    """Flatten run results into a DataFrame."""
    rows = []
    for r in report["results"]:
        token_usage = r.get("token_usage", {})
        row = {
            "config": report["config"]["name"],
            "test_case": r["test_case_id"],
            "iteration": r["iteration"],
            "latency_s": round(r["latency_ms"] / 1000, 1),
            "total_tokens": token_usage.get("total_tokens", 0),
            "error": r.get("error"),
        }
        for field in METRIC_FIELDS:
            row[field] = r["scores"][field]
        rows.append(row)
    return pd.DataFrame(rows)


def overall_scores_df(reports: list[dict]) -> pd.DataFrame:
    """Build a comparison DataFrame of overall scores across configs."""
    rows = []
    for report in reports:
        o = report["overall_scores"]
        row = {"config": report_label(report)}
        for field in METRIC_FIELDS:
            row[f"{field}_mean"] = o[f"{field}_mean"]
            row[f"{field}_std"] = o[f"{field}_std"]
        # Latency (seconds)
        lats = [r["latency_ms"] / 1000 for r in report["results"]]
        row["latency_s_mean"] = sum(lats) / len(lats) if lats else 0.0
        row["latency_s_min"] = min(lats) if lats else 0.0
        row["latency_s_max"] = max(lats) if lats else 0.0
        # Total tokens
        toks = [r.get("token_usage", {}).get("total_tokens", 0) for r in report["results"]]
        row["total_tokens_mean"] = sum(toks) / len(toks) if toks else 0.0
        row["total_tokens_min"] = min(toks) if toks else 0.0
        row["total_tokens_max"] = max(toks) if toks else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


# --- Page setup ---

st.set_page_config(page_title="Eval Dashboard", layout="wide")
st.title("Video LLM Eval Dashboard")

# --- Sidebar: file selection ---

result_files = get_result_files()
if not result_files:
    st.warning("No result files found in `evals/results/`. Run an eval first.")
    st.stop()

st.sidebar.header("Select Results")
selected_files = st.sidebar.multiselect(
    "Result files",
    options=[str(p) for p in result_files],
    default=[str(result_files[0])] if result_files else [],
    format_func=lambda x: Path(x).stem,
)

if not selected_files:
    st.info("Select at least one result file from the sidebar.")
    st.stop()

reports = [load_report(f) for f in selected_files]

# --- Tabs ---

tab_compare, tab_details, tab_heatmap, tab_stochasticity = st.tabs(
    ["Config Comparison", "Per-Test-Case Details", "Score Heatmap", "Stochasticity"]
)

# --- Tab 1: Config comparison ---

with tab_compare:
    st.header("Config Comparison")

    overall_df = overall_scores_df(reports)

    # Bar chart of mean scores + latency & tokens
    mean_cols = [f"{f}_mean" for f in METRIC_FIELDS] + ["latency_s_mean", "total_tokens_mean"]
    melted = overall_df.melt(
        id_vars="config",
        value_vars=mean_cols,
        var_name="metric",
        value_name="value",
    )
    melted["metric"] = melted["metric"].str.replace("_mean", "")

    score_melted = melted[melted["metric"].isin(METRIC_FIELDS)]
    latency_melted = melted[melted["metric"] == "latency_s"]
    tokens_melted = melted[melted["metric"] == "total_tokens"]

    fig = px.bar(
        score_melted,
        x="metric",
        y="value",
        color="config",
        barmode="group",
        title="Overall Mean Scores by Config",
        range_y=[0, 1.05],
    )
    fig.update_layout(xaxis_title="", yaxis_title="Score", legend_title="Config")
    st.plotly_chart(fig, width="stretch")

    col_lat, col_tok = st.columns(2)
    with col_lat:
        fig_lat = px.bar(
            latency_melted,
            x="config",
            y="value",
            color="config",
            title="Mean Latency (s)",
        )
        fig_lat.update_layout(xaxis_title="", yaxis_title="Seconds", showlegend=False)
        st.plotly_chart(fig_lat, width="stretch")
    with col_tok:
        fig_tok = px.bar(
            tokens_melted,
            x="config",
            y="value",
            color="config",
            title="Total Tokens",
        )
        fig_tok.update_layout(xaxis_title="", yaxis_title="Tokens", showlegend=False)
        st.plotly_chart(fig_tok, width="stretch")

    # Summary table
    st.subheader("Score Table")
    display_df = overall_df.set_index("config")
    for field in METRIC_FIELDS:
        display_df[field] = display_df.apply(
            lambda row, f=field: f"{row[f'{f}_mean']:.3f} ± {row[f'{f}_std']:.3f}",
            axis=1,
        )
    display_df["latency (s)"] = display_df.apply(
        lambda row: f"{row['latency_s_mean']:.1f}  (min {row['latency_s_min']:.1f} / max {row['latency_s_max']:.1f})",
        axis=1,
    )
    display_df["tokens"] = display_df.apply(
        lambda row: f"{row['total_tokens_mean']:,.0f}  (min {row['total_tokens_min']:,.0f} / max {row['total_tokens_max']:,.0f})",
        axis=1,
    )
    st.dataframe(display_df[[*METRIC_FIELDS, "latency (s)", "tokens"]], width="stretch")


# --- Tab 2: Per-test-case details ---

with tab_details:
    st.header("Per-Test-Case Details")

    if len(reports) == 1:
        report = reports[0]
    else:
        report_choice = st.selectbox(
            "Select config",
            range(len(reports)),
            format_func=lambda i: report_label(reports[i]),
        )
        report = reports[report_choice]

    df = results_to_dataframe(report)
    test_cases = sorted(df["test_case"].unique())

    selected_tc = st.selectbox("Select test case", test_cases)
    tc_df = df[df["test_case"] == selected_tc]

    # Scores per iteration
    st.subheader("Scores per iteration")
    st.dataframe(
        tc_df[["iteration", *METRIC_FIELDS, "latency_s", "total_tokens", "error"]].set_index("iteration"),
        width="stretch",
    )

    # Raw model outputs
    st.subheader("Model outputs")
    tc_results = [r for r in report["results"] if r["test_case_id"] == selected_tc]
    for r in tc_results:
        with st.expander(f"Iteration {r['iteration']} — {'ERROR' if r.get('error') else 'OK'}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Model output:**")
                st.json(r["model_output"])
            with col2:
                st.write("**Scores:**")
                st.json(r["scores"])
                if r.get("judge_detail"):
                    st.write("**Judge detail:**")
                    st.json(r["judge_detail"])
            if r.get("error"):
                st.error(r["error"])


# --- Tab 3: Score heatmap ---

with tab_heatmap:
    st.header("Score Heatmap")

    if len(reports) == 1:
        hm_report = reports[0]
    else:
        hm_choice = st.selectbox(
            "Select config for heatmap",
            range(len(reports)),
            format_func=lambda i: report_label(reports[i]),
            key="heatmap_config",
        )
        hm_report = reports[hm_choice]

    # Build matrix: test cases × metrics (including latency & tokens)
    hm_data = []
    for tc_id, agg in hm_report["aggregate_scores"].items():
        row = {"test_case": tc_id}
        for field in METRIC_FIELDS:
            row[field] = agg[f"{field}_mean"]
        # Per-test-case latency & tokens
        tc_results = [r for r in hm_report["results"] if r["test_case_id"] == tc_id]
        lats = [r["latency_ms"] / 1000 for r in tc_results]
        row["latency_s"] = sum(lats) / len(lats) if lats else 0.0
        tokens = [r.get("token_usage", {}).get("total_tokens", 0) for r in tc_results]
        row["total_tokens"] = sum(tokens) / len(tokens) if tokens else 0.0
        hm_data.append(row)

    if hm_data:
        hm_df = pd.DataFrame(hm_data).set_index("test_case")

        # Score heatmap (0-1 fields)
        score_df = hm_df[METRIC_FIELDS]
        fig = go.Figure(
            data=go.Heatmap(
                z=score_df.values,
                x=score_df.columns.tolist(),
                y=score_df.index.tolist(),
                colorscale="RdYlGn",
                zmin=0,
                zmax=1,
                text=[[f"{v:.2f}" for v in row] for row in score_df.values],
                texttemplate="%{text}",
            )
        )
        fig.update_layout(
            title="Mean Scores: Test Cases × Metrics",
            xaxis_title="Metric",
            yaxis_title="Test Case",
            height=max(400, len(hm_data) * 40 + 100),
        )
        st.plotly_chart(fig, width="stretch")

        # Latency heatmap
        lat_df = hm_df[["latency_s"]]
        fig_lat = go.Figure(
            data=go.Heatmap(
                z=lat_df.values,
                x=["latency (s)"],
                y=lat_df.index.tolist(),
                colorscale="Oranges",
                text=[[f"{v:.1f}" for v in row] for row in lat_df.values],
                texttemplate="%{text}",
            )
        )
        fig_lat.update_layout(
            title="Mean Latency (s): Test Cases",
            xaxis_title="",
            yaxis_title="Test Case",
            height=max(400, len(hm_data) * 40 + 100),
        )

        # Tokens heatmap
        tok_df = hm_df[["total_tokens"]]
        fig_tok = go.Figure(
            data=go.Heatmap(
                z=tok_df.values,
                x=["total tokens"],
                y=tok_df.index.tolist(),
                colorscale="Blues",
                text=[[f"{v:,.0f}" for v in row] for row in tok_df.values],
                texttemplate="%{text}",
            )
        )
        fig_tok.update_layout(
            title="Mean Total Tokens: Test Cases",
            xaxis_title="",
            yaxis_title="Test Case",
            height=max(400, len(hm_data) * 40 + 100),
        )

        col_lat, col_tok = st.columns(2)
        with col_lat:
            st.plotly_chart(fig_lat, width="stretch")
        with col_tok:
            st.plotly_chart(fig_tok, width="stretch")
    else:
        st.info("No aggregate scores available.")


# --- Tab 4: Stochasticity ---

with tab_stochasticity:
    st.header("Stochasticity Analysis")

    if len(reports) == 1:
        var_report = reports[0]
    else:
        var_choice = st.selectbox(
            "Select config for stochasticity",
            range(len(reports)),
            format_func=lambda i: report_label(reports[i]),
            key="var_config",
        )
        var_report = reports[var_choice]

    var_data = []
    for tc_id, agg in var_report["aggregate_scores"].items():
        row = {"test_case": tc_id}
        for field in METRIC_FIELDS:
            row[f"{field}_std"] = agg[f"{field}_std"]
        var_data.append(row)

    if var_data:
        var_df = pd.DataFrame(var_data)

        # Highlight high-variance cases
        std_cols = [f"{f}_std" for f in METRIC_FIELDS]
        melted_var = var_df.melt(
            id_vars="test_case",
            value_vars=std_cols,
            var_name="metric",
            value_name="std",
        )
        melted_var["metric"] = melted_var["metric"].str.replace("_std", "")

        fig = px.bar(
            melted_var,
            x="test_case",
            y="std",
            color="metric",
            barmode="group",
            title="Standard Deviation Across Iterations",
            range_y=[0, max(0.6, melted_var["std"].max() * 1.1)],
        )
        fig.update_layout(xaxis_title="Test Case", yaxis_title="Std Dev")
        st.plotly_chart(fig, width="stretch")

        # Flag high variance
        threshold = st.slider(
            "High variance threshold",
            min_value=0.0,
            max_value=0.5,
            value=0.15,
            step=0.05,
        )
        high_var = melted_var[melted_var["std"] > threshold]
        if not high_var.empty:
            st.warning(f"Found {len(high_var)} high-variance results (std > {threshold}):")
            st.dataframe(high_var, width="stretch")
        else:
            st.success(f"No high-variance results (all std ≤ {threshold}).")
    else:
        st.info("No aggregate scores available.")
