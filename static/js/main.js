// 交易系統前端邏輯

// 財報日期顯示為 M/D
function formatEarningsDate(isoDate) {
    if (!isoDate || isoDate.length < 10) return isoDate || '';
    const [y, m, d] = isoDate.slice(0, 10).split('-');
    return (parseInt(m, 10) + '/' + parseInt(d, 10));
}

// 下方區塊載入順序（輕→重、依序發送，避免單一 worker 同時接多個重請求而 502）
function runBelowSectionsInOrder(forceRefresh) {
    forceRefresh = !!forceRefresh;
    var delayMs = 400;
    function next(i, list) {
        if (i >= list.length) return Promise.resolve();
        return list[i](forceRefresh).then(function() {
            return new Promise(function(r) { setTimeout(r, delayMs); });
        }).then(function() { return next(i + 1, list); }).catch(function(e) {
            console.error('Below section load error:', e);
            return next(i + 1, list);
        });
    }
    var order = [loadEconomicCalendar, loadInstitutionalNet, loadIRMeetings, loadPremarketData, loadNewsVolume];
    return next(0, order);
}

// 初始化：市場數據先載入；下方區塊延遲 2 秒後依固定順序「一個接一個」載入，首輪不強制 refresh 以減輕算力
document.addEventListener('DOMContentLoaded', function() {
    loadMarketData(false);
    setTimeout(function() {
        runBelowSectionsInOrder(false).catch(function(e) { console.error(e); });
    }, 2000);
});

// 區塊顯示順序：依此順序更新畫面，避免資料回傳先後造成區塊亂跳
var MARKET_SECTION_ORDER = ['us_indices', 'us_stocks', 'tw_markets', 'international_markets', 'metals_futures', 'crypto', 'ratios'];

// 合併 API 回傳的區塊到總快取並更新畫面
function mergeAndDisplayMarketData(newData) {
    window._marketDataCache = window._marketDataCache || {};
    if (newData && typeof newData === 'object') {
        MARKET_SECTION_ORDER.forEach(function(k) {
            if (newData[k] !== undefined) window._marketDataCache[k] = newData[k];
        });
        if (newData.timestamp !== undefined) window._marketDataCache.timestamp = newData.timestamp;
        if (newData.earnings_upcoming !== undefined) window._marketDataCache.earnings_upcoming = newData.earnings_upcoming;
        if (newData.metals_session !== undefined) window._marketDataCache.metals_session = newData.metals_session;
        if (newData.metals_session_et !== undefined) window._marketDataCache.metals_session_et = newData.metals_session_et;
        if (newData.skipped_symbols !== undefined) window._marketDataCache.skipped_symbols = newData.skipped_symbols;
        if (newData.ratios !== undefined) window._marketDataCache.ratios = newData.ratios;
    }
    displayMarketData(window._marketDataCache);
    if (newData && newData.timestamp) {
        updateSectionTime('us-markets-update-time', newData.timestamp);
        updateSectionTime('tw-markets-update-time', newData.timestamp);
        updateSectionTime('international-markets-update-time', newData.timestamp);
        updateSectionTime('metals-update-time', newData.timestamp);
        updateSectionTime('crypto-update-time', newData.timestamp);
        if (newData.ratios && newData.ratios.timestamp) {
            updateSectionTime('ratios-update-time', newData.ratios.timestamp);
        }
    }
}

// 載入市場數據：先載入美股指數（資料量小、顯示快），再並行載入其餘區塊，避免首屏卡住
async function loadMarketData(forceRefresh = false) {
    console.log('loadMarketData called, forceRefresh:', forceRefresh);
    window._marketDataCache = {};
    const baseUrl = '/api/market-data';
    const refreshQ = forceRefresh ? '&refresh=true' : '';

    // 第一階段：只拉美股指數，快速顯示
    try {
        const url1 = baseUrl + '?sections=us_indices' + refreshQ;
        const controller1 = new AbortController();
        const timeout1 = setTimeout(function() { controller1.abort(); }, 90000);
        const response1 = await fetch(url1, { signal: controller1.signal });
        clearTimeout(timeout1);
        if (!response1.ok) throw new Error('HTTP ' + response1.status);
        const result1 = await response1.json();
        if (result1.success && result1.data) {
            mergeAndDisplayMarketData(result1.data);
        } else {
            throw new Error(result1.error || '首階段載入失敗');
        }
    } catch (error) {
        console.error('載入美股指數錯誤:', error);
        var msg = (error.name === 'AbortError' || (error.message && error.message.indexOf('abort') !== -1))
            ? '請求逾時（伺服器可能正在啟動或忙碌），請稍後按「更新」重試。'
            : ('載入市場數據時發生錯誤: ' + (error.message || ''));
        showError(msg);
        var containers = ['us-indices', 'us-stocks', 'tw-markets', 'international-markets', 'metals-futures', 'crypto-markets'];
        containers.forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="error">載入錯誤: ' + (msg.replace(/^載入市場數據時發生錯誤: /, '') || '') + '</div>';
        });
        return;
    }

    // 第二階段拆成兩批，避免單次請求過久逾時（Free 主機負載大時易超時）
    function setErrorForIds(ids, msg) {
        ids.forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="error">載入錯誤: ' + msg + '</div>';
        });
    }
    var timeoutMsg = '請求逾時（伺服器可能正在啟動或忙碌），請稍後按「更新」重試。';
    var idsAll = ['us-stocks', 'tw-markets', 'international-markets', 'metals-futures', 'crypto-markets'];

    // 2a：美股個股 + 台股（標的多、最吃時間）
    try {
        const url2a = baseUrl + '?sections=us_stocks,tw_markets' + refreshQ;
        const controller2a = new AbortController();
        const timeout2a = setTimeout(function() { controller2a.abort(); }, 120000);
        const response2a = await fetch(url2a, { signal: controller2a.signal });
        clearTimeout(timeout2a);
        if (!response2a.ok) throw new Error('HTTP ' + response2a.status);
        const result2a = await response2a.json();
        if (result2a.success && result2a.data) mergeAndDisplayMarketData(result2a.data);
        else setErrorForIds(['us-stocks', 'tw-markets'], result2a.error || '載入失敗');
    } catch (err2a) {
        console.error('載入美股/台股錯誤:', err2a);
        var isAbort = err2a.name === 'AbortError' || (err2a.message && err2a.message.indexOf('abort') !== -1);
        showError(isAbort ? timeoutMsg : ('載入美股/台股失敗: ' + (err2a.message || '')));
        setErrorForIds(['us-stocks', 'tw-markets'], isAbort ? timeoutMsg : (err2a.message || ''));
    }

    // 2b：國際、金屬、加密、比率
    try {
        const url2b = baseUrl + '?sections=international_markets,metals_futures,crypto,ratios' + refreshQ;
        const controller2b = new AbortController();
        const timeout2b = setTimeout(function() { controller2b.abort(); }, 120000);
        const response2b = await fetch(url2b, { signal: controller2b.signal });
        clearTimeout(timeout2b);
        if (!response2b.ok) throw new Error('HTTP ' + response2b.status);
        const result2b = await response2b.json();
        if (result2b.success && result2b.data) mergeAndDisplayMarketData(result2b.data);
        else setErrorForIds(['international-markets', 'metals-futures', 'crypto-markets'], result2b.error || '載入失敗');
    } catch (err2b) {
        console.error('載入國際/金屬/加密/比率錯誤:', err2b);
        var isAbort2 = err2b.name === 'AbortError' || (err2b.message && err2b.message.indexOf('abort') !== -1);
        showError(isAbort2 ? timeoutMsg : ('載入國際/金屬/加密/比率失敗: ' + (err2b.message || '')));
        setErrorForIds(['international-markets', 'metals-futures', 'crypto-markets'], isAbort2 ? timeoutMsg : (err2b.message || ''));
    }
}

// 刷新市場數據（全市場重新載入，使用分區以加快顯示）
async function refreshMarketData(market) {
    const button = event && event.target;
    if (button) {
        button.disabled = true;
        button.textContent = '更新中...';
    }
    try {
        await loadMarketData(true);
        if (button) {
            button.textContent = '✓ 已更新';
            setTimeout(function() {
                button.textContent = '🔄 更新';
                button.disabled = false;
            }, 2000);
        }
    } catch (error) {
        showError('更新市場數據時發生錯誤: ' + error.message);
        if (button) {
            button.textContent = '🔄 更新';
            button.disabled = false;
        }
    }
}

