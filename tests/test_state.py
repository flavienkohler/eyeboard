from plot_studio.state import initialize_session_state, remember_recent_config


def test_remember_recent_config_keeps_most_recent_first():
    session_state = {
        "saved_configs": [
            {"id": "cfg-1"},
            {"id": "cfg-2"},
            {"id": "cfg-3"},
        ],
        "recent_config_ids": ["cfg-2", "cfg-1"],
    }

    remember_recent_config(session_state, "cfg-3")
    remember_recent_config(session_state, "cfg-1")

    assert session_state["recent_config_ids"] == ["cfg-1", "cfg-3", "cfg-2"]


def test_initialize_session_state_prunes_deleted_recent_configs():
    session_state = {
        "saved_configs": [{"id": "cfg-1"}, {"id": "cfg-3"}],
        "saved_configs_load_error": None,
        "recent_config_ids": ["cfg-2", "cfg-1", "cfg-3"],
    }

    initialize_session_state(session_state)

    assert session_state["recent_config_ids"] == ["cfg-1", "cfg-3"]
