import requests
import json

try:
    # We call the local dev server if it's running, or we just simulate the function call.
    # Since I can't easily call the API without the server running, I'll simulate the data_service call.
    import sys
    import os
    sys.path.append('c:/Users/gollu/Documents/GitHub/Worx_GPS')
    import config
    from web_ui.data_service import DataService
    
    ds = DataService(
        project_root_path='c:/Users/gollu/Documents/GitHub/Worx_GPS',
        heatmap_config=config.HEATMAP_CONFIG,
        problem_config=config.PROBLEM_CONFIG,
        geo_config_main=config.GEO_CONFIG,
        rec_config_main=config.REC_CONFIG
    )
    
    cfg = ds.get_editable_config()
    print(json.dumps(cfg, indent=2))
except Exception as e:
    print(f"Error: {e}")
