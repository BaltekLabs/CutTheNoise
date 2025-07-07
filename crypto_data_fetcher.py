#!/usr/bin/env python3
"""
Crypto Data Fetcher
Fetches cryptocurrency data from CoinGecko API and generates summaries
"""

import requests
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional

class CryptoDataFetcher:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CryptoDataFetcher/1.0'
        })
        
    def parse_tickers_from_file(self, file_path: str) -> List[str]:
        """Parse ticker symbols from markdown file"""
        tickers = []
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                # Find all lines with checkbox format
                ticker_lines = re.findall(r'- \[ \] ([A-Z0-9\.]+)', content)
                tickers = [ticker.strip() for ticker in ticker_lines]
        except FileNotFoundError:
            print(f"File {file_path} not found")
        return tickers
    
    def get_coin_id_from_symbol(self, symbol: str) -> Optional[str]:
        """Get CoinGecko coin ID from ticker symbol"""
        try:
            url = f"{self.base_url}/coins/list"
            response = self.session.get(url)
            response.raise_for_status()
            coins = response.json()
            
            # Find coin by symbol (case insensitive)
            for coin in coins:
                if coin['symbol'].upper() == symbol.upper():
                    return coin['id']
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"Rate limit hit for {symbol}, waiting 60 seconds...")
                time.sleep(60)
                return self.get_coin_id_from_symbol(symbol)  # Retry
            else:
                print(f"Error getting coin ID for {symbol}: {e}")
                return None
        except Exception as e:
            print(f"Error getting coin ID for {symbol}: {e}")
            return None
    
    def get_coin_data(self, coin_id: str) -> Optional[Dict]:
        """Fetch comprehensive coin data from CoinGecko"""
        try:
            url = f"{self.base_url}/coins/{coin_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'false',
                'sparkline': 'false'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching data for {coin_id}: {e}")
            return None
    
    def format_price(self, price: float) -> str:
        """Format price for display"""
        if price >= 1:
            return f"${price:,.2f}"
        elif price >= 0.01:
            return f"${price:.4f}"
        else:
            return f"${price:.8f}"
    
    def calculate_sentiment(self, data: Dict) -> str:
        """Calculate basic sentiment from available data"""
        try:
            price_change_24h = data.get('market_data', {}).get('price_change_percentage_24h', 0)
            price_change_7d = data.get('market_data', {}).get('price_change_percentage_7d', 0)
            
            if price_change_24h > 5:
                return "Bullish"
            elif price_change_24h < -5:
                return "Bearish"
            elif price_change_7d > 10:
                return "Positive"
            elif price_change_7d < -10:
                return "Negative"
            else:
                return "Neutral"
        except:
            return "Unknown"
    
    def generate_summary(self, symbol: str, data: Dict) -> str:
        """Generate summary for a cryptocurrency"""
        if not data:
            return f"## {symbol}\n**Data not available**\n"
        
        try:
            name = data.get('name', symbol)
            description = data.get('description', {}).get('en', '')
            # Limit description to first sentence
            description = description.split('.')[0][:200] + '...' if description else 'No description available'
            
            market_data = data.get('market_data', {})
            current_price = market_data.get('current_price', {}).get('usd', 0)
            market_cap = market_data.get('market_cap', {}).get('usd', 0)
            volume_24h = market_data.get('total_volume', {}).get('usd', 0)
            price_change_24h = market_data.get('price_change_percentage_24h', 0)
            price_change_7d = market_data.get('price_change_percentage_7d', 0)
            
            sentiment = self.calculate_sentiment(data)
            
            # Basic opportunities and risks
            opportunities = []
            risks = []
            
            if price_change_7d > 15:
                opportunities.append("Strong recent momentum")
            if market_cap > 1000000000:  # > $1B
                opportunities.append("Established market presence")
            if volume_24h > current_price * 1000000:  # High volume
                opportunities.append("High liquidity")
            
            if price_change_24h < -10:
                risks.append("Recent price volatility")
            if market_cap < 100000000:  # < $100M
                risks.append("Small market cap volatility")
            
            if not opportunities:
                opportunities.append("Market dependent")
            if not risks:
                risks.append("General market risk")
            
            summary = f"""## {symbol} - {name}

**Description:** {description}

**Price Data:**
- Current Price: {self.format_price(current_price)}
- 24h Change: {price_change_24h:.2f}%
- 7d Change: {price_change_7d:.2f}%
- Market Cap: ${market_cap:,.0f}
- 24h Volume: ${volume_24h:,.0f}

**Sentiment:** {sentiment}

**Opportunities:**
{chr(10).join(f"- {opp}" for opp in opportunities)}

**Risks:**
{chr(10).join(f"- {risk}" for risk in risks)}

---

"""
            return summary
        except Exception as e:
            return f"## {symbol}\n**Error generating summary: {e}**\n"
    
    def process_all_tickers(self, file_path: str, output_file: str = None):
        """Process all tickers from file and generate summaries"""
        tickers = self.parse_tickers_from_file(file_path)
        print(f"Found {len(tickers)} tickers to process")
        
        summaries = []
        summaries.append(f"# Crypto Ticker Analysis\n")
        summaries.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        
        for i, ticker in enumerate(tickers, 1):
            print(f"Processing {i}/{len(tickers)}: {ticker}")
            
            coin_id = self.get_coin_id_from_symbol(ticker)
            if not coin_id:
                summaries.append(f"## {ticker}\n**Coin not found on CoinGecko**\n---\n\n")
                continue
            
            data = self.get_coin_data(coin_id)
            summary = self.generate_summary(ticker, data)
            summaries.append(summary)
            
            # Rate limiting - CoinGecko allows 30 calls/minute for free tier
            # Use longer delays to avoid rate limits
            time.sleep(5)
        
        output_content = ''.join(summaries)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"Analysis saved to {output_file}")
        else:
            print(output_content)

def main():
    fetcher = CryptoDataFetcher()
    fetcher.process_all_tickers('crypto_tickers_checklist.md', 'crypto_analysis_report.md')

if __name__ == "__main__":
    main()