"""
聲量分析模組 - 分析前24小時公司新聞出現頻率
"""
from datetime import datetime, timedelta
from typing import Dict, List
from collections import Counter
from news_analysis.news_fetcher import NewsFetcher
from config import Config

class VolumeAnalyzer:
    """聲量分析器"""
    
    def __init__(self):
        self.news_fetcher = NewsFetcher()
    
    def get_top_companies_by_volume(self, hours: int = 24, top_n: int = 20) -> List[Dict]:
        """
        獲取前24小時新聞聲量最高的公司
        
        Args:
            hours: 時間範圍（小時）
            top_n: 返回前N名
            
        Returns:
            公司聲量列表，按頻率排序
        """
        try:
            keywords = ['台股', '股票', '股市']
            result = self.news_fetcher.get_news_volume_with_news(keywords, hours, max_news_per_company=50)
            volume_dict = result['volume']
            news_by_symbol = result.get('news_by_symbol', {})
            
            company_names = {}
            company_names.update(Config.US_INDICES)
            company_names.update(Config.US_STOCKS)
            company_names.update(Config.TW_MARKETS)
            company_names.update(Config.INTERNATIONAL_MARKETS)
            
            volume_list = []
            for symbol, count in sorted(volume_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]:
                volume_list.append({
                    'symbol': symbol,
                    'name': company_names.get(symbol, symbol),
                    'count': count,
                    'rank': len(volume_list) + 1,
                    'news': news_by_symbol.get(symbol, []),
                })
            
            return volume_list
        except Exception as e:
            print(f"Error in get_top_companies_by_volume: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_volume_summary(self, refresh: bool = False) -> Dict:
        """
        獲取聲量總覽
        
        Returns:
            聲量分析結果
        """
        try:
            top_companies = self.get_top_companies_by_volume(hours=24, top_n=20)
        except Exception as e:
            print(f"Error in get_top_companies_by_volume: {str(e)}")
            # 如果出錯，返回空列表
            top_companies = []
        
        return {
            'top_companies': top_companies,
            'period': '24小時',
            'timestamp': datetime.now().isoformat(),
            'total_companies': len(top_companies)
        }

