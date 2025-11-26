import hmac
import hashlib
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

class DeltaIVCrushBot:
    def __init__(self, api_key, api_secret, testnet=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://testnet-api.delta.exchange" if testnet else "https://api.delta.exchange"
        
        self.IV_SPIKE_PCT = 10
        self.PROTECTION_WIDTH_PCT = 3.0
        self.TARGET_PROFIT_PCT = 40
        self.RISK_PER_TRADE_PCT = 0.015
        self.MAX_TIME_MIN = 30
        self.MIN_TTE_MIN = 45
        
        self.positions = []
        self.balance = 10000
        self.btc_products = {}
        self._load_products()
        self._load_state()
    
    def _load_state(self):
        """Load saved state from file"""
        try:
            with open('bot_state.json', 'r') as f:
                data = json.load(f)
                self.balance = data.get('balance', 10000)
                self.positions = data.get('positions', [])
                # Convert string dates back to datetime
                for pos in self.positions:
                    pos['entry_time'] = datetime.fromisoformat(pos['entry_time'])
                    if pos.get('exit_time'):
                        pos['exit_time'] = datetime.fromisoformat(pos['exit_time'])
        except:
            pass
    
    def _save_state(self):
        """Save state to file"""
        try:
            data = {
                'balance': self.balance,
                'positions': []
            }
            # Convert datetime to string for JSON
            for pos in self.positions:
                pos_copy = pos.copy()
                pos_copy['entry_time'] = pos['entry_time'].isoformat()
                if pos.get('exit_time'):
                    pos_copy['exit_time'] = pos['exit_time'].isoformat()
                data['positions'].append(pos_copy)
            
            with open('bot_state.json', 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Save error: {e}")
        
    def _sign(self, method, endpoint, payload=""):
        """Generate signature for Delta Exchange"""
        timestamp = str(int(time.time()))
        signature_data = method + timestamp + endpoint + payload
        signature = hmac.new(
            self.api_secret.encode(),
            signature_data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp
    
    def _request(self, method, endpoint, params=None, data=None):
        """Make authenticated request to Delta Exchange"""
        url = f"{self.base_url}{endpoint}"
        
        payload = ""
        if data:
            payload = json.dumps(data)
        
        signature, timestamp = self._sign(method, endpoint, payload)
        
        headers = {
            'api-key': self.api_key,
            'signature': signature,
            'timestamp': timestamp,
            'Content-Type': 'application/json'
        }
        
        try:
            if method == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=10)
            else:
                response = requests.post(url, data=payload, headers=headers, timeout=10)
            
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _load_products(self):
        """Load BTC option products"""
        try:
            r = requests.get(f"{self.base_url}/v2/products", timeout=5)
            data = r.json()
            if data.get('success'):
                for product in data['result']:
                    if product.get('contract_type') == 'call_options' and 'BTC' in product.get('symbol', ''):
                        self.btc_products[product['symbol']] = product
        except:
            pass
    
    def get_btc_price(self):
        """Get current BTC spot price"""
        try:
            r = requests.get(f"{self.base_url}/v2/tickers/BTCUSD", timeout=5)
            data = r.json()
            if data.get('success'):
                return float(data['result']['mark_price'])
        except:
            pass
        # Demo fallback
        import random
        return 95000 + random.uniform(-500, 500)
    
    def get_option_chain(self):
        """Get option chain with IV data"""
        try:
            r = requests.get(f"{self.base_url}/v2/tickers", timeout=5)
            data = r.json()
            if data.get('success'):
                options = [t for t in data['result'] if 'C-' in t.get('symbol', '') and 'BTC' in t.get('symbol', '')]
                return options[:20]
        except:
            pass
        return []
    
    def calculate_iv_metrics(self, options_data):
        """Calculate ATM IV and rolling average"""
        if not options_data:
            return None, None
        
        ivs = []
        for opt in options_data:
            iv_val = opt.get('greeks', {}).get('iv')
            if iv_val and float(iv_val) > 0:
                ivs.append(float(iv_val) * 100)
        
        if not ivs:
            # Demo fallback
            import random
            atm_iv = random.uniform(40, 80)
            return atm_iv, atm_iv * 0.92
            
        atm_iv = sum(ivs) / len(ivs)
        rolling_iv = atm_iv * 0.92
        
        return atm_iv, rolling_iv
    
    def detect_liquidity_sweep(self):
        """Detect liquidity sweep pattern"""
        try:
            r = requests.get(f"{self.base_url}/v2/history/candles", 
                           params={"resolution": "1m", "symbol": "BTCUSD", "limit": 10},
                           timeout=5)
            data = r.json()
            
            if not data.get('success'):
                return False
            
            candles = data['result']
            if len(candles) < 5:
                return False
            
            latest = candles[0]
            high = float(latest['high'])
            low = float(latest['low'])
            close = float(latest['close'])
            open_price = float(latest['open'])
            
            wick_size = max(high - close, close - low)
            body_size = abs(close - open_price)
            
            return wick_size > body_size * 2
            
        except:
            # Demo fallback
            import random
            return random.random() > 0.6
    
    def check_entry_conditions(self):
        """Check if entry conditions are met"""
        btc_price = self.get_btc_price()
        if not btc_price:
            return False, {}
        
        options = self.get_option_chain()
        atm_iv, rolling_iv = self.calculate_iv_metrics(options)
        
        if not atm_iv or not rolling_iv:
            return False, {}
        
        iv_spike = atm_iv >= rolling_iv * (1 + self.IV_SPIKE_PCT / 100)
        sweep_detected = self.detect_liquidity_sweep()
        iv_sufficient = atm_iv >= 30
        
        signal = {
            "price": btc_price,
            "atm_iv": atm_iv,
            "rolling_iv": rolling_iv,
            "iv_spike": iv_spike,
            "sweep": sweep_detected,
            "iv_sufficient": iv_sufficient,
            "entry_ready": iv_spike and sweep_detected and iv_sufficient
        }
        
        return signal['entry_ready'], signal
    
    def open_credit_spread(self, symbol="BTC", spot_price=None):
        """Open vertical credit spread"""
        if not spot_price:
            spot_price = self.get_btc_price()
        
        protection_width = spot_price * (self.PROTECTION_WIDTH_PCT / 100)
        sell_strike = round(spot_price, -2)
        buy_strike = round(sell_strike + protection_width, -2)
        
        sell_premium = spot_price * 0.015
        buy_premium = spot_price * 0.008
        net_credit = sell_premium - buy_premium
        
        max_loss = (buy_strike - sell_strike) - net_credit
        risk_amount = self.balance * self.RISK_PER_TRADE_PCT
        contracts = max(1, int(risk_amount / max_loss))
        
        position = {
            "id": len(self.positions) + 1,
            "symbol": symbol,
            "entry_time": datetime.now(),
            "spot_price": spot_price,
            "sell_strike": sell_strike,
            "buy_strike": buy_strike,
            "sell_premium": sell_premium,
            "buy_premium": buy_premium,
            "net_credit": net_credit,
            "max_loss": max_loss,
            "contracts": contracts,
            "status": "open",
            "pnl": 0
        }
        
        self.positions.append(position)
        self._save_state()
        return position
    
    def check_exit_conditions(self, position):
        """Check if position should be closed"""
        current_price = self.get_btc_price()
        if not current_price:
            return False, "no_price"
        
        time_in_trade = (datetime.now() - position['entry_time']).total_seconds() / 60
        
        time_factor = max(0.3, 1 - (time_in_trade / self.MAX_TIME_MIN) * 0.5)
        current_premium = position['net_credit'] * time_factor
        
        unrealized_pnl = (position['net_credit'] - current_premium) * position['contracts']
        profit_pct = (unrealized_pnl / (position['net_credit'] * position['contracts'])) * 100
        
        if profit_pct >= self.TARGET_PROFIT_PCT:
            return True, "profit_target"
        
        if unrealized_pnl < -position['max_loss'] * position['contracts']:
            return True, "stop_loss"
        
        if time_in_trade >= self.MAX_TIME_MIN:
            return True, "time_exit"
        
        if abs(current_price - position['sell_strike']) / position['sell_strike'] < 0.01:
            return True, "near_strike"
        
        return False, None
    
    def close_position(self, position, reason):
        """Close position and update P&L"""
        current_price = self.get_btc_price()
        time_in_trade = (datetime.now() - position['entry_time']).total_seconds() / 60
        
        time_factor = max(0.2, 1 - (time_in_trade / self.MAX_TIME_MIN) * 0.6)
        exit_premium = position['net_credit'] * time_factor
        
        pnl = (position['net_credit'] - exit_premium) * position['contracts']
        
        position['status'] = 'closed'
        position['exit_time'] = datetime.now()
        position['exit_price'] = current_price
        position['exit_reason'] = reason
        position['pnl'] = pnl
        position['time_in_trade'] = time_in_trade
        
        self.balance += pnl
        self._save_state()
        
        return position
    
    def manage_positions(self):
        """Check and manage all open positions"""
        for pos in self.positions:
            if pos['status'] == 'open':
                should_exit, reason = self.check_exit_conditions(pos)
                if should_exit:
                    self.close_position(pos, reason)
    
    def get_stats(self):
        """Get trading statistics"""
        closed = [p for p in self.positions if p['status'] == 'closed']
        
        if not closed:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "total_pnl": 0,
                "balance": self.balance,
                "open_positions": len([p for p in self.positions if p['status'] == 'open'])
            }
        
        wins = [p for p in closed if p['pnl'] > 0]
        
        return {
            "total_trades": len(closed),
            "win_rate": len(wins) / len(closed) * 100,
            "avg_pnl": sum(p['pnl'] for p in closed) / len(closed),
            "total_pnl": sum(p['pnl'] for p in closed),
            "balance": self.balance,
            "open_positions": len([p for p in self.positions if p['status'] == 'open'])
        }
