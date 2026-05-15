import streamlit as st
import requests
import pandas as pd

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="GuardPath",
    page_icon="🛡️",
    layout="wide"
)

# =========================================================
# CUSTOM STYLING
# =========================================================
st.markdown(
    """
    <style>
    .main { padding-top: 2rem; }
    .title { font-size: 42px; font-weight: bold; color: #00C2FF; }
    .subtitle { font-size: 18px; color: #BBBBBB; margin-bottom: 30px; }

    .risk-low { color: #00CC66; font-weight: bold; }
    .risk-medium { color: orange; font-weight: bold; }
    .risk-high { color: red; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# SESSION STATE (FOR CLEAR BUTTON)
# =========================================================
if "result" not in st.session_state:
    st.session_state.result = None

if "prompt" not in st.session_state:
    st.session_state.prompt = ""


# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="title">🛡️ GuardPath</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="subtitle">AI-Powered Secure Natural Language to SQL Firewall</div>',
    unsafe_allow_html=True
)


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("⚙️ Settings")

    api_url = st.text_input(
        "GuardPath API URL",
        value="http://localhost:8000/scan"
    )

    st.divider()

    if st.button("🧹 Clear Output"):
        st.session_state.result = None
        st.session_state.prompt = ""
        st.rerun()

    st.markdown("### 📌 Example Prompts")
    st.code("Show all customers")
    st.code("Show product category with total sales per region")
    st.code("Show customers with highest profit")
    st.code("Show monthly sales trends")


# =========================================================
# MAIN INPUT
# =========================================================
st.subheader("🧠 Natural Language Query")

prompt = st.text_area(
    "Enter business question",
    height=180,
    value=st.session_state.prompt,
    placeholder="Example: Show customers and their total sales"
)


# =========================================================
# ANALYZE BUTTON
# =========================================================
if st.button("🚀 Analyze Query", use_container_width=True):

    if not prompt.strip():
        st.warning("Please enter a query.")
        st.stop()

    with st.spinner("GuardPath analyzing request..."):
        try:
            response = requests.post(
                api_url,
                json={"prompt": prompt},
                timeout=60
            )

            data = response.json()
            st.session_state.result = data
            st.session_state.prompt = prompt

        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
            st.stop()


# =========================================================
# RESULT DISPLAY (persisted)
# =========================================================
data = st.session_state.result

if data:

    st.divider()

    # =====================================================
    # STATUS
    # =====================================================
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Risk Score", data.get("risk_score", 0))

    with col2:
        st.metric("Risk Level", data.get("risk_level", "UNKNOWN"))

    with col3:
        st.metric("SQL Allowed", "YES" if data.get("sql_allowed") else "NO")


    # =====================================================
    # REDACTED PROMPT (NEW)
    # =====================================================
    st.subheader("🛡️ Redacted Prompt Sent to LLM")

    if data.get("redacted_prompt"):
        st.code(data["redacted_prompt"], language="text")
    else:
        st.info("No redacted prompt returned")


    # =====================================================
    # SYSTEM PROMPT (OPTIONAL DEBUG VIEW)
    # =====================================================
    with st.expander("🧠 System Prompt (Debug View)"):
        if data.get("system_prompt"):
            st.code(data["system_prompt"], language="text")
        else:
            st.info("System prompt not returned by API")


    # =====================================================
    # DETECTED ENTITIES
    # =====================================================
    st.subheader("🔍 Detected Sensitive Entities")

    entities = data.get("detected_entities", [])

    if entities:
        st.dataframe(pd.DataFrame({"Detected Entity": entities}), use_container_width=True)
    else:
        st.success("No sensitive entities detected")


    # =====================================================
    # SCOPED TABLES
    # =====================================================
    st.subheader("🧩 Scoped Database Tables")

    scoped_tables = data.get("scoped_tables", [])

    if scoped_tables:
        st.dataframe(pd.DataFrame({"Relevant Tables": scoped_tables}), use_container_width=True)
    else:
        st.warning("No tables matched")


    # =====================================================
    # SQL RISKS
    # =====================================================
    st.subheader("⚠️ SQL Risks")

    sql_risks = data.get("sql_risks", [])

    if sql_risks:
        for risk in sql_risks:
            st.error(risk)
    else:
        st.success("No SQL risks detected")


    # =====================================================
    # FINAL SQL
    # =====================================================
    st.subheader("🧾 Generated SQL")

    if data.get("final_query"):
        st.code(data["final_query"], language="sql")
    else:
        st.error("No SQL generated")


    # =====================================================
    # MESSAGE
    # =====================================================
    st.subheader("📢 GuardPath Decision")
    st.info(data.get("message", "No message returned"))