// 顯示市場數據
function displayMarketData(data) {
    console.log('displayMarketData called with:', data);

    // 無資料標的（404/環境差異）：顯示清單方便比對代碼
    var skippedEl = document.getElementById('skipped-symbols-hint');
    if (skippedEl) {
        if (data && data.skipped_symbols && data.skipped_symbols.length > 0) {
            var list = data.skipped_symbols;
            var msg;
            if (list.length > 20) {
                msg = '⚠️ 多數標的暫無報價（多為 Yahoo 對雲端 IP 限流或阻擋，非代碼錯誤）。請稍後重試或於本機使用。';
            } else {
                var parts = list.map(function (s) {
                    return (s.symbol || s.name) + (s.section ? ' (' + s.section + ')' : '');
                });
                msg = '⚠️ 以下標的暫無報價（可檢查代碼或環境）：<code>' + parts.join(', ') + '</code>';
            }
            skippedEl.innerHTML = msg;
            skippedEl.classList.remove('hidden');
            skippedEl.setAttribute('aria-hidden', 'false');
        } else {
            skippedEl.innerHTML = '';
            skippedEl.classList.add('hidden');
            skippedEl.setAttribute('aria-hidden', 'true');
        }
    }

    // 顯示美股指數；僅在 API 已回傳該區塊時更新
    if (data && data.us_indices !== undefined) {
        if (Object.keys(data.us_indices).length > 0) {
            displayMarketSection('us-indices', data.us_indices, '美股指數');
        } else {
            const container = document.getElementById('us-indices');
            if (container) container.innerHTML = '<div class="loading">暫無美股指數數據</div>';
        }
    }
    // 即將公布財報（60 天內）；僅在 API 已回傳該區塊時更新
    if (data && data.earnings_upcoming !== undefined) {
        const earningsEl = document.getElementById('us-earnings-calendar');
        if (earningsEl) {
            if (data.earnings_upcoming && data.earnings_upcoming.length > 0) {
                const list = data.earnings_upcoming.slice(0, 30).map(function (e) {
                    return '<span class="earnings-chip" title="' + (e.date || '') + '">' +
                        (e.name || e.symbol) + ' <strong>' + formatEarningsDate(e.date) + '</strong>' +
                        (e.days_until !== undefined ? ' <em>(' + e.days_until + ' 天後)</em>' : '') + '</span>';
                }).join('');
                earningsEl.innerHTML = '<div class="earnings-calendar-hint">📅 接下來 60 天內公布財報：</div><div class="earnings-chips">' + list + '</div>';
                earningsEl.classList.remove('hidden');
            } else {
                earningsEl.innerHTML = '';
                earningsEl.classList.add('hidden');
            }
        }
    }

    // 顯示美股個股（三行 + 排序）；僅在 API 已回傳該區塊時更新，否則保留「載入中」
    if (data && data.us_stocks !== undefined) {
        if (Object.keys(data.us_stocks).length > 0) {
            window._lastUsStocksData = data.us_stocks;
            displayMarketSection('us-stocks', data.us_stocks, '美股個股', true, 'threeRows', false, 'price');
        } else {
            const container = document.getElementById('us-stocks');
            if (container) container.innerHTML = '<div class="loading">暫無美股個股數據</div>';
        }
    }
    
    // 顯示台股；僅在 API 已回傳該區塊時更新
    if (data && data.tw_markets !== undefined) {
        if (Object.keys(data.tw_markets).length > 0) {
            window._lastTwMarketsData = data.tw_markets;
            displayMarketSection('tw-markets', data.tw_markets, '台股', false, false, true, 'percentDesc', false, true);
        } else {
            const container = document.getElementById('tw-markets');
            if (container) container.innerHTML = '<div class="loading">暫無台股數據</div>';
        }
    }
    // 顯示國際市場；僅在 API 已回傳該區塊時更新
    if (data && data.international_markets !== undefined) {
        if (Object.keys(data.international_markets).length > 0) {
            displayMarketSection('international-markets', data.international_markets, null, false, false, true);
        } else {
            const container = document.getElementById('international-markets');
            if (container) container.innerHTML = '<div class="loading">暫無國際市場數據</div>';
        }
    }

    // 重金屬專區：期貨；僅在 API 已回傳該區塊時更新
    if (data && data.metals_futures !== undefined) {
        if (Object.keys(data.metals_futures).length > 0) {
            window._lastMetalsFuturesData = data.metals_futures;
            displayMarketSection('metals-futures', data.metals_futures, null, false, false, true, 'percentDesc', true, true);
        } else {
            const container = document.getElementById('metals-futures');
            if (container) container.innerHTML = '<div class="loading">暫無期貨數據</div>';
        }
    }
    // COMEX 目前時段提示（顯示美東時間，說明為何是夜盤/日盤）
    const sessionHint = document.getElementById('metals-session-hint');
    if (sessionHint && data) {
        var msg = 'COMEX 期貨：';
        if (data.metals_session_et) {
            msg += '美東現在 ' + data.metals_session_et + ' → ';
        }
        msg += (data.metals_session || '—');
        msg += '（日盤 = 美東 8:20–13:30，其餘為夜盤）';
        sessionHint.textContent = msg;
    }

    // 加密貨幣專區；僅在 API 已回傳該區塊時更新
    if (data && data.crypto !== undefined) {
        if (Object.keys(data.crypto).length > 0) {
            window._lastCryptoData = data.crypto;
            displayMarketSection('crypto-markets', data.crypto, null, false, false, true, 'percentDesc', false, true);
        } else {
            const container = document.getElementById('crypto-markets');
            if (container) container.innerHTML = '<div class="loading">暫無加密貨幣數據</div>';
        }
    }
    // 重要比率專區；僅在 API 已回傳該區塊時更新
    if (data && data.ratios !== undefined) {
        displayRatios(data.ratios);
        if (data.ratios && data.ratios.timestamp) updateSectionTime('ratios-update-time', data.ratios.timestamp);
    }
}

