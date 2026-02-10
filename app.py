"""
Trading System - 主應用程式
"""
# 雲端（如 Render）上 Python 預設憑證路徑可能失敗，先強制使用 certifi 的憑證
import os
try:
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
except ImportError:
    pass

from flask import Flask, render_template, jsonify
from market_data.data_fetcher import MarketDataFetcher
from timing.timing_selector import TimingSelector
from strategy.strategy_matcher import StrategyMatcher
from news_analysis.volume_analyzer import VolumeAnalyzer
from news_analysis.premarket_analyzer import PremarketAnalyzer
from news_analysis.ir_fetcher import IRFetcher
from economic_data.economic_calendar import EconomicCalendar
from market_data.institutional_net import (
    get_institutional_net_ytd,
    list_uploaded_dates,
    save_uploaded_csv,
    try_parse_date_from_csv,
    try_parse_date_from_filename,
)
from config import Config
from datetime import datetime, timezone
import json

app = Flask(__name__)
app.config.from_object(Config)

# 初始化模組
data_fetcher = MarketDataFetcher()
timing_selector = TimingSelector()
strategy_matcher = StrategyMatcher()
volume_analyzer = VolumeAnalyzer()
premarket_analyzer = PremarketAnalyzer()
ir_fetcher = IRFetcher()
economic_calendar = EconomicCalendar()

