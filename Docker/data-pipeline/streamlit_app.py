import streamlit as st
from dashboard_sections import section_diego, section_tugba, section_duong, section_negar

st.set_page_config(layout="wide", page_title="Group 8 - Data Engineering Project")

st.title("NYC Trip Analysis Dashboard")
st.markdown("""
### Project by **Group 8** – Data Engineering  
This dashboard was developed as part of the *Data Engineering* course.  
It analyzes NYC taxi trip data to explore trends in distance, fare, and passenger behavior.
""")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "Provider Preise",                 # Diego
    "Angebot & Nachfrage Analyse",     # Tugba
    "Wait & Trip Time",                # Duong
    "Taxi Demand"                      # Negar 
])

with tab1:
    section_diego.render()
with tab2:
    section_tugba.render()
with tab3:
    section_duong.render()
with tab4:
    section_negar.render()
