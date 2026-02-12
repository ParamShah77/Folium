import numpy as np
import pandas as pd
import hashlib
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

print("="*60)
print("SYNTHETIC DATA GENERATION FOR BEHAVIORAL FINANCE PROJECT")
print("="*60)

# ==============================================================================
# STEP 1: Generate Synthetic User Profiles
# ==============================================================================
print("\n[STEP 1] Generating Synthetic User Profiles...")

n_users = 1000

# Generate user data with realistic distributions
data = {
    "user_id": range(n_users),
    "age": np.random.randint(25, 65, n_users),
    "monthly_income": np.random.lognormal(mean=10, sigma=0.5, size=n_users),
    "expense_ratio": np.random.uniform(0.4, 0.8, n_users),
    "risk_tolerance": np.random.beta(2, 5, n_users),
    "investment_horizon": np.random.randint(10, 30, n_users)
}

df_users = pd.DataFrame(data)
df_users["monthly_expense"] = df_users["monthly_income"] * df_users["expense_ratio"]

# Assign investment goals based on age and horizon
def assign_goal(row):
    if row['age'] > 50 or row['investment_horizon'] > 20:
        return 'retirement'
    else:
        return 'wealth growth'

df_users['goal'] = df_users.apply(assign_goal, axis=1)

# Reorder columns
df_users = df_users[['user_id', 'age', 'monthly_income', 'monthly_expense', 
                     'risk_tolerance', 'investment_horizon', 'goal']]

# Save to CSV
df_users.to_csv('synthetic_users.csv', index=False)
print(f"✅ Created: synthetic_users.csv ({len(df_users)} users)")
print(f"   Sample stats: Avg income=${df_users['monthly_income'].mean():.2f}, "
      f"Avg risk={df_users['risk_tolerance'].mean():.3f}")

# ==============================================================================
# STEP 2: Generate Synthetic Behavioral Bias Parameters
# ==============================================================================
print("\n[STEP 2] Generating Synthetic Behavioral Bias Parameters...")

bias_data = {
    "user_id": df_users["user_id"],
    "disposition_strength": np.random.beta(3, 2, n_users),  # Tendency to sell winners early
    "loss_aversion": np.random.uniform(1, 3, n_users),      # Loss aversion coefficient (λ)
    "herd_sensitivity": np.random.beta(2, 4, n_users)       # Tendency to follow crowd
}

df_bias = pd.DataFrame(bias_data)
df_bias.to_csv('synthetic_bias_profiles.csv', index=False)
print(f"✅ Created: synthetic_bias_profiles.csv ({len(df_bias)} profiles)")
print(f"   Avg disposition={df_bias['disposition_strength'].mean():.3f}, "
      f"Avg loss_aversion={df_bias['loss_aversion'].mean():.3f}")

# ==============================================================================
# STEP 3: Generate Synthetic Market & Long-Horizon Paths
# ==============================================================================
print("\n[STEP 3] Generating Synthetic Market Paths (30-year simulation)...")

years = 30
n_paths = 10000

# Geometric Brownian Motion parameters
mu = 0.10       # Expected annual return (10%)
sigma = 0.20    # Volatility (20%)

# Generate returns for each path and year
market_returns = np.random.normal(mu, sigma, (n_paths, years))

# Add regime switches (inject crashes at certain years)
crash_years = [10, 20]  # Market crashes at years 10 and 20
for crash_year in crash_years:
    crash_magnitudes = np.random.uniform(0.3, 0.5, n_paths)
    market_returns[:, crash_year] -= crash_magnitudes

# Save as numpy array
np.save('synthetic_market_paths.npy', market_returns)
print(f"✅ Created: synthetic_market_paths.npy ({n_paths} paths × {years} years)")
print(f"   Avg return={market_returns.mean():.3f}, Volatility={market_returns.std():.3f}")

# Create a summary dataframe for visualization (average path)
avg_returns = market_returns.mean(axis=0)
market_summary = pd.DataFrame({
    'year': range(years),
    'avg_market_return': avg_returns,
    'regime': ['bull' if r > 0.05 else ('crash' if r < -0.15 else 'bear') for r in avg_returns]
})
market_summary.to_csv('synthetic_market_summary.csv', index=False)
print(f"   Bonus: synthetic_market_summary.csv (average path summary)")

# ==============================================================================
# STEP 4: Generate Synthetic Decisions (Decision-Time Data)
# ==============================================================================
print("\n[STEP 4] Generating Synthetic Decisions...")

