#!/usr/bin/env python3
"""
Crypto Batch Data Fetcher - Efficient version with caching and batch processing
"""

import requests
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional

class CryptoBatchFetcher:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CryptoBatchFetcher/1.0'
        })
        self.coin_list_cache = None
        
    def get_coin_list(self) -> List[Dict]:
        """Get and cache the full coin list"""
        if self.coin_list_cache is None:
            try:
                print("Fetching coin list from CoinGecko...")
                url = f"{self.base_url}/coins/list"
                response = self.session.get(url)
                response.raise_for_status()
                self.coin_list_cache = response.json()
                print(f"Cached {len(self.coin_list_cache)} coins")
            except Exception as e:
                print(f"Error fetching coin list: {e}")
                self.coin_list_cache = []
        return self.coin_list_cache
    
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
    
    def get_coin_ids_from_symbols(self, symbols: List[str]) -> Dict[str, str]:
        """Get coin IDs for multiple symbols at once"""
        coin_list = self.get_coin_list()
        symbol_to_id = {}
        
        for symbol in symbols:
            for coin in coin_list:
                if coin['symbol'].upper() == symbol.upper():
                    symbol_to_id[symbol] = coin['id']
                    break
        
        return symbol_to_id
    
    def get_coins_data_batch(self, coin_ids: List[str]) -> Dict[str, Dict]:
        """Fetch data for multiple coins using the /coins/markets endpoint"""
        try:
            # CoinGecko markets endpoint can handle multiple coins
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ','.join(coin_ids),
                'order': 'market_cap_desc',
                'per_page': '250',
                'page': '1',
                'sparkline': 'false',
                'price_change_percentage': '24h,7d'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            market_data = response.json()
            
            # Convert to dict keyed by coin ID
            result = {}
            for coin in market_data:
                result[coin['id']] = coin
            
            return result
        except Exception as e:
            print(f"Error fetching batch market data: {e}")
            return {}
    
    def format_price(self, price: float) -> str:
        """Format price for display"""
        if price is None:
            return "N/A"
        if price >= 1:
            return f"${price:,.2f}"
        elif price >= 0.01:
            return f"${price:.4f}"
        else:
            return f"${price:.8f}"
    
    def calculate_sentiment(self, data: Dict) -> str:
        """Calculate basic sentiment from market data"""
        try:
            price_change_24h = data.get('price_change_percentage_24h', 0) or 0
            price_change_7d = data.get('price_change_percentage_7d', 0) or 0
            
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
    
    def get_basic_project_info(self, coin_id: str) -> str:
        """Get basic project description (with rate limiting)"""
        try:
            url = f"{self.base_url}/coins/{coin_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'false',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            description = data.get('description', {}).get('en', '')
            if description:
                # Get first sentence, limit to 200 chars
                first_sentence = description.split('.')[0][:200]
                return first_sentence + '...' if len(first_sentence) == 200 else first_sentence + '.'
            return "No description available"
        except Exception as e:
            print(f"Error getting description for {coin_id}: {e}")
            return "Description unavailable"
    
    def generate_summary(self, symbol: str, coin_id: str, market_data: Dict, description: str = None) -> str:
        """Generate summary for a cryptocurrency"""
        if not market_data:
            return f"## {symbol}\n**Market data not available**\n---\n\n"
        
        try:
            name = market_data.get('name', symbol)
            current_price = market_data.get('current_price', 0)
            market_cap = market_data.get('market_cap', 0)
            volume_24h = market_data.get('total_volume', 0)
            price_change_24h = market_data.get('price_change_percentage_24h', 0) or 0
            price_change_7d = market_data.get('price_change_percentage_7d', 0) or 0
            market_cap_rank = market_data.get('market_cap_rank', 'N/A')
            
            sentiment = self.calculate_sentiment(market_data)
            
            # Basic opportunities and risks based on data
            opportunities = []
            risks = []
            
            if price_change_7d > 15:
                opportunities.append("Strong recent momentum")
            if market_cap and market_cap > 1000000000:  # > $1B
                opportunities.append("Established market presence")
            if market_cap_rank and isinstance(market_cap_rank, int) and market_cap_rank <= 100:
                opportunities.append("Top 100 market cap")
            if volume_24h and current_price and volume_24h > (current_price * 1000000):
                opportunities.append("High trading volume")
            
            if price_change_24h < -10:
                risks.append("Recent price volatility")
            if market_cap and market_cap < 100000000:  # < $100M
                risks.append("Small market cap - higher volatility")
            if market_cap_rank and isinstance(market_cap_rank, int) and market_cap_rank > 500:
                risks.append("Low market cap ranking")
            
            if not opportunities:
                opportunities.append("Market dependent performance")
            if not risks:
                risks.append("General crypto market risk")
            
            desc_text = description or "Project information not available"
            
            summary = f"""## {symbol} - {name}

**Market Cap Rank:** #{market_cap_rank}

**Description:** {desc_text}

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
            return f"## {symbol}\n**Error generating summary: {e}**\n---\n\n"
    
    def process_batch(self, symbols: List[str], batch_size: int = 25) -> List[str]:
        """Process symbols in batches"""
        all_summaries = []
        
        # Get coin IDs for all symbols
        print("Mapping symbols to coin IDs...")
        symbol_to_id = self.get_coin_ids_from_symbols(symbols)
        found_symbols = list(symbol_to_id.keys())
        not_found = [s for s in symbols if s not in found_symbols]
        
        print(f"Found {len(found_symbols)} symbols on CoinGecko")
        print(f"Not found: {not_found}")
        
        # Process in batches
        for i in range(0, len(found_symbols), batch_size):
            batch_symbols = found_symbols[i:i+batch_size]
            batch_coin_ids = [symbol_to_id[s] for s in batch_symbols]
            
            print(f"Processing batch {i//batch_size + 1}: {batch_symbols}")
            
            # Get market data for batch
            market_data = self.get_coins_data_batch(batch_coin_ids)
            
            # Generate summaries for batch
            for symbol in batch_symbols:
                coin_id = symbol_to_id[symbol]
                coin_market_data = market_data.get(coin_id, {})
                
                if coin_market_data:
                    summary = self.generate_summary(symbol, coin_id, coin_market_data)
                    all_summaries.append(summary)
                else:
                    all_summaries.append(f"## {symbol}\n**Market data not available**\n---\n\n")
            
            # Rate limiting between batches
            if i + batch_size < len(found_symbols):
                print("Waiting 10 seconds before next batch...")
                time.sleep(10)
        
        # Add not found symbols
        for symbol in not_found:
            all_summaries.append(f"## {symbol}\n**Coin not found on CoinGecko**\n---\n\n")
        
        return all_summaries
    
    def process_all_tickers(self, file_path: str, output_file: str = None):
        """Process all tickers from file"""
        tickers = self.parse_tickers_from_file(file_path)
        print(f"Found {len(tickers)} tickers to process")
        
        header = f"# Crypto Ticker Analysis\n"
        header += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        
        summaries = self.process_batch(tickers)
        
        output_content = header + ''.join(summaries)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"Analysis saved to {output_file}")
        else:
            print(output_content)

def main():
    fetcher = CryptoBatchFetcher()
    fetcher.process_all_tickers('crypto_tickers_checklist.md', 'crypto_analysis_report.md')

if __name__ == "__main__":
    main()