"""The application state of the current Streamlit session."""

import streamlit as st

from eyeboard.state import AppState

# ``st.session_state`` resolves the current session on every access, so one
# module-level object is correct for all sessions and reruns.
state = AppState(st.session_state)