# Generate multiple decision moments per user
n_decisions_per_user = 5
n_total_decisions = n_users * n_decisions_per_user

decisions_data = []

for user_idx in range(n_users):
    user_id = df_users.loc[user_idx, 'user_id']
    disposition = df_bias.loc[user_idx, 'disposition_strength']
    loss_aversion = df_bias.loc[user_idx, 'loss_aversion']
    herd_sens = df_bias.loc[user_idx, 'herd_sensitivity']
    
    for decision_num in range(n_decisions_per_user):
        # Simulate decision context
        market_return_recent = np.random.normal(0.01, 0.05)  # Recent monthly return
        unrealized_gain_loss = np.random.normal(0, 0.15)      # Unrealized P&L %
        crowd_action_ratio = np.random.uniform(0, 1)          # % of crowd selling
        
        # Decision logic based on biases
        decision = "hold"
        bias_present = "no"
        bias_type = "none"
        
        # Disposition Effect: Sell winners too early, hold losers too long
        if disposition > 0.6 and unrealized_gain_loss > 0.05:
            decision = "sell"
            bias_present = "yes"
            bias_type = "disposition"
        elif disposition > 0.6 and unrealized_gain_loss < -0.05:
            decision = "hold"
            bias_present = "yes"
            bias_type = "disposition"
        
        # Loss Aversion: Strong aversion causes premature selling during losses
        elif loss_aversion > 2.5 and unrealized_gain_loss < -0.10:
            decision = "sell"
            bias_present = "yes"
            bias_type = "loss_aversion"
        
        # Herd Behavior: Follow crowd
        elif herd_sens > 0.7 and crowd_action_ratio > 0.7:
            decision = "sell"
            bias_present = "yes"
            bias_type = "herd"
        
        # Rational decision
        else:
            if unrealized_gain_loss < -0.20 or market_return_recent < -0.05:
                decision = "sell"
            else:
                decision = "hold"
            bias_type = "rational"
        
        decisions_data.append({
            'decision_id': len(decisions_data),
            'user_id': user_id,
            'market_return_recent': market_return_recent,
            'unrealized_gain_loss': unrealized_gain_loss,
            'crowd_action_ratio': crowd_action_ratio,
            'decision': decision,
            'bias_present': bias_present,
            'bias_type': bias_type
        })

df_decisions = pd.DataFrame(decisions_data)
df_decisions.to_csv('synthetic_decisions.csv', index=False)
print(f"✅ Created: synthetic_decisions.csv ({len(df_decisions)} decisions)")
print(f"   Bias present: {(df_decisions['bias_present']=='yes').sum()} decisions "
      f"({100*(df_decisions['bias_present']=='yes').sum()/len(df_decisions):.1f}%)")

# ==============================================================================
# STEP 5: Generate Synthetic Counterfactuals
# ==============================================================================
print("\n[STEP 5] Generating Synthetic Counterfactuals...")

counterfactuals_data = []

for idx, row in df_decisions.iterrows():
    decision_id = row['decision_id']
    user_id = row['user_id']
    actual_decision = row['decision']
    unrealized_gl = row['unrealized_gain_loss']
    
    # Get user's investment horizon
    user_horizon = df_users.loc[df_users['user_id']==user_id, 'investment_horizon'].values[0]
    
    # Simulate future returns for this specific decision horizon (use 20 years for comparison)
    horizon = min(20, user_horizon)
    future_returns = market_returns[np.random.randint(0, n_paths), :horizon]
    
    initial_wealth = 10000  # Starting amount
    
    # Scenario A: User HOLDS
    wealth_hold = initial_wealth * (1 + unrealized_gl) * np.prod(1 + future_returns)
    
    # Scenario B: User SELLS (misses future growth, reinvests at lower rate)
    wealth_sell = initial_wealth * (1 + unrealized_gl * 0.9) * np.prod(1 + future_returns * 0.7)
    
    # Store both counterfactuals
    counterfactuals_data.append({
        'decision_id': decision_id,
        'user_id': user_id,
        'action': 'hold',
        'final_wealth_20y': wealth_hold,
        'horizon_years': horizon
    })
    
    counterfactuals_data.append({
        'decision_id': decision_id,
        'user_id': user_id,
        'action': 'sell',
        'final_wealth_20y': wealth_sell,
        'horizon_years': horizon
    })

