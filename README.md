Q : why is prior conversation context resent with everyturn? 

Ans: The answer lies in the very architecture of the LLMs. All LLMs are stateless i.e. they don't remeber or store the content from the last call, hence each call/request is a separate. Moreover, users has no idea which computer or node provides response to them. Hence full context is needed to be sent on every request so that LLMs provide reesponse back and understand continuity.

Q: How is a system prompt different from a user message? 
Ans:  The fules for model is categorized as "system prompt" but the user's messages are basically the tasks or questions from users.

Q: Why do input tokens grow over a conversation?
Ans: Since each inputs are once again fed for continuity and context understanding hence tokens grow over a conversation.

Q What eventually limits that growth?
Ans :The model’s maximm content window is reached, messages must be truncated.
