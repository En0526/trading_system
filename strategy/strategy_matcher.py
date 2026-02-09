"""
策略匹配器 - 根據市場環境選擇最適合的交易策略
"""
from typing import Dict, List, Optional
from datetime import datetime

class StrategyMatcher:
    """策略匹配器"""
    
    def __init__(self):
        # 定義可用策略
        self.strategies = {
            'momentum': {
                'name': '動量策略',
                'description': '適合趨勢明確的市場環境',
                'conditions': ['high_volatility', 'strong_trend']
            },
            'mean_reversion': {
                'name': '均值回歸策略',
                'description': '適合波動較大的震盪市場',
                'conditions': ['high_volatility', 'sideways_market']
            },
            'breakout': {
                'name': '突破策略',
                'description': '適合關鍵價位突破時機',
                'conditions': ['low_volatility', 'consolidation']
            },
            'trend_following': {
                'name': '趨勢跟隨策略',
                'description': '適合明確趨勢方向',
                'conditions': ['clear_trend', 'moderate_volatility']
            }
        }
    
    def match_strategy(self, market_data: Dict, timing_signal: Dict) -> Dict:
        """
        根據市場數據和擇時信號匹配策略
        
        Args:
            market_data: 市場數據
            timing_signal: 擇時信號
        
        Returns:
            匹配的策略建議
        """
        if not market_data or not timing_signal:
            return {
                'recommended_strategy': None,
                'confidence': 0,
                'reason': '數據不足'
            }
        
        signal = timing_signal.get('signal', 'UNKNOWN')
        change_percent = abs(market_data.get('change_percent', 0))
        volume = market_data.get('volume', 0)
        
        # 簡單的策略匹配邏輯（後續可擴展為更複雜的算法）
        if signal == 'BULLISH' and change_percent > 2:
            strategy = 'momentum'
            confidence = 75
            reason = '強勁上漲趨勢，適合動量策略'
        elif signal == 'BEARISH' and change_percent > 2:
            strategy = 'mean_reversion'
            confidence = 70
            reason = '大幅下跌後可能反彈，適合均值回歸'
        elif signal == 'NEUTRAL' and change_percent < 0.5:
            strategy = 'breakout'
            confidence = 60
            reason = '市場整理，等待突破機會'
        elif signal == 'BULLISH':
            strategy = 'trend_following'
            confidence = 65
            reason = '溫和上漲，適合趨勢跟隨'
        else:
            strategy = 'mean_reversion'
            confidence = 55
            reason = '市場震盪，適合均值回歸'
        
        strategy_info = self.strategies.get(strategy, {})
        
        return {
            'recommended_strategy': strategy,
            'strategy_name': strategy_info.get('name', strategy),
            'strategy_description': strategy_info.get('description', ''),
            'confidence': confidence,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_all_strategies(self) -> Dict:
        """獲取所有可用策略"""
        return self.strategies