// 顯示重要比率專區（當前值、區間最高/最低、區間標籤）
function displayRatios(ratioData) {
    const container = document.getElementById('ratios-container');
    if (!container) return;
    if (!ratioData || !ratioData.ratios || ratioData.ratios.length === 0) {
        container.innerHTML = '<div class="loading">暫無比率數據</div>';
        return;
    }
    const cards = ratioData.ratios.map(function(r) {
        const current = r.current != null ? r.current.toLocaleString(undefined, { maximumFractionDigits: 4 }) : '—';
        const high = r.range_high != null ? r.range_high.toLocaleString(undefined, { maximumFractionDigits: 4 }) : '—';
        const low = r.range_low != null ? r.range_low.toLocaleString(undefined, { maximumFractionDigits: 4 }) : '—';
        const period = r.period_label || '';
        const err = r.error ? `<div class="ratio-error">${r.error}</div>` : '';
        let rangeBar = '';
        if (r.range_high != null && r.range_low != null && r.current != null && r.range_high > r.range_low) {
            const pct = ((r.current - r.range_low) / (r.range_high - r.range_low)) * 100;
            rangeBar = `<div class="ratio-range-bar"><div class="ratio-range-fill" style="width:${Math.min(100, Math.max(0, pct))}%"></div></div>`;
        }
        const rid = (r.id || '').replace(/"/g, '&quot;');
        return `
            <div class="ratio-card ratio-card-clickable" data-ratio-id="${rid}" onclick="openRatioChartModal('${rid}')" title="點擊查看走勢圖">
                <div class="ratio-card-name">${(r.name || '').replace(/</g, '&lt;')}</div>
                <div class="ratio-card-desc">${(r.description || '').replace(/</g, '&lt;')}</div>
                <div class="ratio-card-current"><span class="ratio-value">${current}</span> <span class="ratio-unit">${r.unit || ''}</span></div>
                <div class="ratio-card-range">
                    <span>${period} 高: ${high}</span>
                    <span>${period} 低: ${low}</span>
                </div>
                ${rangeBar}
                ${err}
            </div>
        `;
    }).join('');
    container.innerHTML = '<div class="ratios-inner">' + cards + '</div>';
}

var _ratioChartInstance = null;

function closeRatioChartModal() {
    var modal = document.getElementById('ratio-chart-modal');
    if (modal) modal.style.display = 'none';
    if (_ratioChartInstance) {
        _ratioChartInstance.destroy();
        _ratioChartInstance = null;
    }
}

function openRatioChartModal(ratioId) {
    var modal = document.getElementById('ratio-chart-modal');
    var titleEl = document.getElementById('ratio-chart-modal-title');
    var loadingEl = document.getElementById('ratio-chart-loading');
    var wrapEl = document.getElementById('ratio-chart-wrap');
    if (!modal || !titleEl || !loadingEl || !wrapEl) return;
    if (_ratioChartInstance) {
        _ratioChartInstance.destroy();
        _ratioChartInstance = null;
    }
    titleEl.textContent = '載入中…';
    loadingEl.style.display = 'block';
    wrapEl.style.display = 'none';
    modal.style.display = 'flex';

    fetch('/api/ratios/' + encodeURIComponent(ratioId) + '/history?resample=1M')
        .then(function(res) { return res.json(); })
        .then(function(result) {
            loadingEl.style.display = 'none';
            if (!result.success || !result.data || !result.data.dates || result.data.dates.length === 0) {
                titleEl.textContent = (result.data && result.data.name) ? result.data.name : '比率走勢';
                wrapEl.innerHTML = '<p class="ratio-chart-loading">無歷史資料可顯示</p>';
                wrapEl.style.display = 'block';
                return;
            }
            var data = result.data;
            titleEl.textContent = (data.name || '比率走勢') + '（' + (data.period_label || '') + '）';
            wrapEl.innerHTML = '<canvas id="ratio-chart-canvas"></canvas>';
            wrapEl.style.display = 'block';

            var ctx = document.getElementById('ratio-chart-canvas').getContext('2d');
            _ratioChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: data.name || '比率',
                        data: data.values,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            display: true,
                            ticks: { maxTicksLimit: 12 }
                        },
                        y: {
                            display: true,
                            beginAtZero: false
                        }
                    }
                }
            });
        })
        .catch(function(err) {
            loadingEl.style.display = 'none';
            titleEl.textContent = '比率走勢';
            wrapEl.innerHTML = '<p class="ratio-chart-loading">載入失敗：' + (err.message || '請稍後再試') + '</p>';
            wrapEl.style.display = 'block';
        });
}

var _stockChartInstance = null;

function closeStockChartModal() {
    var modal = document.getElementById('stock-chart-modal');
    if (modal) modal.style.display = 'none';
    if (_stockChartInstance) {
        _stockChartInstance.destroy();
        _stockChartInstance = null;
    }
}

function openStockChartModal(symbol, displayName) {
    var modal = document.getElementById('stock-chart-modal');
    var titleEl = document.getElementById('stock-chart-modal-title');
    var loadingEl = document.getElementById('stock-chart-loading');
    var wrapEl = document.getElementById('stock-chart-wrap');
    if (!modal || !titleEl || !loadingEl || !wrapEl) return;
    if (_stockChartInstance) {
        _stockChartInstance.destroy();
        _stockChartInstance = null;
    }
    var name = (displayName && displayName.trim()) ? displayName.trim() : symbol;
    titleEl.textContent = name + ' － 過去一年價格走勢';
    loadingEl.style.display = 'block';
    loadingEl.innerHTML = '載入中...';
    wrapEl.style.display = 'none';
    wrapEl.innerHTML = '<canvas id="stock-chart-canvas"></canvas>';
    modal.style.display = 'flex';

    fetch('/api/stock-history/' + encodeURIComponent(symbol) + '?period=1y')
        .then(function(res) { return res.json(); })
        .then(function(result) {
            loadingEl.style.display = 'none';
            if (!result.success || !result.data || !result.data.dates || result.data.dates.length === 0) {
                titleEl.textContent = name + ' － 過去一年價格走勢';
                wrapEl.innerHTML = '<p class="ratio-chart-loading">無歷史資料可顯示</p>';
                wrapEl.style.display = 'block';
                return;
            }
            var data = result.data;
            titleEl.textContent = (data.name || name) + ' － 過去一年價格走勢';
            wrapEl.innerHTML = '<canvas id="stock-chart-canvas"></canvas>';
            wrapEl.style.display = 'block';

            var ctx = document.getElementById('stock-chart-canvas').getContext('2d');
            _stockChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: '收盤價',
                        data: data.values,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            display: true,
                            ticks: { maxTicksLimit: 12 }
                        },
                        y: {
                            display: true,
                            beginAtZero: false
                        }
                    }
                }
            });
        })
        .catch(function(err) {
            loadingEl.style.display = 'none';
            titleEl.textContent = name + ' － 過去一年價格走勢';
            wrapEl.innerHTML = '<p class="ratio-chart-loading">載入失敗：' + (err.message || '請稍後再試') + '</p>';
            wrapEl.style.display = 'block';
        });
}

// 即時更新比率（只打 /api/ratios，不重拉全部市場）
async function refreshRatios() {
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '更新中...';
    try {
        const response = await fetch('/api/ratios?refresh=true');
        const result = await response.json();
        if (result.success && result.data) {
            displayRatios(result.data);
            if (result.data.timestamp) updateSectionTime('ratios-update-time', result.data.timestamp);
            button.textContent = '✓ 已更新';
        } else {
            showError('更新比率失敗: ' + (result.error || '未知錯誤'));
            button.textContent = originalText;
        }
    } catch (e) {
        showError('更新比率時發生錯誤: ' + e.message);
        button.textContent = originalText;
    }
    setTimeout(function() {
        button.textContent = originalText;
        button.disabled = false;
    }, 2000);
}