@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/api/ratios')
def get_ratios():
    """重要比率 API（金銀比、銀銅比、以太比特比、比特黃金比等），可即時更新"""
    from flask import request
    try:
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        data = data_fetcher.get_ratios_summary(force_refresh=refresh)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ratios/<ratio_id>/history')
def get_ratio_history(ratio_id):
    """單一比率歷史序列，供走勢圖使用（20年或全期）"""
    from flask import request
    try:
        resample = request.args.get('resample', '1M')
        data = data_fetcher.get_ratio_history(ratio_id, resample=resample)
        if not data:
            return jsonify({'success': False, 'error': '無此比率或無資料'}), 404
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/market-data')
def get_market_data():
    """獲取市場數據 API。可傳 sections=us_indices,us_stocks,... 只取部分區塊以加快首屏顯示。"""
    from flask import request
    from datetime import datetime
    
    try:
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        if refresh:
            # 清除緩存強制刷新（含財報行事曆）
            data_fetcher.cache.clear()
            data_fetcher.cache_time.clear()
            data_fetcher._earnings_cache = None
            data_fetcher._earnings_cache_time = 0
            data_fetcher._earnings_cache_tw = None
            data_fetcher._earnings_cache_tw_time = 0
        
        sections_param = request.args.get('sections', '').strip()
        sections = None
        if sections_param:
            sections = [s.strip() for s in sections_param.split(',') if s.strip()]
        
        summary = data_fetcher.get_market_summary(sections=sections if sections else None)
        summary['timestamp'] = datetime.now(timezone.utc).isoformat()
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock-history/<path:symbol>')
def get_stock_history(symbol):
    """取得單一標的過去一年收盤價歷史，供走勢圖使用（點擊卡片時才拉取）。"""
    from flask import request
    try:
        period = request.args.get('period', '1y')
        data = data_fetcher.get_stock_history(symbol, period=period)
        if not data:
            return jsonify({'success': False, 'error': '無歷史資料'}), 404
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/economic-calendar')
def get_economic_calendar():
    """獲取總經重要事記 API"""
    from flask import request
    from datetime import datetime
    
    try:
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # 只有用户主动刷新时才从BLS爬取新数据
        calendar_data = economic_calendar.get_economic_calendar(force_refresh=refresh)
        calendar_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        return jsonify({
            'success': True,
            'data': calendar_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/strategy-recommendation/<symbol>')
def get_strategy_recommendation(symbol):
    """獲取策略建議 API"""
    try:
        market_data = data_fetcher.get_market_data(symbol)
        if not market_data:
            return jsonify({
                'success': False,
                'error': '無法獲取市場數據'
            }), 404
        
        timing = timing_selector.analyze_market_timing(market_data)
        strategy = strategy_matcher.match_strategy(market_data, timing)
        
        return jsonify({
            'success': True,
            'data': {
                'market_data': market_data,
                'timing': timing,
                'strategy': strategy
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/strategies')
def get_all_strategies():
    """獲取所有策略列表"""
    try:
        strategies = strategy_matcher.get_all_strategies()
        return jsonify({
            'success': True,
            'data': strategies
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/news-volume')
def get_news_volume():
    """獲取新聞聲量分析 API"""
    from flask import request
    from datetime import datetime
    
    try:
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        summary = volume_analyzer.get_volume_summary(refresh=refresh)
        summary['timestamp'] = datetime.now(timezone.utc).isoformat()
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        # 回傳 200 + 空資料，避免前端只看到 502；前端可顯示 error 訊息
        return jsonify({
            'success': False,
            'error': error_msg,
            'data': {
                'top_companies': [],
                'period': '24小時',
                'total_companies': 0,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        })

@app.route('/api/premarket-data')
@app.route('/api/premarket-data/<market>')
def get_premarket_data(market=None):
    """獲取盤前資料 API
    
    Args:
        market: 可選，'taiwan' 或 'us'，指定要刷新的市場
    """
    try:
        force_refresh = market is not None
        
        if market == 'taiwan':
            # 只刷新台股
            taiwan_data = premarket_analyzer.get_taiwan_premarket_news(force_refresh=True)
            us_data = premarket_analyzer.get_us_premarket_news(force_refresh=False)
        elif market == 'us':
            # 只刷新美股
            taiwan_data = premarket_analyzer.get_taiwan_premarket_news(force_refresh=False)
            us_data = premarket_analyzer.get_us_premarket_news(force_refresh=True)
        else:
            # 都不刷新（使用緩存）
            summary = premarket_analyzer.get_premarket_summary()
            return jsonify({
                'success': True,
                'data': summary
            })
        
        summary = {
            'taiwan': taiwan_data,
            'us': us_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        # 確保返回 JSON，即使出錯
        response = jsonify({
            'success': False,
            'error': error_msg,
            'data': {
                'taiwan': {
                    'market': '台股',
                    'type': '錯誤',
                    'news_count': 0,
                    'news': []
                },
                'us': {
                    'market': '美股',
                    'type': '錯誤',
                    'news_count': 0,
                    'news': []
                }
            }
        })
        response.status_code = 500
        return response

@app.route('/api/institutional-net')
def get_institutional_net():
    """三大法人買賣超（當年累計）：三大法人總和、外資。資料來源：證交所 BFI82U"""
    from flask import request
    from datetime import datetime
    try:
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        data = get_institutional_net_ytd(force_refresh=refresh)
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
        data['uploaded_dates'] = list_uploaded_dates()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/institutional-net/dates')
def get_institutional_net_dates():
    """回傳已上傳 CSV 的日期列表（YYYYMMDD），供前端顯示 0101、0102… 等。"""
    try:
        dates = list_uploaded_dates()
        return jsonify({'success': True, 'data': {'dates': dates, 'year': datetime.now().year}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/institutional-net/upload', methods=['POST'])
def upload_institutional_csv():
    """上傳 BFI82U CSV，表單欄位：file（檔案）、date（可選，YYYYMMDD）。日期會依序從：表單 → 檔名 → CSV 內容 辨識。"""
    from flask import request
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '請選擇檔案'}), 400
        f = request.files['file']
        if not f or f.filename == '':
            return jsonify({'success': False, 'error': '請選擇檔案'}), 400
        content = f.read()
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('big5', errors='replace')
        date_str = request.form.get('date', '').strip().replace('-', '').replace('/', '')
        if len(date_str) != 8 or not date_str.isdigit():
            date_str = try_parse_date_from_filename(f.filename or '')
        if not date_str:
            date_str = try_parse_date_from_csv(text)
        if not date_str or len(date_str) != 8:
            return jsonify({
                'success': False,
                'error': '無法辨識日期。請檔名含 YYYYMMDD（如 20260102.csv）或在「日期」欄輸入 YYYYMMDD'
            }), 400
        save_uploaded_csv(date_str, content)
        return jsonify({
            'success': True,
            'data': {'saved_date': date_str, 'uploaded_dates': list_uploaded_dates()},
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ir-meetings')
def get_ir_meetings():
    """獲取法人說明會資料 API"""
    from flask import request
    from datetime import datetime
    
    try:
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        if refresh:
            # 清除緩存強制刷新
            ir_fetcher.cache.clear()
            ir_fetcher.cache_time.clear()
        
        timeline = ir_fetcher.get_ir_timeline(months_ahead=3)
        timeline['timestamp'] = datetime.now(timezone.utc).isoformat()
        return jsonify({
            'success': True,
            'data': timeline
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        # 回傳 200 + 空資料，避免前端只看到 502；前端可顯示 error 訊息
        return jsonify({
            'success': False,
            'error': error_msg,
            'data': {
                'timeline': [],
                'total_meetings': 0,
                'date_range': {
                    'start': None,
                    'end': None
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        })

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)

