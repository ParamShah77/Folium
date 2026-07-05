import pandas as pd

def get_demo_cases():
    df = pd.read_csv('synthetic_decisions.csv')
    
    biases = ['rational', 'loss_aversion', 'herd', 'disposition']
    results = []
    
    for bias in biases:
        sample = df[df['bias_type'] == bias].sample(1, random_state=42)
        results.append(sample)
        
    # Add one more random one to make it 5
    results.append(df[df['bias_type'] == 'rational'].sample(1, random_state=100))
    
    final_df = pd.concat(results)
    
    for _, row in final_df.iterrows():
        user_id = int(row['user_id'])
        bias = row['bias_type']
        unrealized = row['unrealized_gain_loss'] * 100
        holding = int(row['holding_period_months'])
        position = row['position_size_pct'] * 100
        decision = "Thinking of selling" if row['decision'] == 'sell' else "Planning to hold"
        
        print(f"User ID: {user_id}")
        print(f"Expected Bias: {bias.upper()}")
        print(f"Inputs to fill in the form:")
        print(f"- Unrealized Gain/Loss (%): {unrealized:.1f}")
        print(f"- Holding Period (months): {holding}")
        print(f"- Position Size (%): {position:.1f}")
        print(f"- Decision Intent: {decision}")
        print("-" * 40)

if __name__ == "__main__":
    get_demo_cases()