// 顯示市場區塊
// sortBy: 'price' | 'priceDesc' | 'percent' | 'percentDesc'
// showSessionLabel: 是否在卡片上顯示時段（日盤/夜盤），用於期貨
// showSortDropdown: 是否顯示排序下拉（台股等），與 twoRows 二擇一使用
function displayMarketSection(containerId, markets, sectionTitle = null, useScroll = false, twoRows = false, useHorizontalGrid = false, sortBy = 'percentDesc', showSessionLabel = false, showSortDropdown = false) {
    console.log(`displayMarketSection called: containerId=${containerId}, markets count=${markets ? Object.keys(markets).length : 0}`);
    
    const container = document.getElementById(containerId);
    
    if (!container) {
        console.error(`找不到容器: ${containerId}`);
        return;
    }
    
    if (!markets || typeof markets !== 'object' || Object.keys(markets).length === 0) {
        console.warn(`無數據或數據格式錯誤: ${containerId}`, markets);
        container.innerHTML = '<div class="loading">暫無數據</div>';
        return;
    }
    
    try {
        let sortedMarkets = Object.values(markets);
        const useSort = (twoRows === 'twoRows' || twoRows === 'threeRows') || showSortDropdown;
        
        // 依選擇排序（美股個股、台股等）
        if (useSort) {
            if (sortBy === 'price') {
                sortedMarkets = sortedMarkets.sort((a, b) => (a.current_price || 0) - (b.current_price || 0));
            } else if (sortBy === 'priceDesc') {
                sortedMarkets = sortedMarkets.sort((a, b) => (b.current_price || 0) - (a.current_price || 0));
            } else if (sortBy === 'percent') {
                sortedMarkets = sortedMarkets.sort((a, b) => (a.change_percent || 0) - (b.change_percent || 0));
            } else {
                sortedMarkets = sortedMarkets.sort((a, b) => (b.change_percent || 0) - (a.change_percent || 0));
            }
        }
        
        const scrollClass = useScroll && twoRows !== 'twoRows' && twoRows !== 'threeRows' ? 'market-grid-scroll' : '';
        const twoRowsClass = twoRows === 'threeRows' ? 'market-grid-three-rows' : (twoRows === 'twoRows' ? 'market-grid-two-rows' : '');
        const horizontalClass = useHorizontalGrid ? 'market-grid-horizontal' : '';
        
        const sortSelectId = containerId + '-sort-select';
        const sortCallbackMap = {
            'us-stocks': 'applyUsStocksSort',
            'tw-markets': 'applyTwMarketsSort',
            'metals-futures': 'applyMetalsFuturesSort',
            'crypto-markets': 'applyCryptoSort'
        };
        const sortOnChange = sortCallbackMap[containerId] ? sortCallbackMap[containerId] + '(this.value)' : '';
        const sortSelectHtml = `
            <div class="us-stocks-sort">
                <label for="${sortSelectId}">排序：</label>
                <select id="${sortSelectId}" onchange="${sortOnChange}">
                    <option value="percentDesc" ${sortBy === 'percentDesc' ? 'selected' : ''}>漲跌幅 高→低</option>
                    <option value="percent" ${sortBy === 'percent' ? 'selected' : ''}>漲跌幅 低→高</option>
                    <option value="priceDesc" ${sortBy === 'priceDesc' ? 'selected' : ''}>價格 高→低</option>
                    <option value="price" ${sortBy === 'price' ? 'selected' : ''}>價格 低→高</option>
                </select>
            </div>
        `;
        
        let titleHtml = '';
        if (sectionTitle) {
            if (twoRows === 'twoRows' || twoRows === 'threeRows') {
                titleHtml = `
                    <div class="us-stocks-header">
                        <h3 class="market-subsection-title">${sectionTitle}</h3>
                        <div class="us-stocks-sort">
                            <label for="us-stocks-sort-select">排序：</label>
                            <select id="us-stocks-sort-select" onchange="applyUsStocksSort(this.value)">
                                <option value="percentDesc" ${sortBy === 'percentDesc' ? 'selected' : ''}>漲跌幅 高→低</option>
                                <option value="percent" ${sortBy === 'percent' ? 'selected' : ''}>漲跌幅 低→高</option>
                                <option value="priceDesc" ${sortBy === 'priceDesc' ? 'selected' : ''}>價格 高→低</option>
                                <option value="price" ${sortBy === 'price' ? 'selected' : ''}>價格 低→高</option>
                            </select>
                        </div>
                    </div>
                `;
            } else if (showSortDropdown && sortOnChange) {
                titleHtml = `<div class="us-stocks-header"><h3 class="market-subsection-title">${sectionTitle}</h3>${sortSelectHtml}</div>`;
            } else {
                titleHtml = `<h3 class="market-subsection-title">${sectionTitle}</h3>`;
            }
        } else if (showSortDropdown && sortOnChange) {
            titleHtml = `<div class="us-stocks-header">${sortSelectHtml}</div>`;
        }
        
        const marketCards = sortedMarkets.map(market => {
            if (!market) {
                console.warn('Invalid market data:', market);
                return '';
            }
            
            const changePercent = market.change_percent || 0;
            const change = market.change || 0;
            const changeClass = changePercent > 0 ? 'change-positive' : 
                               changePercent < 0 ? 'change-negative' : 'change-neutral';
            const changeSymbol = changePercent > 0 ? '↑' : 
                                changePercent < 0 ? '↓' : '→';
            const sessionBadge = showSessionLabel && market.session
                ? `<span class="market-card-session ${market.session === '日盤' ? 'session-day' : 'session-night'}">${market.session}</span>`
                : '';
            const earningsBadge = market.earnings_date
                ? `<span class="market-card-earnings" title="財報公布日 ${market.earnings_date}">財報 ${formatEarningsDate(market.earnings_date)}</span>`
                : '';
            const symbolAttr = (market.symbol || '').replace(/"/g, '&quot;');
            const nameAttr = (market.display_name || market.name || '').replace(/"/g, '&quot;');
            
            return `
                <div class="market-card market-card-chartable ${market.earnings_date ? 'has-upcoming-earnings' : ''}" data-symbol="${symbolAttr}" data-display-name="${nameAttr}" title="點擊查看過去一年走勢">
                    <div class="market-card-header">
                        <div>
                            <div class="market-card-name">${(market.display_name || market.name || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                            <div class="market-card-symbol">${(market.symbol || 'N/A').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                        </div>
                        <div class="market-card-badges">${sessionBadge}${earningsBadge}</div>
                    </div>
                    <div class="market-card-price">
                        ${market.current_price ? market.current_price.toLocaleString() : 'N/A'}
                    </div>
                    <div class="market-card-change ${changeClass}">
                        <span>${changeSymbol}</span>
                        <span>${changePercent.toFixed(2)}%</span>
                        <span>(${change > 0 ? '+' : ''}${change.toFixed(2)})</span>
                    </div>
                    <div class="market-card-details">
                        <div class="detail-item">
                            <span>開盤:</span>
                            <span>${market.open ? market.open.toLocaleString() : 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span>最高:</span>
                            <span>${market.high ? market.high.toLocaleString() : 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span>最低:</span>
                            <span>${market.low ? market.low.toLocaleString() : 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span>成交量:</span>
                            <span>${market.volume ? market.volume.toLocaleString() : 'N/A'}</span>
                        </div>
                    </div>
                </div>
            `;
        }).filter(card => card !== '').join('');
        
        container.innerHTML = `
            ${titleHtml}
            <div class="market-grid ${scrollClass} ${twoRowsClass} ${horizontalClass}">
                ${marketCards}
            </div>
        `;
        
        container.querySelectorAll('.market-card-chartable').forEach(function(card) {
            card.addEventListener('click', function(e) {
                e.preventDefault();
                var s = this.getAttribute('data-symbol');
                var n = this.getAttribute('data-display-name') || s;
                if (s) openStockChartModal(s, n);
            });
        });
        
        console.log(`成功顯示 ${containerId}, 卡片數量: ${Object.keys(markets).length}`);
    } catch (error) {
        console.error(`顯示市場區塊錯誤 (${containerId}):`, error);
        container.innerHTML = `<div class="error">顯示錯誤: ${error.message}</div>`;
    }
}

// 美股個股：切換排序後重新顯示
function applyUsStocksSort(sortBy) {
    const data = window._lastUsStocksData;
    if (!data) return;
    displayMarketSection('us-stocks', data, '美股個股', true, 'threeRows', false, sortBy);
}

// 台股市場：切換排序後重新顯示
function applyTwMarketsSort(sortBy) {
    const data = window._lastTwMarketsData;
    if (!data) return;
    displayMarketSection('tw-markets', data, '台股', false, false, true, sortBy, false, true);
}

// 重金屬期貨：切換排序後重新顯示
function applyMetalsFuturesSort(sortBy) {
    const data = window._lastMetalsFuturesData;
    if (!data) return;
    displayMarketSection('metals-futures', data, null, false, false, true, sortBy, true, true);
}

// 加密貨幣：切換排序後重新顯示
function applyCryptoSort(sortBy) {
    const data = window._lastCryptoData;
    if (!data) return;
    displayMarketSection('crypto-markets', data, null, false, false, true, sortBy, false, true);
}

// 載入總經重要事記
async function loadEconomicCalendar(forceRefresh = false) {
    console.log('loadEconomicCalendar called, forceRefresh:', forceRefresh);
    try {
        const url = forceRefresh ? '/api/economic-calendar?refresh=true' : '/api/economic-calendar';
        console.log('Fetching from:', url);
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Economic calendar API response:', result);
        
        if (result && result.success && result.data) {
            displayEconomicCalendar(result.data);
            if (result.data.timestamp) {
                updateSectionTime('economic-update-time', result.data.timestamp);
            }
        } else {
            console.error('總經事記API返回錯誤:', result);
            const errorMsg = (result && result.error) ? result.error : 'API返回格式錯誤或無數據';
            showError('載入總經重要事記失敗: ' + errorMsg);
            const container = document.getElementById('economic-calendar');
            if (container) {
                container.innerHTML = `<div class="error">載入失敗: ${errorMsg}</div>`;
            }
        }
    } catch (error) {
        console.error('載入總經重要事記錯誤:', error);
        showError('載入總經重要事記時發生錯誤: ' + error.message);
        const container = document.getElementById('economic-calendar');
        if (container) {
            container.innerHTML = `<div class="error">載入錯誤: ${error.message}</div>`;
        }
    }
}

// 刷新總經重要事記
async function refreshEconomicCalendar() {
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '更新中...';
    
    try {
        const response = await fetch('/api/economic-calendar?refresh=true');
        const result = await response.json();
        
        if (result && result.success) {
            displayEconomicCalendar(result.data);
            updateSectionTime('economic-update-time', result.data.timestamp || new Date().toISOString());
            button.textContent = '✓ 已更新';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 2000);
        } else {
            showError('更新總經重要事記失敗: ' + (result.error || '未知錯誤'));
            button.textContent = originalText;
            button.disabled = false;
        }
    } catch (error) {
        showError('更新總經重要事記時發生錯誤: ' + error.message);
        button.textContent = originalText;
        button.disabled = false;
    }
}

// 顯示總經重要事記
function displayEconomicCalendar(data) {
    const container = document.getElementById('economic-calendar');
    
    if (!data) {
        container.innerHTML = '<div class="loading">暫無經濟數據</div>';
        return;
    }
    
    const upcoming = data.upcoming || [];
    const past = data.past || [];
    
    if (upcoming.length === 0 && past.length === 0) {
        container.innerHTML = '<div class="loading">暫無確切發布日期（請按「更新」從 BLS 抓取，或每月至上方的 BLS 連結查看）</div>';
        return;
    }
    
    // 按日期分組
    const groupedUpcoming = groupEventsByDate(upcoming);
    const groupedPast = groupEventsByDate(past);
    
    window._economicEventNames = window._economicEventNames || {};
    
    let html = '<div class="economic-timeline">';
    
    // 即將發布
    if (upcoming.length > 0) {
        html += '<div class="timeline-section">';
        html += '<h3 class="timeline-section-title">即將發布</h3>';
        html += '<div class="timeline-horizontal">';
        
        for (const [date, events] of Object.entries(groupedUpcoming).sort()) {
            html += `<div class="timeline-day-horizontal">`;
            html += `<div class="timeline-date">${formatDate(date)}</div>`;
            html += `<div class="timeline-events">`;
            
            for (const event of events) {
                const eventKey = getEconomicEventKey(event);
                window._economicEventNames[eventKey] = event.name || eventKey;
                const note = getEconomicNote(eventKey);
                const importanceClass = event.importance === 'high' ? 'event-high' : 'event-medium';
                const prevMonth = (event.prev_month_value != null) ? event.prev_month_value : '—';
                const prevYear = (event.prev_year_value != null) ? event.prev_year_value : '—';
                const eventKeyEsc = (eventKey || '').replace(/'/g, "\\'");
                html += `
                    <div class="economic-event economic-event-clickable ${importanceClass}" data-event-key="${eventKey}" onclick="openEconomicNoteModal('${eventKeyEsc}')" title="點擊填寫筆記">
                        <div class="event-time">${event.release_date_tw}</div>
                        <div class="event-name">${event.name}</div>
                        <div class="event-name-en">${event.name_en}</div>
                        <div class="event-prev-values">
                            <span>前月：${prevMonth}</span>
                            <span>前年：${prevYear}</span>
                        </div>
                        <div class="event-source">來源: ${event.source}</div>
                        ${note ? '<div class="event-note-badge">📝 有筆記</div>' : ''}
                    </div>
                `;
            }
            
            html += `</div></div>`;
        }
        
        html += '</div></div>';
    }
    
    // 過往事件（可摺疊）
    if (past.length > 0) {
        html += '<div class="timeline-section">';
        html += '<button class="timeline-past-toggle" onclick="togglePastEvents()">▼ 過往事件</button>';
        html += '<div class="timeline-past" id="past-events" style="display: none;">';
        html += '<div class="timeline-horizontal">';
        
        for (const [date, events] of Object.entries(groupedPast).sort().reverse()) {
            html += `<div class="timeline-day-horizontal timeline-past-day">`;
            html += `<div class="timeline-date">${formatDate(date)}</div>`;
            html += `<div class="timeline-events">`;
            
            for (const event of events) {
                const eventKey = getEconomicEventKey(event);
                window._economicEventNames[eventKey] = event.name || eventKey;
                const note = getEconomicNote(eventKey);
                const prevMonth = (event.prev_month_value != null) ? event.prev_month_value : '—';
                const prevYear = (event.prev_year_value != null) ? event.prev_year_value : '—';
                const eventKeyEsc = (eventKey || '').replace(/'/g, "\\'");
                html += `
                    <div class="economic-event economic-event-clickable event-past" data-event-key="${eventKey}" onclick="openEconomicNoteModal('${eventKeyEsc}')" title="點擊填寫筆記">
                        <div class="event-time">${event.release_date_tw}</div>
                        <div class="event-name">${event.name}</div>
                        <div class="event-name-en">${event.name_en}</div>
                        <div class="event-prev-values"><span>前月：${prevMonth}</span> <span>前年：${prevYear}</span></div>
                        ${note ? '<div class="event-note-badge">📝 有筆記</div>' : ''}
                    </div>
                `;
            }
            
            html += `</div></div>`;
        }
        
        html += '</div></div></div>';
    }
    
    html += '</div>';
    container.innerHTML = html;
}

function getEconomicEventKey(event) {
    const date = event.release_date ? event.release_date.split('T')[0] : '';
    return (event.indicator || '') + '_' + date;
}

function getEconomicNote(eventKey) {
    try {
        return localStorage.getItem('economic_note_' + eventKey) || '';
    } catch (e) {
        return '';
    }
}

let _economicNoteCurrentKey = null;

function openEconomicNoteModal(eventKey) {
    _economicNoteCurrentKey = eventKey;
    const titleEl = document.getElementById('economic-note-modal-title');
    const textareaEl = document.getElementById('economic-note-textarea');
    const modalEl = document.getElementById('economic-note-modal');
    const eventName = (window._economicEventNames && window._economicEventNames[eventKey]) || eventKey;
    if (titleEl) titleEl.textContent = '筆記 － ' + eventName;
    if (textareaEl) textareaEl.value = getEconomicNote(eventKey);
    if (modalEl) modalEl.style.display = 'flex';
}

function closeEconomicNoteModal() {
    _economicNoteCurrentKey = null;
    const modalEl = document.getElementById('economic-note-modal');
    if (modalEl) modalEl.style.display = 'none';
}

function saveEconomicNote() {
    if (!_economicNoteCurrentKey) return;
    const textareaEl = document.getElementById('economic-note-textarea');
    const text = textareaEl ? textareaEl.value.trim() : '';
    try {
        if (text) {
            localStorage.setItem('economic_note_' + _economicNoteCurrentKey, text);
        } else {
            localStorage.removeItem('economic_note_' + _economicNoteCurrentKey);
        }
    } catch (e) {}
    closeEconomicNoteModal();
    // 重新渲染總經區塊以顯示「有筆記」badge（需有辦法只重繪日曆；這裡簡化為提示）
    const container = document.getElementById('economic-calendar');
    if (container && container.querySelector('.economic-timeline')) {
        const noteBadge = container.querySelector('[data-event-key="' + _economicNoteCurrentKey + '"] .event-note-badge');
        if (noteBadge) {
            if (!text) noteBadge.remove();
        } else if (text) {
            const card = container.querySelector('[data-event-key="' + _economicNoteCurrentKey + '"]');
            if (card) {
                const div = document.createElement('div');
                div.className = 'event-note-badge';
                div.textContent = '📝 有筆記';
                card.appendChild(div);
            }
        }
    }
}

// 按日期分组事件
function groupEventsByDate(events) {
    const grouped = {};
    for (const event of events) {
        const date = event.release_date.split('T')[0]; // 只取日期部分
        if (!grouped[date]) {
            grouped[date] = [];
        }
        grouped[date].push(event);
    }
    return grouped;
}

// 格式化日期显示
function formatDate(dateString) {
    const date = new Date(dateString + 'T00:00:00');
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    const weekday = weekdays[date.getDay()];
    return `${month}/${day} (${weekday})`;
}

// 切换过往事件显示
function togglePastEvents() {
    const pastEvents = document.getElementById('past-events');
    const button = document.querySelector('.timeline-past-toggle');
    if (pastEvents.style.display === 'none') {
        pastEvents.style.display = 'block';
        button.textContent = '▲ 隱藏過往事件';
    } else {
        pastEvents.style.display = 'none';
        button.textContent = '▼ 過往事件';
    }
}

// 更新最後更新時間
function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleString('zh-TW');
    // 已移除全局更新时间
}

// 更新區塊時間（固定顯示台灣時間，後端送 UTC）
function updateSectionTime(elementId, timestamp) {
    const element = document.getElementById(elementId);
    if (element && timestamp) {
        const date = new Date(timestamp);
        const timeString = date.toLocaleString('zh-TW', {
            timeZone: 'Asia/Taipei',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        element.textContent = `更新: ${timeString}`;
    }
}

// 載入新聞聲量分析
async function loadNewsVolume(forceRefresh = false) {
    try {
        const url = forceRefresh ? '/api/news-volume?refresh=true' : '/api/news-volume';
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            displayNewsVolume(result.data);
            if (result.data && result.data.timestamp) {
                updateSectionTime('volume-update-time', result.data.timestamp);
            }
        } else {
            console.error('新聞聲量API返回錯誤:', result.error);
            showError('載入新聞聲量失敗: ' + (result.error || '未知錯誤'));
            const container = document.getElementById('news-volume');
            if (container) {
                container.innerHTML = `<div class="error">載入失敗: ${result.error || '未知錯誤'}</div>`;
            }
        }
    } catch (error) {
        console.error('載入新聞聲量錯誤:', error);
        showError('載入新聞聲量時發生錯誤: ' + error.message);
        const container = document.getElementById('news-volume');
        if (container) {
            container.innerHTML = `<div class="error">載入錯誤: ${error.message}</div>`;
        }
    }
}

// 刷新新聞聲量
async function refreshNewsVolume() {
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '更新中...';
    
    try {
        const response = await fetch('/api/news-volume?refresh=true');
        const result = await response.json();
        
        if (result.success) {
            displayNewsVolume(result.data);
            updateSectionTime('volume-update-time', result.data.timestamp || new Date().toISOString());
            button.textContent = '✓ 已更新';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 2000);
        } else {
            showError('更新新聞聲量失敗: ' + result.error);
            button.textContent = originalText;
            button.disabled = false;
        }
    } catch (error) {
        showError('更新新聞聲量時發生錯誤: ' + error.message);
        button.textContent = originalText;
        button.disabled = false;
    }
}

// 顯示新聞聲量分析（預設只顯示前 5 筆，其餘摺疊）
const VOLUME_VISIBLE_COUNT = 5;

function displayNewsVolume(data) {
    const container = document.getElementById('news-volume');
    
    if (!data || !data.top_companies || data.top_companies.length === 0) {
        container.innerHTML = '<div class="loading">暫無聲量數據</div>';
        return;
    }
    
    window._volumeNewsBySymbol = {};
    const topCompanies = data.top_companies.slice(0, 20);
    topCompanies.forEach(function(c) {
        window._volumeNewsBySymbol[c.symbol] = { name: c.name, news: c.news || [] };
    });
    
    const visible = topCompanies.slice(0, VOLUME_VISIBLE_COUNT);
    const extra = topCompanies.slice(VOLUME_VISIBLE_COUNT);
    const extraCount = extra.length;
    
    function makeItem(company) {
        const hasNews = (company.news && company.news.length) > 0;
        const countEl = hasNews
            ? `<button type="button" class="volume-count volume-count-clickable" onclick="openVolumeNewsModal('${(company.symbol || '').replace(/'/g, "\\'")}')" title="點擊查看新聞連結">
                <span class="count-badge">${company.count}</span>
                <span class="count-label">則新聞</span>
               </button>`
            : `<div class="volume-count"><span class="count-badge">${company.count}</span><span class="count-label">則新聞</span></div>`;
        return `
            <div class="volume-item">
                <div class="volume-rank">#${company.rank}</div>
                <div class="volume-info">
                    <div class="volume-name">${(company.name || '').replace(/</g, '&lt;')}</div>
                    <div class="volume-symbol">${(company.symbol || '').replace(/</g, '&lt;')}</div>
                </div>
                ${countEl}
            </div>`;
    }
    
    container.innerHTML = `
        <div class="volume-header">
            <span>統計期間: ${data.period}</span>
            <span>總計: ${data.total_companies} 家公司</span>
        </div>
        <div class="volume-list">
            ${visible.map(c => makeItem(c)).join('')}
            ${extraCount > 0 ? `
            <div class="volume-list-extra" id="volume-list-extra" aria-expanded="false">
                ${extra.map(c => makeItem(c)).join('')}
            </div>
            <button type="button" class="volume-toggle-btn" id="volume-toggle-btn" aria-expanded="false">
                <span class="volume-toggle-text">展開更多（${extraCount} 筆）</span>
                <span class="volume-toggle-icon">▼</span>
            </button>
            ` : ''}
        </div>
    `;
    
    const toggleBtn = document.getElementById('volume-toggle-btn');
    const extraEl = document.getElementById('volume-list-extra');
    if (toggleBtn && extraEl) {
        toggleBtn.addEventListener('click', function () {
            const expanded = extraEl.getAttribute('aria-expanded') === 'true';
            extraEl.classList.toggle('volume-list-extra-open', !expanded);
            extraEl.setAttribute('aria-expanded', !expanded);
            toggleBtn.setAttribute('aria-expanded', !expanded);
            toggleBtn.querySelector('.volume-toggle-text').textContent = expanded ? `展開更多（${extraCount} 筆）` : '收合';
            toggleBtn.querySelector('.volume-toggle-icon').textContent = expanded ? '▼' : '▲';
        });
    }
}

function openVolumeNewsModal(symbol) {
    var info = window._volumeNewsBySymbol && window._volumeNewsBySymbol[symbol];
    var modal = document.getElementById('volume-news-modal');
    var titleEl = document.getElementById('volume-news-modal-title');
    var listEl = document.getElementById('volume-news-modal-list');
    if (!modal || !titleEl || !listEl) return;
    var name = (info && info.name) ? info.name : symbol;
    var newsList = (info && info.news) ? info.news : [];
    titleEl.textContent = name + '（' + symbol + '）－新聞連結';
    if (newsList.length === 0) {
        listEl.innerHTML = '<p class="volume-news-empty">暫無新聞連結</p>';
    } else {
        listEl.innerHTML = newsList.map(function(n) {
            var title = (n.title || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            var link = (n.link || '').replace(/"/g, '&quot;');
            var pub = (n.publisher || '') ? ' · ' + (n.publisher || '').replace(/</g, '&lt;') : '';
            var time = (n.published_at || '').substring(0, 19).replace('T', ' ');
            return '<div class="volume-news-item">' +
                (link ? '<a href="' + link + '" target="_blank" rel="noopener noreferrer" class="volume-news-link">' + title + '</a>' : '<span>' + title + '</span>') +
                '<div class="volume-news-meta">' + pub + (time ? ' · ' + time : '') + '</div>' +
                '</div>';
        }).join('');
    }
    modal.style.display = 'flex';
}

function closeVolumeNewsModal() {
    var modal = document.getElementById('volume-news-modal');
    if (modal) modal.style.display = 'none';
}

// 載入盤前資料
async function loadPremarketData(forceRefresh = false) {
    try {
        const url = forceRefresh ? '/api/premarket-data?refresh=true' : '/api/premarket-data';
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            displayPremarketData(result.data);
            if (result.data.taiwan && result.data.taiwan.timestamp) {
                updateSectionTime('taiwan-premarket-update-time', result.data.taiwan.timestamp);
            }
            if (result.data.us && result.data.us.timestamp) {
                updateSectionTime('us-premarket-update-time', result.data.us.timestamp);
            }
        } else {
            console.error('盤前資料API返回錯誤:', result.error);
            showError('載入盤前資料失敗: ' + (result.error || '未知錯誤'));
            const containers = ['taiwan-premarket', 'us-premarket'];
            containers.forEach(id => {
                const container = document.getElementById(id);
                if (container) {
                    container.innerHTML = `<div class="error">載入失敗: ${result.error || '未知錯誤'}</div>`;
                }
            });
        }
    } catch (error) {
        console.error('載入盤前資料錯誤:', error);
        showError('載入盤前資料時發生錯誤: ' + error.message);
        const containers = ['taiwan-premarket', 'us-premarket'];
        containers.forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = `<div class="error">載入錯誤: ${error.message}</div>`;
            }
        });
    }
}

