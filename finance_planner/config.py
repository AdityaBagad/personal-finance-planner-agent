import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL_GEMMA4 = os.getenv("OLLAMA_MODEL", "ollama_chat/gemma4:e4b")
OLLAMA_MODEL_GEMMA3 = os.getenv("OLLAMA_MODEL", "ollama_chat/gemma3:4b")
WARNING_THRESHOLD = float(os.getenv("BUDGET_WARNING_THRESHOLD", "80.0"))
CRITICAL_THRESHOLD = float(os.getenv("BUDGET_CRITICAL_THRESHOLD", "100.0"))
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "INR")

STANDARD_CATEGORIES = [
    "Groceries", "Utilities", "Rent", "Transport", "Travel",
    "Entertainment", "Healthcare", "Shopping", "Education",
    "Investment", "Income", "Transfer", "Other"
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "store")
os.makedirs(DATA_DIR, exist_ok=True)
