# 🎯 GAP 1: Causal Decision-Time Reasoning
## Detecting Behavioral Biases in Real-Time Using Causal AI

---

## 📖 NON-TECHNICAL EXPLANATION

### **What's the Problem?**

Imagine you're about to sell your stocks during a market crash. Most financial apps will tell you AFTER you've sold whether it was a good or bad decision. That's too late! It's like a doctor diagnosing you after you're already sick instead of preventing the illness.

**Current systems:**
- ❌ Look at past decisions (hindsight, not helpful now)
- ❌ Find patterns but don't understand WHY they happen
- ❌ Can't tell if you're making an emotional mistake RIGHT NOW
- ❌ Say "people who sell during crashes regret it" but don't explain the cause-effect chain

### **What We're Building:**

A smart system that:
- ✅ **Catches you in the act**: "WAIT! You're about to panic sell because you're scared of losses"
- ✅ **Understands cause-and-effect**: "Your fear of loss is CAUSING you to sell, not rational analysis"
- ✅ **Intervenes immediately**: Shows you what will happen if you make this emotional decision
- ✅ **Explains WHY**: "Because you're loss-averse, you feel this -15% loss as -30% pain"

**Real-world analogy**: It's like having a friend who stops you from drunk-texting your ex. They catch you in the moment, explain why you're doing it (emotions, not logic), and show you the consequences.

---

## 🎯 OBJECTIVE

**Build a Real-Time Bias Detection and Causal Reasoning Engine**

This system will:
1. **Detect** when someone is making an emotionally-driven financial decision
2. **Identify** which specific bias is affecting them (loss aversion, herd mentality, etc.)
3. **Explain** the cause-and-effect chain: "Loss → Fear → Panic Sell → Locked Losses"
4. **Intervene** BEFORE the decision is finalized

---

## 🗂️ DATASETS TO USE

### **Synthetic Datasets (Primary - For Training & Validation)**

#### 1. **synthetic_decisions.csv** ⭐ MAIN DATASET
**Why this dataset?**
- Contains 5,000 decision moments with **ground truth labels**
- We KNOW which decisions are biased (impossible to know in real life!)
- Has the exact moment of decision with market conditions

**What's inside:**
```csv
decision_id,user_id,market_return_recent,unrealized_gain_loss,crowd_action_ratio,decision,bias_present,bias_type
0,0,-0.08,-0.12,0.73,sell,yes,loss_aversion
1,0,0.03,0.05,0.45,hold,no,rational
```

**When to use:**
- **Training the bias detector** (ML model learns from this)
- **Validation** (check if our detector is correct)
- **Ground truth comparison** (prove accuracy)

---

#### 2. **synthetic_bias_profiles.csv** ⭐ VALIDATION
**Why this dataset?**
- Contains users' true personality traits (disposition_strength, loss_aversion, herd_sensitivity)
- Allows us to validate: "Did we correctly identify this user's loss aversion?"
- Provides psychological ground truth

**What's inside:**
```csv
user_id,disposition_strength,loss_aversion,herd_sensitivity
0,0.65,2.31,0.42
```

**When to use:**
- **Validation only** (not for training - that would be cheating!)
- **Post-hoc analysis** (understand why detector works)
- **User profiling** (build psychological profiles)

---

#### 3. **synthetic_users.csv** 🔧 CONTEXT
**Why this dataset?**
- Personal circumstances matter (age, income, risk tolerance)
- A 25-year-old can afford to wait out a crash; a 60-year-old might not
- Helps personalize interventions
- **✨ REALISTIC DATA**: Income rounded to thousands (₹50,000 not ₹50,234.56) - matches real user input
- **✨ EDGE CASES**: Includes users with expenses > income (5-15% of population)

**What's inside:**
```csv
user_id,age,monthly_income,monthly_expense,monthly_surplus,financial_strategy,has_emergency_fund,risk_tolerance,investment_horizon,goal
0,38,60000,48000,12000,saving,True,0.35,18,wealth growth
1,42,75000,78000,-3000,credit_card,False,0.28,15,wealth growth
```

**Key Features:**
- **monthly_income**: Rounded to nearest ₹1,000 (realistic!)
- **monthly_expense**: Calculated based on lifestyle (can exceed income!)
- **monthly_surplus**: Positive = saving, Negative = deficit
- **financial_strategy**: How users manage finances:
  - `saving`: Surplus > ₹5,000 (healthy savers ~60%)
  - `balanced`: Break-even budget (~25%)
  - `credit_card`: Small deficit, using credit (~10%)
  - `family_support`: Large deficit, family help/savings drawdown (~5%)
- **has_emergency_fund**: 3-6 months expenses saved? (70% yes for savers, 20% yes for deficit users)

**Edge Cases Covered:**
1. ⚠️ **Income < Expenses** (5-15% of users):
   - Young professionals with student loans
   - Users building business (initial losses)
   - Medical emergency expenses
   - **How they manage**: Credit cards, family loans, drawing from savings, side income
   