// 刷新盤前資料（指定市場）
async function refreshPremarketData(market) {
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '更新中...';
    
    try {
        const response = await fetch(`/api/premarket-data/${market}`);
        const result = await response.json();
        
        if (result.success) {
            displayPremarketData(result.data);
            if (result.data.taiwan && result.data.taiwan.timestamp) {
                updateSectionTime('taiwan-premarket-update-time', result.data.taiwan.timestamp);
            }
            if (result.data.us && result.data.us.timestamp) {
                updateSectionTime('us-premarket-update-time', result.data.us.timestamp);
            }
            button.textContent = '✓ 已更新';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 2000);
        } else {
            showError('更新盤前資料失敗: ' + result.error);
            button.textContent = originalText;
            button.disabled = false;
        }
    } catch (error) {
        showError('更新盤前資料時發生錯誤: ' + error.message);
        button.textContent = originalText;
        button.disabled = false;
    }
}

// 顯示盤前資料
function displayPremarketData(data) {
    // 顯示台股盤前資料
    if (data.taiwan) {
        displayPremarketMarket('taiwan-premarket', data.taiwan);
    }
    
    // 顯示美股盤前資料
    if (data.us) {
        displayPremarketMarket('us-premarket', data.us);
    }
}

// 顯示單一市場的盤前資料
function displayPremarketMarket(containerId, marketData) {
    const container = document.getElementById(containerId);
    
    if (!marketData || !marketData.news || marketData.news.length === 0) {
        container.innerHTML = '<div class="loading">暫無盤前資料</div>';
        return;
    }
    
    const typeClass = marketData.type === '盤前' ? 'premarket-type-before' : 'premarket-type-after';
    
    container.innerHTML = `
        <div class="premarket-header">
            <span class="premarket-type ${typeClass}">${marketData.type}</span>
            <span class="premarket-count">${marketData.news_count} 則新聞</span>
        </div>
        <div class="premarket-news-list">
            ${marketData.news.map(news => {
                const date = new Date(news.published_at);
                const timeStr = date.toLocaleString('zh-TW', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
                
                return `
                    <div class="premarket-news-item">
                        <div class="news-time">${timeStr}</div>
                        <div class="news-content">
                            <div class="news-title">${news.title}</div>
                            <div class="news-publisher">${news.publisher}</div>
                        </div>
                        ${news.link ? `<a href="${news.link}" target="_blank" class="news-link">🔗</a>` : ''}
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// 載入法人說明會資料
async function loadIRMeetings(forceRefresh = false) {
    try {
        const url = forceRefresh ? '/api/ir-meetings?refresh=true' : '/api/ir-meetings';
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            displayIRTimeline(result.data);
            if (result.data && result.data.timestamp) {
                updateSectionTime('ir-update-time', result.data.timestamp);
            }
        } else {
            console.error('法說會API返回錯誤:', result.error);
            showError('載入法說會資料失敗: ' + (result.error || '未知錯誤'));
            const container = document.getElementById('ir-timeline');
            if (container) {
                container.innerHTML = `<div class="error">載入失敗: ${result.error || '未知錯誤'}</div>`;
            }
        }
    } catch (error) {
        console.error('載入法說會資料錯誤:', error);
        showError('載入法說會資料時發生錯誤: ' + error.message);
        const container = document.getElementById('ir-timeline');
        if (container) {
            container.innerHTML = `<div class="error">載入錯誤: ${error.message}</div>`;
        }
    }
}

