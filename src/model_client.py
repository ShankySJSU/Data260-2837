
from langchain_ollama import OllamaLLM

class ModelClient:


    def __init__(self, model_name="qwen3:8b", temperature=0.7):
        self.llm = OllamaLLM(model=model_name, temperature=temperature)

    def complete(self, messages, tools=None):
        """
        messages = list of dicts, each dict has:
            {"role": "system"|"user"|"assistant", "content": "..."}
        tools = not used in HW1 but kept for interface stability
        Returns:
            content, input_tokens, output_tokens, total_tokens
        """
        response = self.llm.invoke(messages)


        content = response

        def count_tokens(text):
            return len(text.split())

        input_text = " ".join([m["content"] for m in messages])
        input_tokens = count_tokens(input_text)
        output_tokens = count_tokens(content)
        total_tokens = input_tokens + output_tokens

