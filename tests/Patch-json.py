def call_json(self, agent: autogen.AssistantAgent, payload: Any) -> AgentCallResult:
    """Call an agent once (max_turns=1) and parse JSON."""

    # ✅ AutoGen 0.11.x needs message to be str (or dict with 'content')
    if isinstance(payload, (dict, list)):
        message = json.dumps(payload, ensure_ascii=False)
    elif payload is None:
        message = ""
    else:
        message = str(payload)

    if not message.strip():
        raise ValueError("Agent call payload is empty after normalization")

    # Always single-turn to prevent loops
    self.user_proxy.initiate_chat(agent, message=message, max_turns=1)

    msgs = self.user_proxy.chat_messages.get(agent, [])
    raw = msgs[-1].get("content", "") if msgs else ""

    obj: Optional[Dict[str, Any]] = None
    try:
        obj = json.loads(raw)
    except Exception:
        m = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
            except Exception:
                obj = None

    return AgentCallResult(raw_text=raw, json_obj=obj)
