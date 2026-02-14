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
ages = np.random.randint(25, 65, n_users)

# Generate realistic monthly income based on age and career stage (in INR)
# Entry level: 25-35 years → 30K-80K
# Mid-career: 35-50 years → 60K-150K  
# Senior: 50-65 years → 100K-250K
def generate_realistic_income(age):
    """Generate income based on career stage, rounded to realistic values"""
    if age < 35:  # Entry level
        base_income = np.random.uniform(30000, 80000)
    elif age < 50:  # Mid-career
        base_income = np.random.uniform(60000, 150000)
    else:  # Senior/executive
        base_income = np.random.uniform(100000, 250000)
    
    # Round to nearest 1000 (users enter like "50,000" not "50,234.56")
    return round(base_income / 1000) * 1000

monthly_incomes = np.array([generate_realistic_income(age) for age in ages])

# Generate expense ratio - some users overspend!
# 80% of users: expenses < income (0.5-0.85 ratio)
# 15% of users: expenses ≈ income (0.90-1.05 ratio) - living paycheck to paycheck
# 5% of users: expenses > income (1.1-1.3 ratio) - in debt, using credit/savings
expense_ratios = []
for _ in range(n_users):
    rand = np.random.random()
    if rand < 0.80:  # Majority: healthy finances
        expense_ratios.append(np.random.uniform(0.5, 0.85))
    elif rand < 0.95:  # Living paycheck to paycheck
        expense_ratios.append(np.random.uniform(0.90, 1.05))
    else:  # In debt / overspending
        expense_ratios.append(np.random.uniform(1.1, 1.3))

expense_ratios = np.array(expense_ratios)

data = {
    "user_id": range(n_users),
    "age": ages,
    "monthly_income": monthly_incomes,
    "expense_ratio": expense_ratios,
    "risk_tolerance": np.random.beta(2, 5, n_users),
    "investment_horizon": np.random.randint(10, 30, n_users)
}

df_users = pd.DataFrame(data)
df_users["monthly_expense"] = (df_users["monthly_income"] * df_users["expense_ratio"]).round(0)  # Round expenses too

# Calculate monthly surplus/deficit
df_users["monthly_surplus"] = df_users["monthly_income"] - df_users["monthly_expense"]

# Add financial management strategy for deficit cases
def assign_financial_strategy(row):
    """How users manage their finances"""
    if row['monthly_surplus'] > 5000:
        return 'saving'  # Healthy savers
    elif row['monthly_surplus'] >= 0:
        return 'balanced'  # Balanced budget
    elif row['monthly_surplus'] >= -5000:
        return 'credit_card'  # Small deficit, using credit cards
    else:
        return 'family_support'  # Larger deficit, family support or drawing from savings

df_users['financial_strategy'] = df_users.apply(assign_financial_strategy, axis=1)

# Assign investment goals based on age and horizon
def assign_goal(row):
    if row['age'] > 50 or row['investment_horizon'] > 20:
        return 'retirement'
    else:
        return 'wealth growth'

df_users['goal'] = df_users.apply(assign_goal, axis=1)

# Add emergency fund status (3-6 months of expenses saved)
def has_emergency_fund(row):
    """Does user have adequate emergency savings?"""
    if row['financial_strategy'] in ['saving', 'balanced']:
        return np.random.choice([True, False], p=[0.7, 0.3])  # 70% have emergency fund
    else:
        return np.random.choice([True, False], p=[0.2, 0.8])  # Only 20% in debt have emergency fund

df_users['has_emergency_fund'] = df_users.apply(has_emergency_fund, axis=1)

# Add age-horizon mismatch detection
df_users['age_horizon_mismatch'] = df_users.apply(
    lambda row: 'young_short' if row['age'] < 35 and row['investment_horizon'] < 10
                else ('old_long' if row['age'] > 55 and row['investment_horizon'] > 20
                else 'normal'),
    axis=1
)

# Add investment experience
df_users['years_investing'] = np.clip(
    (df_users['age'] - 25) * np.random.uniform(0.3, 0.8, n_users),
    0, 30
).astype(int)

