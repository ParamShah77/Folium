# 🤝 GAP 1: Team Collaboration & GitHub Workflow
## Implementation Split Strategy + Git Best Practices

---

## 📋 TABLE OF CONTENTS

1. [Team Split Strategy](#team-split-strategy)
2. [GitHub Setup & Branching](#github-setup--branching)
3. [Daily Workflow](#daily-workflow)
4. [Integration Points](#integration-points)
5. [Merge & Conflict Resolution](#merge--conflict-resolution)
6. [Quick Reference](#quick-reference)

---

## 🎯 TEAM SPLIT STRATEGY

### **Person 1: ML & Real-Time Detection Track** 🤖

**Primary Responsibility:** Build the bias detection engine

#### **Week 1: Data Preparation**
**Tasks:**
- Load and explore all synthetic datasets (`synthetic_decisions.csv`, `synthetic_users.csv`, `synthetic_bias_profiles.csv`)
- Load real market data (NIFTY/SENSEX historical data)
- Merge datasets on `user_id`
- Feature engineering:
  - Market regime classification
  - Loss magnitude categories
  - Crowd pressure levels
  - Risk-adjusted features
  - Interaction features (`loss_x_crowd`, `loss_x_market`)
- Create train/test split (80/20)
- **DELIVERABLE:** `data/processed/merged_features.csv` (share with Person 2)

**Files to Create:**
```
src/
  └── data_preparation.py
notebooks/
  └── 01_data_exploration.ipynb
data/processed/
  ├── merged_features.csv
  ├── train_indices.npy
  └── test_indices.npy
```

---

#### **Week 2-3: Bias Detection Model**
**Tasks:**
- Train XGBoost classifier for bias detection
- Hyperparameter tuning (n_estimators, max_depth, learning_rate)
- Evaluate performance:
  - Target: >85% accuracy
  - Generate confusion matrix
  - Calculate precision/recall/F1 per bias type
- Feature importance analysis
- Build `detect_bias_realtime()` function
- Optimize inference speed (target: <100ms)
- Create real-time prediction API

**Files to Create:**
```
src/
  └── bias_detector.py
notebooks/
  └── 02_train_bias_model.ipynb
models/
  └── bias_detector_xgboost.pkl
results/
  └── figures/
      ├── confusion_matrix.png
      └── feature_importance.png
```

**Key Functions:**
```python
def detect_bias_realtime(market_return, unrealized_gl, crowd_ratio, 
                         age, risk_tolerance, investment_horizon):
    """Real-time bias detection"""
    pass
```

---

#### **Week 3: API & Optimization**
**Tasks:**
- Build prediction endpoint
- Add input validation
- Performance profiling and optimization
- Create unit tests
- Documentation

**Files to Create:**
```
src/
  └── api.py
tests/
  └── test_bias_detector.py
```

---

### **Person 2: Causal Analysis Track** 🧠

**Primary Responsibility:** Understand WHY biases happen and quantify interventions

#### **Week 1: Setup & Data Prep**
**Tasks:**
- Set up Python environment (CausalNex, DoWhy, pgmpy)
- Read causal inference documentation
- **WAIT** for Person 1 to complete data preparation
- Load Person 1's prepared data
- Extract causal-relevant variables
- Normalize data for NOTEARS algorithm

**Files to Create:**
```
src/
  └── causal_utils.py
notebooks/
  └── 03_causal_data_prep.ipynb
```

---

#### **Week 4: Causal Structure Learning**
**Tasks:**
- Implement NOTEARS algorithm (via CausalNex)
- Learn causal graph:
  - Which variables cause which?
  - Edge weights (strength of causality)
  - Validate discovered structure
- Visualize causal relationships (networkx visualization)
- Save causal graph structure

**Files to Create:**
```
src/
  └── causal_structure.py
notebooks/
  └── 04_causal_structure_learning.ipynb
models/
  └── causal_graph.pkl
results/
  └── figures/
      └── causal_graph.png
```

**Key Output:**
```
Discovered Causal Relationships:
  loss_aversion → decision (strength: 0.452)
  unrealized_gain_loss → decision (strength: 0.389)
  crowd_action_ratio → decision (strength: 0.267)
```

---

#### **Week 5: Causal Inference & Interventions**
**Tasks:**
- Implement DoWhy causal inference
- Estimate causal effects:
  - Loss aversion → decision probability
  - Crowd behavior → decision probability
- Propensity score matching
- Refutation tests (validate not spurious)
- Build `simulate_intervention()` function
- Quantify intervention effects

**Files to Create:**
```
src/
  └── causal_inference.py
notebooks/
  └── 05_causal_interventions.ipynb
results/
  └── causal_effects.pkl
```

**Key Functions:**
```python
def simulate_intervention(user_data, intervention_type):
    """Simulate what happens if we remove bias"""
    pass

def get_causal_effect(treatment, outcome):
    """Get quantified causal effect"""
    pass
```

---

## 🌲 PROJECT FOLDER STRUCTURE

**Designed to minimize conflicts:**

```
Major Project/
├── .git/                           # Git repository
├── .gitignore                      # Ignore large files, .venv, etc.
├── README.md                       # Project overview
├── requirements.txt                # Python dependencies (both contribute)
├── GAP1_Causal_Decision_Time_Reasoning.md  # Technical spec
├── GAP1_TEAM_WORKFLOW.md           # This file
│
├── data/
│   ├── raw/                        # ✅ Both read from here
│   │   ├── synthetic_decisions.csv
│   │   ├── synthetic_users.csv
│   │   ├── synthetic_bias_profiles.csv
│   │   └── nifty_historical.csv
│   └── processed/                  # ⚠️ Person 1 writes (Week 1)
│       ├── merged_features.csv
│       ├── train_indices.npy
│       └── test_indices.npy
│
├── src/                            # ⚠️ Separate files per person
│   ├── __init__.py
│   ├── data_preparation.py         # Person 1 owns
│   ├── bias_detector.py            # Person 1 owns
│   ├── api.py                      # Person 1 owns
│   ├── causal_utils.py             # Person 2 owns
│   ├── causal_structure.py         # Person 2 owns
│   ├── causal_inference.py         # Person 2 owns
│   └── integration.py              # 🤝 Both collaborate (Week 5)
│
├── models/                         # ⚠️ Each saves their own models
│   ├── bias_detector_xgboost.pkl  # Person 1 creates
│   └── causal_graph.pkl            # Person 2 creates
│
├── notebooks/                      # ⚠️ Separate notebooks per person
│   ├── 01_data_exploration.ipynb        # Person 1
│   ├── 02_train_bias_model.ipynb        # Person 1
│   ├── 03_causal_data_prep.ipynb        # Person 2
│   ├── 04_causal_structure_learning.ipynb  # Person 2
│   ├── 05_causal_interventions.ipynb    # Person 2
│   └── 06_final_integration.ipynb       # 🤝 Both (Week 5)
│
├── tests/
│   ├── test_bias_detector.py       # Person 1
│   └── test_causal_inference.py    # Person 2
│
└── results/
    ├── figures/
    │   ├── confusion_matrix.png            # Person 1
    │   ├── feature_importance.png          # Person 1
    │   └── causal_graph.png                # Person 2
    └── reports/
        ├── bias_detection_report.md        # Person 1
        └── causal_analysis_report.md       # Person 2
```

**Key Principle:** Each person has their own files = minimal conflicts!

---

## 🐙 GITHUB SETUP & BRANCHING

### **Step 1: Initialize Repository (Person 1)**

```bash
cd "C:/Users/Lenovo/Desktop/Major Project"

# Initialize git
git init

# Create .gitignore
cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
ENV/
env/

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# Models (large files)
models/*.pkl
models/*.h5
*.npy

# Data (too large for git)
data/raw/*.csv
data/raw/*.npy
data/processed/*.csv

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOL

# Add all files
git add .
git commit -m "Initial commit: Project structure and documentation"

# Create GitHub repository (on github.com), then:
git remote add origin https://github.com/yourusername/major-project.git
git branch -M main
git push -u origin main
```

---

### **Step 2: Add Collaborator (On GitHub)**

1. Go to: `https://github.com/yourusername/major-project`
2. Click: **Settings** → **Collaborators** → **Add people**
3. Enter Person 2's GitHub username
4. Person 2 accepts email invitation

---

### **Step 3: Person 2 Clones Repository**

```bash
# Person 2 on their machine
git clone https://github.com/yourusername/major-project.git
cd major-project

# Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

---

### **Step 4: Create Feature Branches**

**Person 1:**
```bash
git checkout -b person1-bias-detection
git push -u origin person1-bias-detection
```

**Person 2:**
```bash
git checkout -b person2-causal-analysis
git push -u origin person2-causal-analysis
```

**Branch Structure:**
```
main (protected, production-ready)
├── person1-bias-detection (Person 1's work)
└── person2-causal-analysis (Person 2's work)
```

---

## 💻 DAILY WORKFLOW

### **Person 1: Morning Routine**

```bash
# 1. Switch to your branch
git checkout person1-bias-detection

# 2. Get latest changes (yours + any merges from main)
git pull origin person1-bias-detection

# 3. Check if Person 2 merged anything to main that you need
git fetch origin main
git log origin/main --oneline -5  # See what's new in main

# 4. If needed, merge main into your branch
git merge origin/main

# 5. Start coding!
```

---

### **Person 1: During the Day**

```bash
# Work on bias_detector.py
# Make changes...
# Test your code...

# Save progress (commit frequently!)
git add src/bias_detector.py
git commit -m "feat: implement feature engineering for bias detection"

# Continue working...
# More changes...

git add notebooks/02_train_bias_model.ipynb
git commit -m "feat: train XGBoost model with 87% accuracy"

# Push to GitHub (backup + let Person 2 see progress)
git push origin person1-bias-detection
```

---

### **Person 1: End of Day**

```bash
# Commit any remaining work
git add .
git status  # Review what you're committing
git commit -m "progress: completed model evaluation and visualization"

# Push everything
git push origin person1-bias-detection

# Optional: Update Person 2 on Slack/Discord
# "Pushed bias detector updates. Model hitting 87% accuracy! 🎉"
```

---

### **Person 2: Morning Routine**

```bash
# 1. Switch to your branch
git checkout person2-causal-analysis

# 2. Get latest changes
git pull origin person2-causal-analysis

# 3. Check if Person 1 has updates you need (e.g., Week 1 data prep)
git fetch origin person1-bias-detection
git log origin/person1-bias-detection --oneline -5

# 4. If Person 1 completed data prep, merge their work
# (Only do this after Person 1 explicitly says "data prep done!")
git merge origin/person1-bias-detection

# 5. Start coding!
```

---

### **Person 2: During the Day**

```bash
# Work on causal_structure.py
# Make changes...

git add src/causal_structure.py
git commit -m "feat: implement NOTEARS causal discovery"

# Continue...
git add notebooks/04_causal_structure_learning.ipynb
git commit -m "feat: visualize learned causal graph"

# Push progress
git push origin person2-causal-analysis
```

---

## 🔗 INTEGRATION POINTS

### **Integration Point 1: Week 1 - Data Sharing**

**Person 1 (After completing data prep):**
```bash
# You've completed data preparation
git add data/processed/merged_features.csv
git add src/data_preparation.py
git add notebooks/01_data_exploration.ipynb
git commit -m "feat: complete data preparation and feature engineering"
git push origin person1-bias-detection

# Create Pull Request on GitHub
# Go to: https://github.com/yourusername/major-project/pulls
# Click: "New Pull Request"
# Base: main ← Compare: person1-bias-detection
# Title: "Week 1: Data Preparation Complete"
# Description: 
#   - ✅ Loaded and merged all datasets
#   - ✅ Feature engineering complete
#   - ✅ Train/test split created
#   - 📦 Person 2 can now access data/processed/merged_features.csv

# After Person 2 reviews and approves, merge PR on GitHub
```

**Person 2 (After Person 1 merges to main):**
```bash
# Pull the data from main
git checkout person2-causal-analysis
git fetch origin main
git merge origin/main  # Now you have the prepared data!

# Verify data is there
ls data/processed/merged_features.csv

# Start your causal analysis work
```

---

### **Integration Point 2: Week 3 - Model Sharing**

**Person 1 (After completing bias detector):**
```bash
# Bias detector is working!
git add src/bias_detector.py
git add models/bias_detector_xgboost.pkl
git add notebooks/02_train_bias_model.ipynb
git commit -m "feat: complete bias detection model (87% accuracy)"
git push origin person1-bias-detection

# Create PR to main
# Title: "Week 3: Bias Detection Model Complete"
# Request review from Person 2
# After approval, merge
```

**Person 2 (Use Person 1's model for validation):**
```bash
# After Person 1 merges to main
git checkout person2-causal-analysis
git merge origin/main

# Now you can import Person 1's functions
# In your notebook/code:
from src.bias_detector import detect_bias_realtime

# Use it in your causal validation
result = detect_bias_realtime(...)
```

---

### **Integration Point 3: Week 5 - Final Integration**

**Both work on `src/integration.py` together:**

**Option A: One person creates, other reviews**
```bash
# Person 1 creates integration file
git checkout person1-bias-detection
# Create src/integration.py
git add src/integration.py
git commit -m "feat: create integration module"
git push origin person1-bias-detection

# Create PR to main, Person 2 reviews
# After merge:

# Person 2 adds causal analysis integration
git checkout person2-causal-analysis
git merge origin/main  # Get Person 1's integration.py
# Edit src/integration.py to add your causal functions
git add src/integration.py
git commit -m "feat: integrate causal analysis into main pipeline"
git push origin person2-causal-analysis

# Create PR, Person 1 reviews
```

**Option B: Pair programming (recommended)**
```bash
# Meet on call, Person 1 shares screen
# Person 1 codes while Person 2 guides
# OR use VS Code Live Share extension

# Person 1 creates and pushes
git add src/integration.py
git commit -m "feat: complete GAP1 integration (pair programmed)"
git push origin person1-bias-detection

# Create final PR to main
```

---

## 🔀 MERGE & CONFLICT RESOLUTION

### **Scenario 1: No Conflicts (Happy Path)**

```bash
# Person 1 wants to merge their completed work to main
git checkout main
git pull origin main  # Get latest main
git merge person1-bias-detection

# If no conflicts:
# Merge successful! ✅

git push origin main
```

---

### **Scenario 2: Merge Conflict in requirements.txt**

**Both added different packages:**

```bash
# Person 2 trying to merge
git checkout main
git merge person2-causal-analysis

# Git says:
# CONFLICT (content): Merge conflict in requirements.txt
# Automatic merge failed; fix conflicts and then commit

# Open requirements.txt, you'll see:
<<<<<<< HEAD
scikit-learn==1.3.0
xgboost==2.0.0
matplotlib==3.7.0
=======
scikit-learn==1.3.0
causalnex==0.11.0
dowhy==0.8
pgmpy==0.1.23
>>>>>>> person2-causal-analysis

# Manually edit to combine both:
scikit-learn==1.3.0
xgboost==2.0.0
matplotlib==3.7.0
causalnex==0.11.0
dowhy==0.8
pgmpy==0.1.23

# Save file, then:
git add requirements.txt
git commit -m "merge: resolve requirements.txt conflict (combined dependencies)"
git push origin main
```

---

### **Scenario 3: Accidentally Edited Same File**

**Both edited `src/utils.py` (rare if you follow folder structure):**

```bash
# Git will show conflict markers
# Open the file and look for:
<<<<<<< HEAD
def normalize_data(df):
    # Person 1's version
    return (df - df.mean()) / df.std()
=======
def normalize_data(df):
    # Person 2's version
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    return scaler.fit_transform(df)
>>>>>>> person2-causal-analysis

# Discuss with teammate which version is better
# Or combine both approaches
# After fixing:
git add src/utils.py
git commit -m "merge: resolve utils.py conflict (using sklearn approach)"
git push
```

---

### **Conflict Prevention Strategy**

✅ **DO:**
- Work in separate files (`bias_detector.py` vs `causal_structure.py`)
- Use separate notebooks (`01_*.ipynb` vs `04_*.ipynb`)
- Communicate before editing shared files
- Pull often (`git pull` multiple times per day)

❌ **DON'T:**
- Both edit same file simultaneously
- Go days without pulling
- Merge without testing
- Ignore conflicts (they won't go away!)

---

## 📊 WEEKLY TIMELINE WITH GIT WORKFLOW

### **Week 1: Data Preparation**

**Monday:**
```bash
# Person 1:
git checkout person1-bias-detection
# Start data exploration
git commit -m "feat: add data loading script"
git push origin person1-bias-detection

# Person 2:
git checkout person2-causal-analysis
# Set up environment, read docs
git commit -m "docs: add causal inference resources"
git push origin person2-causal-analysis
```

**Friday:**
```bash
# Person 1:
git commit -m "feat: complete data preparation and feature engineering"
git push origin person1-bias-detection
# Create PR to main: "Week 1: Data Prep Complete"
# Person 2 reviews → Approve → Merge

# Person 2:
git merge origin/main  # Get Person 1's data
```

---

### **Week 2-3: Parallel Development**

**Both work independently:**
```bash
# Daily routine:
git pull origin your-branch  # Morning
# Work...
git commit -m "progress: ..."  # Multiple times per day
git push origin your-branch  # End of day
```

**No integration needed this week!** 🎉

---

### **Week 4: Model Handoff**

**Wednesday:**
```bash
# Person 1:
git commit -m "feat: bias detector complete (87% accuracy)"
git push origin person1-bias-detection
# Create PR to main

# Person 2:
# After Person 1's PR merges:
git merge origin/main
# Now can use bias_detector.py
```

---

### **Week 5: Integration Week**

**Monday-Wednesday: Parallel (final pieces)**
```bash
# Each person finishes their components
# Person 1: API optimization
# Person 2: Causal intervention simulations
```

**Thursday-Friday: Integration** 🤝
```bash
# Option 1: Merge both branches to main first
git checkout main
git merge person1-bias-detection
git merge person2-causal-analysis

# Option 2: Create integration branch
git checkout -b integration
git merge person1-bias-detection
git merge person2-causal-analysis

# Both work on src/integration.py
# Test end-to-end
# Create final PR to main
```

---

## 🎯 PULL REQUEST TEMPLATE

**When creating PR on GitHub, use this template:**

```markdown
## 📋 Summary
Brief description of what this PR accomplishes.

## ✅ What's Changed
- Item 1
- Item 2
- Item 3

## 📁 Files Changed
- `src/bias_detector.py` - Main bias detection logic
- `models/bias_detector_xgboost.pkl` - Trained model
- `notebooks/02_train_bias_model.ipynb` - Training process

## 🧪 Testing
- [x] Model accuracy >85% ✅
- [x] Real-time latency <100ms ✅
- [x] All unit tests passing ✅

## 📊 Results
- Accuracy: 87.3%
- F1 Score: 0.86
- Inference time: 43ms

## 🔗 Dependencies
- Requires data from Week 1 (already in main)
- No breaking changes to existing code

## 👀 Reviewers
@person2username - Please review causal integration compatibility

## 📝 Notes
Next steps: Person 2 can now import `detect_bias_realtime()` for validation.
```

---

## 🚨 TROUBLESHOOTING

### **Problem: "Permission denied" when pushing**

```bash
# You're not a collaborator yet
# Person 1: Add Person 2 on GitHub (Settings → Collaborators)
# Person 2: Check email for invitation
```

---

### **Problem: "Your branch is behind 'origin/main'"**

```bash
# You need to pull first
git pull origin main
# If conflicts, resolve them
git push origin your-branch
```

---

### **Problem: "I accidentally committed to main instead of my branch!"**

```bash
# If you haven't pushed yet:
git log --oneline -5  # Find the commit hash
git checkout person1-bias-detection
git cherry-pick COMMIT_HASH  # Copy commit to your branch
git checkout main
git reset --hard HEAD~1  # Undo commit on main (⚠️ dangerous!)

# If you already pushed:
# Contact teammate to coordinate fix
```

---

### **Problem: "I need to undo my last commit"**

```bash
# If you haven't pushed:
git reset --soft HEAD~1  # Undo commit, keep changes
# OR
git reset --hard HEAD~1  # Undo commit, delete changes (⚠️ dangerous!)

# If you already pushed:
git revert HEAD  # Create new commit that undoes last one
git push origin your-branch
```

---

### **Problem: "Git says I have uncommitted changes but I don't see them"**

```bash
git status  # Shows what's changed

# If you want to save them:
git add .
git commit -m "save work in progress"

# If you want to discard them:
git checkout .  # Discard all changes (⚠️ dangerous!)

# If you want to temporarily hide them:
git stash  # Hide changes
# Do other git stuff
git stash pop  # Restore changes
```

---

## 📚 QUICK REFERENCE COMMANDS

### **Essential Daily Commands**

```bash
# Check status
git status                    # What's changed?
git log --oneline -10         # Last 10 commits
git branch                    # Show all branches

# Basic workflow
git add filename.py           # Stage one file
git add .                     # Stage all changes
git commit -m "message"       # Save checkpoint
git push origin your-branch   # Upload to GitHub

# Getting updates
git pull origin your-branch   # Get your branch updates
git fetch origin              # Get all branch info
git merge origin/main         # Merge main into your branch

# Branch management
git checkout branch-name      # Switch branches
git checkout -b new-branch    # Create and switch to new branch

# Viewing changes
git diff                      # See unstaged changes
git diff --staged             # See staged changes
git log --graph --oneline     # Visual commit history
```

---

### **Advanced Commands**

```bash
# Undoing
git stash                     # Temporarily hide changes
git stash pop                 # Restore hidden changes
git reset --soft HEAD~1       # Undo last commit, keep changes
git reset --hard HEAD~1       # Undo last commit, delete changes ⚠️
git revert COMMIT_HASH        # Undo specific commit (safe)

# Conflict resolution
git merge --abort             # Cancel merge if conflicts
git checkout --theirs file    # Use their version
git checkout --ours file      # Use our version

# Inspection
git show COMMIT_HASH          # Show specific commit
git blame filename.py         # Who changed each line?
git remote -v                 # Show GitHub connection
```

---

## 🎓 GIT BEST PRACTICES

### **Commit Messages**

✅ **Good:**
```bash
git commit -m "feat: implement XGBoost bias classifier"
git commit -m "fix: correct feature scaling bug in data prep"
git commit -m "docs: add docstrings to detect_bias_realtime()"
git commit -m "test: add unit tests for bias detector"
git commit -m "refactor: optimize prediction speed (43ms → 28ms)"
```

❌ **Bad:**
```bash
git commit -m "update"
git commit -m "changes"
git commit -m "asdf"
git commit -m "fixed it"
```

**Commit Prefixes:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code restructuring
- `perf:` - Performance improvement
- `style:` - Formatting

---

### **When to Commit**

```bash
# ✅ Commit often (3-10 times per day)
# After completing a logical unit of work:
- Finished one function
- Fixed one bug
- Completed one notebook section
- Added one test

# ❌ Don't:
- Wait until end of day (too much at once)
- Commit broken code (test first!)
- Commit secrets/passwords (use .env files)
```

---

### **When to Push**

```bash
# ✅ Push at least once per day
# - End of work day (backup!)
# - After completing a milestone
# - Before asking teammate to review

# ✅ Push immediately:
# - When teammate is waiting for your work
# - Before switching computers
# - When you complete a feature
```

---

### **Branch Hygiene**

```bash
# ✅ Keep branches short-lived (max 1-2 weeks)
# ✅ Merge to main when feature is complete
# ✅ Delete branches after merging:
git branch -d person1-bias-detection  # After final merge

# ✅ Keep branches up-to-date with main:
git checkout your-branch
git merge origin/main  # Do this weekly
```

---

## 🎯 SUCCESS CRITERIA

### **Week 1 ✅**
- [ ] Person 1: Data prep complete, PR merged to main
- [ ] Person 2: Environment set up, data accessible
- [ ] Both: No merge conflicts

### **Week 3 ✅**
- [ ] Person 1: Bias detector merged to main (>85% accuracy)
- [ ] Person 2: Causal graph learned and visualized
- [ ] Both: Can import each other's functions

### **Week 5 ✅**
- [ ] Both branches merged to main
- [ ] Integration complete in `src/integration.py`
- [ ] End-to-end pipeline works
- [ ] All tests passing
- [ ] Documentation updated

---

## 📞 COMMUNICATION PROTOCOL

### **Daily Standup (5 minutes, async on Slack/Discord)**

**Format:**
```
📅 Date: Feb 14, 2026

Person 1:
✅ Yesterday: Completed feature engineering, started XGBoost training
🚀 Today: Hyperparameter tuning, aim for >85% accuracy
⚠️ Blockers: None

Person 2:
✅ Yesterday: Set up CausalNex environment, read NOTEARS paper
🚀 Today: Waiting for Person 1's data (ETA today), will start causal prep
⚠️ Blockers: Need merged_features.csv from Person 1
```

### **Before Creating PR:**
```
Hey @teammate, I'm about to create PR for [feature name].
Would you mind reviewing? Focus on [specific areas].
Thanks! 🙏
```

### **After Merging to Main:**
```
🎉 Just merged [feature] to main!
You can now pull and use:
- src/bias_detector.py
- models/bias_detector_xgboost.pkl

Let me know if any issues!
```

---

## 🚀 FINAL CHECKLIST

### **Before Starting (Day 1):**
- [ ] Git installed and configured (`git config --global user.name "Your Name"`)
- [ ] GitHub accounts created
- [ ] Repository created and both have access
- [ ] Feature branches created
- [ ] .gitignore set up properly
- [ ] Virtual environments created
- [ ] Requirements.txt shared

### **During Work (Daily):**
- [ ] Pull before starting work
- [ ] Commit multiple times per day
- [ ] Push at end of day
- [ ] Test before committing
- [ ] Write descriptive commit messages

### **Before Merging (End of Week):**
- [ ] Code reviewed by teammate
- [ ] All tests passing
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] PR description complete

### **Final Integration (Week 5):**
- [ ] Both branches merged cleanly
- [ ] Integration code works end-to-end
- [ ] All deliverables present
- [ ] Performance metrics met
- [ ] README updated with usage instructions

---

## 🎉 YOU'RE READY!

This workflow will let you and your teammate work efficiently without stepping on each other's toes. Remember:

1. **Communicate early and often**
2. **Commit small, push daily**
3. **Work in separate files when possible**
4. **Pull before you push**
5. **Test before you merge**

Good luck with GAP 1! 🚀

---

**Questions?** Check these resources:
- [Git Cheat Sheet](https://education.github.com/git-cheat-sheet-education.pdf)
- [GitHub Docs](https://docs.github.com)
- [Atlassian Git Tutorials](https://www.atlassian.com/git/tutorials)