2. 💰 **No Emergency Fund** (30-80% depending on financial health):
   - Cannot weather market crashes
   - More likely to panic sell
   - Higher stress during downturns

**When to use:**
- Context enrichment (understand WHO is making the decision)
- Personalized explanations ("You have 18 years to recover" vs "You need cash now")
- Risk profiling (users in debt = lower risk tolerance in practice)
- Intervention customization (don't tell debt-strapped users to "just hold"!)

---

### **Real Datasets (Secondary - For Market Context)**

#### 4. **NIFTY/SENSEX Historical Data** 📈 MARKET STATE
**Why this dataset?**
- Provides REAL market conditions (is market actually crashing or just normal volatility?)
- Validates our synthetic market patterns
- Contextualizes decisions

**What to extract:**
- Daily returns (%)
- Volatility (rolling 30-day std)
- Regime classification (bull/bear/crash)
- Current market phase

**When to use:**
- **Real-time analysis**: "Market is down 12% - checking if user is panic selling"
- **Regime detection**: Different biases activate in different market conditions
- **Contextualization**: Compare user's loss to market average

**Example code:**
```python
# Load real market data
nifty = pd.read_csv('data/nifty_historical.csv', parse_dates=['Date'])
nifty['daily_return'] = nifty['Close'].pct_change()
nifty['volatility'] = nifty['daily_return'].rolling(30).std()

# Get current market state
current_return = nifty['daily_return'].iloc[-1]
current_vol = nifty['volatility'].iloc[-1]
is_crisis = current_return < -0.10 and current_vol > 0.03
```

---

#### 5. **Macrofinance Data** (Interest Rates, Inflation) 📊 MACRO CONTEXT
**Why this dataset?**
- Economic environment affects decisions
- High inflation → people more risk-averse
- Low interest rates → people take more risks

**What to use:**
- RBI interest rates
- CPI inflation
- GDP growth rate
- Unemployment rate

**When to use:**
- **Macro-aware bias detection**: "Inflation is 8% - expect more loss aversion"
- **Contextual explanations**: "Selling now means reinvesting at 4% rates"
- **Regime-dependent models**: Different models for different economic climates

---

## 🤖 MODELS TO USE

### **Model 1: Bias Detection Model** ⭐ CORE ML MODEL

#### **Pre-trained Models Available:**
❌ **NO** - There are no pre-trained models for this specific task (behavioral bias detection in finance is novel)

#### **Model Options (Choose One):**

**Option A: Gradient Boosting (RECOMMENDED)**
- **Algorithm**: XGBoost or LightGBM
- **Why**: Best for tabular data, handles non-linear patterns, feature importance built-in
- **Pros**: High accuracy (85-90%), fast inference, interpretable
- **Cons**: Needs feature engineering

**Option B: Random Forest**
- **Algorithm**: Scikit-learn RandomForestClassifier
- **Why**: Robust, less prone to overfitting, good baseline
- **Pros**: Easy to tune, handles mixed data types
- **Cons**: Slightly lower accuracy than boosting

**Option C: Neural Network** (Not Recommended)
- **Algorithm**: TensorFlow/PyTorch MLP
- **Why**: Can capture complex patterns
- **Pros**: High capacity
- **Cons**: Overkill for 5,000 samples, hard to interpret, requires more data

**RECOMMENDED CHOICE: XGBoost**

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split

# This is the model we'll use
model = xgb.XGBClassifier(
    n_estimators=200,      # 200 decision trees
    max_depth=6,           # How deep each tree
    learning_rate=0.1,     # How fast it learns
    objective='multi:softmax',  # Multi-class classification
    num_class=4,           # 4 bias types
    random_state=42
)
```

---

### **Model 2: Causal Structure Learning** 🧠 CAUSAL GRAPH

#### **Pre-trained Models Available:**
❌ **NO** - Causal structure is learned from YOUR data (dataset-specific)

#### **Algorithm Options:**

**Option A: NOTEARS (RECOMMENDED)**
- **Package**: `causalnex`
- **Why**: Continuous optimization for DAG structure
- **Pros**: Fast, scalable, works with continuous data
- **Cons**: Requires enough data (we have 5,000 samples ✓)

**Option B: PC Algorithm**
- **Package**: `causal-learn` or `pgmpy`
- **Why**: Constraint-based causal discovery
- **Pros**: Well-established, conservative
- **Cons**: Slower, requires independence tests

**Option C: Bayesian Network Learning**
- **Package**: `pgmpy`
- **Why**: Probabilistic graphical models
- **Pros**: Handles uncertainty well
- **Cons**: Computationally expensive

**RECOMMENDED CHOICE: NOTEARS (via CausalNex)**

```python
from causalnex.structure.notears import from_pandas

# This learns: Which variables cause which?
# Example: loss_aversion → decision (loss aversion CAUSES selling)
causal_graph = from_pandas(
    data=df_causal,
    max_iter=100,
    w_threshold=0.3  # Edge weight threshold
)
```

---

### **Model 3: Causal Inference Engine** 🔬 DO-CALCULUS

#### **Pre-trained Models Available:**
✅ **YES** - DoWhy library provides pre-built causal inference methods

#### **Algorithm Options:**

**Option A: Propensity Score Matching (RECOMMENDED)**
- **Package**: `dowhy`
- **Why**: Estimates causal effects by matching similar individuals
- **Pros**: Robust, well-validated in medical/social sciences
- **Cons**: Requires overlap assumption

**Option B: Inverse Propensity Weighting**
- **Package**: `dowhy`
- **Why**: Re-weights samples to simulate interventions
- **Pros**: Uses all data
- **Cons**: Sensitive to extreme weights

**Option C: Regression Discontinuity**
- **Package**: `dowhy`
- **Why**: Natural experiments with threshold effects
- **Pros**: Strong identification
- **Cons**: Requires natural threshold (not applicable here)

**RECOMMENDED CHOICE: Propensity Score Matching**

```python
import dowhy

# This answers: "What if we REMOVE the bias?"
# do(loss_aversion = 0) → effect on decision
model = dowhy.CausalModel(
    data=df,
    treatment='loss_aversion',
    outcome='decision',
    graph=causal_graph_string
)

# Estimate causal effect
effect = model.estimate_effect(
    identified_estimand,
    method_name="backdoor.propensity_score_matching"
)
```

---

## 📋 DETAILED APPROACH (STEP-BY-STEP)

### **PHASE 1: Data Preparation (Week 1)**

#### **Step 1.1: Load and Explore Datasets**

**Why**: Understand what data you have before building models
**When**: First thing to do
**How**:

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Load synthetic datasets
df_decisions = pd.read_csv('data/synthetic_decisions.csv')
df_bias_profiles = pd.read_csv('data/synthetic_bias_profiles.csv')
df_users = pd.read_csv('data/synthetic_users.csv')

# Load real market data
nifty = pd.read_csv('data/nifty_historical.csv', parse_dates=['Date'])
macro = pd.read_csv('data/macro_indicators.csv', parse_dates=['Date'])

# Quick exploration
print("="*60)
print("DATASET OVERVIEW")
print("="*60)
print(f"\n📊 Decisions: {len(df_decisions)} rows")
print(f"📊 Users: {len(df_users)} rows")
print(f"📊 Market data: {len(nifty)} days")

# Check bias distribution
print("\n🧠 BIAS DISTRIBUTION:")
print(df_decisions['bias_type'].value_counts())
print(f"\n% Biased: {(df_decisions['bias_present']=='yes').mean():.1%}")

# Visualize
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Plot 1: Bias distribution
df_decisions['bias_type'].value_counts().plot(kind='bar', ax=axes[0,0])
axes[0,0].set_title('Distribution of Bias Types')
axes[0,0].set_ylabel('Count')

# Plot 2: Decision context
axes[0,1].scatter(df_decisions['market_return_recent'], 
                  df_decisions['unrealized_gain_loss'],
                  c=df_decisions['bias_present'].map({'yes': 'red', 'no': 'green'}),
                  alpha=0.5)
axes[0,1].set_xlabel('Market Return')
axes[0,1].set_ylabel('Unrealized Gain/Loss')
axes[0,1].set_title('Decision Context (Red=Biased, Green=Rational)')

# Plot 3: User demographics
df_users['age'].hist(ax=axes[1,0], bins=20)
axes[1,0].set_title('User Age Distribution')
axes[1,0].set_xlabel('Age')

# Plot 4: Market volatility
nifty['daily_return'] = nifty['Close'].pct_change()
nifty['volatility'] = nifty['daily_return'].rolling(30).std()
axes[1,1].plot(nifty['Date'], nifty['volatility'])
axes[1,1].set_title('NIFTY Volatility Over Time')
axes[1,1].set_ylabel('30-day Rolling Volatility')

plt.tight_layout()
plt.savefig('results/figures/data_exploration.png', dpi=300)
print("\n✅ Exploration plots saved to results/figures/data_exploration.png")
```

**What this does:**
- Loads all datasets
- Shows you what's inside
- Creates visualizations to understand patterns
- Validates data quality

---

#### **Step 1.2: Merge and Feature Engineering**

**Why**: Combine datasets to create rich feature set for ML
**When**: After exploring individual datasets
**How**:

```python
# Merge decisions with user profiles
df_merged = df_decisions.merge(df_users, on='user_id', how='left')
df_merged = df_merged.merge(df_bias_profiles, on='user_id', how='left')

print(f"✅ Merged dataset: {df_merged.shape}")

# Feature Engineering
print("\n🔧 ENGINEERING FEATURES...")

# 1. Market regime features (from real NIFTY data)
def get_market_regime(date):
    """Get market regime on specific date"""
    recent_returns = nifty[nifty['Date'] <= date].tail(30)['daily_return']
    recent_vol = recent_returns.std()
    avg_return = recent_returns.mean()
    
    if avg_return > 0.001 and recent_vol < 0.02:
        return 'bull', recent_vol
    elif avg_return < -0.003 or recent_vol > 0.03:
        return 'crisis', recent_vol
    else:
        return 'bear', recent_vol

# Note: For synthetic data, we'll create synthetic dates
# In production, you'd have actual decision timestamps
df_merged['market_regime'] = 'bear'  # Placeholder
df_merged['market_volatility'] = 0.02  # Placeholder

# 2. Loss magnitude categories
df_merged['loss_category'] = pd.cut(
    df_merged['unrealized_gain_loss'],
    bins=[-1, -0.15, -0.05, 0.05, 0.15, 1],
    labels=['large_loss', 'small_loss', 'neutral', 'small_gain', 'large_gain']
)

# 3. Crowd pressure level
df_merged['crowd_pressure'] = pd.cut(
    df_merged['crowd_action_ratio'],
    bins=[0, 0.3, 0.7, 1.0],
    labels=['low', 'medium', 'high']
)

# 4. Risk-adjusted features
df_merged['risk_adjusted_loss'] = (
    df_merged['unrealized_gain_loss'] / df_merged['risk_tolerance']
)

# 5. Age-horizon mismatch (young person with short horizon = unusual)
df_merged['age_horizon_ratio'] = df_merged['age'] / df_merged['investment_horizon']

# 6. Interaction features (these capture complex patterns)
df_merged['loss_x_crowd'] = (
    df_merged['unrealized_gain_loss'] * df_merged['crowd_action_ratio']
)
df_merged['loss_x_market'] = (
    df_merged['unrealized_gain_loss'] * df_merged['market_return_recent']
)

print("✅ Feature engineering complete!")
print(f"\n📊 Total features: {df_merged.shape[1]}")
print("\n🎯 New features created:")
print("  - market_regime")
print("  - loss_category")
print("  - crowd_pressure")
print("  - risk_adjusted_loss")
print("  - age_horizon_ratio")
print("  - loss_x_crowd")
print("  - loss_x_market")
```

**What this does:**
- Combines user info with decisions
- Creates new features that capture complex patterns
- Prepares data for machine learning

---

### **PHASE 2: Build Bias Detection Model (Week 2-3)**

#### **Step 2.1: Prepare Training Data**

**Why**: ML models need properly formatted input/output
**When**: After feature engineering
**How**:

```python
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

print("\n" + "="*60)
print("PREPARING TRAINING DATA")
print("="*60)

# Select features for the model
# Start with basic features (you can add more later)
feature_cols = [
    # Decision context
    'market_return_recent',
    'unrealized_gain_loss',
    'crowd_action_ratio',
    
    # User profile
    'age',
    'risk_tolerance',
    'investment_horizon',
    
    # Engineered features
    'risk_adjusted_loss',
    'loss_x_crowd',
    'loss_x_market'
]

X = df_merged[feature_cols]
y = df_merged['bias_type']

print(f"\n📊 Feature matrix shape: {X.shape}")
print(f"📊 Target distribution:\n{y.value_counts()}")

# Split: 80% training, 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y  # Keep same proportion of each bias type
)

print(f"\n✅ Training set: {X_train.shape[0]} samples")
print(f"✅ Test set: {X_test.shape[0]} samples")

# Save split for reproducibility
np.save('data/processed/train_indices.npy', X_train.index)
np.save('data/processed/test_indices.npy', X_test.index)
print("\n✅ Indices saved for reproducibility")
```

**What this does:**
- Selects which features to use (not all are needed!)
- Splits data into training (to learn) and testing (to validate)
- Ensures balanced classes

---

#### **Step 2.2: Train XGBoost Model**

**Why**: Learn patterns from data to detect biases
**When**: After data preparation
**How**:

```python
import xgboost as xgb
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib

print("\n" + "="*60)
print("TRAINING BIAS DETECTION MODEL")
print("="*60)

# Initialize XGBoost
model = xgb.XGBClassifier(
    n_estimators=200,           # 200 trees (more = better usually)
    max_depth=6,                # Depth of trees (prevents overfitting)
    learning_rate=0.1,          # How fast to learn (smaller = more careful)
    objective='multi:softmax',  # Multi-class classification
    eval_metric='mlogloss',     # How to measure error
    random_state=42,
    n_jobs=-1                   # Use all CPU cores
)

print("\n🚀 Training started...")
print("   (This may take 1-2 minutes...)")

# Train the model
model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_test, y_test)],
    verbose=50  # Print progress every 50 iterations
)

print("\n✅ Training complete!")

# Evaluate on test set
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\n" + "="*60)
print("MODEL PERFORMANCE")
print("="*60)
print(f"\n🎯 Overall Accuracy: {accuracy:.2%}")

print("\n📊 DETAILED REPORT:")
print(classification_report(y_test, y_pred))

print("\n📊 CONFUSION MATRIX:")
cm = confusion_matrix(y_test, y_pred)
print(cm)

# Visualize confusion matrix
import seaborn as sns
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=model.classes_,
            yticklabels=model.classes_)
plt.title('Confusion Matrix - Bias Detection')
plt.ylabel('True Bias Type')
plt.xlabel('Predicted Bias Type')
plt.savefig('results/figures/confusion_matrix.png', dpi=300)
print("\n✅ Confusion matrix saved")

# Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("\n📊 TOP 5 MOST IMPORTANT FEATURES:")
print(feature_importance.head())

# Plot feature importance
plt.figure(figsize=(10, 6))
feature_importance.plot(x='feature', y='importance', kind='barh')
plt.title('Feature Importance for Bias Detection')
plt.xlabel('Importance')
plt.tight_layout()
plt.savefig('results/figures/feature_importance.png', dpi=300)
print("✅ Feature importance plot saved")

# Save model
model_path = 'models/bias_detector_xgboost.pkl'
joblib.dump(model, model_path)
print(f"\n✅ Model saved to {model_path}")
```

**What this does:**
- Trains XGBoost to recognize bias patterns
- Tests accuracy on unseen data
- Shows which features matter most
- Saves model for later use

**Expected Output:**
```
🎯 Overall Accuracy: 87.3%

📊 DETAILED REPORT:
                precision    recall  f1-score   support

  disposition       0.89      0.85      0.87       250
         herd       0.84      0.88      0.86       248
loss_aversion       0.90      0.89      0.89       252
     rational       0.86      0.87      0.86       250

✅ Model performs well! Above 85% target.
```

---

#### **Step 2.3: Real-Time Prediction Function**

**Why**: Make model easy to use for live decisions
**When**: After model is trained
**How**:

```python
def detect_bias_realtime(market_return, unrealized_gl, crowd_ratio, 
                         age, risk_tolerance, investment_horizon,
                         model_path='models/bias_detector_xgboost.pkl'):
    """
    Detect behavioral bias in real-time
    
    Args:
        market_return: Recent market return (-1 to 1)
        unrealized_gl: Unrealized gain/loss on position (-1 to 1)
        crowd_ratio: % of people selling (0 to 1)
        age: User age (years)
        risk_tolerance: Risk tolerance (0 to 1)
        investment_horizon: Investment horizon (years)
        
    Returns:
        dict: {
            'bias_detected': bool,
            'bias_type': str,
            'confidence': float,
            'probabilities': dict,
            'warning_message': str
        }
    """
    # Load model
    model = joblib.load(model_path)
    
    # Engineer features (same as training)
    risk_adjusted_loss = unrealized_gl / risk_tolerance if risk_tolerance > 0 else 0
    loss_x_crowd = unrealized_gl * crowd_ratio
    loss_x_market = unrealized_gl * market_return
    
    # Create feature vector
    features = np.array([[
        market_return,
        unrealized_gl,
        crowd_ratio,
        age,
        risk_tolerance,
        investment_horizon,
        risk_adjusted_loss,
        loss_x_crowd,
        loss_x_market
    ]])
    
    # Predict
    bias_type = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]
    confidence = probabilities.max()
    
    # Create probability dict
    prob_dict = dict(zip(model.classes_, probabilities))
    
    # Generate warning message
    warnings = {
        'loss_aversion': "⚠️ LOSS AVERSION DETECTED: You're reacting to short-term pain. Consider your long-term goals.",
        'disposition': "⚠️ DISPOSITION EFFECT DETECTED: You may be selling winners too early or holding losers too long.",
        'herd': "⚠️ HERD BEHAVIOR DETECTED: You're following the crowd. Independent analysis recommended.",
        'rational': "✅ NO BIAS DETECTED: Your decision appears rational based on the circumstances."
    }
    
    return {
        'bias_detected': bias_type != 'rational',
        'bias_type': bias_type,
        'confidence': confidence,
        'probabilities': prob_dict,
        'warning_message': warnings[bias_type]
    }

# Test the function
print("\n" + "="*60)
print("TESTING REAL-TIME DETECTION")
print("="*60)

# Test Case: Panic selling during market crash
result = detect_bias_realtime(
    market_return=-0.12,      # Market down 12%
    unrealized_gl=-0.18,      # Portfolio down 18%
    crowd_ratio=0.88,         # 88% are selling
    age=35,
    risk_tolerance=0.4,
    investment_horizon=25
)

print("\n📊 SCENARIO: Market crash, user considering panic selling")
print(f"   Bias Detected: {result['bias_detected']}")
print(f"   Bias Type: {result['bias_type']}")
print(f"   Confidence: {result['confidence']:.0%}")
print(f"\n   {result['warning_message']}")

print("\n📊 PROBABILITIES:")
for bias, prob in result['probabilities'].items():
    print(f"   {bias:15s}: {prob:.1%}")
```

**What this does:**
- Wraps model in easy-to-use function
- Takes real-time inputs
- Returns clear results
- Provides actionable warnings

---

### **PHASE 3: Causal Structure Learning (Week 4)**

#### **Step 3.1: Prepare Causal Data**

**Why**: Learn which variables cause which (beyond correlation)
**When**: After bias detector is working
**How**:

```python
from causalnex.structure.notears import from_pandas
import networkx as nx

print("\n" + "="*60)
print("LEARNING CAUSAL STRUCTURE")
print("="*60)

# Select variables for causal analysis
causal_vars = [
    # External factors (potential causes)
    'market_return_recent',
    'crowd_action_ratio',
    
    # User traits (potential causes)
    'disposition_strength',
    'loss_aversion',
    'herd_sensitivity',
    'risk_tolerance',
    
    # Position state (potential cause)
    'unrealized_gain_loss',
    
    # Decision (effect)
    'decision'
]

df_causal = df_merged[causal_vars].copy()

# Convert decision to binary (0=hold, 1=sell)
df_causal['decision'] = (df_causal['decision'] == 'sell').astype(int)

# Normalize data (NOTEARS works better with normalized data)
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df_causal_scaled = pd.DataFrame(
    scaler.fit_transform(df_causal),
    columns=df_causal.columns
)

print(f"\n📊 Causal dataset shape: {df_causal_scaled.shape}")
print(f"📊 Variables: {len(causal_vars)}")
```

---

#### **Step 3.2: Learn Causal Graph**

**Why**: Discover cause-effect relationships automatically
**When**: After preparing causal data
**How**:

```python
print("\n🧠 Running NOTEARS algorithm...")
print("   (This may take 2-3 minutes...)")

# Learn causal structure
sm = from_pandas(
    df_causal_scaled,
    max_iter=100,
    w_threshold=0.3  # Only keep edges with weight > 0.3
)

print(f"\n✅ Causal structure learned!")
print(f"   Edges found: {len(sm.edges)}")

# Print discovered causal relationships
print("\n📊 DISCOVERED CAUSAL RELATIONSHIPS:")
for i, (cause, effect) in enumerate(sm.edges, 1):
    weight = sm[cause][effect]['weight']
    print(f"   {i}. {cause:25s} → {effect:25s} (strength: {abs(weight):.3f})")

# Visualize causal graph
plt.figure(figsize=(16, 12))
pos = nx.spring_layout(sm, k=2, iterations=50)
nx.draw_networkx_nodes(sm, pos, node_size=3000, node_color='lightblue')
nx.draw_networkx_labels(sm, pos, font_size=10)
nx.draw_networkx_edges(sm, pos, edge_color='gray', 
                       arrows=True, arrowsize=20, width=2)

plt.title('Learned Causal Graph: What Causes Financial Decisions?', fontsize=16)
plt.axis('off')
plt.tight_layout()
plt.savefig('results/figures/causal_graph.png', dpi=300, bbox_inches='tight')
print("\n✅ Causal graph saved to results/figures/causal_graph.png")

# Save causal graph
import pickle
with open('models/causal_graph.pkl', 'wb') as f:
    pickle.dump(sm, f)
print("✅ Causal graph saved to models/causal_graph.pkl")
```

**What this does:**
- Automatically discovers which variables cause which
- Creates visual map of causality
- Saves structure for later use

**Example Output:**
```
📊 DISCOVERED CAUSAL RELATIONSHIPS:
   1. loss_aversion          → decision              (strength: 0.452)
   2. unrealized_gain_loss   → decision              (strength: 0.389)
   3. crowd_action_ratio     → decision              (strength: 0.267)
   4. loss_aversion          → unrealized_gain_loss  (strength: 0.198)
   5. disposition_strength   → decision              (strength: 0.156)
```

**Interpretation:**
- Loss aversion STRONGLY causes selling decisions
- Current losses affect decisions
- Crowd behavior has moderate causal effect
- Loss aversion also makes people more sensitive to losses

---

### **PHASE 4: Causal Inference (Week 5)**

#### **Step 4.1: Estimate Causal Effects**

**Why**: Quantify HOW MUCH one variable affects another
**When**: After learning causal structure
**How**:

```python
import dowhy
from dowhy import CausalModel

print("\n" + "="*60)
print("ESTIMATING CAUSAL EFFECTS")
print("="*60)

# Convert graph to DoWhy format
def graph_to_gml(sm):
    """Convert CausalNex graph to GML string for DoWhy"""
    gml = "graph [directed 1\n"
    for node in sm.nodes:
        gml += f'  node [id "{node}" label "{node}"]\n'
    for cause, effect in sm.edges:
        gml += f'  edge [source "{cause}" target "{effect}"]\n'
    gml += "]"
    return gml

causal_graph_gml = graph_to_gml(sm)

# Question 1: How does loss_aversion affect decision?
print("\n🔬 CAUSAL QUESTION 1:")
print("   How does loss aversion affect selling decisions?")

model = CausalModel(
    data=df_causal,
    treatment='loss_aversion',
    outcome='decision',
    graph=causal_graph_gml
)

# Identify causal effect
identified_estimand = model.identify_effect(proceed_when_unidentifiable=True)
print("\n   Identified causal estimand:")
print(str(identified_estimand))

# Estimate effect using Propensity Score Matching
causal_estimate = model.estimate_effect(
    identified_estimand,
    method_name="backdoor.propensity_score_matching"
)

print(f"\n✅ CAUSAL EFFECT ESTIMATE:")
print(f"   Increasing loss aversion by 1 unit increases")
print(f"   probability of selling by: {causal_estimate.value:.3f}")
print(f"   (This is a CAUSAL effect, not just correlation!)")

# Refute the estimate (validate)
print("\n🔬 VALIDATING ESTIMATE...")
refute = model.refute_estimate(
    identified_estimand,
    causal_estimate,
    method_name="random_common_cause"
)
print(f"   Refutation p-value: {refute.refutation_result['p_value']:.4f}")
if refute.refutation_result['p_value'] > 0.05:
    print("   ✅ Effect is robust (survives refutation)")
else:
    print("   ⚠️ Effect may be spurious")

# Question 2: How does crowd behavior affect decision?
print("\n\n🔬 CAUSAL QUESTION 2:")
print("   How does crowd behavior affect decisions?")

model2 = CausalModel(
    data=df_causal,
    treatment='crowd_action_ratio',
    outcome='decision',
    graph=causal_graph_gml
)

identified_estimand2 = model2.identify_effect(proceed_when_unidentifiable=True)
causal_estimate2 = model2.estimate_effect(
    identified_estimand2,
    method_name="backdoor.propensity_score_matching"
)

print(f"\n✅ CAUSAL EFFECT ESTIMATE:")
print(f"   Increasing crowd selling from 0% to 100% increases")
print(f"   probability of selling by: {causal_estimate2.value:.3f}")

# Save causal estimates
causal_effects = {
    'loss_aversion_to_decision': causal_estimate.value,
    'crowd_ratio_to_decision': causal_estimate2.value
}

with open('results/causal_effects.pkl', 'wb') as f:
    pickle.dump(causal_effects, f)
print("\n✅ Causal effects saved")
```

**What this does:**
- Measures exact causal impact
- Validates results (not just correlations!)
- Quantifies intervention effects

**Example Output:**
```
✅ CAUSAL EFFECT ESTIMATE:
   Increasing loss aversion by 1 unit increases
   probability of selling by: 0.234
   (This is a CAUSAL effect, not just correlation!)
```

**Interpretation:**
- If we could magically reduce someone's loss aversion by 1 point, they'd be 23.4% less likely to panic sell
- This is actionable: interventions that reduce loss aversion will reduce panic selling

---

#### **Step 4.2: Intervention Simulation**

**Why**: Show what happens if we remove bias
**When**: After estimating causal effects
**How**:

```python
def simulate_intervention(user_data, intervention_type):
    """
    Simulate what happens if we intervene to remove bias
    
    Args:
        user_data: dict with user's current state
        intervention_type: 'remove_loss_aversion', 'ignore_crowd', 'both'
    
    Returns:
        dict: Before/after decision probabilities
    """
    # Original state
    original_features = np.array([[
        user_data['market_return'],
        user_data['unrealized_gl'],
        user_data['crowd_ratio'],
        user_data['age'],
        user_data['risk_tolerance'],
        user_data['investment_horizon'],
        user_data['unrealized_gl'] / user_data['risk_tolerance'],
        user_data['unrealized_gl'] * user_data['crowd_ratio'],
        user_data['unrealized_gl'] * user_data['market_return']
    ]])
    
    # Load model
    model = joblib.load('models/bias_detector_xgboost.pkl')
    
    # Original prediction
    original_probs = model.predict_proba(original_features)[0]
    original_bias = model.predict(original_features)[0]
    
    # Intervened state
    if intervention_type == 'remove_loss_aversion':
        # Simulate as if user has LOW loss aversion
        # This changes their risk-adjusted loss perception
        intervened_features = original_features.copy()
        intervened_features[0, 6] *= 0.3  # 70% reduction in risk-adjusted loss
        
    elif intervention_type == 'ignore_crowd':
        # Simulate as if user ignores crowd
        intervened_features = original_features.copy()
        intervened_features[0, 2] = 0.2  # Reduce crowd influence to 20%
        intervened_features[0, 7] *= 0.2  # Reduce loss_x_crowd
        
    elif intervention_type == 'both':
        intervened_features = original_features.copy()
        intervened_features[0, 6] *= 0.3
        intervened_features[0, 2] = 0.2
        intervened_features[0, 7] *= 0.2
    
    # Intervened prediction
    intervened_probs = model.predict_proba(intervened_features)[0]
    intervened_bias = model.predict(intervened_features)[0]
    
    return {
        'original': {
            'bias_type': original_bias,
            'prob_sell': original_probs[model.classes_ != 'rational'].sum(),
            'probabilities': dict(zip(model.classes_, original_probs))
        },
        'intervened': {
            'bias_type': intervened_bias,
            'prob_sell': intervened_probs[model.classes_ != 'rational'].sum(),
            'probabilities': dict(zip(model.classes_, intervened_probs))
        },
        'effect': {
            'change_in_bias': original_bias != intervened_bias,
            'change_in_sell_prob': (
                original_probs[model.classes_ != 'rational'].sum() -
                intervened_probs[model.classes_ != 'rational'].sum()
            )
        }
    }

# Test intervention
print("\n" + "="*60)
print("INTERVENTION SIMULATION")
print("="*60)

test_user = {
    'market_return': -0.12,
    'unrealized_gl': -0.18,
    'crowd_ratio': 0.88,
    'age': 35,
    'risk_tolerance': 0.4,
    'investment_horizon': 25
}

print("\n📊 SCENARIO: User about to panic sell")
print(f"   Market: {test_user['market_return']:.1%}")
print(f"   Loss: {test_user['unrealized_gl']:.1%}")
print(f"   Crowd selling: {test_user['crowd_ratio']:.0%}")

result = simulate_intervention(test_user, 'remove_loss_aversion')

print("\n🔬 INTERVENTION: Remove loss aversion")
print(f"\n   BEFORE intervention:")
print(f"      Detected bias: {result['original']['bias_type']}")
print(f"      Prob of selling: {result['original']['prob_sell']:.1%}")

print(f"\n   AFTER intervention:")
print(f"      Detected bias: {result['intervened']['bias_type']}")
print(f"      Prob of selling: {result['intervened']['prob_sell']:.1%}")

print(f"\n✅ INTERVENTION EFFECT:")
print(f"      Reduction in sell probability: {result['effect']['change_in_sell_prob']:.1%}")
print(f"      Bias removed: {result['effect']['change_in_bias']}")
```

**What this does:**
- Shows effect of removing bias
- Demonstrates intervention value
- Proves causality works

---

## 🎯 WHEN TO USE EACH COMPONENT

### **Use Bias Detector When:**
- ✅ User is about to make a decision (real-time)
- ✅ You want to flag risky decisions
- ✅ Building automated trading guard rails
- ✅ Providing decision support

### **Use Causal Graph When:**
- ✅ Understanding why biases happen
- ✅ Finding root causes of bad decisions
- ✅ Designing interventions
- ✅ Explaining system to stakeholders

### **Use Causal Inference When:**
- ✅ Quantifying intervention effects
- ✅ A/B testing decision support features
- ✅ Proving impact of your system
- ✅ Research validation

### **Use Real Market Data When:**
- ✅ Contextualizing decisions (is market really crashing?)
- ✅ Regime-specific models (different patterns in bull/bear markets)
- ✅ Calibrating synthetic data
- ✅ Production deployment

---

## 📊 VALIDATION & EVALUATION

```python
print("\n" + "="*60)
print("FINAL VALIDATION")
print("="*60)

# Metric 1: Bias detection accuracy
print("\n✅ METRIC 1: Bias Detection Accuracy")
print(f"   Target: >85%")
print(f"   Achieved: {accuracy:.1%}")
print(f"   Status: {'PASS ✓' if accuracy > 0.85 else 'FAIL ✗'}")

# Metric 2: Causal effect validation
print("\n✅ METRIC 2: Causal Effects Identified")
print(f"   Target: ≥3 significant causal paths")
print(f"   Achieved: {len(sm.edges)} causal edges")
print(f"   Status: {'PASS ✓' if len(sm.edges) >= 3 else 'FAIL ✗'}")

# Metric 3: Real-time performance
import time
start = time.time()
for _ in range(100):
    detect_bias_realtime(-0.12, -0.18, 0.88, 35, 0.4, 25)
avg_time = (time.time() - start) / 100

print("\n✅ METRIC 3: Real-Time Performance")
print(f"   Target: <100ms per prediction")
print(f"   Achieved: {avg_time*1000:.1f}ms")
print(f"   Status: {'PASS ✓' if avg_time < 0.1 else 'FAIL ✗'}")

print("\n" + "="*60)
print("GAP 1 IMPLEMENTATION COMPLETE! 🎉")
print("="*60)
```

---

## 📦 DELIVERABLES FOR GAP 1

1. ✅ **Bias Detection Model** (`models/bias_detector_xgboost.pkl`)
2. ✅ **Causal Graph** (`models/causal_graph.pkl`)
3. ✅ **Causal Effects** (`results/causal_effects.pkl`)
4. ✅ **Real-time Prediction Function** (`detect_bias_realtime()`)
5. ✅ **Intervention Simulator** (`simulate_intervention()`)
6. ✅ **Validation Report** (accuracy, causal paths, performance)

---

## 🚀 NEXT STEPS

After completing Gap 1:
1. Move to **Gap 2**: Long-horizon simulation
2. Use bias detector output as input for counterfactual analysis
3. Integration: Combine bias detection with wealth projection

**Gap 1 is the foundation - everything else builds on this!**
