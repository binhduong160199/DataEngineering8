import streamlit as st
from dashboard_sections import section_diego, section_tugba

st.set_page_config(layout="wide", page_title="Team Dashboard")
st.title("NYC Trip Analysis Dashboard")
st.markdown("""
Hier schöne Beschreibung einfügen
""")
st.markdown("---")

tabs = st.tabs(["Provider Market Share", "Angebot & Nachfrage Analyse"])

with tabs[0]:
    section_diego.render()

with tabs[1]:
    section_tugba.render()
