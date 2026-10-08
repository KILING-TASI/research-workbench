"""Keep embedded ETF assets intact when rebuilding the existing platform."""
def embed(page,assets):
    def resource(name):
        path=assets/name
        if not path.is_file():
            raise FileNotFoundError(f'工作台模块资源缺失：{name}；保留原页面')
        text=path.read_text(encoding='utf-8')
        if name.endswith('.json'):
            import json
            text=json.dumps(json.loads(text),ensure_ascii=False).replace('<',r'\u003c')
        return text
    for marker,name in [('/*ETF_STYLE*/','etf-style.css'),('<!--ETF_PANEL-->','etf-panel.html'),
                        ('/*ETF_ENGINE*/','etf-engine.js'),('/*ETF_UI*/','etf-ui.js')]:
        if marker in page:page=page.replace(marker,resource(name))
    for marker,name in [('<!--ETF_REPLACEMENT_PANEL-->','etf-replacement-panel.html'),('/*ETF_REPLACEMENT_TRIAL*/','etf-replacement-trial.json'),('/*ETF_REPLACEMENT_UI*/','etf-replacement-ui.js')]:
        if marker in page:page=page.replace(marker,resource(name))
    if '/*ETF_SNAPSHOT*/' in page:page=page.replace('/*ETF_SNAPSHOT*/',resource('etf-data.json'))
    for marker,name in [('<!--STOCK_MASTERS_PANEL-->','stock-masters-panel.html'),('/*STOCK_MASTERS_STYLE*/','stock-masters-style.css'),('/*STOCK_MASTERS_DATA*/','stock-masters-data.json'),('/*STOCK_MASTERS_UI*/','stock-masters-ui.js'),('/*RESEARCH_WORKFLOW*/','research-workflow.js'),('/*WORKBENCH_LAYOUT*/','workbench-layout.css'),('/*FINANCIAL_EVIDENCE*/','financial-evidence.js'),('/*RESEARCH_JOURNAL*/','research-journal.js'),('/*MARKET_TAXONOMY*/','market-taxonomy.js'),('<!--STOCK_PANEL-->','stock-panel.html'),('/*STOCK_UI*/','stock-ui.js'),('/*STOCK_SNAPSHOT*/','stock-data.json'),('<!--FUND_PANEL-->','fund-panel.html'),('/*FUND_UI*/','fund-ui.js'),('/*FUND_SNAPSHOT*/','fund-data.json'),('/*FACTOR_STYLE*/','factor-style.css'),('<!--FACTOR_PANEL-->','factor-panel.html'),('/*FACTOR_UI*/','factor-ui.js'),('/*FACTOR_SNAPSHOT*/','factor-data.json'),('/*MACRO_STYLE*/','macro-style.css'),('<!--MACRO_PANEL-->','macro-panel.html'),('/*MACRO_ENGINE*/','macro-engine.js'),('/*MACRO_UI*/','macro-ui.js'),('/*MACRO_SNAPSHOT*/','macro-data.json')]:
        if marker in page:page=page.replace(marker,resource(name))
    # These modules share the workbench and must survive a BJX-only rebuild.
    for marker,name in [('<!--FUND_TOOLS_PANEL-->','fund-tools-panel.html'),
                        ('/*FUND_TOOLS_UI*/','fund-tools-ui.js'),
                        ('/*FUND_DETAIL_SNAPSHOT*/','fund-detail-data.json'),
                        ('<!--STOCK_RESEARCH_PANEL-->','stock-research-panel.html'),
                        ('/*STOCK_RESEARCH_UI*/','stock-research-ui.js')]:
        if marker not in page:
            continue
        page=page.replace(marker,resource(name))
    marker='/*FACTOR_VALIDATION*/[]'
    if marker in page:
        page=page.replace(marker,resource('factor-validation.json'))
    return page