// 刷新法說會資料
async function refreshIRMeetings() {
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '更新中...';
    
    try {
        const response = await fetch('/api/ir-meetings?refresh=true');
        const result = await response.json();
        
        if (result.success) {
            displayIRTimeline(result.data);
            updateSectionTime('ir-update-time', result.data.timestamp || new Date().toISOString());
            button.textContent = '✓ 已更新';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 2000);
        } else {
            showError('更新法說會資料失敗: ' + result.error);
            button.textContent = originalText;
            button.disabled = false;
        }
    } catch (error) {
        showError('更新法說會資料時發生錯誤: ' + error.message);
        button.textContent = originalText;
        button.disabled = false;
    }
}

// --- 三大法人買賣超專區 ---
var _institutionalChartTotal = null;
var _institutionalChartBreakdown = null;

async function loadInstitutionalNet(forceRefresh) {
    const container = document.getElementById('institutional-charts');
    if (!container) return;
    try {
        const url = forceRefresh ? '/api/institutional-net?refresh=true' : '/api/institutional-net';
        const response = await fetch(url);
        const result = await response.json();
        if (result.success && result.data) {
            displayInstitutionalCharts(result.data);
            renderInstitutionalDates(result.data.uploaded_dates || [], result.data.year || new Date().getFullYear());
            if (result.data.timestamp) {
                updateSectionTime('institutional-update-time', result.data.timestamp);
            }
        } else {
            container.innerHTML = '<div class="error">載入失敗: ' + (result.error || '未知錯誤') + '</div>';
        }
    } catch (err) {
        container.innerHTML = '<div class="error">載入錯誤: ' + (err.message || '請稍後再試') + '</div>';
    }
}