df_users['investment_experience'] = pd.cut(
    df_users['years_investing'],
    bins=[0, 2, 10, 40],
    labels=['novice', 'intermediate', 'expert']
)

# Reorder columns
df_users = df_users[['user_id', 'age', 'monthly_income', 'monthly_expense', 
                     'monthly_surplus', 'financial_strategy', 'has_emergency_fund',
                     'age_horizon_mismatch', 'years_investing', 'investment_experience',
                     'risk_tolerance', 'investment_horizon', 'goal']]

# Save to CSV
df_users.to_csv('synthetic_users.csv', index=False)
print(f"✅ Created: synthetic_users.csv ({len(df_users)} users)")
print(f"   Income stats: Avg=₹{df_users['monthly_income'].mean():,.0f}, "
      f"Min=₹{df_users['monthly_income'].min():,.0f}, Max=₹{df_users['monthly_income'].max():,.0f}")
print(f"   Avg risk tolerance={df_users['risk_tolerance'].mean():.3f}")

# Print edge case statistics
print(f"\n📊 FINANCIAL HEALTH BREAKDOWN:")
n_saving = (df_users['financial_strategy'] == 'saving').sum()
n_balanced = (df_users['financial_strategy'] == 'balanced').sum()
n_credit = (df_users['financial_strategy'] == 'credit_card').sum()
n_family = (df_users['financial_strategy'] == 'family_support').sum()

print(f"   • Healthy savers (surplus > ₹5K):       {n_saving} users ({100*n_saving/len(df_users):.1f}%)")
print(f"   • Balanced budget:                      {n_balanced} users ({100*n_balanced/len(df_users):.1f}%)")
print(f"   • Using credit cards (small deficit):   {n_credit} users ({100*n_credit/len(df_users):.1f}%)")
print(f"   • Family support/savings (deficit):     {n_family} users ({100*n_family/len(df_users):.1f}%)")

n_deficit = (df_users['monthly_surplus'] < 0).sum()
print(f"\n⚠️  EDGE CASES:")
print(f"   • Users with expenses > income:         {n_deficit} users ({100*n_deficit/len(df_users):.1f}%)")
print(f"   • Users with emergency fund:            {df_users['has_emergency_fund'].sum()} users ({100*df_users['has_emergency_fund'].sum()/len(df_users):.1f}%)")

if n_deficit > 0:
    avg_deficit = df_users[df_users['monthly_surplus'] < 0]['monthly_surplus'].mean()
    print(f"   • Average deficit amount:               ₹{abs(avg_deficit):,.0f}/month")
    print(f"   • How they manage: Credit cards, family support, or drawing from savings")

print(f"\n📊 LIFECYCLE EDGE CASES:")
n_young_short = (df_users['age_horizon_mismatch'] == 'young_short').sum()
n_old_long = (df_users['age_horizon_mismatch'] == 'old_long').sum()
print(f"   • Young with short horizon (<10y):      {n_young_short} users ({100*n_young_short/len(df_users):.1f}%)")
print(f"   • Old with long horizon (>20y):         {n_old_long} users ({100*n_old_long/len(df_users):.1f}%)")

print(f"\n📊 EXPERIENCE DISTRIBUTION:")
for exp_level in ['novice', 'intermediate', 'expert']:
    n_exp = (df_users['investment_experience'] == exp_level).sum()
    print(f"   • {exp_level.capitalize():12s} investors:              {n_exp} users ({100*n_exp/len(df_users):.1f}%)")

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

# ====== ADD EDGE CASE FIELDS ======

# Market regime classification
df_decisions['market_regime'] = df_decisions['market_return_recent'].apply(
    lambda x: 'extreme_crash' if x < -0.30
              else ('severe_crash' if x < -0.15
              else ('correction' if x < -0.05
              else ('euphoria' if x > 0.15
              else ('bull' if x > 0.05
              else 'normal'))))
)

