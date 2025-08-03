from pyzap.webapp import app, get_plugins_metadata


def test_plugins_help_page_lists_all_params():
    info = get_plugins_metadata()
    client = app.test_client()
    resp = client.get("/help/plugins")
    assert resp.status_code == 200
    html = resp.data.decode()
    for section in info["triggers"] + info["actions"]:
        assert section["name"] in html
        for param in section["params"]:
            assert f"<code>{param['name']}</code>" in html
