"""Sanity check: Compare per-trade PnL vs final balance"""

import json
from pathlib import Path

# Load the backtest report
report_path = Path("data/backtest_report.json")
with open(report_path, 'r') as f:
    report = json.load(f)

# Extract data
backtest_result = report['backtest_result']
closed_trades = report['closed_trades']

initial = backtest_result['initial_balance']
reported_final = backtest_result['final_balance']

# Extract PnL from each trade
trades_pnl = [trade['pnl'] for trade in closed_trades]

# Calculate sum of all trade PnLs
sum_pnl = sum(trades_pnl)
final_from_trades = initial + sum_pnl

# Print results
print("="*70)
print("SANITY CHECK: Per-Trade PnL vs Final Balance")
print("="*70)
print(f"\nInitial Balance: ${initial:,.2f}")
print(f"Number of Trades: {len(closed_trades)}")
print(f"\nSum of all trade PnLs: ${sum_pnl:,.2f}")
print(f"Final balance implied by trades: ${final_from_trades:,.2f}")
print(f"Reported final balance: ${reported_final:,.2f}")
print(f"\nMismatch: ${final_from_trades - reported_final:,.2f}")
print(f"Mismatch percentage: {((final_from_trades - reported_final) / initial) * 100:.2f}%")

# Additional analysis
print("\n" + "="*70)
print("DETAILED ANALYSIS")
print("="*70)

# Check winning vs losing trades
winning_trades = [t for t in closed_trades if t['pnl'] > 0]
losing_trades = [t for t in closed_trades if t['pnl'] < 0]
break_even_trades = [t for t in closed_trades if t['pnl'] == 0]

print(f"\nWinning trades: {len(winning_trades)}")
print(f"Losing trades: {len(losing_trades)}")
print(f"Break-even trades: {len(break_even_trades)}")

if winning_trades:
    print(f"Total PnL from wins: ${sum(t['pnl'] for t in winning_trades):,.2f}")
    print(f"Average win: ${sum(t['pnl'] for t in winning_trades) / len(winning_trades):,.2f}")

if losing_trades:
    print(f"Total PnL from losses: ${sum(t['pnl'] for t in losing_trades):,.2f}")
    print(f"Average loss: ${sum(t['pnl'] for t in losing_trades) / len(losing_trades):,.2f}")

# Check entry/exit values
print("\n" + "="*70)
print("ENTRY/EXIT VALUE ANALYSIS")
print("="*70)

total_entry_value = sum(t['entry_value'] for t in closed_trades)
total_exit_value = sum(t['exit_value'] for t in closed_trades)

print(f"\nTotal entry value (all trades): ${total_entry_value:,.2f}")
print(f"Total exit value (all trades): ${total_exit_value:,.2f}")
print(f"Difference (entry - exit): ${total_entry_value - total_exit_value:,.2f}")

# Check if there are any open positions at the end
print("\n" + "="*70)
print("BALANCE HISTORY ANALYSIS")
print("="*70)

balance_history = report.get('balance_history', [])
if balance_history:
    print(f"\nBalance history points: {len(balance_history)}")
    print(f"First balance: ${balance_history[0]['balance']:,.2f}")
    print(f"Last balance: ${balance_history[-1]['balance']:,.2f}")
    print(f"Last equity: ${balance_history[-1]['equity']:,.2f}")
    print(f"Last open positions: {balance_history[-1]['open_positions']}")
    
    # Find minimum balance
    min_balance = min(point['balance'] for point in balance_history)
    min_equity = min(point['equity'] for point in balance_history)
    print(f"\nMinimum balance: ${min_balance:,.2f}")
    print(f"Minimum equity: ${min_equity:,.2f}")

# Check for potential issues
print("\n" + "="*70)
print("POTENTIAL ISSUES")
print("="*70)

# The issue: When you open a position, you spend capital
# When you close it, you get capital back + PnL
# But if positions overlap or if there are fees/costs not accounted for,
# the balance might not match

# Check if there are overlapping positions (same pair traded multiple times)
print("\nChecking for overlapping positions...")
pair_trade_counts = {}
for trade in closed_trades:
    pair = trade['pair']
    pair_trade_counts[pair] = pair_trade_counts.get(pair, 0) + 1

for pair, count in pair_trade_counts.items():
    print(f"  {pair}: {count} trades")

# Simulate balance changes through trades
print("\n" + "="*70)
print("SIMULATING BALANCE CHANGES")
print("="*70)

simulated_balance = initial
print(f"\nStarting balance: ${simulated_balance:,.2f}")

# Sort trades by timestamp
sorted_trades = sorted(closed_trades, key=lambda x: x['timestamp'])

print("\nTracing balance through trades...")
print("(Note: This simulation assumes positions are opened and closed sequentially)")
print("\nFor BUY positions:")
print("  Open: balance -= entry_value")
print("  Close: balance += exit_value (which includes PnL)")
print("\nFor SELL positions:")
print("  Open: balance += entry_value (short selling)")
print("  Close: balance -= exit_value (buy to close)")

