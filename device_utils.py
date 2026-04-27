import streamlit as st


def detect_mobile_client():
    mobile_tokens = (
        "android",
        "iphone",
        "ipad",
        "ipod",
        "mobile",
        "windows phone",
        "blackberry",
    )

    user_agent = ""
    try:
        context = getattr(st, "context", None)
        if context is not None:
            headers = getattr(context, "headers", None)
            if headers:
                user_agent = str(headers.get("user-agent", ""))

            if not user_agent:
                user_agent = str(getattr(context, "user_agent", ""))
    except Exception:
        user_agent = ""

    ua = user_agent.lower()
    return any(token in ua for token in mobile_tokens)
