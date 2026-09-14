Q : why is prior conversation context resent with everyturn? 

Ans: The answer lies in the very architecture of the LLMs. All LLMs are stateless i.e. they don't remeber or store the content from the last call, hence each call/request is a separate. Moreover, users has no idea which computer or node provides response to them. Hence full context is needed to be sent on every request so that LLMs provide reesponse back and understand continuity.

Q: How is a system prompt different from a user message? 
Ans:  The fules for model is categorized as "system prompt" but the user's messages are basically the tasks or questions from users.

Q: Why do input tokens grow over a conversation?
Ans: As explained in first question, since for every conversation /request, input are sent to LLMs for continuity and along with that tokens are also sent, hence they grow.

Q What eventually limits that growth?
Ans: Each model's has a maximum content window and when that maximum reached, the messages must be truncated.
