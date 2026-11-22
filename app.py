from finance_planner.tools.sip_tools import get_latest_sip_plan
import asyncio
import os
import pandas as pd
import streamlit as st
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from finance_planner.agent import root_agent
from finance_planner.config import CRITICAL_THRESHOLD, WARNING_THRESHOLD
from finance_planner.tools.memory_tools import get_saved_transactions


st.set_page_config(page_title="Personal Finance & SIP Agent", page_icon="💰", layout="wide")

APP_NAME = "finance_planner_ui"
USER_ID = "demo_user"
SESSION_ID = "demo_session"
UPLOAD_DIR = os.path.join("data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- ADK Runner Setup (Shared across Streamlit reruns) ---
@st.cache_resource
def get_runner() -> Runner:
    session_service = InMemorySessionService()
    asyncio.run(
        session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    )
    return Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


runner = get_runner()


def run_agent_turn(prompt_text: str, status_container) -> str:
    """Sends a message to the ADK agent, renders live tool calls, and returns the final text."""
    content = types.Content(role="user", parts=[types.Part.from_text(text=prompt_text)])
    final_reply = ""

    for event in runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        # 1. Display tool calls in real time
        for call in event.get_function_calls():
            status_container.write(f"🔧 **Calling tool:** `{call.name}`")
            status_container.json(call.args, expanded=False)

        # 2. Display tool responses in real time
        for resp in event.get_function_responses():
            status_container.write(f"✅ **Tool result:** `{resp.name}`")
            status_container.json(resp.response, expanded=False)

        # 3. Capture final assistant text
        if event.is_final_response() and event.content and event.content.parts:
            final_reply = "".join(p.text for p in event.content.parts if p.text)

    return final_reply


# --- Sidebar: File Upload & Budget Settings ---
with st.sidebar:
    st.header("📂 Upload & Settings")
    monthly_budget = st.number_input("Monthly Budget (₹)", min_value=1000, value=40000, step=1000)

    uploaded_file = st.file_uploader("Upload Statement (CSV) or Receipt (TXT)", type=["csv", "txt"])
    if uploaded_file is not None:
        saved_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(saved_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Uploaded: `{saved_path}`")
        if st.button("Analyze Uploaded File"):
            st.session_state["queued_prompt"] = (
                f"Parse '{saved_path}', categorize the transactions, and show them for my review."
            )

    st.divider()
    st.caption(
        "⚠️ **Disclaimer:** Educational planning support only — not regulated financial advice."
    )

# --- Layout: Left = Chat Interface | Right = Live Budget Dashboard ---
col_chat, col_dash = st.columns([1.35, 1.0], gap="large")

with col_chat:
    st.subheader("💬 Finance & SIP Planner Agent")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Render chat history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            if msg.get("tools"):
                with st.expander(f"🛠️ Tools used ({len(msg['tools'])})", expanded=False):
                    for t in msg["tools"]:
                        st.markdown(t)
            st.markdown(msg["content"])

    # Handle either sidebar quick-button or typed chat input
    user_input = st.chat_input("Ask to parse a statement, check budget, or plan a SIP...")
    prompt = st.session_state.pop("queued_prompt", None) or user_input

    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            tool_logs = []
            with st.status("Agent thinking & selecting tools...", expanded=True) as status:
                # Wrap runner loop to record tool badges for history
                content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
                reply = ""
                for event in runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                    for call in event.get_function_calls():
                        badge = f"🔧 `{call.name}({call.args})`"
                        tool_logs.append(badge)
                        status.write(badge)
                    for resp in event.get_function_responses():
                        status.write(f"✅ `{resp.name}` completed")
                    if event.is_final_response() and event.content and event.content.parts:
                        reply = "".join(p.text for p in event.content.parts if p.text)

                status.update(label="Done", state="complete", expanded=False)

            st.markdown(reply)
            st.session_state["messages"].append(
                {"role": "assistant", "content": reply, "tools": tool_logs}
            )
            st.rerun()

with col_dash:
    st.subheader("📊 Live Budget Dashboard")
    saved_txns = get_saved_transactions()

    if not saved_txns:
        st.info(
            "No approved transactions saved yet. Upload a file or parse "
            "`data/sample/synthetic_statement.csv` and confirm approval in chat."
        )
    else:
        df = pd.DataFrame(saved_txns)
        df["category"] = df.get("category", pd.Series("Other", index=df.index)).fillna("Other")
        df["type"] = df.get("type", pd.Series("", index=df.index)).fillna("").astype(str).str.upper()

        # Fix any legacy rows where 'type' was missing or saved as lowercase
        df.loc[~df["type"].isin(["DEBIT", "CREDIT"]), "type"] = df["category"].apply(
            lambda c: "CREDIT" if str(c).lower() == "income" else "DEBIT"
        )
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

        debits = df[df["type"] == "DEBIT"]
        credits = df[df["type"] == "CREDIT"]
        total_spent = float(debits["amount"].sum()) if not debits.empty else 0.0
        total_income = float(credits["amount"].sum()) if not credits.empty else 0.0
        remaining = monthly_budget - total_spent
        pct_used = (total_spent / monthly_budget) * 100 if monthly_budget > 0 else 0.0

        # KPI Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Spent", f"₹{total_spent:,.0f}")
        m2.metric("Remaining", f"₹{remaining:,.0f}")
        m3.metric("Budget Used", f"{pct_used:.1f}%")

        # Alert Banner
        if pct_used >= CRITICAL_THRESHOLD:
            st.error(f"🚨 CRITICAL ALERT: Spending exceeded {CRITICAL_THRESHOLD:.0f}% of monthly budget!")
        elif pct_used >= WARNING_THRESHOLD:
            st.warning(f"⚠️ WARNING ALERT: Spending reached {pct_used:.1f}% of monthly budget.")
        else:
            st.success("✅ Budget status healthy (below 80% threshold).")

        # Category Breakdown Chart
        if not debits.empty:
            st.markdown("**Spend by Category (₹)**")
            cat_totals = debits.groupby("category")["amount"].sum().sort_values(ascending=False)
            st.bar_chart(cat_totals)

        # Approved Ledger Preview
        display_cols = [c for c in ["date", "merchant", "category", "amount", "type"] if c in df.columns]
        with st.expander("📋 Approved Transactions Ledger", expanded=True):
            st.dataframe(
                df[display_cols],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    st.subheader("🎯 Goal-Based SIP Projection")
    sip_plan = get_latest_sip_plan()

    if not sip_plan:
        st.info(
            "Ask the agent to calculate a goal SIP (e.g., *'Plan a SIP for ₹25,00,000 in 7 years with ₹2,00,000 corpus, moderate risk, and ₹22,000 surplus'*) to visualize your growth curve."
        )
    else:
        s1, s2, s3 = st.columns(3)
        s1.metric("Target Goal", f"₹{sip_plan['target_amount_inr']:,.0f}")
        s2.metric("Required SIP/mo", f"₹{sip_plan['required_monthly_sip_inr']:,.0f}")
        s3.metric(
            "Surplus Fit",
            sip_plan["feasibility"],
            delta=f"-₹{sip_plan['monthly_shortfall_inr']:,.0f}/mo" if sip_plan["monthly_shortfall_inr"] > 0 else "Within Surplus",
            delta_color="inverse" if sip_plan["monthly_shortfall_inr"] > 0 else "normal",
        )

        # Progress bar showing existing corpus vs target goal
        starting_pct = min(1.0, sip_plan["existing_corpus_inr"] / sip_plan["target_amount_inr"])
        st.progress(
            starting_pct,
            text=f"Existing Corpus Head-Start: ₹{sip_plan['existing_corpus_inr']:,.0f} ({starting_pct * 100:.1f}% of goal)",
        )

        # Year-by-year compounding chart (Total Invested vs. Projected Corpus)
        schedule_df = pd.DataFrame(sip_plan.get("yearly_schedule", []))
        if not schedule_df.empty:
            st.markdown(
                f"**Compounding Growth Curve ({sip_plan['horizon_years']} Yrs @ {sip_plan['assumed_annual_return_pct']}% p.a.)**"
            )
            st.area_chart(
                schedule_df.set_index("Year")[["Projected Corpus (₹)", "Total Invested (₹)"]],
                color=["#34d399", "#64748b"],
            )

        st.caption(f"ℹ️ {sip_plan['disclaimer']}")