df_counterfactuals = pd.DataFrame(counterfactuals_data)
df_counterfactuals.to_csv('synthetic_counterfactuals.csv', index=False)
print(f"✅ Created: synthetic_counterfactuals.csv ({len(df_counterfactuals)} scenarios)")
print(f"   Avg wealth (hold)=${df_counterfactuals[df_counterfactuals['action']=='hold']['final_wealth_20y'].mean():.2f}")
print(f"   Avg wealth (sell)=${df_counterfactuals[df_counterfactuals['action']=='sell']['final_wealth_20y'].mean():.2f}")

# ==============================================================================
# STEP 6: Generate Synthetic Audit Logs
# ==============================================================================
print("\n[STEP 6] Generating Synthetic Audit Logs...")

audit_logs = []
base_time = datetime.now()

for idx, row in df_decisions.iterrows():
    decision_id = row['decision_id']
    
    # Create hashes for blockchain-like audit trail
    input_data = {
        'user_id': row['user_id'],
        'market_return': row['market_return_recent'],
        'unrealized_gl': row['unrealized_gain_loss'],
        'crowd_ratio': row['crowd_action_ratio']
    }
    
    decision_data = {
        'decision_id': decision_id,
        'decision': row['decision'],
        'bias_type': row['bias_type']
    }
    
    # Get counterfactual outcomes for this decision
    cf = df_counterfactuals[df_counterfactuals['decision_id']==decision_id]
    explanation_data = {
        'decision': row['decision'],
        'bias_present': row['bias_present'],
        'expected_wealth_hold': cf[cf['action']=='hold']['final_wealth_20y'].values[0] if len(cf)>0 else 0,
        'expected_wealth_sell': cf[cf['action']=='sell']['final_wealth_20y'].values[0] if len(cf)>0 else 0
    }
    
    # Generate SHA-256 hashes
    input_hash = hashlib.sha256(str(input_data).encode()).hexdigest()
    decision_hash = hashlib.sha256(str(decision_data).encode()).hexdigest()
    explanation_hash = hashlib.sha256(str(explanation_data).encode()).hexdigest()
    
    # Timestamp
    timestamp = base_time + timedelta(seconds=idx*10)
    
    audit_logs.append({
        'decision_id': decision_id,
        'user_id': row['user_id'],
        'input_hash': input_hash,
        'decision_hash': decision_hash,
        'explanation_hash': explanation_hash,
        'timestamp': timestamp.isoformat(),
        'bias_detected': row['bias_present']
    })

df_audit = pd.DataFrame(audit_logs)
df_audit.to_csv('synthetic_audit_logs.csv', index=False)
print(f"✅ Created: synthetic_audit_logs.csv ({len(df_audit)} log entries)")
print(f"   All entries cryptographically hashed for audit trail")

# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "="*60)
print("GENERATION COMPLETE!")
print("="*60)
print("\n📊 FINAL DATASETS CREATED:")
print(f"   1. synthetic_users.csv              → {len(df_users):,} users")
print(f"   2. synthetic_bias_profiles.csv      → {len(df_bias):,} profiles")
print(f"   3. synthetic_market_paths.npy       → {n_paths:,} paths × {years} years")
print(f"   4. synthetic_market_summary.csv     → Average market path")
print(f"   5. synthetic_decisions.csv          → {len(df_decisions):,} decisions")
print(f"   6. synthetic_counterfactuals.csv    → {len(df_counterfactuals):,} scenarios")
print(f"   7. synthetic_audit_logs.csv         → {len(df_audit):,} audit entries")

print("\n🎯 KEY INSIGHTS:")
print(f"   • {(df_decisions['bias_present']=='yes').sum()} biased decisions detected")
print(f"   • {len(df_decisions[df_decisions['bias_type']=='disposition'])} disposition effect cases")
print(f"   • {len(df_decisions[df_decisions['bias_type']=='loss_aversion'])} loss aversion cases")
print(f"   • {len(df_decisions[df_decisions['bias_type']=='herd'])} herd behavior cases")

print("\n💡 VIVA EXPLANATION:")
print("   'Synthetic datasets were generated using controlled stochastic")
print("   processes and behavioral rules to provide ground truth for causality,")
print("   bias detection, counterfactual reasoning, and long-horizon evaluation,")
print("   which are not observable in real-world financial datasets.'")
print("\n" + "="*60)
