import json
with open('notebooks/08_portfolio_simulation.ipynb', 'r', encoding='utf-8') as f: nb = json.load(f)
for i, c in enumerate(nb['cells']):
    if c['cell_type'] == 'markdown' and '## 6. Interpreting the Volatility' in ''.join(c['source']):
        print('Already added')
        exit()
nb['cells'].append({'cell_type': 'markdown', 'metadata': {}, 'source': ['## 6. Interpreting the Volatility\n', '\n', '**Why do SELL scenarios exhibit lower volatility (narrower P10-P90 bands) compared to HOLD scenarios?**\n', '\n', 'In the Monte Carlo simulation, a SELL decision represents a panic-selling behavioral pattern. When an investor panic-sells during a market drawdown, the simulator assumes they realize their losses (incurring a 5% transaction/impact cost) and subsequently move their capital into a highly conservative, bond-heavy allocation (e.g. reducing stock allocation by 70%). \n', '\n', 'Because bonds exhibit significantly lower historical volatility compared to equities, this conservative reinvestment naturally results in much narrower uncertainty bands (P10 to P90) over the long horizon. However, this reduced volatility comes at a massive cost to expected wealth, as the portfolio fails to compound at equity market rates during the subsequent recovery years.']})
with open('notebooks/08_portfolio_simulation.ipynb', 'w', encoding='utf-8') as f: json.dump(nb, f, indent=1)
