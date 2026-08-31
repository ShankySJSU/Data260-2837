Q : why is prior conversation context resent with everyturn? 
Ans: LLMs are stateless and they don’t remember history. Hence full context is needed to resent to understand continuity.
Q: How is a system prompt different from a user message? 
Ans: The system prompt is used for rules for model but user message is to set tasks or questions.
Q: Why do input tokens grow over a conversation?
Ans: Since each inputs are once again fed for continuity and context understanding hence tokens grow over a conversation.

Q What eventually limits that growth?
Ans :The model’s maximm content window is reached, messages must be truncated.
