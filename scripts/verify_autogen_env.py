"""scripts.verify_autogen_env

Quick verifier to ensure the runtime Python environment can import autogen.

Run:
  python scripts/verify_autogen_env.py

Recommended app start:
  python -m streamlit run ui/streamlit_app.py
"""

import sys

print("Python executable:", sys.executable)
print("Python version:", sys.version)

try:
    import autogen
    print("Imported autogen OK.")
    print("autogen module:", getattr(autogen, "__file__", None))
    print("autogen version:", getattr(autogen, "__version__", "unknown"))
    print("Has AssistantAgent:", hasattr(autogen, "AssistantAgent"))
    print("Has UserProxyAgent:", hasattr(autogen, "UserProxyAgent"))
    print("Has LLMConfig:", hasattr(autogen, "LLMConfig"))
except Exception as e:
    print("FAILED to import autogen:", repr(e))
    try:
        import ag2 as autogen2
        print("Imported ag2 OK.")
        print("ag2 module:", getattr(autogen2, "__file__", None))
        print("ag2 version:", getattr(autogen2, "__version__", "unknown"))
    except Exception as e2:
        print("FAILED to import ag2:", repr(e2))
