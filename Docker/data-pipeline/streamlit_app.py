import streamlit as st
from dashboard_sections import section_diego

st.set_page_config(layout="wide", page_title="Team Dashboard")
st.title("NYC Trip Analysis Dashboard")
st.markdown("""
Hier schöne Beschreibung einfügen
""")
st.markdown("---")

section_diego.render()