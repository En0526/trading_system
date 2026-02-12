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
    # 美股指數
    US_INDICES = {
        '^GSPC': 'S&P 500',
        '^DJI': 'Dow Jones',
        '^IXIC': 'NASDAQ',
        'QQQ': 'NASDAQ 100',
        'VOO': 'S&P 500 ETF',
        'IWM': 'Russell 2000'
    }
    
    # 美股主要公司（偏科技、半導體、大型軟體；已移除約 8 檔非科技/較小）
    US_STOCKS = {
        'AAPL': 'Apple',
        'MSFT': 'Microsoft',
        'GOOGL': 'Alphabet',
        'AMZN': 'Amazon',
        'NVDA': 'NVIDIA',
        'META': 'Meta',
        'TSLA': 'Tesla',
        'BRK.B': 'Berkshire Hathaway',
        'UNH': 'UnitedHealth',
        'JNJ': 'Johnson & Johnson',
        'V': 'Visa',
        'WMT': 'Walmart',
        'JPM': 'JPMorgan Chase',
        'MA': 'Mastercard',
        'ADBE': 'Adobe',
        'NFLX': 'Netflix',
        'CRM': 'Salesforce',
        'INTC': 'Intel',
        'TMO': 'Thermo Fisher',
        'AVGO': 'Broadcom',
        'CSCO': 'Cisco',
        'ORCL': 'Oracle',
        'TSM': 'TSMC (ADR)',
        'AMD': 'AMD',
        'UMC': '聯電 (ADR)',
        'PLTR': 'Palantir',
        'ASML': 'ASML',
        'LRCX': 'Lam Research',
        'AMAT': 'Applied Materials',
        'KLAC': 'KLA',
        'SNPS': 'Synopsys',
        'CDNS': 'Cadence',
        'MRVL': 'Marvell',
        'QCOM': 'Qualcomm',
        'TER': 'Teradyne',
        'ON': 'ON Semiconductor',
        'MU': 'Micron',
    }
    
    # 兼容舊配置
    US_MARKETS = US_INDICES
    
    TW_MARKETS = {
        '^TWII': '台灣加權指數',
        '2330.TW': '台積電',
        '2317.TW': '鴻海',
        '2454.TW': '聯發科',
        # 聯電、南茂
        '2303.TW': '聯電',
        '8150.TW': '南茂',
        # 記憶體相關
        '2408.TW': '南亞科',
        '2344.TW': '華邦電',
        '2337.TW': '旺宏',
        '3006.TW': '晶豪科',
        # PCB 相關
        '3037.TW': '欣興',
        '2313.TW': '華通',
        '8046.TW': '南電',
        '2383.TW': '台光電',
        '6213.TW': '聯茂',
        '2367.TW': '燿華',
        '4958.TW': '臻鼎-KY',
    }
    
    INTERNATIONAL_MARKETS = {
        '^GSPC': 'S&P 500',
        '^DJI': 'Dow Jones',
        '^IXIC': 'NASDAQ',
        '^N225': '日經225',
        '^HSI': '恆生指數',
        '^FTSE': '富時100',
        '^GDAXI': '德國DAX',
        '^FCHI': '法國CAC40'
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
        'USDT-USD': '泰達幣',
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
    TWELVEDATA_API_KEY = os.environ.get('TWELVEDATA_API_KEY', '').strip()
    # 加密一律用 Deribit 交易所，無需 key

    # 數據更新間隔（秒）
    DATA_UPDATE_INTERVAL = 60
    
    # 端口配置
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