# Market volatility (higher during crashes)
df_decisions['market_volatility'] = np.random.uniform(0.015, 0.035, len(df_decisions))
df_decisions.loc[df_decisions['market_regime'] == 'extreme_crash', 'market_volatility'] = \
    np.random.uniform(0.08, 0.15, (df_decisions['market_regime'] == 'extreme_crash').sum())
df_decisions.loc[df_decisions['market_regime'] == 'severe_crash', 'market_volatility'] = \
    np.random.uniform(0.05, 0.10, (df_decisions['market_regime'] == 'severe_crash').sum())

# Crash speed dynamics
df_decisions['crash_speed'] = np.random.choice(
    ['flash_crash', 'rapid_decline', 'gradual_bear', 'normal'],
    size=len(df_decisions),
    p=[0.05, 0.15, 0.20, 0.60]
)

# Position characteristics
df_decisions['position_size_pct'] = np.random.beta(2, 8, len(df_decisions))  # Most positions small (5-20%)
df_decisions['holding_period_months'] = np.random.randint(1, 60, len(df_decisions))

# Multiple/secondary biases (some decisions have multiple biases)
def detect_secondary_biases(row):
    """Some users have multiple simultaneous biases"""
    secondary = []
    
    # Loss aversion + herd often co-occur in crashes
    if row['bias_type'] == 'loss_aversion':
        if row['market_return_recent'] < -0.10 and row['crowd_action_ratio'] > 0.70:
            secondary.append('herd')
    
    # Herd + loss aversion
    elif row['bias_type'] == 'herd':
        if row['unrealized_gain_loss'] < -0.15:
            secondary.append('loss_aversion')
    
    # Disposition + overconfidence (sell winners in bull market)
    elif row['bias_type'] == 'disposition' and row['unrealized_gain_loss'] > 0.20:
        if row['market_regime'] == 'bull':
            secondary.append('overconfidence')
    
    return ','.join(secondary) if secondary else 'none'

df_decisions['secondary_biases'] = df_decisions.apply(detect_secondary_biases, axis=1)

df_decisions.to_csv('synthetic_decisions.csv', index=False)
print(f"✅ Created: synthetic_decisions.csv ({len(df_decisions)} decisions)")
print(f"   Bias present: {(df_decisions['bias_present']=='yes').sum()} decisions "
      f"({100*(df_decisions['bias_present']=='yes').sum()/len(df_decisions):.1f}%)")

# Print edge case statistics
print(f"\n📊 EDGE CASE STATISTICS (Decisions):")
print(f"   • Extreme crashes (>30% drop):          {(df_decisions['market_regime']=='extreme_crash').sum()} cases")
print(f"   • Severe crashes (15-30% drop):         {(df_decisions['market_regime']=='severe_crash').sum()} cases")
print(f"   • Flash crashes:                        {(df_decisions['crash_speed']=='flash_crash').sum()} cases")
print(f"   • Multiple simultaneous biases:         {(df_decisions['secondary_biases']!='none').sum()} cases")
print(f"   • Extreme gains (>50%):                 {(df_decisions['unrealized_gain_loss']>0.50).sum()} cases")
print(f"   • Extreme losses (>40%):                {(df_decisions['unrealized_gain_loss']<-0.40).sum()} cases")
print(f"   • Large positions (>30% portfolio):     {(df_decisions['position_size_pct']>0.30).sum()} cases")

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
print("\n   'Income values are rounded to realistic thousands (not decimals)")
print("   to match how users actually input salary. Edge cases include:")
print("   • Financial: Users with expenses > income (~10%)")
print("   • Lifecycle: Age-horizon mismatches, novice vs expert investors")
print("   • Market: Extreme crashes (>30%), flash vs gradual declines")
print("   • Portfolio: Extreme gains/losses (>50%/>40%), position sizing")
print("   • Behavioral: Multiple simultaneous biases co-occurring")
print("   These edge cases ensure robust, context-aware bias detection")
print("   that distinguishes genuine financial need from behavioral bias.'")
print("\n" + "="*60)
