# Pytae - Visual Studio Code Extension

Rich syntax highlighting, snippets, and editor support for [Pytae](https://github.com/maddytae/pytae) tabular data expressions in Python.

---

## ✨ Features

- **Dark Green Expression Highlighting**:
  Pytae expressions are automatically styled with rich dark green and emerald tones, matching Pytae's visual brand across all themes:
  - **Vectorized Functions**: `case_when`, `if_else`, `coalesce`, `fillna`, `clip`, `sqrt`, `round` → Deep Forest Green (`#40916c`, bold)
  - **Assignment Targets**: `bmi = ...`, `(cols) = ...` → Dark Pine Green (`#2d6a4f`, bold)
  - **Control Keywords**: `default`, `asc`, `desc`, `and`, `or` → Deep Spruce Green (`#1b4332`, bold)
  - **Parameters & Bracketed Columns**: `@threshold`, `[total bill]` → Sage & Mint Green (`#74c69d`)
  - **Operators & Numbers**: `==`, `!=`, `<=`, `**`, `//`, `1e-9`, `3.14` → Pale Green / Seafoam (`#95d5b2` / `#b7e4c7`)
  - **Nested Strings**: `'Pass'`, `'Fail'` → Warm Golden Amber (`#ffd166`)

- **Bundled "Pytae Dark Green" Theme**:
  Prefer a complete, cohesive dark green editor experience? Switch your theme to **Pytae Dark Green** (`Cmd+K Cmd+T` / `Ctrl+K Ctrl+T`) for a sleek dark slate background with pine and emerald syntax accents.

- **Tagged Strings Support**:
  Add `# pytae` above any multiline string to immediately activate Pytae highlighting:
  ```python
  # pytae
  spec = """
      bmi = weight / (height ** 2),
      status = case_when((score >= 700, 'Pass'), default='Fail')
  """
  ```

- **Built-in Productive Snippets**:
  - `pt-mutate`: Quick `.mutate("new_col = expr")`
  - `pt-mutate-multi`: Multi-line mutate block
  - `pt-case-when`: Vectorized `case_when((cond, val), default=...)`
  - `pt-if-else`: Vectorized `if_else(cond, true, false)`
  - `pt-select`: Negative column selection with canonical `!` negation
  - `pt-validate`: Pre-flight zero-data pipeline validator `pt.validate_pipeline()`
  - `pt-pipeline`: Complete lazy pipeline template

---

## 🚀 Installation

### Option 1: Install Local `.vsix` (Immediate)

Run in your terminal:
```bash
code --install-extension pytae-3.10.3.vsix
```
Or in VS Code:
1. Open the **Extensions** view (`Cmd+Shift+X` / `Ctrl+Shift+X`).
2. Click the `...` (Views and More Actions) menu in the top-right.
3. Select **Install from VSIX...** and choose `pytae-3.10.3.vsix`.

---

## 📦 How to Publish to VS Code Marketplace

You can publish this extension to the official Microsoft VS Code Marketplace so anyone can install it with `code --install-extension maddytae.pytae` or directly search for "pytae" in VS Code.

### Step 1: Create a Personal Access Token (PAT)
1. Go to [Azure DevOps](https://dev.azure.com/) and sign in.
2. Under your user settings in the top-right, click **Personal Access Tokens**.
3. Create a new token with:
   - **Organization**: `All accessible organizations`
   - **Scopes**: Custom defined -> **Marketplace** -> check **Manage**.
4. Copy the generated token.

### Step 2: Create a Publisher
If you don't already have a publisher account on the Marketplace:
1. Visit the [VS Code Marketplace Management Portal](https://marketplace.visualstudio.com/manage).
2. Click **Create publisher** (e.g. ID: `maddytae`, Name: `Maddy`).

### Step 3: Publish from Terminal
Inside `extensions/vscode-pytae`:
```bash
# Login with your token:
npx @vscode/vsce login maddytae

# Publish directly to the Marketplace:
npx @vscode/vsce publish
```

Once published, it will be live globally in the Marketplace in ~2 minutes!

---

## 🛠️ Building the `.vsix` Locally

To rebuild the `.vsix` package:
```bash
cd extensions/vscode-pytae
npx @vscode/vsce package
```
This generates `pytae-3.10.3.vsix`.