async function refreshInstitutionalNet() {
    const btn = event && event.target;
    if (btn) {
        btn.disabled = true;
        btn.textContent = '更新中...';
    }
    await loadInstitutionalNet(true);
    if (btn) {
        btn.textContent = '✓ 已更新';
        setTimeout(function() { btn.textContent = '🔄 更新'; btn.disabled = false; }, 2000);
    }
}

async function uploadInstitutionalCsv() {
    var fileInput = document.getElementById('institutional-csv-file');
    var dateInput = document.getElementById('institutional-csv-date');
    var statusEl = document.getElementById('institutional-upload-status');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showError('請先選擇 CSV 檔案（可多選）');
        return;
    }
    var files = Array.from(fileInput.files);
    var singleDate = dateInput && dateInput.value.trim() ? dateInput.value.trim().replace(/-/g, '').replace(/\//g, '') : '';
    if (files.length > 1) singleDate = '';
    var btn = document.querySelector('.institutional-upload-form button');
    if (btn) btn.disabled = true;
    var ok = 0;
    var fail = 0;
    for (var i = 0; i < files.length; i++) {
        if (statusEl) statusEl.textContent = '上傳中 ' + (i + 1) + '/' + files.length + '…';
        var form = new FormData();
        form.append('file', files[i]);
        if (files.length === 1 && singleDate.length === 8) form.append('date', singleDate);
        try {
            var res = await fetch('/api/institutional-net/upload', { method: 'POST', body: form });
            var result = await res.json();
            if (result.success && result.data) {
                ok++;
                if (i === files.length - 1) {
                    renderInstitutionalDates(result.data.uploaded_dates || [], new Date().getFullYear());
                }
            } else {
                fail++;
                showError((result.error || '上傳失敗') + '：' + (files[i].name || ''));
            }
        } catch (err) {
            fail++;
            showError('上傳錯誤 ' + (files[i].name || '') + ': ' + (err.message || ''));
        }
    }
    fileInput.value = '';
    if (dateInput) dateInput.value = '';
    if (statusEl) statusEl.textContent = ok > 0 ? '已上傳 ' + ok + ' 個' + (fail > 0 ? '，' + fail + ' 個失敗' : '') : '上傳失敗';
    if (ok > 0) await loadInstitutionalNet(true);
    if (btn) {
        btn.textContent = '✓ 上傳';
        setTimeout(function() { btn.textContent = '上傳'; btn.disabled = false; }, 2000);
    } else {
        if (btn) btn.disabled = false;
    }
    setTimeout(function() { if (statusEl) statusEl.textContent = ''; }, 4000);
}

function renderInstitutionalDates(dates, year) {
    var el = document.getElementById('institutional-dates-list');
    if (!el) return;
    year = year || new Date().getFullYear();
    if (!dates || dates.length === 0) {
        el.innerHTML = '<span class="institutional-dates-empty">尚無上傳的日期</span>';
        return;
    }
    var chips = dates.map(function(d) {
        if (d.length === 8 && d.slice(0, 4) === String(year)) {
            return d.slice(4, 6) + d.slice(6, 8);
        }
        return d;
    });
    el.innerHTML = chips.map(function(c) {
        return '<span class="institutional-date-chip">' + c + '</span>';
    }).join('');
}