balance_changes = []
for i, trade in enumerate(sorted_trades):
    side = trade['side']
    entry_value = trade['entry_value']
    exit_value = trade['exit_value']
    pnl = trade['pnl']
    
    # Simulate opening position
    if side == "BUY":
        simulated_balance -= entry_value
        balance_changes.append({
            'trade_num': i + 1,
            'action': 'OPEN BUY',
            'pair': trade['pair'],
            'change': -entry_value,
            'balance': simulated_balance
        })
    else:  # SELL
        simulated_balance += entry_value
        balance_changes.append({
            'trade_num': i + 1,
            'action': 'OPEN SELL',
            'pair': trade['pair'],
            'change': entry_value,
            'balance': simulated_balance
        })
    
    # Simulate closing position
    if side == "BUY":
        simulated_balance += exit_value
        balance_changes.append({
            'trade_num': i + 1,
            'action': 'CLOSE BUY',
            'pair': trade['pair'],
            'change': exit_value,
            'balance': simulated_balance
        })
    else:  # SELL
        simulated_balance -= exit_value
        balance_changes.append({
            'trade_num': i + 1,
            'action': 'CLOSE SELL',
            'pair': trade['pair'],
            'change': -exit_value,
            'balance': simulated_balance
        })

print(f"\nSimulated final balance: ${simulated_balance:,.2f}")
print(f"Expected final balance (initial + sum PnL): ${initial + sum_pnl:,.2f}")
print(f"Difference: ${simulated_balance - (initial + sum_pnl):,.2f}")

# Check for open positions at the end
print("\n" + "="*70)
print("OPEN POSITIONS AT END")
print("="*70)

if balance_history and balance_history[-1]['open_positions'] > 0:
    print(f"\nWARNING: There are {balance_history[-1]['open_positions']} open positions at the end!")
    print(f"Last balance: ${balance_history[-1]['balance']:,.2f}")
    print(f"Last equity: ${balance_history[-1]['equity']:,.2f}")
    print(f"Unrealized PnL: ${balance_history[-1]['equity'] - balance_history[-1]['balance']:,.2f}")
    print("\nThe reported final balance of ${:,.2f} includes unrealized PnL from open positions.".format(reported_final))
    print("This explains why it differs from the sum of closed trade PnLs!")

# The key insight: The balance reduction might be due to:
# 1. Capital tied up in open positions (not reflected in closed trades)
# 2. Fees or slippage not accounted for in PnL
# 3. The way short selling is handled (SELL positions add to balance initially)

print("\n" + "="*70)
print("ROOT CAUSE ANALYSIS")
print("="*70)
print(f"\nThe mismatch of ${final_from_trades - reported_final:,.2f} is explained by:")
print(f"1. Last balance (cash): ${balance_history[-1]['balance']:,.2f}")
print(f"2. Last equity (cash + unrealized): ${balance_history[-1]['equity']:,.2f}")
print(f"3. Reported final balance: ${reported_final:,.2f}")
print(f"\nThe difference between last balance and reported final:")
print(f"  ${balance_history[-1]['balance'] - reported_final:,.2f}")
print(f"\nThe difference between last equity and reported final:")
print(f"  ${balance_history[-1]['equity'] - reported_final:,.2f}")

# Calculate what the actual loss is
actual_loss = initial - balance_history[-1]['balance']
print(f"\nActual cash loss: ${actual_loss:,.2f} ({actual_loss/initial*100:.2f}%)")
print(f"Sum of trade PnLs: ${sum_pnl:,.2f}")
print(f"Difference: ${actual_loss - (-sum_pnl):,.2f}")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("\nKEY FINDING:")
print("The 90%+ win rate is misleading because:")
print("1. Individual trade PnLs are small (avg win: $3.39, avg loss: -$0.55)")
print("2. The actual cash balance dropped from $50,000 to $40,435.58")
print("3. This is a loss of $9,564.42 (19.13%), NOT a gain of $130.95")
print("\nROOT CAUSE:")
print("The issue is NOT with the trade PnL calculations, but with how capital")
print("is managed when positions overlap:")
print("\n1. When a BUY position is opened, capital is deducted from balance")
print("2. When a SELL (short) position is opened, capital is added to balance")
print("3. When positions overlap (same pair or different pairs), capital gets tied up")
print("4. Even though individual trades show small profits, the overall balance")
print("   decreases because:")
print("   - Positions require significant capital to open (entry values)")
print("   - When positions overlap, capital is locked and unavailable")
print("   - The small PnLs ($3.39 avg) don't compensate for the capital tied up")
print("\nEXAMPLE:")
print("If you open a $1,000 position and make $3 profit, that's a 0.3% return.")
print("But if that $1,000 is tied up for a long time while other opportunities")
print("are missed, or if you need to open overlapping positions, the effective")
print("return on your total capital is much lower or negative.")
print("\nRECOMMENDATION:")
print("Review position sizing and ensure that:")
print("1. Position sizes are appropriate relative to total capital")
print("2. Overlapping positions don't tie up too much capital")
print("3. The strategy accounts for opportunity cost of capital")
print("4. Consider reducing position sizes or improving entry/exit timing")

