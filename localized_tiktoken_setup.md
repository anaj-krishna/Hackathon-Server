# Using Localized tiktoken Cache in Your Project

This document explains how to configure your Python project to use a locally cached tiktoken tokenizer, avoiding SSL/certificate issues and enabling fully offline or proxy-friendly operation.

## Quick Start (Recommended)

- **The `tiktoken_cache` folder is already included with this project.**
- You do **not** need to download or generate the cache if this folder is present.
- The code is already set up to use this cache automatically.

## Steps to Use Localized tiktoken (if you need to regenerate the cache)

1. **Prepare the Local tiktoken Cache**
   - Download the required tiktoken files (e.g., `cl100k_base`) on a machine with internet access:
     ```python
     import tiktoken
     tiktoken.get_encoding("cl100k_base")
     ```
   - This will create a `.cache/tiktoken` directory in your home folder with the necessary files.
   - Copy the required file(s) (e.g., `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`) to your project folder under `tiktoken_cache/`.

2. **Set the Cache Directory in Your Code**
   - At the top of your main Python script, add:
     ```python
     import os
     TIKTOKEN_CACHE_DIR = os.path.abspath("tiktoken_cache")
     os.environ["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR
     assert os.path.exists(os.path.join(TIKTOKEN_CACHE_DIR, "9b5ad71b2ce5302211f9c61530b329a4922fc6a4")), "tiktoken cache not found!"
     ```
   - This ensures tiktoken will use your local cache and not attempt to download files from the internet.

3. **Run Your Application**
   - Your app will now use the local tiktoken cache and will not trigger SSL or certificate errors, even in offline or restricted environments.

## Notes
- You can change the cache directory by modifying the `TIKTOKEN_CACHE_DIR` variable.
- The assertion will fail with a clear error if the cache file is missing, helping you debug setup issues.
- This approach is robust for both development and production in secure or air-gapped environments.

---

**Reference:**
- [How to use tiktoken in offline mode (StackOverflow)](https://stackoverflow.com/questions/76106366/how-to-use-tiktoken-in-offline-mode-computer)
