# -*- coding: utf-8 -*-
"""直接测试API"""
import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import app

with app.test_client() as client:
    r = client.get('/api/market-data')
    print(f'Status: {r.status_code}')
    print(f'Content-Type: {r.content_type}')
    
    try:
        data = json.loads(r.data)
        print(f'Success: {data.get("success")}')
        if 'data' in data:
            print(f'Data keys: {list(data["data"].keys())}')
            print(f'us_stocks count: {len(data["data"].get("us_stocks", {}))}')
            print(f'tw_markets count: {len(data["data"].get("tw_markets", {}))}')
            print(f'international_markets count: {len(data["data"].get("international_markets", {}))}')
        else:
            print('No data field')
            print(f'Response: {data}')
    except Exception as e:
        print(f'Error parsing JSON: {e}')
        print(f'Raw response: {r.data[:500]}')
