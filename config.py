"""
配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """應用配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 市場代碼配置
    # 美股指數已併入國際市場，此區塊保留空（兼容）
    US_INDICES = {}
    US_MARKETS = US_INDICES

    # 美股（雲端限制暫不顯示；保留 1 檔供本機或日後恢復）
    US_STOCKS = {
        'AAPL': 'Apple',
    }
    
    # ETF 專區（美股 + 台股 ETF，yfinance，顯示中文名）
    ETF = {
        'VOO': '先鋒標普500',
        'QQQ': '景順那斯達克100',
        '0050.TW': '元大台灣50',
        '00951.TW': '台新日本半導體',
        '009809.TW': '富邦淨零ESG50',
        '00983A.TW': '主動中信ARK創新',
        '00982A.TW': '主動群益台灣強棒',
        '00981A.TW': '主動統一台股增長',
    }
    
    # 台股（雲端限制，精簡至約 5 檔減輕負載）
    TW_MARKETS = {
        '^TWII': '台灣加權指數',
        '2330.TW': '台積電',
        '2317.TW': '鴻海',
        '2454.TW': '聯發科',
        '2303.TW': '聯電',
    }
    
    # 國際市場（雲端限制暫不顯示；保留 1 檔供本機或日後恢復）
    INTERNATIONAL_MARKETS = {
        '^GSPC': 'S&P 500',
    }

    # 重金屬專區：期貨（COMEX/紐約，有夜盤日盤）
    METALS_FUTURES = {
        'GC=F': '黃金期貨',
        'SI=F': '白銀期貨',
        'HG=F': '銅期貨',
        'PL=F': '鉑期貨',
        'PA=F': '鈀期貨',
    }

    # 加密貨幣專區（Yahoo Finance 對 USD 報價，24 小時交易）
    CRYPTO = {
        'BTC-USD': '比特幣',
        'ETH-USD': '以太幣',
        'BNB-USD': 'BNB',
        'XRP-USD': '瑞波幣',
        'SOL-USD': 'Solana',
        'DOGE-USD': '狗狗幣',
        'ADA-USD': 'Cardano',
        'AVAX-USD': 'Avalanche',
        'LINK-USD': 'Chainlink',
    }

    # 重要比率專區：分子/分母，period 為歷史區間（20y 或 max，加密相關用 max）
    RATIO_DEFINITIONS = [
        {'id': 'gold_silver', 'name': '金銀比', 'num': 'GC=F', 'denom': 'SI=F', 'period': '20y', 'unit': '倍', 'desc': '黃金/白銀'},
        {'id': 'silver_copper', 'name': '銀銅比', 'num': 'SI=F', 'denom': 'HG=F', 'period': '20y', 'unit': '倍', 'desc': '白銀/銅'},
        {'id': 'gold_copper', 'name': '金銅比', 'num': 'GC=F', 'denom': 'HG=F', 'period': '20y', 'unit': '倍', 'desc': '黃金/銅'},
        {'id': 'platinum_gold', 'name': '鉑金比', 'num': 'PL=F', 'denom': 'GC=F', 'period': '20y', 'unit': '倍', 'desc': '鉑/黃金'},
        {'id': 'palladium_gold', 'name': '鈀金比', 'num': 'PA=F', 'denom': 'GC=F', 'period': '20y', 'unit': '倍', 'desc': '鈀/黃金'},
        {'id': 'eth_btc', 'name': '以太比特比', 'num': 'ETH-USD', 'denom': 'BTC-USD', 'period': 'max', 'unit': '倍', 'desc': '以太幣/比特幣'},
        {'id': 'btc_gold', 'name': '比特黃金比', 'num': 'BTC-USD', 'denom': 'GC=F', 'period': 'max', 'unit': '倍', 'desc': '1 BTC 等於幾盎司黃金'},
    ]
    
    # 多資料源 API key（選填，未設則該區塊 fallback 用 yfinance）
    FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', '').strip()
    FMP_API_KEY = os.environ.get('FMP_API_KEY', '').strip()  # 財報行事曆備援
    TWELVEDATA_API_KEY = os.environ.get('TWELVEDATA_API_KEY', '').strip()
    # 加密一律用 Deribit 交易所，無需 key

    # 數據更新間隔（秒）
    DATA_UPDATE_INTERVAL = 60
    
    # 端口配置
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