function displayInstitutionalCharts(data) {
    const container = document.getElementById('institutional-charts');
    if (!container) return;
    if (_institutionalChartTotal) {
        _institutionalChartTotal.destroy();
        _institutionalChartTotal = null;
    }
    if (_institutionalChartBreakdown) {
        _institutionalChartBreakdown.destroy();
        _institutionalChartBreakdown = null;
    }
    if (!data || !data.labels || data.labels.length === 0) {
        var msg = '暫無當年累計資料。';
        if (data && data.fetch_error) {
            msg += ' 可能原因：' + data.fetch_error;
        }
        if (data && data.csv_help) {
            msg += ' ' + data.csv_help;
        }
        container.innerHTML = '<div class="institutional-empty">' + msg + '</div>';
        return;
    }
    container.innerHTML =
        '<div class="institutional-two-charts">' +
        '<div class="institutional-chart-box">' +
        '<h3 class="institutional-chart-title">三大法人總和（當年累計）</h3>' +
        '<div class="institutional-chart-wrap"><canvas id="institutional-chart-total"></canvas></div>' +
        '</div>' +
        '<div class="institutional-chart-box">' +
        '<h3 class="institutional-chart-title">三大法人個別（當年累計）</h3>' +
        '<div class="institutional-chart-wrap"><canvas id="institutional-chart-breakdown"></canvas></div>' +
        '</div>' +
        '</div>';
    var opts = {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 2.2,
        plugins: { legend: { position: 'top' } },
        scales: {
            x: { display: true, ticks: { maxTicksLimit: 14, maxRotation: 45 } },
            y: { type: 'linear', display: true, position: 'left', title: { display: true, text: '百萬台幣' } }
        }
    };
    var ctxTotal = document.getElementById('institutional-chart-total');
    if (ctxTotal) {
        _institutionalChartTotal = new Chart(ctxTotal.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: '三大法人總和（百萬）',
                    data: data.cumulative_total_millions,
                    backgroundColor: 'rgba(102, 126, 234, 0.7)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }]
            },
            options: opts
        });
    }
    var ctxBreakdown = document.getElementById('institutional-chart-breakdown');
    if (ctxBreakdown) {
        _institutionalChartBreakdown = new Chart(ctxBreakdown.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [
                    { label: '外資（百萬）', data: data.cumulative_foreign_millions || [], backgroundColor: 'rgba(100, 181, 246, 0.7)', borderColor: 'rgba(100, 181, 246, 1)', borderWidth: 1 },
                    { label: '投信（百萬）', data: data.cumulative_trust_millions || [], backgroundColor: 'rgba(129, 199, 132, 0.7)', borderColor: 'rgba(129, 199, 132, 1)', borderWidth: 1 },
                    { label: '自營商（百萬）', data: data.cumulative_dealer_millions || [], backgroundColor: 'rgba(255, 183, 77, 0.7)', borderColor: 'rgba(255, 183, 77, 1)', borderWidth: 1 }
                ]
            },
            options: opts
        });
    }
}

// 顯示法人說明會時間線
function displayIRTimeline(data) {
    const container = document.getElementById('ir-timeline');
    
    if (!data || !data.timeline || data.timeline.length === 0) {
        container.innerHTML = `
            <div class="ir-error">
                <p>暫無法說會資料</p>
                <p style="font-size: 12px; color: #999; margin-top: 10px;">
                    請手動下載 CSV 文件並放置在 <code>ir_csv</code> 文件夾中<br>
                    <strong>下載步驟：</strong><br>
                    1. 訪問 <a href="https://mopsov.twse.com.tw/mops/web/t100sb02_1" target="_blank" style="color: #667eea;">公開資訊觀測站</a><br>
                    2. 選擇市場別、年度、月份後點擊「查詢」<br>
                    3. 點擊「另存CSV」下載文件<br>
                    4. 將文件放入 <code>ir_csv</code> 文件夾<br>
                    詳細說明請查看 <code>ir_csv/README.md</code>
                </p>
            </div>
        `;
        return;
    }
    
    const totalMeetings = data.total_meetings || 0;
    const dateRange = data.date_range || {};
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    
    // 分離過去和未來的日期
    const pastDays = [];
    const futureDays = [];
    
    data.timeline.forEach(day => {
        const dayDate = new Date(day.date);
        dayDate.setHours(0, 0, 0, 0);
        if (dayDate < now) {
            pastDays.push(day);
        } else {
            futureDays.push(day);
        }
    });
    
    container.innerHTML = `
        <div class="ir-header">
            <div class="ir-stats">
                <span>總計 <strong>${totalMeetings}</strong> 場法說會</span>
                ${dateRange.start && dateRange.end ? 
                    `<span>期間: ${formatDate(dateRange.start)} ~ ${formatDate(dateRange.end)}</span>` : ''}
            </div>
        </div>
        <div class="timeline-container-split">
            ${pastDays.length > 0 ? `
                <div class="timeline-past-section">
                    <div class="timeline-past-header" onclick="togglePastMeetings()">
                        <span class="toggle-icon">▼</span>
                        <span class="toggle-text">過去的法說會</span>
                        <span class="toggle-count">(${pastDays.length} 天, ${pastDays.reduce((sum, d) => sum + d.count, 0)} 場)</span>
                    </div>
                    <div class="timeline-past-content" id="timeline-past" style="display: none;">
                        <div class="timeline-horizontal-past">
                            ${pastDays.map((day, index) => {
                                const date = new Date(day.date);
                                return createTimelineDay(day, date, index, true);
                            }).join('')}
                        </div>
                    </div>
                </div>
            ` : ''}
            <div class="timeline-future-section">
                <div class="timeline-future-header">
                    <span>未來的法說會</span>
                </div>
                <div class="timeline-horizontal-future">
                    ${futureDays.map((day, index) => {
                        const date = new Date(day.date);
                        return createTimelineDay(day, date, index, false);
                    }).join('')}
                </div>
            </div>
        </div>
    `;
}

// 創建時間線日期項目
function createTimelineDay(day, date, index, isPast) {
    return `
        <div class="timeline-day-horizontal ${isPast ? 'past' : ''}">
            <div class="timeline-date-horizontal">
                <div class="date-main-horizontal">${date.getDate()}</div>
                <div class="date-info-horizontal">
                    <div class="date-month-horizontal">${date.toLocaleDateString('zh-TW', { month: 'long' })}</div>
                    <div class="date-weekday-horizontal">${date.toLocaleDateString('zh-TW', { weekday: 'short' })}</div>
                </div>
                <div class="date-count-horizontal">${day.count} 場</div>
            </div>
            <div class="timeline-meetings-horizontal">
                ${day.meetings.map(meeting => {
                    const meetingDate = new Date(meeting.meeting_date);
                    const timeStr = meeting.meeting_time || meetingDate.toLocaleTimeString('zh-TW', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    
                    return `
                        <div class="meeting-item-horizontal">
                            <div class="meeting-time-horizontal">${timeStr}</div>
                            <div class="meeting-content-horizontal">
                                <div class="meeting-company-horizontal">
                                    <span class="company-code-horizontal">${meeting.company_code}</span>
                                    <span class="company-name-horizontal">${meeting.company_name}</span>
                                </div>
                                ${meeting.location ? `<div class="meeting-location-horizontal">📍 ${meeting.location}</div>` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

// 切換過去法說會的顯示
function togglePastMeetings() {
    const pastContainer = document.getElementById('timeline-past');
    const toggleIcon = document.querySelector('.toggle-icon');
    if (pastContainer) {
        if (pastContainer.style.display === 'none') {
            pastContainer.style.display = 'flex';
            if (toggleIcon) toggleIcon.textContent = '▲';
        } else {
            pastContainer.style.display = 'none';
            if (toggleIcon) toggleIcon.textContent = '▼';
        }
    }
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-TW', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

// 顯示錯誤訊息
function showError(message) {
    console.error(message);
    // 可以在頁面上顯示錯誤訊息
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    document.querySelector('.container').insertBefore(errorDiv, document.querySelector('.container').firstChild);
    
    // 3秒後自動移除
    setTimeout(() => {
        errorDiv.remove();
    }, 3000);
}

