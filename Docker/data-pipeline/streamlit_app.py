import streamlit as st

# --- 1. IMPORTS: Import every independent section file ---
# NOTE: Ensure these files exist inside the 'dashboard_sections' directory
# (e.g., dashboard_sections/section_jose.py)
from dashboard_sections import section_diego

# ---------------------------------------------
# 2. SETUP (Initial page layout and titles)
# ---------------------------------------------

# Use a wide layout for maximum dashboard space
st.set_page_config(layout="wide", page_title="Decentralized Team Dashboard 🤝")
st.title("Collaborative NYC Trip Analysis Dashboard")
st.markdown("""
Welcome to the decentralized data analysis platform. Each section below is managed
by a different team member, responsible for their own data loading, transformation, and visualization logic.
""")
st.markdown("---")


# ---------------------------------------------
# 3. DELEGATION (The main application logic)
# ---------------------------------------------

# We call the render() function from each imported module.
# The order in which you call them is the order they appear on the page.

section_diego.render()


# The script ends here. The file remains short and only handles flow control.