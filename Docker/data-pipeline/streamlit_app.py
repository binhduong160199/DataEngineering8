import streamlit as st
from dashboard_sections import section_diego, section_tugba, section_duong

st.set_page_config(layout="wide", page_title="Team Dashboard")
st.title("NYC Trip Analysis Dashboard")
st.markdown("Gruppe 8 - Binh Duong Nguyen, Daniel Frank Iyamu, Jose Zehentner, Negar Rahbar, Tugba Sahin")
st.markdown("---")

tab1, tab2, tab3 = st.tabs([
    "Provider Preise",                 # Diego
    "Angebot & Nachfrage Analyse",     # Tugba
    "Wait & Trip Time"                 # Duong
])

with tab1:
    section_diego.render()
with tab2:
    section_tugba.render()
with tab3:
    section_duong.render()
with tab4:
    section_negar.render()
